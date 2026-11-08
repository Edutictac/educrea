import type { Locale } from './index'

// A display preference only: this cookie never represents identity or access.
export function normalizeAccountLocale(value: string | null): Locale | null {
  if (value === 'ca' || value === 'ca-ES-valencia') return 'va'
  return value === 'es' || value === 'va' || value === 'en' ? value : null
}
export function readSharedLanguage(doc: Pick<Document, 'cookie'>): Locale | null {
  try {
    const item = doc.cookie.split(';').map(part => part.trim()).find(part => part.startsWith('edutictac_language='))
    return normalizeAccountLocale(item?.slice('edutictac_language='.length) ?? null)
  } catch { return null }
}
export function rememberSharedLanguage(value: Locale, doc: Pick<Document, 'cookie'>, loc: Pick<Location, 'hostname' | 'protocol'>) {
  const shared = loc.hostname === 'edutictac.es' || loc.hostname.endsWith('.edutictac.es')
  try {
    doc.cookie = `edutictac_language=${value}; Path=/; Max-Age=31536000; SameSite=Lax`
      + (shared ? '; Domain=edutictac.es' : '') + (loc.protocol === 'https:' ? '; Secure' : '')
  } catch { /* Preference storage may be disabled. */ }
}
