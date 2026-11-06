"""SCORM 1.2 package of a project activity, for Aules (Moodle) and other LMS.

The package is the same offline activity as the ZIP export plus scorm.js (bridge to the LMS API) and
imsmanifest.xml. Interactive templates report their score (best of the session, 0-100) and completion through
EDU.report/EDU.complete in comun.js; other HTML activities are marked as completed when opened.
"""

import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from fastapi import HTTPException

from .assets import credits_text
from .materials import LUCIDE_LICENSE, LUCIDE_NOTICE_PATH, uses_lucide

SCORM_JS = Path(__file__).resolve().parent.parent / "data" / "templates" / "scorm.js"
BRIDGE = "scorm.js"
ENTRY = "index.html"


def manifest(identifier: str, title: str, paths: list[str]) -> str:
    files = "\n".join(f"      <file href={quoteattr(path)}/>" for path in sorted(paths))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier={quoteattr(identifier)} version="1.0"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="org">
    <organization identifier="org">
      <title>{escape(title)}</title>
      <item identifier="item" identifierref="activity" isvisible="true">
        <title>{escape(title)}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="activity" type="webcontent" adlcp:scormtype="sco" href="{ENTRY}">
{files}
    </resource>
  </resources>
</manifest>
"""


def with_bridge(html: str, scored: bool) -> str:
    """Loads scorm.js in <head>; activities without a score are marked as completed when opened."""
    tag = f'<script src="{BRIDGE}"></script>'
    if not scored:
        tag += "<script>window.addEventListener('load', function () { if (window.EduScorm) window.EduScorm.complete() })</script>"
    if re.search(r"</head\s*>", html, re.I):
        return re.sub(r"</head\s*>", tag + "\n</head>", html, count=1, flags=re.I)
    return tag + "\n" + html


def package(slug: str, title: str, files: list[tuple[str, str]], assets: list, scored: bool) -> bytes:
    contents = dict(files)
    if ENTRY not in contents:
        raise HTTPException(409, "El paquete SCORM necesita una actividad con index.html")
    if BRIDGE in contents:
        raise HTTPException(409, "El proyecto ya tiene un archivo scorm.js; cámbiale el nombre para exportar")
    contents[ENTRY] = with_bridge(contents[ENTRY], scored)
    contents.pop("activity.json", None)  # the teacher's brief is not part of the student activity
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        paths: list[str] = []
        for path, content in contents.items():
            archive.writestr(path, content.encode("utf-8"))
            paths.append(path)
        archive.writestr(BRIDGE, SCORM_JS.read_bytes())
        paths.append(BRIDGE)
        for asset in assets:
            archive.writestr(asset.path, asset.data)
            paths.append(asset.path)
        if assets:
            archive.writestr("imagenes/CREDITOS.txt", credits_text(assets).encode("utf-8"))
            paths.append("imagenes/CREDITOS.txt")
        if uses_lucide(files):
            archive.writestr(LUCIDE_NOTICE_PATH, LUCIDE_LICENSE.read_bytes())
            paths.append(LUCIDE_NOTICE_PATH)
        archive.writestr("imsmanifest.xml", manifest(f"edustudio-{slug}", title, paths))
    return buffer.getvalue()
