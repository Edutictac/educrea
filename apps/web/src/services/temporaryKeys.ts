// Never reactive, serialized, persisted, or logged. The map dies when the page reloads.
import type { ProviderName } from './ai'
let owner: string | null = null
let guest = false
const keys = new Map<ProviderName, { key: string; confirmed: string[] }>()

export function setTemporaryIdentity(id: string | null, isGuest: boolean) {
  if (owner !== id || guest !== isGuest) keys.clear()
  owner = id; guest = isGuest
}
export const usesTemporaryKeys = () => guest
export function rememberTemporaryKey(provider: ProviderName, key: string) {
  const value = key.trim()
  if (!/^[\x21-\x7e]{10,512}$/.test(value)) throw new Error('Clave temporal no válida')
  keys.set(provider, { key: value, confirmed: [] })
}
export function forgetTemporaryKey(provider: ProviderName) { keys.delete(provider) }
export function confirmTemporaryModel(provider: ProviderName, model: string) {
  const item = keys.get(provider)
  if (!item) throw new Error('Introduce tu clave temporal antes de confirmar el modelo')
  if (!item.confirmed.includes(model)) item.confirmed.push(model)
}
export function temporaryKeyHeaders(): Record<string, string> {
  return guest && keys.size ? { 'X-Educrea-Temporary-Keys': JSON.stringify(Object.fromEntries(keys)) } : {}
}
