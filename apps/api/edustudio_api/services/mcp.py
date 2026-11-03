"""Minimal MCP (stdio, JSON-RPC 2.0) client that only talks to administrator-approved servers.

Each exchange spawns the server inside bubblewrap (no network, read-only system, private /tmp, only the
paths the administrator lists), sends initialize + one request, closes stdin and reads the answer with hard
limits on time and output. The model never reaches the server: the backend mediates every call, validates
arguments against the tool's JSON Schema, and treats the reply as untrusted data.

EDUSTUDIO_MCP_SERVERS_JSON example:
{"notes": {"command": ["python3", "/opt/mcp/notes.py"], "ro_paths": ["/opt/mcp"], "timeout": 10,
           "tools": {"solfege": {"mutates": false}}}}
"""

import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from fastapi import HTTPException
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ..config import get_settings
from .converter import _sandbox

PROTOCOL_VERSION = "2025-03-26"
MAX_STDOUT_BYTES = 1024 * 1024
MAX_ARGUMENT_BYTES = 16 * 1024
MAX_RESULT_CHARS = 64 * 1024
_slots = threading.BoundedSemaphore(2)


def servers() -> dict[str, dict]:
    try:
        value = json.loads(get_settings().mcp_servers_json or "{}")
    except ValueError:
        return {}
    if not isinstance(value, dict):
        return {}
    valid = {}
    for name, config in value.items():
        if (isinstance(name, str) and name.replace("_", "").replace("-", "").isalnum() and isinstance(config, dict)
                and isinstance(config.get("command"), list) and config["command"]
                and all(isinstance(part, str) for part in config["command"])
                and isinstance(config.get("tools"), dict) and config["tools"]):
            valid[name] = config
    return valid


def _exchange(config: dict, requests: list[dict]) -> dict[int, dict]:
    """Run one short session and return the responses by request id."""
    timeout = min(max(int(config.get("timeout", 10)), 1), 60)
    messages = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "edustudio", "version": "0.1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        *requests,
    ]
    payload = "".join(json.dumps(message) + "\n" for message in messages).encode()
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "Hay demasiadas llamadas MCP en curso")
    try:
        with tempfile.TemporaryDirectory(prefix="edustudio-mcp-") as tmp:
            command = _sandbox(Path(tmp), config["command"], tuple(config.get("ro_paths", [])))
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
            chunks: list[bytes] = []
            size = 0

            def reader() -> None:
                nonlocal size
                for line in iter(process.stdout.readline, b""):  # type: ignore[union-attr]
                    size += len(line)
                    if size > MAX_STDOUT_BYTES:
                        process.kill()
                        return
                    chunks.append(line)

            thread = threading.Thread(target=reader, daemon=True)
            thread.start()
            try:
                process.stdin.write(payload)  # type: ignore[union-attr]
                process.stdin.close()  # type: ignore[union-attr]
            except OSError:
                pass
            deadline = time.monotonic() + timeout
            wanted = {request["id"] for request in requests}
            while time.monotonic() < deadline and thread.is_alive():
                time.sleep(0.02)
                if wanted <= {r.get("id") for r in _parse(chunks)}:
                    break
            process.kill()
            process.wait()
            thread.join(1)
            if size > MAX_STDOUT_BYTES:
                raise HTTPException(502, "El servidor MCP devolvió demasiados datos")
            responses = {r["id"]: r for r in _parse(chunks) if isinstance(r.get("id"), int)}
            if not wanted <= set(responses):
                raise HTTPException(504, "El servidor MCP no respondió a tiempo")
            return responses
    finally:
        _slots.release()


def _parse(chunks: list[bytes]) -> list[dict]:
    out = []
    for line in list(chunks):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def list_tools(server: str) -> list[dict]:
    """Tools of an approved server, limited to the administrator's allowlist."""
    config = servers().get(server)
    if config is None:
        raise HTTPException(404, "Servidor MCP no aprobado")
    response = _exchange(config, [{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}])[1]
    allowed = config["tools"]
    tools = []
    for tool in (response.get("result") or {}).get("tools", []):
        name = tool.get("name")
        if name in allowed:
            tools.append({"name": f"mcp.{server}.{name}", "description": str(tool.get("description", ""))[:500],
                          "input_schema": tool.get("inputSchema") or {"type": "object"},
                          "mutates": bool(allowed[name].get("mutates", True))})
    return tools


def call_tool(server: str, tool: str, arguments: dict) -> dict:
    config = servers().get(server)
    if config is None or tool not in config["tools"]:
        raise HTTPException(404, "Herramienta MCP no aprobada")
    if len(json.dumps(arguments).encode()) > MAX_ARGUMENT_BYTES:
        raise HTTPException(413, "Argumentos demasiado grandes")
    # Validate against the tool's schema BEFORE anything is executed (separate session).
    listing = _exchange(config, [{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}])
    schema = next(({"type": "object"} | (t.get("inputSchema") or {}) for t in
                   (listing[1].get("result") or {}).get("tools", []) if t.get("name") == tool), None)
    if schema is None:
        raise HTTPException(404, "El servidor no ofrece esa herramienta")
    try:
        errors = sorted(Draft202012Validator(schema).iter_errors(arguments), key=lambda e: list(e.path))
    except SchemaError as exc:
        raise HTTPException(502, "Esquema de herramienta no válido") from exc
    if errors:
        raise HTTPException(422, f"Argumentos no válidos: {errors[0].message[:150]}")
    reply = _exchange(config, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": tool, "arguments": arguments}}])[1]
    if "error" in reply:
        raise HTTPException(502, "La herramienta MCP devolvió un error")
    text = json.dumps(reply.get("result"), ensure_ascii=False)
    return {"untrusted": True, "truncated": len(text) > MAX_RESULT_CHARS, "result": text[:MAX_RESULT_CHARS]}
