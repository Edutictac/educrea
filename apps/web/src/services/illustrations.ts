import { apiError } from '../i18n/apiErrors'
// Illustrations for a new resource: the free text AI writes the descriptions, then each image is estimated, paid and
// saved one by one with the ordinary image endpoints. The teacher confirmed the maximum total in the creation form.
import { uploadAsset } from './assets'
import { estimateImage, generateImage } from './images'
import { temporaryKeyHeaders } from './temporaryKeys'

export type IllustrationStyle = 'plana' | 'acuarela' | 'realista' | 'colorear'
export interface IllustrationPrompt { alt: string; prompt: string }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function illustrationPrompts(projectId: string, count: number, style: IllustrationStyle,
  csrf: string): Promise<IllustrationPrompt[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/illustrations/prompts`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ count, style }),
  }))).json() as IllustrationPrompt[]
}

function toFile(base64: string, mediaType: string, index: number): File {
  const bytes = Uint8Array.from(atob(base64), char => char.charCodeAt(0))
  return new File([bytes], `ilustracion-${index}.${mediaType === 'image/png' ? 'png' : 'jpg'}`, { type: mediaType })
}

/** Generates and saves every illustration; returns how many were saved and the errors of the ones that failed. */
export async function createIllustrations(projectId: string, prompts: IllustrationPrompt[], model: string,
  csrf: string, onProgress: (index: number, total: number) => void): Promise<{ saved: number; errors: string[] }> {
  let saved = 0
  const errors: string[] = []
  for (const [index, item] of prompts.entries()) {
    onProgress(index + 1, prompts.length)
    try {
      const estimate = await estimateImage(projectId, item.prompt, model, '1:1', csrf)
      const image = await generateImage(projectId, item.prompt, model, '1:1', estimate, csrf)
      await uploadAsset(projectId, toFile(image.image_base64, image.media_type, index + 1), item.alt,
        image.suggested_credit, csrf)
      saved += 1
    } catch (cause) {
      // One failed image must not stop the others nor the resource: it can be generated later from the panel.
      errors.push(cause instanceof Error ? cause.message : String(cause))
    }
  }
  return { saved, errors }
}
