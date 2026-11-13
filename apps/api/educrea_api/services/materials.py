"""Markdown teaching materials: safe rendering and export. Nothing here runs user code."""

import html
import io
import zipfile
from pathlib import Path

from markdown_it import MarkdownIt

ALLOWED_LINK_SCHEMES = ("http://", "https://", "mailto:", "#")
EXPORT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
EXPORT_STYLE = (
    "body{font-family:system-ui,sans-serif;line-height:1.6;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}"
    "table{border-collapse:collapse}th,td{border:1px solid #888;padding:.3rem .6rem}"
    "pre{background:#f3f3f3;padding:.8rem;overflow:auto}code{font-family:ui-monospace,monospace}"
    "blockquote{border-left:4px solid #bbb;margin-left:0;padding-left:1rem;color:#444}img{max-width:100%;height:auto}"
    ".credits{border-top:1px solid #bbb;margin-top:2rem;padding-top:.8rem;font-size:.9rem;color:#444}"
)


def _parser() -> MarkdownIt:
    # html=False: raw HTML in the source is escaped, never emitted. linkify off: no implicit links.
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")

    def image(self, tokens, idx, options, env):
        # Only images of the project library are shown, embedded as data: URIs. Anything else (remote URLs
        # included) becomes its alternative text, so nothing is ever fetched from another server.
        token = tokens[idx]
        src = (token.attrGet("src") or "").removeprefix("./")
        image = (env or {}).get("images", {}).get(src)
        alt = token.content or (image or {}).get("alt", "")
        if image is None:
            return html.escape(alt)
        return f'<img src="{image["uri"]}" alt="{html.escape(alt, quote=True)}">'

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


def render_markdown(source: str, assets: list | None = None) -> str:
    from .assets import data_uri

    images = {asset.path: {"uri": data_uri(asset), "alt": asset.alt} for asset in assets or []}
    return _MD.render(source, {"images": images})


def credits_html(assets: list | None = None) -> str:
    rows = [f"<li>{html.escape(asset.path)}: {html.escape(asset.alt)} — "
            f"{html.escape(asset.credit or 'sin crédito indicado')}</li>" for asset in assets or []]
    if not rows:
        return ""
    return '<footer class="credits"><h2>Créditos de las imágenes</h2><ul>' + "".join(rows) + "</ul></footer>"


def title_of(path: str, source: str) -> str:
    for line in source.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:160] or path
    return path


def export_html(path: str, source: str, lang: str = "es", assets: list | None = None) -> str:
    title = html.escape(title_of(path, source))
    return (f'<!doctype html>\n<html lang="{html.escape(lang)}">\n<head>\n<meta charset="utf-8">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{EXPORT_CSP}">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{title}</title>\n<style>{EXPORT_STYLE}</style>\n</head>\n<body>\n"
            f"<main>\n{render_markdown(source, assets)}</main>\n{credits_html(assets)}</body>\n</html>\n")


LUCIDE_LICENSE = Path(__file__).resolve().parent.parent / "data" / "lucide-LICENSE.txt"
LUCIDE_NOTICE_PATH = "LICENSES/lucide-LICENSE.txt"


def uses_lucide(files: list[tuple[str, str]]) -> bool:
    return any("lucide" in content.lower() for _, content in files)


def export_zip(files: list[tuple[str, str]], assets: list | None = None, audios: list | None = None) -> bytes:
    from .assets import credits_text

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files:
            archive.writestr(path, content.encode("utf-8"))
        for asset in assets or []:  # same relative paths as in the HTML/Markdown, so the ZIP works offline
            archive.writestr(asset.path, asset.data)
        if assets:
            archive.writestr("imagenes/CREDITOS.txt", credits_text(assets).encode("utf-8"))
        for audio in audios or []:
            archive.writestr(audio.path, audio.data)
        if audios:
            from .audios import credits_text as audio_credits
            archive.writestr("audios/CREDITOS.txt", audio_credits(audios).encode("utf-8"))
        # ISC/MIT require the notice to travel with copies of the icons.
        if uses_lucide(files) and LUCIDE_NOTICE_PATH not in {path for path, _ in files}:
            archive.writestr(LUCIDE_NOTICE_PATH, LUCIDE_LICENSE.read_bytes())
    return buffer.getvalue()
