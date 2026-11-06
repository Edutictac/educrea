import { describe, expect, it } from 'vitest'
import { providerGuides, stepStates, suggestedProvider } from './providerGuide'

describe('providerGuide', () => {
  it('points to official https consoles and covers every provider', () => {
    expect(Object.keys(providerGuides).sort()).toEqual(['anthropic', 'gemini', 'groq', 'mistral', 'nvidia', 'ollama', 'openai', 'openrouter'])
    for (const [name, guide] of Object.entries(providerGuides)) {
      if (name !== 'ollama') expect(guide.url).toMatch(/^https:\/\/(aistudio\.google\.com|openrouter\.ai|console\.groq\.com|console\.mistral\.ai|build\.nvidia\.com|platform\.openai\.com|console\.anthropic\.com)\//)
    }
    expect(providerGuides.gemini.paid).toBe(false)
    expect(providerGuides.mistral).toMatchObject({ paid: true, steps: 'mistral' })
    expect(providerGuides.nvidia).toMatchObject({ paid: false, steps: 'nvidia' })
    expect(providerGuides.openai.paid).toBe(true)
  })
  it('follows the real state of the setup', () => {
    expect(stepStates(false, false)).toEqual(['done', 'current', 'todo'])
    expect(stepStates(true, false)).toEqual(['done', 'done', 'current'])
    expect(stepStates(true, true)).toEqual(['done', 'done', 'done'])
    expect(stepStates(false, false, true)).toEqual(['current', 'todo', 'todo'])
  })
  it('suggests Gemini first and then the next free provider still to configure', () => {
    expect(suggestedProvider({})).toBe('gemini')
    expect(suggestedProvider({ gemini: true })).toBe('nvidia')
    expect(suggestedProvider({ gemini: true, nvidia: true, groq: true, openrouter: true })).toBe('gemini')
  })
})
