import { describe, expect, it } from 'vitest'
import { buildPreview, PREVIEW_CSP } from './preview'

describe('buildPreview', () => {
  it('inlines local css and js and puts the CSP first', () => {
    const out = buildPreview('<html><head><link rel="stylesheet" href="style.css"></head><body><script src="./app.js"></script></body></html>',
      { 'style.css': 'p{color:red}', 'app.js': 'var x = "</script>";' })
    expect(out.indexOf(PREVIEW_CSP)).toBeLessThan(out.indexOf('<style>'))
    expect(out).toContain('<style>p{color:red}</style>')
    expect(out).toContain('<\\/script>')
    expect(out).not.toContain('href="style.css"')
  })
  it('drops external stylesheets and scripts', () => {
    const out = buildPreview('<link rel="stylesheet" href="https://evil.test/a.css"><script src="https://evil.test/a.js"></script>', {})
    expect(out).not.toContain('evil.test/a')
    expect(out.startsWith('<meta http-equiv="Content-Security-Policy"')).toBe(true)
  })
})
