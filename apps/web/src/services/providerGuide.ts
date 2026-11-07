import type { ProviderName } from './ai'

// Official consoles where each teacher creates a personal key. Keys are never stored here.
export interface ProviderGuide { url: string; paid: boolean; steps: 'google' | 'openrouter' | 'groq' | 'mistral' | 'paid' | 'managed' }

export const providerGuides: Record<ProviderName, ProviderGuide> = {
  gemini: { url: 'https://aistudio.google.com/app/apikey', paid: false, steps: 'google' },
  openrouter: { url: 'https://openrouter.ai/settings/keys', paid: false, steps: 'openrouter' },
  groq: { url: 'https://console.groq.com/keys', paid: false, steps: 'groq' },
  mistral: { url: 'https://console.mistral.ai/api-keys', paid: true, steps: 'mistral' },
  openai: { url: 'https://platform.openai.com/api-keys', paid: true, steps: 'paid' },
  anthropic: { url: 'https://console.anthropic.com/settings/keys', paid: true, steps: 'paid' },
  ollama: { url: '', paid: false, steps: 'managed' },
}

export type StepState = 'done' | 'current' | 'todo'

// Creating the key happens on the provider's site; EduCrea can verify steps 2 and 3.
export function stepStates(configured: boolean, ready: boolean, managed = false): [StepState, StepState, StepState] {
  if (!configured) return managed ? ['current', 'todo', 'todo'] : ['done', 'current', 'todo']
  return ready ? ['done', 'done', 'done'] : ['done', 'done', 'current']
}

// Provider shown first: the first one a teacher still has to set up, Gemini by default.
export function suggestedProvider(configured: Partial<Record<ProviderName, boolean>>): ProviderName {
  const order: ProviderName[] = ['gemini', 'groq', 'openrouter']
  return order.find(name => !configured[name]) ?? 'gemini'
}
