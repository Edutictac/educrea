// The AI chosen in the project selector, shared by «Generar la primera versión», DUA and the assistant.
// Kept per viewer in localStorage (a convenience): empty provider/model means «Automática».
import { ref, watch } from 'vue'
import type { ProviderName } from './ai'

export interface AiChoice { provider: ProviderName | 'educrea' | ''; model: string }
const KEY = 'educrea.aiChoice'

function load(key: string): AiChoice | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? 'null') as AiChoice | null
    if (value && typeof value.provider === 'string' && typeof value.model === 'string') return value
  } catch { /* storage unavailable */ }
  return null
}

// `available` means the server says the institutional AI can serve this account right now (service on, account
// invited, keys and prices ready, budgets left), not just that the account has the permission. Otherwise the default
// is «Automática»/BYOK, so a first generation never fails with 503 because the included service is paused.
export function choiceForAccess(saved: AiChoice | null, available: boolean): AiChoice {
  if (saved && (saved.provider !== 'educrea' || available)) return saved
  return available ? { provider: 'educrea', model: 'included' } : { provider: '', model: '' }
}

// The picker offers «IA EduCrea» only if the account has the permission AND the server says it can serve now.
// Never test the response itself for truthiness: the endpoint answers 200 even when the service is paused.
export const includedOffered = (authorized: boolean, status: { available?: boolean } | null): boolean =>
  authorized && status?.available === true

let accountKey = ''
let restoring = false
// Start with BYOK until the authenticated account's server-side permission is known.
export const aiChoice = ref<AiChoice>({ provider: '', model: '' })

export function initializeAiChoice(userId: string, available: boolean) {
  restoring = true
  try {
    accountKey = `${KEY}.${userId}`
    // Preserve legacy BYOK preferences; availability still overrides any saved institutional choice.
    aiChoice.value = choiceForAccess(load(accountKey) ?? load(KEY), available)
  } finally { restoring = false }
}

// Safe default: start on Automática/BYOK and switch to the included AI only if the server confirms it is available
// and the teacher has not picked anything meanwhile. A failed check keeps Automática/BYOK.
export async function startAiChoice(userId: string, authorized: boolean,
  fetchStatus: () => Promise<{ available: boolean }>): Promise<void> {
  initializeAiChoice(userId, false)
  if (!authorized) return
  try {
    const status = await fetchStatus()
    // Ignore a late answer: another account signed in, or the teacher already chose (a saved choice is kept as is).
    if (status.available && accountKey === `${KEY}.${userId}` && aiChoice.value.provider === '') initializeAiChoice(userId, true)
  } catch { /* keep Automática/BYOK */ }
}

export function clearAiChoice() {
  restoring = true
  try { accountKey = ''; aiChoice.value = { provider: '', model: '' } }
  finally { restoring = false }
}

watch(aiChoice, value => {
  if (!accountKey || restoring) return
  try { localStorage.setItem(accountKey, JSON.stringify(value)) } catch { /* ignore */ }
}, { deep: true, flush: 'sync' })

export const PROVIDER_NAMES: Record<ProviderName | 'educrea', string> = {
  educrea: 'IA EduCrea', gemini: 'Gemini (Google)', mistral: 'Mistral', groq: 'Groq', openrouter: 'OpenRouter',
  ollama: 'Ollama (servidor)', openai: 'OpenAI', anthropic: 'Anthropic (Claude)', deepseek: 'DeepSeek',
}

// Explicit institutional selection or personal-key selection; BYOK automatic stays separate.
export function choiceBody(): { provider?: string; model?: string } {
  return aiChoice.value.provider && aiChoice.value.model ? { provider: aiChoice.value.provider, model: aiChoice.value.model } : { provider: 'byok' }
}
