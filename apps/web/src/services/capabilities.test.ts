import { describe, expect, it } from 'vitest'
import { parseArguments } from './capabilities'

describe('parseArguments', () => {
  it('accepts objects and empty text', () => {
    expect(parseArguments('')).toEqual({})
    expect(parseArguments('{"path":"index.html"}')).toEqual({ path: 'index.html' })
  })
  it('rejects non-objects and invalid JSON', () => {
    expect(parseArguments('[1]')).toBeNull()
    expect(parseArguments('null')).toBeNull()
    expect(parseArguments('{path:')).toBeNull()
  })
})
