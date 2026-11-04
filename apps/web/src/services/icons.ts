// Vendored Lucide icons (ISC; MIT for Feather-derived ones). See docs/third-party-licenses.md.
// The SVG files are copied unmodified into third_party/lucide and bundled as raw text: nothing is fetched at runtime.
const modules = import.meta.glob('../../../../third_party/lucide/icons/*.svg', { query: '?raw', import: 'default', eager: true }) as Record<string, string>

export const LUCIDE_NOTICE = '<!-- Iconos: Lucide (ISC; MIT los derivados de Feather), https://lucide.dev. El texto de la licencia va en LICENSES/lucide-LICENSE.txt del ZIP exportado. -->'

const raw: Record<string, string> = {}
for (const [path, svg] of Object.entries(modules)) raw[path.split('/').pop()!.replace('.svg', '')] = svg

export const iconNames = Object.keys(raw).sort()

// Inline SVG without the per-file header comment; decorative unless a label is given.
export function iconSvg(name: string, label = '', size = 48): string {
  const source = raw[name]
  if (!source) throw new Error(`Unknown icon: ${name}`)
  const accessible = label
    ? `role="img" aria-label="${label.replace(/[<>&"]/g, '')}"`
    : 'aria-hidden="true"'
  return source.replace(/<!--[\s\S]*?-->\s*/g, '').trim()
    .replace(/\swidth="24"\s+height="24"/, ` width="${size}" height="${size}" ${accessible}`)
}

// Puts the icon inside <main>/<body> (or at the end) and adds the license notice once.
export function insertIcon(html: string, name: string, label: string): string {
  const svg = `  ${iconSvg(name, label)}\n`
  const withIcon = /<\/main>/i.test(html) ? html.replace(/<\/main>/i, `${svg}</main>`)
    : /<\/body>/i.test(html) ? html.replace(/<\/body>/i, `${svg}</body>`) : `${html}\n${svg}`
  if (withIcon.includes('lucide.dev')) return withIcon
  return /<head[^>]*>/i.test(withIcon) ? withIcon.replace(/<head[^>]*>/i, match => `${match}\n${LUCIDE_NOTICE}`) : `${LUCIDE_NOTICE}\n${withIcon}`
}
