import { describe, expect, it } from 'vitest'
import { embedImages, htmlSnippet, markdownSnippet, type Asset } from './assets'
import { buildPreview } from './preview'

const images = { 'imagenes/sol.png': 'data:image/png;base64,AAA' }

describe('embedImages', () => {
  it('replaces only library references in src, url() and Markdown', () => {
    const out = embedImages('<img src="imagenes/sol.png"><img src=\'./imagenes/sol.png\'><i style="background:url(imagenes/sol.png)"></i>![a](imagenes/sol.png)<img src="imagenes/no.png"><img src="https://x.org/imagenes/sol.png">', images)
    expect(out.match(/data:image\/png/g)?.length).toBe(4)
    expect(out).toContain('src="imagenes/no.png"')
    expect(out).toContain('https://x.org/imagenes/sol.png')
  })
  it('works inside the isolated preview, including inlined CSS', () => {
    const doc = buildPreview('<html><head><link rel="stylesheet" href="style.css"></head><body><img src="imagenes/sol.png" alt="Sol"></body></html>',
      { 'style.css': 'body{background:url("imagenes/sol.png")}' }, images)
    expect(doc.match(/data:image\/png/g)?.length).toBe(2)
    expect(doc).toContain("img-src data:")
  })
  it('builds snippets that keep the alternative text', () => {
    const asset: Asset = { id: '1', path: 'imagenes/sol.png', media_type: 'image/png', size: 1, alt: 'El "sol" [dibujo]', credit: '' }
    expect(htmlSnippet(asset)).toBe('<img src="imagenes/sol.png" alt="El &quot;sol&quot; [dibujo]">')
    expect(markdownSnippet(asset)).toBe('![El "sol" dibujo](imagenes/sol.png)')
  })
})
