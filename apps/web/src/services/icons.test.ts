import { describe, expect, it } from 'vitest'
import { LUCIDE_NOTICE, iconNames, iconSvg, insertIcon } from './icons'

describe('icons', () => {
  it('bundles the vendored set', () => {
    expect(iconNames).toHaveLength(24)
    expect(iconNames).toContain('music')
  })
  it('renders inline, sized, without the header comment, decorative by default', () => {
    const svg = iconSvg('music')
    expect(svg).toContain('width="48" height="48" aria-hidden="true"')
    expect(svg).not.toContain('<!--')
    expect(iconSvg('music', 'Nota "do"')).toContain('role="img" aria-label="Nota do"')
    expect(() => iconSvg('nope')).toThrow()
  })
  it('inserts before </main> and adds the notice once', () => {
    const once = insertIcon('<html><head></head><body><main><p>x</p></main></body></html>', 'star', '')
    expect(once.indexOf('lucide-star')).toBeLessThan(once.indexOf('</main>'))
    expect(once).toContain(LUCIDE_NOTICE)
    const twice = insertIcon(once, 'heart', '')
    expect(twice.split('lucide.dev')).toHaveLength(2)
  })
  it('falls back to the end of the document and prepends the notice without <head>', () => {
    const out = insertIcon('<p>solo</p>', 'sun', '')
    expect(out.startsWith(LUCIDE_NOTICE)).toBe(true)
    expect(out).toContain('lucide-sun')
  })
})
