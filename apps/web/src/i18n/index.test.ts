import { afterEach, describe, expect, it } from 'vitest'
import { detectLocale, intlLocale, locale, messages, t } from './index'
import { apiMessage } from './apiErrors'
import { PROVIDER_NAMES } from '../services/aiChoice'

afterEach(() => { locale.value = 'es' })

describe('translation coverage', () => {
  it('has every message and preserves interpolation parameters in all four languages', () => {
    const keys = Object.keys(messages.es).sort()
    for (const language of ['ca', 'va', 'en'] as const) {
      expect(Object.keys(messages[language]).sort()).toEqual(keys)
      for (const key of keys as (keyof typeof messages.es)[]) {
        expect(messages[language][key].trim(), `${language}.${key}`).not.toBe('')
        const parameters = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort()
        expect(parameters(messages[language][key]), `${language}.${key}`).toEqual(parameters(messages.es[key]))
      }
    }
  })
  it('switches provider labels and formatting with the chosen UI language', () => {
    locale.value = 'en'
    expect(PROVIDER_NAMES.educrea).toBe('EduCrea AI')
    expect(PROVIDER_NAMES.ollama).toBe('Ollama (server)')
    expect(t('languageSpanish')).toBe('Spanish')
    expect(new Date('2026-07-01T00:00:00Z').toLocaleDateString(intlLocale(), { month: 'long', timeZone: 'UTC' })).toBe('July')
    locale.value = 'va'
    expect(intlLocale()).toBe('ca-ES-valencia')
    expect(PROVIDER_NAMES.educrea).toBe('IA EduCrea')
    locale.value = 'ca'
    expect(intlLocale()).toBe('ca')
    expect(t('logout')).toBe('Sortir')
  })
  it('translates known API messages without changing unknown provider diagnostics', () => {
    locale.value = 'en'
    expect(apiMessage('Proyecto no encontrado')).toBe('Project not found')
    expect(apiMessage('Configura tu clave de Gemini antes de generar')).toBe('Set up your Gemini key before generating')
    expect(apiMessage('IA EduCrea no está disponible ahora. Puedes utilizar tu propia API.')).toContain('EduCrea AI is unavailable')
    expect(apiMessage('Provider returned code X-123')).toBe('Provider returned code X-123')
    expect(apiMessage(null)).toBe(t('error'))
    locale.value = 'es'
    expect(apiMessage('Proyecto no encontrado')).toBe('Proyecto no encontrado')
  })
})

describe('detectLocale', () => {
  it('distinguishes Catalan from Valencian', () => {
    expect(detectLocale(['ca'], null)).toBe('ca')
    expect(detectLocale(['ca-ES'], null)).toBe('ca')
    expect(detectLocale(['ca-ES-valencia', 'es'], null)).toBe('va')
  })
  it('uses the first supported browser language', () => {
    expect(detectLocale(['en-US', 'ca', 'es'], null)).toBe('en')
    expect(detectLocale(['fr', 'ca', 'es'], null)).toBe('ca')
    expect(detectLocale(['fr', 'es-ES'], null)).toBe('es')
    expect(detectLocale(['fr'], null)).toBe('es')
  })
  it('prefers a saved choice', () => {
    expect(detectLocale(['ca'], 'es')).toBe('es')
    expect(detectLocale(['es'], 'ca')).toBe('ca')
    expect(detectLocale(['es'], 'va')).toBe('va')
    expect(detectLocale(['es'], 'en')).toBe('en')
    expect(detectLocale(['ca'], 'zz')).toBe('ca')
  })
})
