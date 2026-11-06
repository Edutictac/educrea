import { describe, expect, it } from 'vitest'
import { providerGuides, stepStates, suggestedProvider } from './providerGuide'

describe('providerGuide', () => {
  it('points to official https consoles and covers every provider', () => {
    expect(Object.keys(providerGuides).sort()).toEqual(['anthropic', 'gemini', 'groq', 'mistral', 'nvidia', 'ollama', 'openai', 'openrouter'])
    for (const [name, guide] of Object.entries(providerGuides)) {
      if (name !== 'ollama') expect(guide.url).toMatch(/^https:\/\/(aistudio\.google\.com|openrouter\.ai|console\.groq\.com|console\.mistral\.ai|build\.nvidia\.com|platform\.openai\.com|console\.anthropic\.com)\//)
    }
    expect(providerGuides.gemini.paid).toBe(false)
    expect(providerGuides.openai.paid).toBe(true)
  })
  it('follows the real state of the setup', () => {
    expect(stepStates(false, false, false)).toEqual(['current', 'todo', 'todo'])
    expect(stepStates(true, false, false)).toEqual(['done', 'done', 'current'])
    expect(stepStates(true, true, false)).toEqual(['done', 'done', 'done'])
    expect(stepStates(true, false, true)).toEqual(['done', 'done', 'done'])
  })
  it('suggests Gemini first and then the next free provider still to configure', () => {
    expect(suggestedProvider({})).toBe('gemini')
    expect(suggestedProvider({ gemini: true })).toBe('mistral')
    expect(suggestedProvider({ gemini: true, mistral: true, nvidia: true, groq: true, openrouter: true })).toBe('gemini')
  })
})
