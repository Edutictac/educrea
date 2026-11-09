import { apiError } from '../i18n/apiErrors'
// BYOK short-video generation with Gemini Omni Flash. The clip is previewed before it is saved to the
// project video library; unlike images it is not embedded into PDF/DOCX exports.
import { temporaryKeyHeaders } from './temporaryKeys'
import { notifyAiUsage, type BudgetStatus } from './ai'

export interface VideoModel {
  provider: string
  model: string
  resolutions: Record<string, { second_microusd: number }>
  durations: number[]
  input_microusd_per_million: number
}

export interface VideoModels {
  configured: boolean
  default: string | null
  default_resolution: string | null
  models: VideoModel[]
  budget: BudgetStatus
  quota?: VideoQuota
}

export interface VideoQuota { daily_limit: number; used: number; remaining: number;
  available_remaining: number; renews_at: string; enabled: boolean }

export interface VideoEstimate {
  provider: string
  model: string
  resolution: string
  duration: number
  aspect_ratio: string
  max_input_tokens: number
  maximum_cost_microusd: number
  second_microusd: number
  input_microusd: number
  fingerprint: string
}

export interface GeneratedVideo {
  provider: string
  model: string
  resolution: string
  duration: number
  aspect_ratio: string
  media_type: string
  video_base64: string
  size_bytes: number
  cost_microusd: number
  fingerprint: string
  suggested_credit: string
  suggested_filename: string
}

export interface ProjectVideo {
  id: string
  path: string
  media_type: string
  size: number
  description: string
  credit: string
  duration_seconds: number
  resolution: string
}

export const MAX_VIDEO_BYTES = 30 * 1024 * 1024

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function videoModels(): Promise<VideoModels> {
  return await (await checked(await fetch('/api/ai/videos/models', { headers: temporaryKeyHeaders() })))
    .json() as VideoModels
}

export async function estimateVideo(projectId: string, prompt: string, model: string, resolution: string,
  duration: number, aspectRatio: string, csrf: string): Promise<VideoEstimate> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/videos/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ prompt, model, resolution, duration, aspect_ratio: aspectRatio }),
  }))).json() as VideoEstimate
}

export async function generateVideo(projectId: string, prompt: string, model: string, resolution: string,
  duration: number, aspectRatio: string, estimate: VideoEstimate, csrf: string): Promise<GeneratedVideo> {
  try {
    return await (await checked(await fetch(`/api/projects/${projectId}/ai/videos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
      body: JSON.stringify({
        prompt, model, resolution, duration, aspect_ratio: aspectRatio,
        paid_authorized: true,
        approved_max_cost_microusd: estimate.maximum_cost_microusd,
        approved_estimate_fingerprint: estimate.fingerprint,
        rights_acknowledged: true,
        no_personal_data: true,
      }),
    }))).json() as GeneratedVideo
  } finally { notifyAiUsage() }
}

export async function listVideos(projectId: string): Promise<ProjectVideo[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/videos`))).json() as ProjectVideo[]
}

export const videoUrl = (projectId: string, video: ProjectVideo) =>
  `/api/projects/${projectId}/videos/${video.id}/content`

export async function uploadVideo(projectId: string, blob: Blob, filename: string, description: string,
  credit: string, duration: number, resolution: string, csrf: string): Promise<ProjectVideo> {
  const params = new URLSearchParams({ filename, description, credit, duration: String(duration), resolution })
  return await (await checked(await fetch(`/api/projects/${projectId}/videos?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream', 'X-CSRF-Token': csrf },
    body: blob,
  }))).json() as ProjectVideo
}

export async function deleteVideo(projectId: string, id: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/projects/${projectId}/videos/${id}`, {
    method: 'DELETE', headers: { 'X-CSRF-Token': csrf } }))
}
