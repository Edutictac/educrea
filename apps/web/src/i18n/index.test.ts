import { describe, expect, it } from 'vitest'
import { detectLocale } from './index'

describe('detectLocale', () => {
  it('maps Catalan variants to Valencian', () => {
    expect(detectLocale(['ca'], null)).toBe('va')
    expect(detectLocale(['ca-ES-valencia', 'es'], null)).toBe('va')
  })
  it('uses the first supported browser language', () => {
    expect(detectLocale(['en-US', 'ca', 'es'], null)).toBe('va')
    expect(detectLocale(['fr', 'es-ES'], null)).toBe('es')
    expect(detectLocale(['fr'], null)).toBe('es')
  })
  it('prefers a saved choice', () => {
    expect(detectLocale(['ca'], 'es')).toBe('es')
    expect(detectLocale(['es'], 'va')).toBe('va')
    expect(detectLocale(['ca'], 'zz')).toBe('va')
  })
})
