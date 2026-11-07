export const MAX_INSTRUCTIONS = 20000
export const PROMPT_APP_URL = 'https://pages.edutictac.es/Edutictac/edutictac-prompt/'

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
