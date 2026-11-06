// Line-based diff for the viewer. It is small enough to run in the browser without adding a dependency.
// Long files keep a bounded table: common lines are stripped first and, if the remaining block is huge,
// it is shown as a whole replacement instead of risking a slow comparison.

export type DiffKind = 'context' | 'add' | 'remove'

export interface DiffLine {
  kind: DiffKind
  text: string
  before: number | null
  after: number | null
}

export interface DiffResult {
  lines: DiffLine[]
  additions: number
  removals: number
}

const MAX_CELLS = 4_000_000

function splitLines(text: string): string[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  if (lines.length && lines[lines.length - 1] === '') lines.pop()
  return lines
}

// Shortest edit script for the changed block, reconstructed from an LCS table.
function editScript(a: string[], b: string[]): Array<'equal' | 'remove' | 'add'> {
  const rows = a.length + 1
  const width = b.length + 1
  const table = new Uint32Array(rows * width)
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i * width + j] = a[i] === b[j]
        ? table[(i + 1) * width + j + 1] + 1
        : Math.max(table[(i + 1) * width + j], table[i * width + j + 1])
    }
  }
  const script: Array<'equal' | 'remove' | 'add'> = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { script.push('equal'); i++; j++ }
    else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) { script.push('remove'); i++ }
    else { script.push('add'); j++ }
  }
  while (i < a.length) { script.push('remove'); i++ }
  while (j < b.length) { script.push('add'); j++ }
  return script
}

export function diffLines(before: string, after: string): DiffResult {
  const a = splitLines(before)
  const b = splitLines(after)

  let prefix = 0
  while (prefix < a.length && prefix < b.length && a[prefix] === b[prefix]) prefix++
  let endA = a.length
  let endB = b.length
  while (endA > prefix && endB > prefix && a[endA - 1] === b[endB - 1]) { endA--; endB-- }

  const lines: DiffLine[] = []
  let beforeNo = 1
  let afterNo = 1
  const context = (text: string) => lines.push({ kind: 'context', text, before: beforeNo++, after: afterNo++ })

  for (let i = 0; i < prefix; i++) context(a[i])

  const middleA = a.slice(prefix, endA)
  const middleB = b.slice(prefix, endB)
  if (middleA.length * middleB.length > MAX_CELLS) {
    for (const text of middleA) lines.push({ kind: 'remove', text, before: beforeNo++, after: null })
    for (const text of middleB) lines.push({ kind: 'add', text, before: null, after: afterNo++ })
  } else {
    let i = 0
    let j = 0
    for (const step of editScript(middleA, middleB)) {
      if (step === 'equal') { context(middleA[i]); i++; j++ }
      else if (step === 'remove') { lines.push({ kind: 'remove', text: middleA[i], before: beforeNo++, after: null }); i++ }
      else { lines.push({ kind: 'add', text: middleB[j], before: null, after: afterNo++ }); j++ }
    }
  }

  for (let i = endA; i < a.length; i++) context(a[i])

  return {
    lines,
    additions: lines.filter(line => line.kind === 'add').length,
    removals: lines.filter(line => line.kind === 'remove').length,
  }
}
