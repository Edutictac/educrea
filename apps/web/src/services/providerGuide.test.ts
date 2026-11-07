import { describe, expect, it } from 'vitest'
import { providerGuides, stepStates, suggestedProvider } from './providerGuide'

describe('providerGuide', () => {
  it('points to official https consoles and covers every provider', () => {
    expect(Object.keys(providerGuides).sort()).toEqual(['anthropic', 'deepseek', 'gemini', 'groq', 'mistral', 'ollama', 'openai', 'openrouter'])
    for (const [name, guide] of Object.entries(providerGuides)) {
      if (name !== 'ollama') expect(guide.url).toMatch(/^https:\/\/(aistudio\.google\.com|openrouter\.ai|console\.groq\.com|console\.mistral\.ai|platform\.openai\.com|console\.anthropic\.com|platform\.deepseek\.com)\//)
    }
    expect(providerGuides.gemini.paid).toBe(false)
    expect(providerGuides.mistral).toMatchObject({ paid: true, steps: 'mistral' })
    expect(providerGuides.openai.paid).toBe(true)
    expect(providerGuides.deepseek).toMatchObject({ paid: true, steps: 'paid' })
  })
  it('follows the real state of the setup', () => {
    expect(stepStates(false, false)).toEqual(['done', 'current', 'todo'])
    expect(stepStates(true, false)).toEqual(['done', 'done', 'current'])
    expect(stepStates(true, true)).toEqual(['done', 'done', 'done'])
    expect(stepStates(false, false, true)).toEqual(['current', 'todo', 'todo'])
  })
  it('suggests Gemini first and then the next free provider still to configure', () => {
    expect(suggestedProvider({})).toBe('gemini')
    expect(suggestedProvider({ gemini: true })).toBe('groq')
    expect(suggestedProvider({ gemini: true, groq: true, openrouter: true })).toBe('gemini')
  })
})
