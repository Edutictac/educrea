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
