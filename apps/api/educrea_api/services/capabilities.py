"""Typed capability registry. Built-in read-only project tools plus approved MCP tools.

Every invocation is checked for ownership, rate-limited, size-limited and audited (sizes and outcome only).
Capabilities that change files, publish or cost money must be explicitly approved by the teacher per call;
the model can request a capability but never executes one by itself.
"""

import json
import time
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CapabilityCall, ProjectFile
from ..models.entities import utcnow
from . import mcp

CALLS_PER_MINUTE = 30
MAX_RESULT_CHARS = 64 * 1024


class NoArgs(BaseModel):
    pass


class ReadFileArgs(BaseModel):
    path: str = Field(min_length=1, max_length=200)


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=100)
    max_results: int = Field(default=20, ge=1, le=50)


def _files(db: Session, project_id: UUID) -> list[ProjectFile]:
    return list(db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.path)))


def list_files(db: Session, project_id: UUID, _args: NoArgs) -> dict:
    return {"files": [{"path": f.path, "version": f.version, "bytes": len(f.content.encode())} for f in _files(db, project_id)]}


def read_file(db: Session, project_id: UUID, args: ReadFileArgs) -> dict:
    for file in _files(db, project_id):
        if file.path == args.path:
            return {"path": file.path, "version": file.version, "content": file.content[:MAX_RESULT_CHARS]}
    raise HTTPException(404, "Archivo no encontrado")


def search(db: Session, project_id: UUID, args: SearchArgs) -> dict:
    needle = args.query.lower()
    hits = []
    for file in _files(db, project_id):
        for number, line in enumerate(file.content.splitlines(), 1):
            if needle in line.lower():
                hits.append({"path": file.path, "line": number, "text": line[:200]})
                if len(hits) >= args.max_results:
                    return {"matches": hits}
    return {"matches": hits}


BUILTIN = {
    "project.list_files": ("Lista los archivos del proyecto.", NoArgs, list_files),
    "project.read_file": ("Lee un archivo del proyecto.", ReadFileArgs, read_file),
    "project.search": ("Busca texto en los archivos del proyecto.", SearchArgs, search),
}


def catalog(include_mcp: bool = True) -> list[dict]:
    items = [{"name": name, "description": description, "input_schema": model.model_json_schema(),
              "mutates": False, "source": "builtin"} for name, (description, model, _) in BUILTIN.items()]
    if include_mcp:
        for server in mcp.servers():
            try:
                items += [{**tool, "source": f"mcp:{server}"} for tool in mcp.list_tools(server)]
            except HTTPException:
                continue  # an unavailable server must not hide the rest
    return items


def _audit(db: Session, user_id: UUID, project_id: UUID, name: str, status: str, detail: str,
           input_bytes: int, output_bytes: int, started: float) -> None:
    db.add(CapabilityCall(user_id=user_id, project_id=project_id, capability=name[:160], status=status,
                          detail=detail[:200], input_bytes=input_bytes, output_bytes=output_bytes,
                          duration_ms=int((time.monotonic() - started) * 1000)))
    db.commit()


def invoke(db: Session, user_id: UUID, project_id: UUID, name: str, arguments: dict, approved: bool) -> dict:
    started = time.monotonic()
    input_bytes = len(json.dumps(arguments).encode())
    recent = db.scalar(select(func.count(CapabilityCall.id)).where(
        CapabilityCall.user_id == user_id, CapabilityCall.created_at >= utcnow() - timedelta(minutes=1)))
    if recent >= CALLS_PER_MINUTE:
        raise HTTPException(429, "Demasiadas llamadas a capacidades. Espera un minuto")
    try:
        if name in BUILTIN:
            _, model, run = BUILTIN[name]
            try:
                parsed = model.model_validate(arguments)
            except ValidationError as exc:
                raise HTTPException(422, "Argumentos no válidos") from exc
            result = run(db, project_id, parsed)
        elif name.startswith("mcp."):
            _, server, *rest = name.split(".", 2)
            tool = rest[0] if rest else ""
            config = mcp.servers().get(server)
            if config is None or tool not in config["tools"]:
                raise HTTPException(404, "Capacidad no encontrada")
            if config["tools"][tool].get("mutates", True) and not approved:
                _audit(db, user_id, project_id, name, "denied", "requires approval", input_bytes, 0, started)
                raise HTTPException(409, "Esta capacidad modifica contenido o genera gasto: requiere tu aprobación expresa")
            result = mcp.call_tool(server, tool, arguments)
        else:
            raise HTTPException(404, "Capacidad no encontrada")
    except HTTPException as exc:
        if exc.status_code != 409:
            _audit(db, user_id, project_id, name, "error", str(exc.detail), input_bytes, 0, started)
        raise
    output = json.dumps(result, ensure_ascii=False)
    _audit(db, user_id, project_id, name, "ok", "", input_bytes, len(output.encode()), started)
    return result
