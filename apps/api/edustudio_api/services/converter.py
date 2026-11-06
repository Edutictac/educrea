"""Pandoc conversion of Markdown to DOCX/PDF inside a bubblewrap sandbox.

The worker sees only a private temp directory: no network, read-only system, no secrets,
no database. Raw HTML/TeX in the source is disabled. Time, size and concurrency are capped.
"""

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from fastapi import HTTPException

FORMATS = {
    "docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "pdf": ("pdf", "application/pdf"),
}
TIMEOUTS = {"docx": 30, "pdf": 90}
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
READER = "commonmark+pipe_tables-raw_html"
LUA_FILTER = """
local function safe(target)
  local t = target:lower()
  return t:match('^https?://') or t:match('^mailto:') or t:sub(1, 1) == '#'
end
function Link(el) if not safe(el.target) then return el.content end end
local allowed = {ALLOWED_IMAGES}
function Image(el)
  local src = el.src:gsub('^%./', '')
  if allowed[src] then el.src = src return el end
  return el.caption
end
"""
_slots = threading.BoundedSemaphore(2)


def _sandbox(workdir: Path, command: list[str], extra_ro: tuple[str, ...] = ()) -> list[str]:
    extra = [part for path in extra_ro for part in ("--ro-bind", path, path)]
    return ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc", "--ro-bind", "/var/lib", "/var/lib",
            "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", *extra, "--bind", str(workdir), "/work",
            "--chdir", "/work", "--clearenv", "--setenv", "HOME", "/tmp", "--setenv", "PATH", "/usr/bin", *command]


def lua_filter(image_paths: list[str]) -> str:
    # Asset paths only contain [a-z0-9._/-] (see services/assets.py), so they are safe inside a Lua string.
    table = ", ".join(f'["{path}"] = true' for path in image_paths if all(c.isalnum() or c in "._/-" for c in path))
    return LUA_FILTER.replace("{ALLOWED_IMAGES}", "{" + table + "}")


def convert(source: str, title: str, fmt: str, assets: list | None = None) -> bytes:
    if fmt not in FORMATS:
        raise HTTPException(422, "Formato no admitido")
    if not (shutil.which("pandoc") and shutil.which("bwrap")):
        raise HTTPException(503, "El conversor no está disponible en este servidor")
    if fmt == "pdf" and not shutil.which("xelatex"):
        raise HTTPException(503, "La exportación a PDF no está disponible en este servidor")
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "Hay demasiadas conversiones en curso. Inténtalo de nuevo en unos segundos")
    try:
        with tempfile.TemporaryDirectory(prefix="edustudio-convert-") as tmp:
            workdir = Path(tmp)
            (workdir / "input.md").write_text(source, encoding="utf-8")
            (workdir / "filter.lua").write_text(lua_filter([asset.path for asset in assets or []]), encoding="utf-8")
            for asset in assets or []:  # only library images are copied; pandoc reads nothing else
                target = workdir / asset.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(asset.data)
            args = ["pandoc", "-f", READER, "--lua-filter=filter.lua", "--metadata", f"title={title}", "-o", f"output.{fmt}"]
            if fmt == "pdf":
                args += ["--pdf-engine=xelatex", "-V", "mainfont=DejaVu Serif", "-V", "geometry:margin=2.5cm"]
            try:
                done = subprocess.run(_sandbox(workdir, [*args, "input.md"]), capture_output=True,
                                      timeout=TIMEOUTS[fmt], check=False)
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(504, "La conversión ha tardado demasiado") from exc
            output = workdir / f"output.{fmt}"
            if done.returncode != 0 or not output.is_file():
                raise HTTPException(422, "No se ha podido convertir el documento; revisa el Markdown")
            if output.stat().st_size > MAX_OUTPUT_BYTES:
                raise HTTPException(413, "El resultado es demasiado grande")
            return output.read_bytes()
    finally:
        _slots.release()
