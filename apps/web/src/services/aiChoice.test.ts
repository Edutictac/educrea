import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let values: Map<string, string>
beforeEach(() => {
  vi.resetModules()
  values = new Map()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('invitation-aware AI choice', () => {
  it('defaults to BYOK until authorized and then offers included AI without storing implicit choices', async () => {
    const { aiChoice, initializeAiChoice } = await import('./aiChoice')
    expect(aiChoice.value.provider).toBe('')
    initializeAiChoice('new-account', false)
    expect(aiChoice.value.provider).toBe('')
    expect(values.size).toBe(0)
    initializeAiChoice('new-account', true)
    expect(aiChoice.value).toEqual({ provider: 'educrea', model: 'included' })
    expect(values.size).toBe(0)
  })

  it('isolates choices across accounts and ignores a saved included choice after revocation', async () => {
    const { aiChoice, initializeAiChoice, clearAiChoice } = await import('./aiChoice')
    initializeAiChoice('invited', true)
    aiChoice.value = { provider: 'educrea', model: 'included' }
    clearAiChoice()
    initializeAiChoice('not-invited', false)
    expect(aiChoice.value.provider).toBe('')
    initializeAiChoice('invited', false)
    expect(aiChoice.value.provider).toBe('')
    initializeAiChoice('invited', true)
    expect(aiChoice.value.provider).toBe('educrea')
  })

  it('preserves explicit personal API choices after granting and revoking access', async () => {
    const { aiChoice, initializeAiChoice, choiceBody } = await import('./aiChoice')
    initializeAiChoice('teacher', false)
    aiChoice.value = { provider: 'deepseek', model: 'personal-model' }
    for (const allowed of [true, false, true]) {
      initializeAiChoice('teacher', allowed)
      expect(choiceBody()).toEqual({ provider: 'deepseek', model: 'personal-model' })
    }
    aiChoice.value = { provider: '', model: '' }
    initializeAiChoice('teacher', true)
    expect(choiceBody()).toEqual({ provider: 'byok' })
  })

  it('normalizes legacy preferences without granting permission', async () => {
    values.set('educrea.aiChoice', JSON.stringify({ provider: 'educrea', model: 'included' }))
    const { aiChoice, initializeAiChoice } = await import('./aiChoice')
    initializeAiChoice('teacher', false)
    expect(aiChoice.value.provider).toBe('')
  })
})
