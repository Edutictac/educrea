import { describe, expect, it } from 'vitest'
import { MAX_INSTRUCTIONS, fillInstructions, parseBridgeQuery } from './promptBridge'

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
