// Builds a self-contained document for the isolated activity preview.
// It is shown in an iframe with sandbox="allow-scripts" (no allow-same-origin): the code runs in an
// opaque origin without cookies, storage or API access, and the CSP blocks every network request.
export const PREVIEW_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'"

function normalize(path: string): string {
  return path.replace(/^\.\//, '').replace(/^\/+/, '')
}

export function buildPreview(entry: string, files: Record<string, string>): string {
  const inlineStyles = (html: string) => html.replace(/<link\b[^>]*>/gi, tag => {
    if (!/rel\s*=\s*["']?stylesheet/i.test(tag)) return ''
    const href = /href\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1]
    const css = href ? files[normalize(href)] : undefined
    return css === undefined ? '' : `<style>${css.replace(/<\/style/gi, '<\\/style')}</style>`
  })
  const inlineScripts = (html: string) => html.replace(/<script\b([^>]*)>\s*<\/script>/gi, (tag, attrs: string) => {
    const src = /src\s*=\s*["']([^"']+)["']/i.exec(attrs)?.[1]
    if (!src) return tag
    const js = files[normalize(src)]
    return js === undefined ? '' : `<script>${js.replace(/<\/script/gi, '<\\/script')}</script>`
  })
  const document = inlineScripts(inlineStyles(entry))
  const meta = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}">`
  return /<head[^>]*>/i.test(document) ? document.replace(/<head[^>]*>/i, match => `${match}${meta}`) : `${meta}${document}`
}
