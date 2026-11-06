import { describe, expect, it } from 'vitest'
import { diffLines } from './textDiff'

describe('diffLines', () => {
  it('keeps identical content as context', () => {
    const diff = diffLines('uno\ndos\n', 'uno\ndos')
    expect(diff.additions).toBe(0)
    expect(diff.removals).toBe(0)
    expect(diff.lines.map(line => [line.kind, line.before, line.after])).toEqual([
      ['context', 1, 1], ['context', 2, 2],
    ])
  })
  it('marks added lines and numbers both sides', () => {
    const diff = diffLines('a\nb\nc', 'a\nb\nnueva\nc')
    expect(diff.additions).toBe(1)
    expect(diff.removals).toBe(0)
    const added = diff.lines.find(line => line.kind === 'add')
    expect(added).toMatchObject({ text: 'nueva', before: null, after: 3 })
  })
  it('marks removed lines', () => {
    const diff = diffLines('a\nb\nc', 'a\nc')
    expect(diff.removals).toBe(1)
    expect(diff.lines.find(line => line.kind === 'remove')).toMatchObject({ text: 'b', before: 2, after: null })
  })
  it('shows a replacement as a removal followed by an addition', () => {
    const diff = diffLines('a\nb\nc', 'a\nx\nc')
    expect(diff.lines.filter(line => line.kind !== 'context').map(line => [line.kind, line.text])).toEqual([
      ['remove', 'b'], ['add', 'x'],
    ])
    expect(diff.lines.map(line => [line.before, line.after])).toEqual([
      [1, 1], [2, null], [null, 2], [3, 3],
    ])
  })
  it('treats an empty previous version as all additions', () => {
    const diff = diffLines('', 'nueva\n actividad')
    expect(diff.additions).toBe(2)
    expect(diff.removals).toBe(0)
    expect(diff.lines.every(line => line.kind === 'add')).toBe(true)
  })
  it('normalises CRLF and a trailing newline', () => {
    expect(diffLines('a\r\nb\r\n', 'a\nb').lines.every(line => line.kind === 'context')).toBe(true)
  })
  it('falls back to a whole replacement for very large changed blocks', () => {
    const before = Array.from({ length: 2100 }, (_, index) => `antes ${index}`).join('\n')
    const after = Array.from({ length: 2100 }, (_, index) => `después ${index}`).join('\n')
    const diff = diffLines(before, after)
    expect(diff.removals).toBe(2100)
    expect(diff.additions).toBe(2100)
  })
})
