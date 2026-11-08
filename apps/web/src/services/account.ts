import { watch } from 'vue'
import { locale } from '../i18n'
import { normalizeAccountLocale, readSharedLanguage } from '../i18n/preference'

export const ACCOUNT_BASE = 'https://commons.edutictac.es'
export interface LanguageAdapter { languages: string[]; get: () => string; set: (value: string) => void }
declare global { interface Window { edutictacLanguage?: LanguageAdapter } }

export const accountLocale = normalizeAccountLocale

// Register before the web component mounts: it discovers the host adapter once.
export function installAccountLanguage(host: Window = window): () => void {
  const previous = host.edutictacLanguage
  const adapter: LanguageAdapter = {
    languages: ['ca', 'va', 'es', 'en'], get: () => locale.value,
    set(value) { const next = accountLocale(value); if (next) locale.value = next },
  }
  host.edutictacLanguage = adapter
  const stop = watch(locale, value => {
    host.dispatchEvent(new CustomEvent('edutictac:langchange', { detail: { lang: value } }))
  }, { flush: 'sync' })
  function syncSharedLanguage() {
    if (host.document?.visibilityState !== 'visible') return
    const shared = readSharedLanguage(host.document)
    if (shared) locale.value = shared
  }
  host.document?.addEventListener('visibilitychange', syncSharedLanguage)
  return () => {
    stop(); host.document?.removeEventListener('visibilitychange', syncSharedLanguage)
    if (host.edutictacLanguage === adapter) host.edutictacLanguage = previous
  }
}

// Match the API's relative return-path limit. Never send external redirects to either SSO.
export function accountReturnPath(value: unknown): string {
  if (typeof value !== 'string' || value.length > 300 || !value.startsWith('/')
    || value.startsWith('//') || /[\\\r\n\t]/.test(value)) return '/projects'
  // Returning to the login screen would immediately start the flow again.
  try {
    const parsed = new URL(value, 'https://educrea.example')
    const path = decodeURIComponent(parsed.pathname)
    if (parsed.origin !== 'https://educrea.example' || path.startsWith('//') || /[\\\r\n\t]/.test(path)
      || path.replace(/\/$/, '') === '/login') return '/projects'
  } catch { return '/projects' }
  return value
}

export function localLoginUrl(next: unknown): string {
  return `/api/auth/oidc/login?next=${encodeURIComponent(accountReturnPath(next))}`
}

// First create the central session, then the application's OIDC session. The second exchange
// reuses the identity-provider login. Commons must allow the application's public origin.
export function centralLoginUrl(origin: string, next: unknown): string {
  const callback = new URL(localLoginUrl(next), origin)
  const login = new URL('/api/auth/oidc/login', ACCOUNT_BASE)
  login.searchParams.set('next', callback.href)
  return login.href
}

export interface CentralSession { authenticated: boolean; kind?: string; role?: string | null }
export const isCentralTeacher = (value: CentralSession): boolean => value.authenticated === true
  && value.kind === 'oidc' && (value.role === 'profesor' || value.role === 'administrador')

export async function centralTeacherSession(): Promise<boolean> {
  try {
    const response = await fetch(`${ACCOUNT_BASE}/api/auth/session`, {
      credentials: 'include', cache: 'no-store', headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(2500),
    })
    return response.ok && isCentralTeacher(await response.json() as CentralSession)
  } catch { return false }
}

const CONNECT_ATTEMPT = 'educrea.accountConnectAttempt'
// Do not repeat automatic redirects after a rejected callback or disabled browser storage.
// Explicit use of the account menu always remains available.
export function claimAccountConnection(storage?: Pick<Storage, 'getItem' | 'setItem'>, now = Date.now()): boolean {
  try {
    const target = storage ?? window.sessionStorage
    const previous = Number(target.getItem(CONNECT_ATTEMPT))
    if (previous > 0 && now >= previous && now - previous < 5 * 60_000) return false
    target.setItem(CONNECT_ATTEMPT, String(now))
    return true
  } catch { return false }
}
export function clearAccountConnection(storage?: Pick<Storage, 'removeItem'>) {
  try { (storage ?? window.sessionStorage).removeItem(CONNECT_ATTEMPT) } catch { /* Explicit login still works. */ }
}
