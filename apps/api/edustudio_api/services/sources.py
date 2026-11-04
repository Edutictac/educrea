"""Reference sources: extraction (sandboxed), structure-aware chunking, BM25 retrieval and quote verification.

Only the extracted text is stored (never the original file). Extraction of untrusted PDFs/DOCX runs inside the same
bubblewrap sandbox as the document converter: no network, read-only system, private temp dir, time and size limits.
Retrieval is lexical (BM25 with accent folding and light stemming for Spanish/Catalan), so it needs no external
embedding service and works the same on SQLite and PostgreSQL.
"""

import math
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Source, SourceChunk
from .converter import _sandbox

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 3_000_000
MAX_SOURCES = 5
CHUNK_TARGET = 1400
CHUNK_MAX = 2000
RETRIEVAL_BUDGET = 60_000
MAX_RETRIEVED = 40
MIN_QUOTE_CHARS = 15
PANDOC_FORMATS = {".docx": "docx", ".odt": "odt", ".epub": "epub", ".html": "html", ".htm": "html", ".rtf": "rtf"}
PLAIN = {".md", ".txt"}
ALLOWED = {".pdf", *PANDOC_FORMATS, *PLAIN}

STOPWORDS = frozenset("""
de la el en y a los las del se que por con para un una al lo como mas pero sus le ya o fue este si porque esta son
entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese
eso ante ellos e esto mi antes algunos que unos yo otro otras otra el tanto esa estos mucho quienes nada muchos cual
poco ella estar estas algunas algo nosotros es son ser han has ha
i els les dels amb per una uns unes al del es son que com mes pero seus seu seva seves ja o va aquest aquesta aquests
aquestes entre quan molt sense sobre tambe fins hi on qui des tot ens durant tots un uns altres aquest eixe eixa
""".split())


def norm(text: str) -> str:
    folded = unicodedata.normalize("NFD", text.lower().replace("·", ""))
    return "".join(c for c in folded if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return [word[:6] for word in re.findall(r"[a-z0-9]+", norm(text)) if len(word) > 1 and word not in STOPWORDS]


# ---------------------------------------------------------------- extraction

def _run(workdir: Path, command: list[str], timeout: int) -> None:
    try:
        done = subprocess.run(_sandbox(workdir, command), capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "La extracción del texto ha tardado demasiado") from exc
    if done.returncode != 0:
        raise HTTPException(422, "No se ha podido leer el documento. ¿Está dañado o protegido con contraseña?")


def extract(filename: str, data: bytes) -> list[tuple[int | None, str]]:
    """Returns [(page or None, text)]."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(422, "Formato no admitido. Usa PDF, DOCX, ODT, EPUB, HTML, Markdown o TXT")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera los 25 MB")
    if ext in PLAIN:
        return [(None, data.decode("utf-8", errors="replace"))]
    needed = "pdftotext" if ext == ".pdf" else "pandoc"
    if not (shutil.which(needed) and shutil.which("bwrap")):
        raise HTTPException(503, "El conversor de documentos no está disponible en este servidor")
    with tempfile.TemporaryDirectory(prefix="edustudio-source-") as tmp:
        workdir = Path(tmp)
        (workdir / f"input{ext}").write_bytes(data)
        if ext == ".pdf":
            _run(workdir, ["pdftotext", "-enc", "UTF-8", "input.pdf", "output.txt"], 180)
        else:
            _run(workdir, ["pandoc", "--sandbox", "-f", PANDOC_FORMATS[ext], "-t", "markdown", "--wrap=none",
                           "-o", "output.txt", f"input{ext}"], 120)
        output = workdir / "output.txt"
        if not output.is_file() or output.stat().st_size > MAX_TEXT_CHARS * 4:
            raise HTTPException(413, "El documento contiene demasiado texto")
        text = output.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf":
        pages = [(number, page) for number, page in enumerate(text.split("\f"), 1) if page.strip()]
        if not pages or sum(len(p) for _, p in pages) / max(len(text.split("\f")), 1) < 100:
            raise HTTPException(422, "El PDF parece escaneado (casi no tiene texto). El OCR todavía no está disponible")
        return pages
    return [(None, text)]


# ------------------------------------------------------------------ chunking

HEADING_WORDS = re.compile(
    r"^(art[ií]culo|cap[ií]tulo|t[ií]tulo|anexo|[aàá]rea|materia|mat[eè]ria|bloque|saberes|competencia|criterios|curso|"
    r"ciclo|nivel|disposici[oó]n|secci[oó]n|unidad)\b", re.I)
NUMBERED = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")


def is_heading(line: str) -> str | None:
    text = line.strip()
    if not text or len(text) > 110:
        return None
    if text.startswith("#"):
        return text.lstrip("# ").strip() or None
    if HEADING_WORDS.match(text) and not text.endswith((",", ";")):
        return text
    if text.isupper() and len(text) >= 4 and not text.endswith("."):
        return text
    if NUMBERED.match(text) and len(text) <= 90 and not text.endswith((".", ",", ";")):
        return text
    return None


def _split_long(paragraph: str) -> list[str]:
    if len(paragraph) <= CHUNK_MAX:
        return [paragraph]
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?;:])\s+", paragraph):
        while len(sentence) > CHUNK_MAX:  # pathological: no punctuation
            pieces.append(sentence[:CHUNK_MAX])
            sentence = sentence[CHUNK_MAX:]
        if current and len(current) + len(sentence) + 1 > CHUNK_TARGET:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_pages(pages: list[tuple[int | None, str]]) -> list[dict]:
    """Heading-aware chunks of about CHUNK_TARGET characters; a new heading always starts a new chunk."""
    chunks: list[dict] = []
    heading = ""
    state = {"lines": [], "size": 0, "heading": "", "page": None, "body": False}

    def flush() -> None:
        body = "\n".join(state["lines"]).strip()
        if body:
            chunks.append({"heading": state["heading"][:300], "page": state["page"], "text": body})
        state.update(lines=[], size=0, body=False)

    def add(text: str, page: int | None, is_body: bool) -> None:
        if not state["lines"]:
            state["heading"], state["page"] = heading, page
        state["lines"].append(text)
        state["size"] += len(text)
        state["body"] = state["body"] or is_body

    for page, text in pages:
        for block in re.split(r"\n\s*\n", text):
            paragraph = " ".join(block.split())
            if not paragraph:
                continue
            title = is_heading(paragraph)
            if title:
                if state["body"]:
                    flush()
                heading = title
                add(paragraph, page, False)
                continue
            for piece in _split_long(paragraph):
                if state["body"] and state["size"] + len(piece) > CHUNK_TARGET:
                    flush()
                add(piece, page, True)
    flush()
    return chunks


def ingest(db: Session, project_id: UUID, title: str, filename: str, pages: list[tuple[int | None, str]]) -> Source:
    total = sum(len(text) for _, text in pages)
    if total > MAX_TEXT_CHARS:
        raise HTTPException(413, "El documento contiene demasiado texto (máximo unos 3 millones de caracteres)")
    chunks = chunk_pages(pages)
    if not chunks:
        raise HTTPException(422, "El documento no contiene texto utilizable")
    source = Source(project_id=project_id, title=title[:200], filename=filename[:200],
                    kind=Path(filename).suffix.lower().lstrip(".")[:10], pages=max((p or 0) for p, _ in pages),
                    chars=total, chunk_count=len(chunks))
    db.add(source)
    db.flush()
    db.add_all(SourceChunk(source_id=source.id, project_id=project_id, ordinal=index, heading=chunk["heading"],
                           page=chunk["page"], text=chunk["text"]) for index, chunk in enumerate(chunks))
    db.commit()
    db.refresh(source)
    return source


# ----------------------------------------------------------------- retrieval

def load_chunks(db: Session, project_id: UUID, source_ids: list[UUID]) -> list[tuple[SourceChunk, str]]:
    rows = db.execute(select(SourceChunk, Source.title).join(Source, Source.id == SourceChunk.source_id).where(
        SourceChunk.project_id == project_id, SourceChunk.source_id.in_(source_ids))
        .order_by(Source.created_at, SourceChunk.ordinal)).all()
    return [(chunk, title) for chunk, title in rows]


def retrieve(db: Session, project_id: UUID, source_ids: list[UUID], query: str,
             budget: int = RETRIEVAL_BUDGET, limit: int = MAX_RETRIEVED) -> list[dict]:
    """Top passages for the query, labelled F1, F2... and returned in document order."""
    rows = load_chunks(db, project_id, source_ids)
    query_terms = set(tokens(query))
    if not rows or not query_terms:
        return []
    documents = [Counter(tokens(chunk.heading) * 2 + tokens(chunk.text)) for chunk, _ in rows]
    lengths = [sum(doc.values()) or 1 for doc in documents]
    average = sum(lengths) / len(lengths)
    frequency = Counter(term for doc in documents for term in query_terms if term in doc)
    scored = []
    for index, doc in enumerate(documents):
        score = 0.0
        for term in query_terms:
            tf = doc.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * lengths[index] / average))
        if score > 0:
            scored.append((score, index))
    chosen, used = [], 0
    for score, index in sorted(scored, reverse=True)[:limit]:
        size = len(rows[index][0].text)
        if used + size > budget:
            continue
        chosen.append(index)
        used += size
    chosen.sort()
    return [{"label": f"F{number}", "chunk_id": str(rows[index][0].id), "source": rows[index][1],
             "page": rows[index][0].page, "heading": rows[index][0].heading, "text": rows[index][0].text}
            for number, index in enumerate(chosen, 1)]


# -------------------------------------------------------------- verification

def verify_quotes(db: Session, project_id: UUID, source_ids: list[UUID], quotes: list[str]) -> list[dict]:
    """Checks that each quote appears verbatim (ignoring case, accents, punctuation and spacing) in the sources."""
    rows = load_chunks(db, project_id, source_ids)
    folded = [(" ".join(re.findall(r"[a-z0-9]+", norm(chunk.text))), chunk, title) for chunk, title in rows]
    joined = " ".join(text for text, _, _ in folded)
    results = []
    for quote in quotes:
        wanted = " ".join(re.findall(r"[a-z0-9]+", norm(quote)))
        found = None
        if len(wanted) >= MIN_QUOTE_CHARS:
            found = next(((chunk, title) for text, chunk, title in folded if wanted in text), None)
            if found is None and wanted in joined:  # quote spans two chunks
                found = (None, None)
        results.append({"verified": found is not None,
                        "source": found[1] if found and found[1] else None,
                        "page": found[0].page if found and found[0] else None})
    return results
