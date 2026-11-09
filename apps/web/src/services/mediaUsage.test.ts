import { afterEach, expect, it, vi } from 'vitest'
import { generateImage, type ImageEstimate } from './images'
import { generateVideo, type VideoEstimate } from './videos'

afterEach(() => vi.unstubAllGlobals())

it.each(['image', 'video'] as const)('refreshes the account quota after a %s generation succeeds or fails', async kind => {
  const events = new EventTarget()
  const changed = vi.fn()
  events.addEventListener('educrea-ai-usage', changed)
  vi.stubGlobal('window', events)
  const fetchMock = vi.fn().mockResolvedValueOnce(new Response('{}'))
    .mockRejectedValueOnce(new Error('Generation failed'))
  vi.stubGlobal('fetch', fetchMock)
  const run = kind === 'image'
    ? () => generateImage('project-1', 'Flowers', 'image-model', '1:1',
      { maximum_cost_microusd: 1000, fingerprint: 'estimate' } as ImageEstimate, 'csrf')
    : () => generateVideo('project-1', 'Flowers', 'video-model', '360p', 4, '16:9',
      { maximum_cost_microusd: 1000, fingerprint: 'estimate' } as VideoEstimate, 'csrf')
  await run()
  expect(changed).toHaveBeenCalledTimes(1)
  await expect(run()).rejects.toThrow('Generation failed')
  expect(changed).toHaveBeenCalledTimes(2)
})
