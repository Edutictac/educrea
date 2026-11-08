import { describe, expect, it } from 'vitest'
import { illustrationTarget, templateIllustrable } from './illustrations'

describe('illustrations', () => {
  it('targets the file that holds the content, like the API', () => {
    expect(illustrationTarget({ kind: 'actividad', template: 'infografia' })).toBe('infografia.html')
    expect(illustrationTarget({ kind: 'ficha', template: 'ficha' })).toBe('ficha.md')
    expect(illustrationTarget({ kind: 'situacion' })).toBe('situacion.md')
    expect(illustrationTarget({ kind: 'actividad', template: 'tarjetas' })).toBe('datos.js')
    expect(illustrationTarget({ kind: 'actividad', template: 'sopa_letras' })).toBeNull()
    expect(illustrationTarget({ kind: 'actividad' })).toBeNull()
  })

  it('trusts the catalog flag and falls back for older APIs', () => {
    expect(templateIllustrable({ id: 'infografia', illustrable: true })).toBe(true)
    expect(templateIllustrable({ id: 'tarjetas', illustrable: false })).toBe(false)
    expect(templateIllustrable({ id: 'crucigrama' })).toBe(false)
    expect(templateIllustrable({ id: 'infografia' })).toBe(true)
  })
})

describe('included images', () => {
  it('counts IA EduCrea images only for its model', async () => {
    const { includedLeft } = await import('./images')
    const status = { configured: true, default: 'm', models: [], budget: { monthly_limit_microusd: 0, spent_or_reserved_microusd: 0 },
      included: { model: 'm', weekly_limit: 10, used: 3, remaining: 7, renews_at: '' } } as never
    expect(includedLeft(status, 'm')).toBe(7)
    expect(includedLeft(status, 'other')).toBeNull()
    expect(includedLeft(null, 'm')).toBeNull()
  })
})

describe('api errors in Valencian', () => {
  it('translates illustration and IA EduCrea messages', async () => {
    const { locale } = await import('../i18n')
    const { apiMessage } = await import('../i18n/apiErrors')
    const previous = locale.value
    locale.value = 'va'
    expect(apiMessage('Configura una IA gratuita para que pueda describir las ilustraciones'))
      .toBe('Configura una IA gratuïta perquè puga descriure les il·lustracions')
    expect(apiMessage('Mensaje desconocido')).toBe('Mensaje desconocido')
    locale.value = previous
  })
})
