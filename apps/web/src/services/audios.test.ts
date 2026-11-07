import { describe, expect, it } from 'vitest'
import { buildPreview, PREVIEW_CSP } from './preview'
import { embedAudio } from './audios'

describe('audio in the isolated preview', () => {
  it('embeds library audio in template data and static HTML, while keeping network media blocked', () => {
    const media = { 'audios/voz.wav': 'data:audio/wav;base64,AAAA' }
    const out = buildPreview('<html><head></head><body><script src="datos.js"></script><audio controls src="./audios/voz.wav"></audio></body></html>',
      { 'datos.js': 'window.EDUCREA_DATA = {"audio": "audios/voz.wav"};' }, {}, media)
    expect(out.match(/data:audio\/wav;base64,AAAA/g)).toHaveLength(2)
    expect(PREVIEW_CSP).toContain('media-src data:;')
    expect(PREVIEW_CSP).not.toMatch(/media-src[^;]*https?/)
    expect(embedAudio('<audio src="https://example.org/audios/voz.wav">', media)).toContain('https://example.org')
    expect(embedAudio('<audio src="audios/other.wav">', media)).toContain('audios/other.wav')
  })
})
