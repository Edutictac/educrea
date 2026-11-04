import { describe, expect, it, vi } from 'vitest'
import { uploadSource } from './sources'

describe('sources', () => {
  it('sends the file as the raw body with the CSRF header and the file name in the query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 's1', title: 'Primaria' }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['contenido'], 'curriculo primaria.pdf', { type: 'application/pdf' })
    await uploadSource('p1', file, 'Currículo Primaria', 'csrf-token')
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/projects/p1/sources?')
    const query = new URLSearchParams(url.split('?')[1])
    expect(query.get('filename')).toBe('curriculo primaria.pdf')
    expect(query.get('title')).toBe('Currículo Primaria')
    expect(init.body).toBe(file)
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-token')
    vi.unstubAllGlobals()
  })
  it('surfaces the API error message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'El PDF parece escaneado' }), { status: 422 })))
    await expect(uploadSource('p1', new File(['x'], 'a.pdf'), '', 'c')).rejects.toThrow('escaneado')
    vi.unstubAllGlobals()
  })
})
