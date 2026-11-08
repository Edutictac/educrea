import { apiError } from '../i18n/apiErrors'
// Starter infographic: plain HTML + inline SVG, editable by hand or with the AI assistant.
// Icons are the vendored Lucide set (inline SVG, license notice included). No external fonts, icons or scripts, so it previews and exports to PNG unchanged.
import { LUCIDE_NOTICE, iconSvg } from './icons'
import { locale, t, type Locale } from '../i18n'

export const INFOGRAPHIC_PATH = 'infografia.html'

export function infographicTemplate(title: string, language: Locale = locale.value): string {
  const tr = (key: Parameters<typeof t>[0]) => t(key, language)
  const safe = title.replace(/[<>&"]/g, '')
  return `<!doctype html>
<html lang="${language === 'va' ? 'ca' : language}">
<head>
${LUCIDE_NOTICE}
<meta charset="utf-8">
<title>${safe}</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #fff; color: #1a1a1a; }
  main { max-width: 1100px; margin: 0 auto; padding: 24px; }
  h1 { color: #126382; }
  .steps { display: flex; gap: 16px; flex-wrap: wrap; }
  .step { flex: 1 1 220px; border: 3px solid #126382; border-radius: 14px; padding: 16px; background: #eaf4f8; }
  .step svg { display: block; margin: 0 auto 8px; color: #126382; }
  .step h2 { font-size: 1.2rem; margin: 0 0 6px; }
  .ilustracion { display: block; width: 100%; max-width: 220px; height: auto; margin: .5rem auto; border-radius: 8px; }
  details { margin-top: 20px; }
</style>
</head>
<body>
<main>
  <h1>${safe}</h1>
  <div class="steps">
    <section class="step">
      ${iconSvg('lightbulb', tr('infographicIdeaAlt'), 64)}
      <h2>${tr('infographicStep1')}</h2><p>${tr('infographicText1')}</p>
    </section>
    <section class="step">
      ${iconSvg('music', tr('infographicExampleAlt'), 64)}
      <h2>${tr('infographicStep2')}</h2><p>${tr('infographicText2')}</p>
    </section>
    <section class="step">
      ${iconSvg('check', tr('infographicCheckAlt'), 64)}
      <h2>${tr('infographicStep3')}</h2><p>${tr('infographicText3')}</p>
    </section>
  </div>
  <details><summary>${tr('infographicMore')}</summary><p>${tr('infographicMoreText')}</p></details>
</main>
</body>
</html>
`
}

// Guided templates served by the API (phase 7).
export type TemplateGroup = 'quick' | 'games' | 'reading' | 'docs'
export interface TemplateInfo { id: string; kind: 'interactiva' | 'infografia' | 'ficha'; names: Record<'es' | 'va' | 'en', string>; descriptions: Record<'es' | 'va' | 'en', string>; group?: TemplateGroup; illustrable?: boolean }
export interface TemplateBrief { gap_mode?: 'bank' | 'text'; mix?: ('choice' | 'true_false' | 'gap')[]; title: string; language: 'es' | 'va' | 'en'; level: string; instructions: string; accessibility: { large_text: boolean; high_contrast: boolean } }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function listTemplates(): Promise<TemplateInfo[]> {
  return await (await checked(await fetch('/api/templates'))).json() as TemplateInfo[]
}

export async function applyTemplate(projectId: string, template: string, brief: TemplateBrief, csrf: string): Promise<void> {
  await checked(await fetch(`/api/projects/${projectId}/template`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ template, brief }),
  }))
}

export async function templateStatus(projectId: string): Promise<{ template: string | null; outdated: string[] }> {
  return await (await checked(await fetch(`/api/projects/${projectId}/template`))).json() as { template: string | null; outdated: string[] }
}

export async function updateTemplateEngine(projectId: string, csrf: string): Promise<{ updated: string[] }> {
  return await (await checked(await fetch(`/api/projects/${projectId}/template/update`, { method: 'POST', headers: { 'X-CSRF-Token': csrf } }))).json() as { updated: string[] }
}
