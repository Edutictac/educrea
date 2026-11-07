import { describe, expect, it } from 'vitest'
import { buildPreview } from './preview'
import { infographicTemplate } from './templates'
import { initialGuestFiles } from '../stores/guest'

describe('infographicTemplate', () => {
  it('is self-contained, accessible and escapes the title', () => {
    const html = infographicTemplate('Notas <b>&</b>', 'es')
    expect(html).not.toMatch(/<script|https?:\/\/(?!www\.w3\.org|lucide\.dev)/)
    expect(html).toContain('<title>Notas b/b</title>')
    expect(html.match(/role="img"/g)).toHaveLength(3)
    expect(html).toContain('lucide.dev')
    expect(html).toContain('lucide-lightbulb')
    expect(buildPreview(html, {})).toContain('Primer paso')
  })
  it('translates the infographic body and accessible icon descriptions into English', () => {
    const html = infographicTemplate('Music', 'en')
    expect(html).toContain('<html lang="en">')
    expect(html).toContain('First step')
    expect(html).toContain('Light bulb: an idea')
    expect(html).toContain('More information')
    expect(html).not.toMatch(/Primer paso|Segundo paso|Más información|Bombilla/)
    expect(infographicTemplate('Música', 'va')).toContain('Primer pas')
  })
  it('starts a new English guest draft with English content and metadata', () => {
    const files = initialGuestFiles('en')
    expect(JSON.parse(files['activity.json'])).toMatchObject({ language: 'en', title: 'My activity' })
    expect(files['index.html']).toContain('<html lang="en">')
    expect(files['index.html']).toContain('Start creating here.')
    expect(files['script.js']).toContain('Add interactions here.')
    expect(files['index.html']).not.toMatch(/Mi actividad|Empieza/)
  })
})
