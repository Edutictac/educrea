import { describe, expect, it } from 'vitest'
import { loadIndependently } from './loadIndependently'

describe('loadIndependently', () => {
  it('keeps the requests that worked when another one fails', async () => {
    const { values, errors } = await loadIndependently({
      providers: async () => ['gemini'],
      quota: async (): Promise<number> => { throw new Error('quota 500') },
      budget: async () => ({ limit: 0 }),
    })
    expect(values.providers).toEqual(['gemini'])
    expect(values.budget).toEqual({ limit: 0 })
    expect(values.quota).toBeUndefined()
    expect(errors.quota?.message).toBe('quota 500')
    expect(errors.providers).toBeUndefined()
  })

  it('reports every failure and wraps values that are not errors', async () => {
    const { values, errors } = await loadIndependently({
      a: async (): Promise<number> => { throw 'plain text' },
      b: async (): Promise<number> => { throw new Error('boom') },
    })
    expect(Object.keys(values)).toEqual([])
    expect(errors.a).toBeInstanceOf(Error)
    expect(errors.a?.message).toBe('plain text')
    expect(errors.b?.message).toBe('boom')
  })
})
