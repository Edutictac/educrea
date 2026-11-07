import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  MAX_INSTRUCTIONS,
  clearPendingPrompt,
  decodePromptPayload,
  eduCreaTypeForPrompt,
  fillInstructions,
  parseBridgeQuery,
  payloadFromHash,
  peekPendingPrompt,
  storePendingPrompt,
  takePendingPrompt,
  templateFromHash,
} from './promptBridge'

function base64url(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function rawPayload(text: string): string {
  return `r.${base64url(new TextEncoder().encode(text))}`
}

async function compressedPayload(text: string): Promise<string> {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream('deflate'))
  return `z.${base64url(new Uint8Array(await new Response(stream).arrayBuffer()))}`
}

const stored = new Map<string, string>()
beforeEach(() => {
  stored.clear()
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => stored.has(key) ? stored.get(key)! : null,
    setItem: (key: string, value: string) => { stored.set(key, value) },
    removeItem: (key: string) => { stored.delete(key) },
  })
})
afterAll(() => { vi.unstubAllGlobals() })

describe('parseBridgeQuery', () => {
  it('detects the guided creation and the Prompt origin', () => {
    expect(parseBridgeQuery({ nuevo: '1', desde: 'eduprompt' }))
      .toEqual({ openCreate: true, fromPrompt: true })
  })

  it('ignores unrelated or repeated values', () => {
    expect(parseBridgeQuery({ nuevo: ['1', '0'], desde: undefined }))
      .toEqual({ openCreate: true, fromPrompt: false })
    expect(parseBridgeQuery({})).toEqual({ openCreate: false, fromPrompt: false })
  })
})

describe('fillInstructions', () => {
  it('trims and accepts a normal prompt', () => {
    expect(fillInstructions('  Encargo de prueba  ')).toEqual({ ok: true, text: 'Encargo de prueba' })
  })

  it('rejects empty and over-long prompts without truncating silently', () => {
    expect(fillInstructions('   ')).toEqual({ ok: false, reason: 'empty' })
    expect(fillInstructions('x'.repeat(MAX_INSTRUCTIONS + 1))).toEqual({ ok: false, reason: 'too_long' })
  })

  it('accepts exactly the maximum length', () => {
    const text = 'x'.repeat(MAX_INSTRUCTIONS)
    expect(fillInstructions(text)).toEqual({ ok: true, text })
  })
})

describe('direct handoff', () => {
  it('reads the payload and the Prompt template from the URL fragment', () => {
    expect(payloadFromHash('#encargo=z.abc')).toBe('z.abc')
    expect(payloadFromHash('#otro=1&encargo=r.xyz')).toBe('r.xyz')
    expect(payloadFromHash('')).toBe('')
    expect(templateFromHash('#encargo=z.abc&plantilla=learning-situation')).toBe('learning-situation')
    expect(templateFromHash('#encargo=z.abc')).toBe('')
  })

  it('maps the Prompt product to the matching EduCrea type', () => {
    expect(eduCreaTypeForPrompt('learning-situation')).toBe('situacion')
    expect(eduCreaTypeForPrompt('infographic')).toBe('infografia')
    expect(eduCreaTypeForPrompt('multiple-choice')).toBe('cuestionario')
    expect(eduCreaTypeForPrompt('unknown')).toBe('')
  })

  it('decodes a plain payload', async () => {
    await expect(decodePromptPayload(rawPayload('Encargo de prueba'))).resolves.toBe('Encargo de prueba')
  })

  it('decodes a compressed payload', async () => {
    const text = 'Encargo de prueba con tildes: programación, evaluación y acción.'
    await expect(decodePromptPayload(await compressedPayload(text))).resolves.toBe(text)
  })

  it('rejects invalid, unknown and over-long payloads', async () => {
    await expect(decodePromptPayload('')).resolves.toBeNull()
    await expect(decodePromptPayload('r.***')).resolves.toBeNull()
    await expect(decodePromptPayload(`q.${base64url(new TextEncoder().encode('hola'))}`)).resolves.toBeNull()
    await expect(decodePromptPayload('r.' + 'A'.repeat(48_001))).resolves.toBeNull()
    await expect(decodePromptPayload(rawPayload('x'.repeat(MAX_INSTRUCTIONS + 1)))).resolves.toBeNull()
  })

  it('stores a pending brief once', () => {
    storePendingPrompt('  Encargo recibido  ')
    expect(takePendingPrompt()).toBe('Encargo recibido')
    expect(takePendingPrompt()).toBeNull()
  })

  it('peeks and clears a pending brief separately', () => {
    storePendingPrompt('  Encargo recibido  ')
    expect(peekPendingPrompt()).toBe('Encargo recibido')
    expect(peekPendingPrompt()).toBe('Encargo recibido')
    clearPendingPrompt()
    expect(peekPendingPrompt()).toBeNull()
  })
})
