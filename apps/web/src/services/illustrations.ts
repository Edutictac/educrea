import { apiError } from '../i18n/apiErrors'
// AI illustrations, at creation or with «Ilustrar este recurso»: the free text AI writes the descriptions, then each
// image is estimated, paid and saved with the ordinary image endpoints, one after another (the quota allows one
// generation in progress per user). The teacher confirmed the maximum total once, in the form.
import { type Asset, uploadAsset } from './assets'
import { type AiStreamEvent, type Proposal, streamTeacherAction } from './ai'
import { estimateImage, generateImage } from './images'
import { temporaryKeyHeaders } from './temporaryKeys'

/** Same as the API's illustrations.MAX_ILLUSTRATIONS. */
export const MAX_ILLUSTRATIONS = 10
export type IllustrationStyle = 'plana' | 'acuarela' | 'realista' | 'colorear'
export interface IllustrationPrompt { alt: string; prompt: string }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

// Templates whose data has no image field; used only if the API predates the catalog's «illustrable» flag.
const WITHOUT_IMAGES = ['sopa_letras', 'crucigrama', 'escucha']
export const templateIllustrable = (template: { id: string; illustrable?: boolean }): boolean =>
  template.illustrable ?? !WITHOUT_IMAGES.includes(template.id)

/** The file that holds the resource's content (same rule as the API's illustrations.main_path). */
export function illustrationTarget(brief: { kind?: string; template?: string }): string | null {
  if (brief.kind === 'situacion') return 'situacion.md'
  if (brief.kind === 'ficha') return 'ficha.md'
  if (brief.template === 'infografia') return 'infografia.html'
  if (brief.template) return WITHOUT_IMAGES.includes(brief.template) ? null : 'datos.js'
  return null
}

export async function illustrationPrompts(projectId: string, count: number, style: IllustrationStyle,
  csrf: string, fromContent = false): Promise<IllustrationPrompt[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/illustrations/prompts`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ count, style, from_content: fromContent }),
  }))).json() as IllustrationPrompt[]
}

function toFile(base64: string, mediaType: string, index: number): File {
  const bytes = Uint8Array.from(atob(base64), char => char.charCodeAt(0))
  return new File([bytes], `ilustracion-${index}.${mediaType === 'image/png' ? 'png' : 'jpg'}`, { type: mediaType })
}

/** Generates and saves every illustration; returns how many were saved and the errors of the ones that failed. */
export async function createIllustrations(projectId: string, prompts: IllustrationPrompt[], model: string,
  csrf: string, onProgress: (index: number, total: number) => void, paid = true): Promise<{ saved: number; assets: Asset[]; errors: string[] }> {
  let saved = 0
  const assets: Asset[] = []
  const errors: string[] = []
  for (const [index, item] of prompts.entries()) {
    onProgress(index + 1, prompts.length)
    try {
      const estimate = await estimateImage(projectId, item.prompt, model, '1:1', csrf)
      const image = await generateImage(projectId, item.prompt, model, '1:1', estimate, csrf, paid)
      assets.push(await uploadAsset(projectId, toFile(image.image_base64, image.media_type, index + 1), item.alt,
        image.suggested_credit, csrf))
      saved += 1
    } catch (cause) {
      // One failed image must not stop the others nor the resource: it can be generated later from the panel.
      errors.push(cause instanceof Error ? cause.message : String(cause))
    }
  }
  return { saved, assets, errors }
}

/** Proposal (applied, with history and «Deshacer») that inserts the saved images into the resource. */
export async function placeIllustrations(projectId: string, paths: string[], choice: object, csrf: string,
  signal: AbortSignal, onEvent: (event: AiStreamEvent) => void): Promise<Proposal> {
  return await streamTeacherAction(projectId, 'illustrations/place', { ...choice, paths }, csrf, signal, onEvent)
}
