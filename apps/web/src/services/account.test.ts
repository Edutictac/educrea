import { afterEach, describe, expect, it, vi } from 'vitest'
import { locale } from '../i18n'
import { normalizeAccountLocale, readSharedLanguage, rememberSharedLanguage } from '../i18n/preference'
import { ACCOUNT_BASE, accountReturnPath, centralLoginUrl, centralTeacherSession, claimAccountConnection, clearAccountConnection, installAccountLanguage, isCentralTeacher, localLoginUrl } from './account'

afterEach(() => { locale.value = 'es'; vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('account language adapter', () => {
  it('connects all four languages and announces changes without accepting unsupported values', () => {
    const events: Event[] = []
    vi.stubGlobal('CustomEvent', class extends Event { detail: unknown; constructor(name: string, init?: CustomEventInit) { super(name); this.detail = init?.detail } })
    const host = { dispatchEvent: (event: Event) => { events.push(event); return true } } as unknown as Window
    const dispose = installAccountLanguage(host)
    expect(host.edutictacLanguage?.languages).toEqual(['ca', 'va', 'es', 'en'])
    host.edutictacLanguage?.set('ca')
    expect(locale.value).toBe('ca')
    expect(host.edutictacLanguage?.get()).toBe('ca')
    expect(events.at(-1)?.type).toBe('edutictac:langchange')
    host.edutictacLanguage?.set('en')
    expect(locale.value).toBe('en')
    host.edutictacLanguage?.set('fr')
    expect(locale.value).toBe('en')
    dispose()
    expect(host.edutictacLanguage).toBeUndefined()
  })
  it('uses the shared display preference and scopes it only to EduTicTac domains', () => {
    expect(readSharedLanguage({ cookie: 'other=value; edutictac_language=ca' })).toBe('ca')
    expect(readSharedLanguage({ cookie: 'edutictac_language=ca-ES-valencia' })).toBe('va')
    expect(readSharedLanguage({ cookie: 'edutictac_language=unknown' })).toBeNull()
    expect(normalizeAccountLocale('ca-ES-valencia')).toBe('va')
    const doc = { cookie: '' }
    rememberSharedLanguage('en', doc, { hostname: 'educrea.edutictac.es', protocol: 'https:' })
    expect(doc.cookie).toContain('Domain=edutictac.es')
    expect(doc.cookie).toContain('; Secure')
    rememberSharedLanguage('va', doc, { hostname: 'localhost', protocol: 'http:' })
    expect(doc.cookie).not.toContain('Domain=')
    expect(doc.cookie).not.toContain('Secure')
    rememberSharedLanguage('es', doc, { hostname: 'fakeedutictac.es', protocol: 'https:' })
    expect(doc.cookie).not.toContain('Domain=')
  })
})

describe('coordinated SSO', () => {
  it('opens the central session then returns through local OIDC with the original screen', () => {
    const next = '/projects/example?tab=tools#fuentes'
    const start = new URL(centralLoginUrl('https://educrea.edutictac.es', next))
    expect(start.origin).toBe(ACCOUNT_BASE)
    expect(start.pathname).toBe('/api/auth/oidc/login')
    const local = new URL(start.searchParams.get('next')!)
    expect(local.origin).toBe('https://educrea.edutictac.es')
    expect(local.pathname).toBe('/api/auth/oidc/login')
    expect(local.searchParams.get('next')).toBe(next)
    expect(localLoginUrl(next)).toBe(local.pathname + local.search)
  })
  it.each(['https://example.org', '//example.org', '/\\example.org', '/login', '/login?central=1', '/login/#hash', '/projects/../login', '/%6cogin', '/%2fexample.org', '/%5cexample.org', '/projects\nX', '/' + 'x'.repeat(301), undefined])('rejects unsafe or looping returns: %s', value => {
    expect(accountReturnPath(value)).toBe('/projects')
  })
  it('does not treat central students or local teacher sessions as OIDC teacher accounts', () => {
    expect(isCentralTeacher({ authenticated: true, kind: 'oidc', role: 'profesor' })).toBe(true)
    expect(isCentralTeacher({ authenticated: true, kind: 'oidc', role: 'administrador' })).toBe(true)
    expect(isCentralTeacher({ authenticated: true, kind: 'student', role: 'alumno' })).toBe(false)
    expect(isCentralTeacher({ authenticated: true, kind: 'teacher', role: 'profesor' })).toBe(false)
    expect(isCentralTeacher({ authenticated: false, kind: 'oidc', role: 'profesor' })).toBe(false)
  })
  it('keeps guest access usable if the central service fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect(await centralTeacherSession()).toBe(false)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    expect(await centralTeacherSession()).toBe(false)
  })
})


describe('automatic connection retries', () => {
  it('stops redirect loops across reloads and clears the guard after successful login', () => {
    const values = new Map<string, string>()
    const storage = { getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value) }, removeItem: (key: string) => { values.delete(key) } }
    expect(claimAccountConnection(storage, 1_000_000)).toBe(true)
    expect(claimAccountConnection(storage, 1_001_000)).toBe(false)
    expect(claimAccountConnection(storage, 1_301_000)).toBe(true)
    clearAccountConnection(storage)
    expect(claimAccountConnection(storage, 1_302_000)).toBe(true)
  })
  it('leaves explicit login available when session storage is blocked', () => {
    expect(claimAccountConnection({ getItem: () => { throw new Error('blocked') }, setItem: () => {} })).toBe(false)
  })
})
