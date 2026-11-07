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

export function choiceForAccess(saved: AiChoice | null, authorized: boolean): AiChoice {
  if (saved && (saved.provider !== 'educrea' || authorized)) return saved
  return authorized ? { provider: 'educrea', model: 'included' } : { provider: '', model: '' }
}

let accountKey = ''
let restoring = false
// Start with BYOK until the authenticated account's server-side permission is known.
export const aiChoice = ref<AiChoice>({ provider: '', model: '' })

export function initializeAiChoice(userId: string, authorized: boolean) {
  restoring = true
  try {
    accountKey = `${KEY}.${userId}`
    // Preserve legacy BYOK preferences; authorization still overrides any saved institutional choice.
    aiChoice.value = choiceForAccess(load(accountKey) ?? load(KEY), authorized)
  } finally { restoring = false }
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
