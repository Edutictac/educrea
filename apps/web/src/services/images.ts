import { apiError } from '../i18n/apiErrors'
// BYOK image generation with Gemini Nano Banana. The image is returned for review and is only saved to the
// project when the teacher accepts the preview through the normal asset library.
import { temporaryKeyHeaders } from './temporaryKeys'
import type { BudgetStatus } from './ai'

export interface ImageModel {
  provider: string
  model: string
  sizes: string[]
  prices: Record<string, number>
  input_microusd_per_million: number
  max_cost_microusd: number  // upper bound for any accepted prompt
}

export interface ImageModels {
  configured: boolean
  default: string | null
  models: ImageModel[]
  budget: BudgetStatus
}

export interface ImageEstimate {
  provider: string
  model: string
  size: string
  aspect_ratio: string
  max_input_tokens: number
  maximum_cost_microusd: number
  image_microusd: number
  input_microusd: number
  fingerprint: string
}

export interface GeneratedImage {
  provider: string
  model: string
  size: string
  aspect_ratio: string
  media_type: string
  image_base64: string
  size_bytes: number
  cost_microusd: number
  fingerprint: string
  suggested_credit: string
  suggested_filename: string
}

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function imageModels(): Promise<ImageModels> {
  return await (await checked(await fetch('/api/ai/images/models', { headers: temporaryKeyHeaders() })))
    .json() as ImageModels
}

export async function estimateImage(projectId: string, prompt: string, model: string,
  aspectRatio: string, csrf: string): Promise<ImageEstimate> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/images/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ prompt, model, aspect_ratio: aspectRatio }),
  }))).json() as ImageEstimate
}

export async function generateImage(projectId: string, prompt: string, model: string, aspectRatio: string,
  estimate: ImageEstimate, csrf: string): Promise<GeneratedImage> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/images`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({
      prompt, model, aspect_ratio: aspectRatio,
      paid_authorized: true,
      approved_max_cost_microusd: estimate.maximum_cost_microusd,
      approved_estimate_fingerprint: estimate.fingerprint,
      rights_acknowledged: true,
      no_personal_data: true,
    }),
  }))).json() as GeneratedImage
}
