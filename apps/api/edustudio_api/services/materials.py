"""Markdown teaching materials: safe rendering and export. Nothing here runs user code."""

import html
import io
import zipfile

from markdown_it import MarkdownIt

ALLOWED_LINK_SCHEMES = ("http://", "https://", "mailto:", "#")
EXPORT_CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
EXPORT_STYLE = (
    "body{font-family:system-ui,sans-serif;line-height:1.6;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}"
    "table{border-collapse:collapse}th,td{border:1px solid #888;padding:.3rem .6rem}"
    "pre{background:#f3f3f3;padding:.8rem;overflow:auto}code{font-family:ui-monospace,monospace}"
    "blockquote{border-left:4px solid #bbb;margin-left:0;padding-left:1rem;color:#444}"
)


def _parser() -> MarkdownIt:
    # html=False: raw HTML in the source is escaped, never emitted. linkify off: no implicit links.
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")

    def image(self, tokens, idx, options, env):
        # No images yet: show the alternative text so nothing is fetched from remote servers.
        return html.escape(tokens[idx].content)

    def link_open(self, tokens, idx, options, env):
        token = tokens[idx]
        href = token.attrGet("href") or ""
        if not href.lower().startswith(ALLOWED_LINK_SCHEMES):
            token.attrSet("href", "#")
        token.attrSet("rel", "noopener noreferrer nofollow")
        return self.renderToken(tokens, idx, options, env)

    md.add_render_rule("image", image)
    md.add_render_rule("link_open", link_open)
    return md


_MD = _parser()


def render_markdown(source: str) -> str:
    return _MD.render(source)


def title_of(path: str, source: str) -> str:
    for line in source.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:160] or path
    return path


def export_html(path: str, source: str, lang: str = "es") -> str:
    title = html.escape(title_of(path, source))
    return (f'<!doctype html>\n<html lang="{html.escape(lang)}">\n<head>\n<meta charset="utf-8">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{EXPORT_CSP}">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{title}</title>\n<style>{EXPORT_STYLE}</style>\n</head>\n<body>\n"
            f"<main>\n{render_markdown(source)}</main>\n</body>\n</html>\n")


def export_zip(files: list[tuple[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files:
            archive.writestr(path, content.encode("utf-8"))
    return buffer.getvalue()
