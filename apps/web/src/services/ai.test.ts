import { describe, expect, it, vi } from 'vitest'
import { estimatePaid, parseSseBlock, streamProposal } from './ai'

describe('contexto automático', () => {
  it('envía automatic y no manda rutas cuando la IA decide', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ maximum_cost_microusd: 1 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await estimatePaid('p1', 'Crea una actividad', 'openai', 'm', ['index.html'], 'csrf', true)
    const sent = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)
    expect(sent.automatic).toBe(true)
    expect(sent.context_paths).toEqual([])
    vi.unstubAllGlobals()
  })
})

describe('streaming de propuestas', () => {
  it('interpreta eventos SSE y fragmentos divididos entre lecturas', async () => {
    expect(parseSseBlock('event: token\ndata: {"text":"hola"}')).toEqual({ event: 'token', data: { text: 'hola' } })
    const encoder = new TextEncoder()
    const body = new ReadableStream<Uint8Array>({ start(controller) {
      controller.enqueue(encoder.encode('event: token\ndata: {"text":"ho'))
      controller.enqueue(encoder.encode('la"}\n\nevent: proposal\ndata: {"id":"p1"}\n\n'))
      controller.close()
    } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })))
    const events: string[] = []
    await streamProposal('project-1', 'Crea una actividad', 'gemini', 'gemini-test-free', [], false,
      'csrf', new AbortController().signal,
      event => events.push(event.event))
    expect(events).toEqual(['token', 'proposal'])
    vi.unstubAllGlobals()
  })

  it('rechaza una respuesta que termina sin propuesta', async () => {
    const body = new ReadableStream<Uint8Array>({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: token\ndata: {"text":"incompleto"}\n\n'))
      controller.close()
    } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })))
    await expect(streamProposal('project-1', 'Crea una actividad', 'gemini', 'gemini-test-free', [], false, 'csrf',
      new AbortController().signal, () => {})).rejects.toThrow('Respuesta incompleta')
    vi.unstubAllGlobals()
  })

  it('envía la aceptación exacta de una estimación de pago', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ maximum_cost_microusd: 1234, fingerprint: 'abc' }), { status: 200 }))
      .mockResolvedValueOnce(new Response('event: proposal\ndata: {"id":"p1"}\n\n', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    const estimate = await estimatePaid('project-1', 'Crea una actividad', 'openai', 'model-1', [], 'csrf')
    await streamProposal('project-1', 'Crea una actividad', 'openai', 'model-1', [], false, 'csrf',
      new AbortController().signal, () => {}, 'paid', estimate.maximum_cost_microusd, estimate.fingerprint)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ mode: 'paid', provider: 'openai' })
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      mode: 'paid', paid_authorized: true, approved_max_cost_microusd: 1234,
      approved_estimate_fingerprint: 'abc',
    })
    vi.unstubAllGlobals()
  })
})

describe('primera versión desde el encargo', () => {
  it('envía la IA elegida al generar la primera versión', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'p1', status: 'applied' }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)
    const { generateFromBrief } = await import('./ai')
    const proposal = await generateFromBrief('pr1', 'csrf-1', { provider: 'mistral', model: 'mistral-small-latest' })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/projects/pr1/ai/from-brief')
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-1')
    expect(JSON.parse(init.body as string)).toEqual({ provider: 'mistral', model: 'mistral-small-latest' })
    expect(proposal.status).toBe('applied')
    vi.unstubAllGlobals()
  })
})
