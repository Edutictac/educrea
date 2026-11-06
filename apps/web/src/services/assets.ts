// Image library of a project (PNG/JPEG uploaded by the teacher). Activities and documents reference images with a
// relative path such as imagenes/trompeta.png; the preview embeds them as data: URIs, so nothing is fetched.
export interface Asset { id: string; path: string; media_type: string; size: number; alt: string; credit: string }

export const MAX_IMAGE_BYTES = 2 * 1024 * 1024
const REFERENCE = /((?:src\s*=\s*["']|url\(\s*["']?|\]\())\s*(?:\.\/)?(imagenes\/[A-Za-z0-9._-]+)/g

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export const assetUrl = (projectId: string, asset: Asset) => `/api/projects/${projectId}/assets/${asset.id}/content`

export async function listAssets(projectId: string): Promise<Asset[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/assets`))).json() as Asset[]
}

export async function uploadAsset(projectId: string, file: File, alt: string, credit: string, csrf: string): Promise<Asset> {
  const params = new URLSearchParams({ filename: file.name, alt, credit })
  return await (await checked(await fetch(`/api/projects/${projectId}/assets?${params}`, {
    method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-CSRF-Token': csrf }, body: file,
  }))).json() as Asset
}

export async function updateAsset(projectId: string, id: string, alt: string, credit: string, csrf: string): Promise<Asset> {
  return await (await checked(await fetch(`/api/projects/${projectId}/assets/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ alt, credit }),
  }))).json() as Asset
}

export async function deleteAsset(projectId: string, id: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/projects/${projectId}/assets/${id}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrf } }))
}

function toDataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

// path -> data: URI, for the isolated preview.
export async function assetImages(projectId: string): Promise<Record<string, string>> {
  const assets = await listAssets(projectId)
  const entries = await Promise.all(assets.map(async asset =>
    [asset.path, await toDataUri(await (await checked(await fetch(assetUrl(projectId, asset)))).blob())] as const))
  return Object.fromEntries(entries)
}

export function embedImages(html: string, images: Record<string, string>): string {
  return html.replace(REFERENCE, (match, lead: string, path: string) => images[path] ? lead + images[path] : match)
}

export const htmlSnippet = (asset: Asset) => `<img src="${asset.path}" alt="${asset.alt.replace(/"/g, '&quot;')}">`
export const markdownSnippet = (asset: Asset) => `![${asset.alt.replace(/[[\]]/g, '')}](${asset.path})`
