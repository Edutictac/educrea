import { afterEach, expect, it, vi } from 'vitest'
import { loadWallet, openCheckout } from './billing'

afterEach(() => vi.unstubAllGlobals())

it('loads only the current account balance without caching', async () => {
  const wallet = { enabled: true, livemode: false, balance_microeur: 0, currency: 'eur', entries: [], topups: [] }
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(wallet)))
  vi.stubGlobal('fetch', fetch)
  expect(await loadWallet()).toEqual(wallet)
  expect(fetch).toHaveBeenCalledWith('/api/billing/wallet', { credentials: 'same-origin', cache: 'no-store' })
})

it('sends CSRF and a stable attempt ID without an editable amount', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ url: 'https://checkout.stripe.com/c/pay/test' })))
  vi.stubGlobal('fetch', fetch)
  expect(await openCheckout('attempt-id', 'csrf-test')).toBe('https://checkout.stripe.com/c/pay/test')
  const options = fetch.mock.calls[0]![1] as RequestInit
  expect(options.headers).toEqual({ 'Content-Type': 'application/json', 'X-CSRF-Token': 'csrf-test' })
  expect(JSON.parse(options.body as string)).toEqual({ request_id: 'attempt-id' })
})

it.each(['https://checkout.stripe.com.evil.example/pay', 'https://evil.example/pay', 'http://checkout.stripe.com/pay'])
  ('rejects an unexpected checkout destination: %s', async url => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ url }))))
    await expect(openCheckout('attempt-id', 'csrf-test')).rejects.toThrow()
  })

it('does not treat a failed checkout request as a payment', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 502 })))
  await expect(openCheckout('attempt-id', 'csrf-test')).rejects.toThrow()
})
