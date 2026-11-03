// Starter infographic: plain HTML + inline SVG, editable by hand or with the AI assistant.
// No external fonts, icons or scripts, so it previews and exports to PNG unchanged.
export const INFOGRAPHIC_PATH = 'infografia.html'

export function infographicTemplate(title: string): string {
  const safe = title.replace(/[<>&"]/g, '')
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>${safe}</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #fff; color: #1a1a1a; }
  main { max-width: 1100px; margin: 0 auto; padding: 24px; }
  h1 { color: #126382; }
  .steps { display: flex; gap: 16px; flex-wrap: wrap; }
  .step { flex: 1 1 220px; border: 3px solid #126382; border-radius: 14px; padding: 16px; background: #eaf4f8; }
  .step svg { display: block; margin: 0 auto 8px; }
  .step h2 { font-size: 1.2rem; margin: 0 0 6px; }
  details { margin-top: 20px; }
</style>
</head>
<body>
<main>
  <h1>${safe}</h1>
  <div class="steps">
    <section class="step">
      <svg role="img" aria-labelledby="t1" width="80" height="80" viewBox="0 0 80 80"><title id="t1">Círculo con el número 1</title>
        <circle cx="40" cy="40" r="34" fill="#126382"/><text x="40" y="52" font-size="36" text-anchor="middle" fill="#fff">1</text></svg>
      <h2>Primer paso</h2><p>Explica la idea principal con una frase corta.</p>
    </section>
    <section class="step">
      <svg role="img" aria-labelledby="t2" width="80" height="80" viewBox="0 0 80 80"><title id="t2">Cuadrado con el número 2</title>
        <rect x="6" y="6" width="68" height="68" rx="12" fill="#bd8b24"/><text x="40" y="52" font-size="36" text-anchor="middle" fill="#fff">2</text></svg>
      <h2>Segundo paso</h2><p>Añade un ejemplo que el alumnado reconozca.</p>
    </section>
    <section class="step">
      <svg role="img" aria-labelledby="t3" width="80" height="80" viewBox="0 0 80 80"><title id="t3">Triángulo con el número 3</title>
        <polygon points="40,6 76,72 4,72" fill="#2f855a"/><text x="40" y="62" font-size="32" text-anchor="middle" fill="#fff">3</text></svg>
      <h2>Tercer paso</h2><p>Cierra con lo que se debe recordar.</p>
    </section>
  </div>
  <details><summary>Más información</summary><p>Contenido que se revela al pulsar.</p></details>
</main>
</body>
</html>
`
}
