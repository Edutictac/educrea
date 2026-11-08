import { afterEach, expect, it, vi } from 'vitest'
import { betaDashboard, changeBetaAccess, sendBetaInvitation, revokeBetaInvitation, updateImageLimits } from './betaAdmin'
afterEach(() => vi.unstubAllGlobals())

it('uses authenticated admin endpoints with CSRF for mutations and no client role assignments', async () => {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')))
  vi.stubGlobal('fetch', fetchMock)
  await betaDashboard()
  await changeBetaAccess('user-1', true, 'csrf')
  await sendBetaInvitation('teacher@example.org', 'csrf')
  await revokeBetaInvitation('invite-1', 'csrf')
  expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
    '/api/admin/beta', '/api/admin/beta/users/user-1/access', '/api/admin/beta/invitations',
    '/api/admin/beta/invitations/invite-1/revoke',
  ])
  for (const call of fetchMock.mock.calls.slice(1)) expect(call[1].headers['X-CSRF-Token']).toBe('csrf')
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ authorized: true })
  expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ email: 'teacher@example.org' })
})

it('reports denied access instead of treating it as an empty dashboard', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Acceso restringido' }), { status: 403 })))
  await expect(betaDashboard()).rejects.toThrow('Acceso restringido')
})

it('saves image limits through the protected admin endpoint', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}'))
  vi.stubGlobal('fetch', fetchMock)
  await updateImageLimits(5, 50, 'csrf')
  expect(fetchMock.mock.calls[0][0]).toBe('/api/admin/beta/image-limits')
  expect(fetchMock.mock.calls[0][1].method).toBe('PUT')
  expect(fetchMock.mock.calls[0][1].headers['X-CSRF-Token']).toBe('csrf')
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ weekly_limit: 5, global_daily_limit: 50 })
})
