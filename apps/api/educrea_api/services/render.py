"""Static PNG rendering of HTML/SVG infographics with headless Chromium inside bubblewrap.

The page is first reduced to a static document (no scripts, no event handlers, no external resources),
then rendered in a sandbox with no network, a read-only system and a private temp directory.
"""

import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from fastapi import HTTPException

from .assets import embed

from .converter import _sandbox

STATIC_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'"
MAX_PNG_BYTES = 10 * 1024 * 1024
TIMEOUT_SECONDS = 40
_slots = threading.BoundedSemaphore(2)


def _normalize(path: str) -> str:
    return path.strip().removeprefix("./").lstrip("/")


def static_document(entry: str, files: dict[str, str]) -> str:
    def stylesheet(match: re.Match) -> str:
        tag = match.group(0)
        if not re.search(r"rel\s*=\s*[\"']?stylesheet", tag, re.I):
            return ""
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", tag, re.I)
        css = files.get(_normalize(href.group(1))) if href else None
        return "" if css is None else "<style>" + re.sub(r"</style", r"<\\/style", css, flags=re.I) + "</style>"

    document = re.sub(r"<link\b[^>]*>", stylesheet, entry, flags=re.I)
    document = re.sub(r"<script\b.*?</script\s*>", "", document, flags=re.I | re.S)
    document = re.sub(r"<script\b[^>]*>", "", document, flags=re.I)
    document = re.sub(r"\s+on[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", document, flags=re.I)
    document = re.sub(r"<(iframe|object|embed|base|meta\s+http-equiv)\b[^>]*>", "", document, flags=re.I)
    meta = f'<meta http-equiv="Content-Security-Policy" content="{STATIC_CSP}">'
    head = re.search(r"<head[^>]*>", document, re.I)
    return document[:head.end()] + meta + document[head.end():] if head else meta + document


def render_png(entry: str, files: dict[str, str], width: int, height: int, assets: list | None = None) -> bytes:
    if not (1 <= width <= 2000 and 1 <= height <= 4000):
        raise HTTPException(422, "Dimensiones no válidas")
    browser = shutil.which("chromium") or shutil.which("chromium-browser")
    if not (browser and shutil.which("bwrap")):
        raise HTTPException(503, "La exportación a PNG no está disponible en este servidor")
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "Hay demasiados renderizados en curso. Inténtalo de nuevo en unos segundos")
    try:
        with tempfile.TemporaryDirectory(prefix="educrea-render-") as tmp:
            workdir = Path(tmp)
            (workdir / "page.html").write_text(embed(static_document(entry, files), assets or []), encoding="utf-8")
            command = ["chromium", "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                       "--disable-extensions", "--hide-scrollbars", "--force-device-scale-factor=1",
                       "--host-resolver-rules=MAP * ~NOTFOUND", f"--window-size={width},{height}",
                       "--screenshot=/work/out.png", "file:///work/page.html"]
            try:
                subprocess.run(_sandbox(workdir, command), capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(504, "El renderizado ha tardado demasiado") from exc
            output = workdir / "out.png"
            if not output.is_file():
                raise HTTPException(422, "No se ha podido renderizar la página")
            if output.stat().st_size > MAX_PNG_BYTES:
                raise HTTPException(413, "La imagen resultante es demasiado grande")
            return output.read_bytes()
    finally:
        _slots.release()
