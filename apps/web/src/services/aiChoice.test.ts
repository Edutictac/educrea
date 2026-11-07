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

describe('safe default while the included AI is paused', () => {
  it('stays on Automática/BYOK when the server says the included AI is not available', async () => {
    const { aiChoice, startAiChoice, choiceBody } = await import('./aiChoice')
    await startAiChoice('invited', true, async () => ({ available: false }))  // e.g. EDUCREA_FREE_AI_ENABLED=false or zero prices
    expect(aiChoice.value).toEqual({ provider: '', model: '' })
    expect(choiceBody()).toEqual({ provider: 'byok' })
    await startAiChoice('invited', true, async () => { throw new Error('503') })
    expect(choiceBody()).toEqual({ provider: 'byok' })
    await startAiChoice('not-invited', false, async () => { throw new Error('must not be called') })
    expect(aiChoice.value.provider).toBe('')
  })

  it('offers the included AI by default only when it is available', async () => {
    const { aiChoice, startAiChoice } = await import('./aiChoice')
    await startAiChoice('invited', true, async () => ({ available: true }))
    expect(aiChoice.value).toEqual({ provider: 'educrea', model: 'included' })
    expect(values.size).toBe(0)  // the implicit default is never stored
  })

  it('does not override what the teacher picked while the check was running', async () => {
    const { aiChoice, startAiChoice } = await import('./aiChoice')
    let answer: (value: { available: boolean }) => void = () => {}
    const pending = startAiChoice('teacher', true, () => new Promise(resolve => { answer = resolve }))
    aiChoice.value = { provider: 'gemini', model: 'gemini-test' }
    answer({ available: true })
    await pending
    expect(aiChoice.value).toEqual({ provider: 'gemini', model: 'gemini-test' })
  })

  it('ignores a late answer after another account signed in', async () => {
    const { aiChoice, startAiChoice } = await import('./aiChoice')
    let answer: (value: { available: boolean }) => void = () => {}
    const first = startAiChoice('first', true, () => new Promise(resolve => { answer = resolve }))
    await startAiChoice('second', false, async () => ({ available: true }))
    answer({ available: true })
    await first
    expect(aiChoice.value.provider).toBe('')
  })
})

describe('included AI offered in the picker', () => {
  it('needs permission and an available service, and never trusts a bare 200 response', async () => {
    const { includedOffered } = await import('./aiChoice')
    expect(includedOffered(true, { available: true })).toBe(true)
    expect(includedOffered(true, { available: false })).toBe(false)  // service paused: the status object exists but is not available
    expect(includedOffered(true, null)).toBe(false)                  // status could not be read
    expect(includedOffered(false, { available: true })).toBe(false)  // no permission
  })
})
