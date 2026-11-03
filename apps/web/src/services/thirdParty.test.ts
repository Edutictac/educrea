import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = join(__dirname, '../../../../third_party/lucide')
const manifest = JSON.parse(readFileSync(join(root, 'manifest.json'), 'utf8')) as {
  icons: { name: string; license: string }[]
}
const license = readFileSync(join(root, 'LICENSE'), 'utf8')
const feather = new Set((/derived from the Feather project:\n\n([\s\S]*?)\n\n/.exec(license)?.[1] ?? '').replace(/\n/g, '').split(', '))
const RENAMED_FROM_FEATHER = new Set(['circle-help']) // help-circle in Feather

describe('vendored Lucide icons', () => {
  it('keeps the ISC and MIT notices', () => {
    expect(license).toContain('ISC License')
    expect(license).toContain('The MIT License (MIT)')
    expect(feather.size).toBeGreaterThan(100)
  })
  it('has a manifest entry for every SVG and vice versa', () => {
    const files = readdirSync(join(root, 'icons')).map(name => name.replace('.svg', '')).sort()
    expect(manifest.icons.map(icon => icon.name)).toEqual(files)
  })
  it('keeps the license header and flags Feather-derived icons as MIT', () => {
    for (const icon of manifest.icons) {
      expect(readFileSync(join(root, 'icons', `${icon.name}.svg`), 'utf8')).toMatch(/@license lucide-static v[\d.]+ - ISC/)
      const derived = feather.has(icon.name) || RENAMED_FROM_FEATHER.has(icon.name)
      expect(icon.license).toBe(derived ? 'ISC AND MIT (Feather)' : 'ISC')
    }
  })
  it('contains no scripts or external references', () => {
    for (const icon of manifest.icons) {
      expect(readFileSync(join(root, 'icons', `${icon.name}.svg`), 'utf8')).not.toMatch(/<script|href=|https?:\/\/(?!www\.w3\.org)/)
    }
  })
})
