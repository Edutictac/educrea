// Starter infographic: plain HTML + inline SVG, editable by hand or with the AI assistant.
// Icons are the vendored Lucide set (inline SVG, license notice included). No external fonts, icons or scripts, so it previews and exports to PNG unchanged.
import { LUCIDE_NOTICE, iconSvg } from './icons'

export const INFOGRAPHIC_PATH = 'infografia.html'

export function infographicTemplate(title: string): string {
  const safe = title.replace(/[<>&"]/g, '')
  return `<!doctype html>
<html lang="es">
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
  details { margin-top: 20px; }
</style>
</head>
<body>
<main>
  <h1>${safe}</h1>
  <div class="steps">
    <section class="step">
      ${iconSvg('lightbulb', 'Bombilla: una idea', 64)}
      <h2>Primer paso</h2><p>Explica la idea principal con una frase corta.</p>
    </section>
    <section class="step">
      ${iconSvg('music', 'Nota musical: un ejemplo', 64)}
      <h2>Segundo paso</h2><p>Añade un ejemplo que el alumnado reconozca.</p>
    </section>
    <section class="step">
      ${iconSvg('check', 'Marca de verificación: lo que hay que recordar', 64)}
      <h2>Tercer paso</h2><p>Cierra con lo que se debe recordar.</p>
    </section>
  </div>
  <details><summary>Más información</summary><p>Contenido que se revela al pulsar.</p></details>
</main>
</body>
</html>
`
}
