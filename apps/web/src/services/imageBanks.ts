import { apiError } from '../i18n/apiErrors'
import type { Asset } from './assets'

// Free image banks searched server-side. The browser only talks to EduCrea; the API contacts the provider,
// validates the PNG and stores it in the project library with its attribution.
export interface BankItem {
  provider: 'arasaac'
  id: number
  title: string
  keywords: string[]
  thumbnail_url: string
  content_url: string
  license: string
  license_url: string
  source_url: string
  credit: string
  media_type: string
}

export interface BankSearch {
  provider: string
  license: string
  license_url: string
  commercial_use: boolean
  items: BankItem[]
}

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function searchImageBank(query: string, language: string, signal?: AbortSignal): Promise<BankSearch> {
  const params = new URLSearchParams({ q: query, language })
  return await (await checked(await fetch(`/api/image-banks/arasaac/search?${params}`, { signal }))).json() as BankSearch
}

export async function importBankItem(projectId: string, item: BankItem, alt: string, csrf: string): Promise<Asset> {
  return await (await checked(await fetch(`/api/projects/${projectId}/assets/from-bank`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ provider: item.provider, id: item.id, alt }),
  }))).json() as Asset
}
