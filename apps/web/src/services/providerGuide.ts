import type { ProviderName } from './ai'

// Official consoles where each teacher creates a personal key. Keys are never stored here.
export interface ProviderGuide { url: string; paid: boolean; steps: 'google' | 'openrouter' | 'groq' | 'paid' | 'managed' }

export const providerGuides: Record<ProviderName, ProviderGuide> = {
  gemini: { url: 'https://aistudio.google.com/app/apikey', paid: false, steps: 'google' },
  openrouter: { url: 'https://openrouter.ai/settings/keys', paid: false, steps: 'openrouter' },
  groq: { url: 'https://console.groq.com/keys', paid: false, steps: 'groq' },
  openai: { url: 'https://platform.openai.com/api-keys', paid: true, steps: 'paid' },
  anthropic: { url: 'https://console.anthropic.com/settings/keys', paid: true, steps: 'paid' },
  ollama: { url: '', paid: false, steps: 'managed' },
}

export type StepState = 'done' | 'current' | 'todo'

// Step 1 (create key) is informational; steps 2 and 3 follow the real configuration state.
export function stepStates(configured: boolean, confirmedFree: boolean, paid: boolean): [StepState, StepState, StepState] {
  if (!configured) return ['current', 'todo', 'todo']
  if (paid) return ['done', 'done', 'done']
  return confirmedFree ? ['done', 'done', 'done'] : ['done', 'done', 'current']
}

// Provider shown first: the first one a teacher still has to set up, Gemini by default.
export function suggestedProvider(configured: Partial<Record<ProviderName, boolean>>): ProviderName {
  const order: ProviderName[] = ['gemini', 'openrouter', 'groq']
  return order.find(name => !configured[name]) ?? 'gemini'
}
