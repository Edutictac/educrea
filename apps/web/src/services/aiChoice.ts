// The AI chosen in the project selector, shared by «Generar la primera versión», DUA and the assistant.
// Kept per viewer in localStorage (a convenience): empty provider/model means «Automática».
import { ref, watch } from 'vue'
import type { ProviderName } from './ai'

export interface AiChoice { provider: ProviderName | ''; model: string }
const KEY = 'edustudio.aiChoice'

function load(): AiChoice {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? 'null') as AiChoice | null
    if (value && typeof value.provider === 'string' && typeof value.model === 'string') return value
  } catch { /* storage unavailable */ }
  return { provider: '', model: '' }
}

export const aiChoice = ref<AiChoice>(load())
watch(aiChoice, value => { try { localStorage.setItem(KEY, JSON.stringify(value)) } catch { /* ignore */ } }, { deep: true })

export const PROVIDER_NAMES: Record<ProviderName, string> = {
  gemini: 'Gemini (Google)', mistral: 'Mistral', nvidia: 'NVIDIA', groq: 'Groq', openrouter: 'OpenRouter',
  ollama: 'Ollama (servidor)', openai: 'OpenAI', anthropic: 'Anthropic (Claude)',
}

// Body for /ai/from-brief and /ai/dua: nothing when «Automática».
export function choiceBody(): { provider?: string; model?: string } {
  return aiChoice.value.provider && aiChoice.value.model ? { provider: aiChoice.value.provider, model: aiChoice.value.model } : {}
}
