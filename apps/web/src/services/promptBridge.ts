export const MAX_INSTRUCTIONS = 20000
export const MAX_HANDOFF_PAYLOAD = 48000
export const PROMPT_APP_URL = 'https://pages.edutictac.es/Edutictac/edutictac-prompt/'
export const HANDOFF_STORAGE_KEY = 'eduprompt.handoff'

export type BridgeQuery = { openCreate: boolean; fromPrompt: boolean }
export type FillResult = { ok: true; text: string } | { ok: false; reason: 'empty' | 'too_long' }

function first(value: unknown): string {
  if (Array.isArray(value)) return String(value[0] ?? '')
  return value == null ? '' : String(value)
}

export function parseBridgeQuery(query: Record<string, unknown>): BridgeQuery {
  return { openCreate: first(query.nuevo) === '1', fromPrompt: first(query.desde) === 'eduprompt' }
}

export function fillInstructions(text: string): FillResult {
  const value = text.trim()
  if (!value) return { ok: false, reason: 'empty' }
  if (value.length > MAX_INSTRUCTIONS) return { ok: false, reason: 'too_long' }
  return { ok: true, text: value }
}

export function payloadFromHash(hash: string): string {
  if (!hash) return ''
  return new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash).get('encargo') ?? ''
}

export function templateFromHash(hash: string): string {
  if (!hash) return ''
  return new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash).get('plantilla') ?? ''
}

const PROMPT_TYPE_TO_EDUCREA: Record<string, string> = {
  'learning-situation': 'situacion',
  infographic: 'infografia',
  'multiple-choice': 'cuestionario',
}

export function eduCreaTypeForPrompt(template: string): string {
  return PROMPT_TYPE_TO_EDUCREA[template] ?? ''
}

function base64urlToBytes(value: string): Uint8Array | null {
  if (!value || !/^[A-Za-z0-9_-]+$/.test(value)) return null
  const padded = value.replace(/-/g, '+').replace(/_/g, '/').padEnd(value.length + (4 - value.length % 4) % 4, '=')
  try {
    const binary = atob(padded)
    const bytes = new Uint8Array(binary.length)
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
    return bytes
  } catch { return null }
}

async function inflate(bytes: Uint8Array): Promise<Uint8Array | null> {
  if (typeof DecompressionStream === 'undefined') return null
  try {
    const stream = new Blob([bytes as unknown as BlobPart]).stream().pipeThrough(new DecompressionStream('deflate'))
    return new Uint8Array(await new Response(stream).arrayBuffer())
  } catch { return null }
}

export async function decodePromptPayload(payload: string): Promise<string | null> {
  if (!payload || payload.length > MAX_HANDOFF_PAYLOAD + 2) return null
  const separator = payload.indexOf('.')
  if (separator < 1) return null
  const kind = payload.slice(0, separator)
  const bytes = base64urlToBytes(payload.slice(separator + 1))
  if (!bytes) return null
  const decoded = kind === 'r' ? bytes : kind === 'z' ? await inflate(bytes) : null
  if (!decoded) return null
  try {
    const result = fillInstructions(new TextDecoder('utf-8', { fatal: true }).decode(decoded))
    return result.ok ? result.text : null
  } catch { return null }
}

export function storePendingPrompt(text: string): void {
  try { sessionStorage.setItem(HANDOFF_STORAGE_KEY, text.trim()) } catch { /* ignore unavailable storage */ }
}

export function peekPendingPrompt(): string | null {
  try {
    const text = sessionStorage.getItem(HANDOFF_STORAGE_KEY)
    const result = text ? fillInstructions(text) : null
    return result?.ok ? result.text : null
  } catch { return null }
}

export function clearPendingPrompt(): void {
  try { sessionStorage.removeItem(HANDOFF_STORAGE_KEY) } catch { /* ignore unavailable storage */ }
}

export function takePendingPrompt(): string | null {
  const text = peekPendingPrompt()
  if (text !== null) clearPendingPrompt()
  return text
}
