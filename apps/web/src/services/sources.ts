export interface Source { id: string; title: string; filename: string; kind: string; pages: number; chars: number;
  chunk_count: number; created_at: string; url: string | null; fetched_at: string | null }
export interface Passage { label: string; source: string; page: number | null; heading: string; text: string }
export interface Citation { quote: string; chunk: string; used_for: string; verified: boolean; source: string | null; page: number | null }
export interface Grounding { mode: 'sources_only' | 'template'; kind?: 'actividad' | 'situacion'; sources: string[];
  citations: Citation[]; verified: number; unverified: number; not_covered: string[]; sections_missing?: string[];
  supported: boolean }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function listSources(projectId: string): Promise<Source[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/sources`, { credentials: 'same-origin' }))).json() as Source[]
}

export async function uploadSource(projectId: string, file: File, title: string, csrf: string): Promise<Source> {
  const query = new URLSearchParams({ filename: file.name, title })
  return await (await checked(await fetch(`/api/projects/${projectId}/sources?${query}`, {
    method: 'POST', credentials: 'same-origin', body: file,
    headers: { 'Content-Type': 'application/octet-stream', 'X-CSRF-Token': csrf } }))).json() as Source
}

export async function addSourceFromUrl(projectId: string, url: string, title: string, csrf: string): Promise<Source> {
  return await (await checked(await fetch(`/api/projects/${projectId}/sources/url`, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ url, title }) }))).json() as Source
}

export async function refreshSource(projectId: string, sourceId: string, csrf: string): Promise<Source> {
  return await (await checked(await fetch(`/api/projects/${projectId}/sources/${sourceId}/refresh`, {
    method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrf } }))).json() as Source
}

export async function deleteSource(projectId: string, sourceId: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/projects/${projectId}/sources/${sourceId}`, {
    method: 'DELETE', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrf } }))
}

export async function searchSource(projectId: string, sourceId: string, query: string): Promise<Passage[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/sources/${sourceId}/search?q=${encodeURIComponent(query)}`,
    { credentials: 'same-origin' }))).json() as Passage[]
}
