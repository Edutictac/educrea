import { describe, expect, it } from 'vitest'
import { buildPreview } from './preview'
import { infographicTemplate } from './templates'

describe('infographicTemplate', () => {
  it('is self-contained, accessible and escapes the title', () => {
    const html = infographicTemplate('Notas <b>&</b>')
    expect(html).not.toMatch(/<script|https?:\/\/(?!www\.w3\.org|lucide\.dev)/)
    expect(html).toContain('<title>Notas b/b</title>')
    expect(html.match(/role="img"/g)).toHaveLength(3)
    expect(html).toContain('lucide.dev')
    expect(html).toContain('lucide-lightbulb')
    expect(buildPreview(html, {})).toContain('Primer paso')
  })
})
