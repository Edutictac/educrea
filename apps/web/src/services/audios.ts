import { apiError } from '../i18n/apiErrors'
export interface ProjectAudio {
  id: string; path: string; media_type: string; size: number
  description: string; transcript: string; credit: string
}
export const MAX_AUDIO_BYTES = 10 * 1024 * 1024
export const AUDIO_ACCEPT = '.mp3,.wav,.ogg,.opus,audio/mpeg,audio/wav,audio/ogg'

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: unknown }
    throw apiError(typeof data.detail === 'string' ? data.detail : `Error ${response.status}`)
  }
  return response
}
export const audioUrl = (projectId: string, audio: ProjectAudio) => `/api/projects/${projectId}/audios/${audio.id}/content`
export async function listAudios(projectId: string): Promise<ProjectAudio[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/audios`))).json() as ProjectAudio[]
}
function dataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}
export async function uploadAudio(projectId: string, file: File, description: string, transcript: string, credit: string, csrf: string): Promise<ProjectAudio> {
  const encoded = await dataUri(file)
  return await (await checked(await fetch(`/api/projects/${projectId}/audios`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ filename: file.name, description, transcript, credit, audio_base64: encoded.slice(encoded.indexOf(',') + 1) }),
  }))).json() as ProjectAudio
}
export async function updateAudio(projectId: string, audio: ProjectAudio, csrf: string): Promise<void> {
  await checked(await fetch(`/api/projects/${projectId}/audios/${audio.id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ description: audio.description, transcript: audio.transcript, credit: audio.credit }),
  }))
}
export async function deleteAudio(projectId: string, id: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/projects/${projectId}/audios/${id}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrf } }))
}
export async function audioResources(projectId: string, source?: string): Promise<Record<string, string>> {
  if (source !== undefined && !source.includes('audios/')) return {}
  const audios = (await listAudios(projectId)).filter(audio => source === undefined || source.includes(audio.path))
  return Object.fromEntries(await Promise.all(audios.map(async audio =>
    [audio.path, await dataUri(await (await checked(await fetch(audioUrl(projectId, audio)))).blob())] as const)))
}
export function embedAudio(html: string, audios: Record<string, string>): string {
  return html.replace(/((?:src\s*=\s*["']|"audio"\s*:\s*"))\s*(?:\.\/)?(audios\/[A-Za-z0-9._-]+)/g,
    (match, lead: string, path: string) => audios[path] ? lead + audios[path] : match)
}
