"""Guided templates (phase 7).

Interactive templates are a fixed, accessible engine (index.html, style.css, comun.js, script.js) plus a data file
(datos.js: ``window.EDUSTUDIO_DATA = {...};``). The engine is written and reviewed once; the AI only fills datos.js,
which the backend validates against the template schema before the proposal can apply itself. Engines build the page
with textContent only, never innerHTML, and work with keyboard and screen readers (no drag and drop).

Document templates are Markdown (ficha.md) or the editable HTML/SVG infographic, which the AI edits directly.
"""

import json
import re
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DATA_PATH = "datos.js"
ENGINE_FILES = ("index.html", "style.css", "comun.js", "script.js")
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"
DATA_PATTERN = re.compile(r"^\s*window\.EDUSTUDIO_DATA\s*=\s*(\{.*\})\s*;?\s*$", re.S)
IMAGE_PATH = r"^(imagenes/[A-Za-z0-9._-]+)?$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Illustrated(Strict):
    image: str = Field(default="", max_length=120, pattern=IMAGE_PATH)
    alt: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def alt_for_image(self):
        if self.image and not self.alt.strip():
            raise ValueError("cada imagen necesita texto alternativo (alt)")
        return self


class Question(Illustrated):
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int = Field(ge=0)
    feedback: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def answer_in_range(self):
        if self.answer >= len(self.options):
            raise ValueError("answer debe ser el índice de una opción existente (empieza en 0)")
        if any(not option.strip() for option in self.options):
            raise ValueError("las opciones no pueden estar vacías")
        return self


class Pair(Illustrated):
    left: str = Field(min_length=1, max_length=200)
    right: str = Field(min_length=1, max_length=200)


class Step(Illustrated):
    text: str = Field(min_length=1, max_length=300)


class Card(Illustrated):
    front: str = Field(min_length=1, max_length=200)
    back: str = Field(min_length=1, max_length=500)


class ClassItem(Illustrated):
    text: str = Field(min_length=1, max_length=200)
    group: int = Field(ge=0)


class ReadingQuestion(Strict):
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=5)
    answer: int = Field(ge=0)
    feedback: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def answer_in_range(self):
        if self.answer >= len(self.options):
            raise ValueError("answer debe ser el índice de una opción existente (empieza en 0)")
        return self


class Section(Illustrated):
    heading: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=3000)
    more: str = Field(default="", max_length=2000)
    question: ReadingQuestion | None = None


class Base(Strict):
    title: str = Field(min_length=1, max_length=160)
    instructions: str = Field(default="", max_length=1000)
    language: Literal["es", "va"] = "es"
    accessibility: dict = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)


class QuizData(Base):
    questions: list[Question] = Field(min_length=1, max_length=30)


class MatchData(Base):
    pairs: list[Pair] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def at_least_two_answers(self):
        # Several pairs may share an answer (e.g. instruments of the same family), but with a single answer
        # for every pair there would be nothing to choose.
        if len({p.right.strip().lower() for p in self.pairs}) < 2:
            raise ValueError("hace falta al menos dos respuestas distintas a la derecha")
        return self


class OrderData(Base):
    items: list[Step] = Field(min_length=2, max_length=15)


class CardsData(Base):
    cards: list[Card] = Field(min_length=1, max_length=40)


class ClassifyData(Base):
    groups: list[str] = Field(min_length=2, max_length=6)
    items: list[ClassItem] = Field(min_length=2, max_length=40)

    @model_validator(mode="after")
    def groups_exist(self):
        if any(item.group >= len(self.groups) for item in self.items):
            raise ValueError("group debe ser el índice de un grupo existente (empieza en 0)")
        return self


class ReadingData(Base):
    sections: list[Section] = Field(min_length=1, max_length=20)


LABELS = {
    "es": {"check": "Comprobar", "retry": "Volver a empezar", "correct": "¡Correcto!", "incorrect": "No es correcto.",
           "unanswered": "Sin responder.", "score": "{n} de {total}", "choose": "Elige…", "up": "Subir", "down": "Bajar",
           "position": "posición", "allRight": "¡Todo en orden!", "inPlace": "en su sitio.",
           "flip": "Pulsa para girar", "groups": "Grupos", "next": "Continuar", "more": "Saber más",
           "done": "¡Has terminado!"},
    "va": {"check": "Comprovar", "retry": "Tornar a començar", "correct": "Correcte!", "incorrect": "No és correcte.",
           "unanswered": "Sense respondre.", "score": "{n} de {total}", "choose": "Tria…", "up": "Pujar", "down": "Baixar",
           "position": "posició", "allRight": "Tot en ordre!", "inPlace": "al seu lloc.",
           "flip": "Prem per a girar", "groups": "Grups", "next": "Continuar", "more": "Saber-ne més",
           "done": "Has acabat!"},
}

SAMPLES = {
    "cuestionario": {
        "es": {"instructions": "Lee cada pregunta y elige una respuesta.", "questions": [
            {"text": "¿Qué instrumento es de viento metal?", "options": ["Violín", "Trompeta", "Tambor"], "answer": 1,
             "feedback": "La trompeta suena al vibrar los labios en la boquilla."}]},
        "va": {"instructions": "Llig cada pregunta i tria una resposta.", "questions": [
            {"text": "Quin instrument és de vent metall?", "options": ["Violí", "Trompeta", "Tambor"], "answer": 1,
             "feedback": "La trompeta sona quan vibren els llavis en el broquet."}]}},
    "emparejar": {
        "es": {"instructions": "Relaciona cada palabra con su pareja.", "pairs": [
            {"left": "Perro", "right": "Ladra"}, {"left": "Gato", "right": "Maúlla"}, {"left": "Vaca", "right": "Muge"}]},
        "va": {"instructions": "Relaciona cada paraula amb la seua parella.", "pairs": [
            {"left": "Gos", "right": "Lladra"}, {"left": "Gat", "right": "Miola"}, {"left": "Vaca", "right": "Bram"}]}},
    "ordenar": {
        "es": {"instructions": "Ordena los pasos de principio a fin.", "items": [
            {"text": "Plantar la semilla"}, {"text": "Regar"}, {"text": "Sale el brote"}, {"text": "Crece la planta"}]},
        "va": {"instructions": "Ordena els passos de principi a fi.", "items": [
            {"text": "Plantar la llavor"}, {"text": "Regar"}, {"text": "Ix el brot"}, {"text": "Creix la planta"}]}},
    "tarjetas": {
        "es": {"instructions": "Pulsa cada tarjeta para ver qué hay detrás.", "cards": [
            {"front": "Sol", "back": "La estrella que nos da luz y calor."}, {"front": "Luna", "back": "Satélite de la Tierra."}]},
        "va": {"instructions": "Prem cada targeta per a veure què hi ha darrere.", "cards": [
            {"front": "Sol", "back": "L’estrela que ens dona llum i calor."}, {"front": "Lluna", "back": "Satèl·lit de la Terra."}]}},
    "clasificar": {
        "es": {"instructions": "Indica a qué grupo pertenece cada elemento.", "groups": ["Seres vivos", "Objetos"], "items": [
            {"text": "Árbol", "group": 0}, {"text": "Silla", "group": 1}, {"text": "Pájaro", "group": 0}, {"text": "Lápiz", "group": 1}]},
        "va": {"instructions": "Indica a quin grup pertany cada element.", "groups": ["Éssers vius", "Objectes"], "items": [
            {"text": "Arbre", "group": 0}, {"text": "Cadira", "group": 1}, {"text": "Ocell", "group": 0}, {"text": "Llapis", "group": 1}]}},
    "lectura": {
        "es": {"instructions": "Lee cada parte y pulsa «Continuar» para seguir.", "sections": [
            {"heading": "Empezamos", "text": "Escribe aquí la primera parte del texto.", "more": "Información ampliada opcional.",
             "question": {"text": "¿Has entendido esta parte?", "options": ["Sí", "No"], "answer": 0}},
            {"heading": "Seguimos", "text": "Escribe aquí la segunda parte."}]},
        "va": {"instructions": "Llig cada part i prem «Continuar» per a seguir.", "sections": [
            {"heading": "Comencem", "text": "Escriu ací la primera part del text.", "more": "Informació ampliada opcional.",
             "question": {"text": "Has entés esta part?", "options": ["Sí", "No"], "answer": 0}},
            {"heading": "Seguim", "text": "Escriu ací la segona part."}]}},
}

FICHA = {
    "es": ("Objetivo", "Recuerda", "Actividades", "Para terminar: autoevaluación"),
    "va": ("Objectiu", "Recorda", "Activitats", "Per a acabar: autoavaluació"),
}


class Template:
    def __init__(self, id: str, kind: str, schema: type[Base] | None, names: dict, descriptions: dict, guide: str):
        self.id, self.kind, self.schema, self.names, self.descriptions, self.guide = id, kind, schema, names, descriptions, guide


TEMPLATES = {t.id: t for t in (
    Template("cuestionario", "interactiva", QuizData, {"es": "Cuestionario", "va": "Qüestionari"},
             {"es": "Preguntas de opción única con corrección y explicación.",
              "va": "Preguntes d’opció única amb correcció i explicació."},
             "questions: lista de {text, options (2-6 textos), answer (índice de la correcta, empieza en 0), feedback "
             "(explicación breve), image y alt opcionales}. Varía la posición de la respuesta correcta."),
    Template("emparejar", "interactiva", MatchData, {"es": "Emparejar", "va": "Aparellar"},
             {"es": "Relacionar cada elemento con su pareja (sin arrastrar, accesible con teclado).",
              "va": "Relacionar cada element amb la seua parella (sense arrossegar, accessible amb teclat)."},
             "pairs: lista de {left, right, image y alt opcionales}. Varias parejas pueden compartir el mismo right "
             "(por ejemplo, instrumentos de la misma familia); escribe ese right exactamente igual en todas."),
    Template("ordenar", "interactiva", OrderData, {"es": "Ordenar una secuencia", "va": "Ordenar una seqüència"},
             {"es": "Poner en orden los pasos de un proceso, una historia o una línea del tiempo.",
              "va": "Posar en ordre els passos d’un procés, una història o una línia del temps."},
             "items: lista de {text, image y alt opcionales} EN EL ORDEN CORRECTO (la plantilla los desordena)."),
    Template("tarjetas", "interactiva", CardsData, {"es": "Tarjetas de repaso", "va": "Targetes de repàs"},
             {"es": "Tarjetas que se giran para repasar vocabulario o conceptos.",
              "va": "Targetes que es giren per a repassar vocabulari o conceptes."},
             "cards: lista de {front (palabra o pregunta), back (definición o respuesta), image y alt opcionales}."),
    Template("clasificar", "interactiva", ClassifyData, {"es": "Clasificar", "va": "Classificar"},
             {"es": "Asignar cada elemento a su grupo o categoría.", "va": "Assignar cada element al seu grup o categoria."},
             "groups: 2-6 nombres de grupo; items: lista de {text, group (índice del grupo, empieza en 0), image y alt "
             "opcionales}. Reparte los elementos entre todos los grupos."),
    Template("lectura", "interactiva", ReadingData, {"es": "Lectura por partes", "va": "Lectura per parts"},
             {"es": "Texto que se descubre sección a sección, con «Saber más» y preguntas de comprensión.",
              "va": "Text que es descobreix secció a secció, amb «Saber-ne més» i preguntes de comprensió."},
             "sections: lista de {heading, text (párrafo breve), more (ampliación opcional), question opcional {text, "
             "options, answer (índice, empieza en 0), feedback}, image y alt opcionales}."),
    Template("infografia", "infografia", None, {"es": "Infografía", "va": "Infografia"},
             {"es": "Infografía editable en HTML/SVG con iconos, exportable a PNG.",
              "va": "Infografia editable en HTML/SVG amb icones, exportable a PNG."}, ""),
    Template("ficha", "ficha", None, {"es": "Ficha imprimible", "va": "Fitxa imprimible"},
             {"es": "Documento para imprimir o exportar a PDF y DOCX: objetivo, recuerda, actividades y autoevaluación.",
              "va": "Document per a imprimir o exportar a PDF i DOCX: objectiu, recorda, activitats i autoavaluació."}, ""),
)}


def catalog() -> list[dict]:
    return [{"id": t.id, "kind": t.kind, "names": t.names, "descriptions": t.descriptions} for t in TEMPLATES.values()]


def get(template_id: str) -> Template:
    template = TEMPLATES.get(template_id)
    if template is None:
        raise HTTPException(404, "Plantilla no encontrada")
    return template


def data_js(data: dict) -> str:
    return "window.EDUSTUDIO_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"


def parse_data(content: str) -> dict:
    match = DATA_PATTERN.match(content)
    if not match:
        raise ValueError("datos.js debe tener la forma window.EDUSTUDIO_DATA = {...};")
    try:
        value = json.loads(match.group(1))
    except ValueError as exc:
        raise ValueError(f"el objeto de datos no es JSON válido ({exc.msg}, línea {exc.lineno})") from exc
    if not isinstance(value, dict):
        raise ValueError("los datos deben ser un objeto")
    return value


def validate_data(template_id: str, content: str) -> list[str]:
    """Returns human-readable problems (empty when datos.js matches the template)."""
    template = get(template_id)
    if template.schema is None:
        return []
    try:
        template.schema.model_validate(parse_data(content))
    except ValueError as exc:
        if isinstance(exc, ValidationError):
            return [f"{'.'.join(str(p) for p in error['loc']) or 'datos'}: {error['msg'].removeprefix('Value error, ')}"
                    for error in exc.errors()[:8]]
        return [str(exc)]
    return []


def initial_files(template_id: str, brief: dict) -> dict[str, str]:
    """Files a new project gets from the template (the brief comes from activity.json)."""
    template = get(template_id)
    language = "va" if brief.get("language") == "va" else "es"
    title = str(brief.get("title") or template.names[language]).strip()[:160]
    accessibility = brief.get("accessibility") if isinstance(brief.get("accessibility"), dict) else {}
    if template.kind == "ficha":
        sections = "\n\n".join(f"## {heading}\n\n" for heading in FICHA[language])
        return {"ficha.md": f"# {title}\n\n{sections}".rstrip() + "\n"}
    if template.kind != "interactiva":
        return {}  # the infographic is created by the web client from its own template
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    index = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    index = index.replace("{LANG}", "ca" if language == "va" else "es").replace("{TITLE}", safe_title)
    data = {"title": title, "language": language,
            "accessibility": {"large_text": accessibility.get("large_text") is True,
                              "high_contrast": accessibility.get("high_contrast") is True},
            "labels": LABELS[language], **SAMPLES[template_id][language]}
    return {"index.html": index,
            "style.css": (TEMPLATE_DIR / "style.css").read_text(encoding="utf-8"),
            "comun.js": (TEMPLATE_DIR / "comun.js").read_text(encoding="utf-8"),
            "script.js": (TEMPLATE_DIR / f"{template_id}.js").read_text(encoding="utf-8"),
            DATA_PATH: data_js(data)}


def instruction(template_id: str, brief: dict, base: str) -> str:
    """Instruction for the first version of a project created from a template."""
    template = get(template_id)
    language = "valenciano (catalán)" if brief.get("language") == "va" else "castellano"
    if template.kind == "interactiva":
        return (f"{base}\n\nEste proyecto usa la plantilla «{template.names['es']}». NO modifiques index.html, style.css, "
                f"comun.js ni script.js: son el motor accesible de la plantilla. Modifica SOLO {DATA_PATH} y devuelve su "
                "contenido completo con la forma exacta window.EDUSTUDIO_DATA = {...}; donde {...} es JSON válido "
                "(comillas dobles, sin comentarios ni comas finales). Conserva language, accessibility y labels tal como "
                f"están; rellena title, instructions (consigna breve para el alumnado) y {template.guide} Escribe todo el "
                f"texto en {language}, adecuado al nivel educativo, claro y breve. Usa imágenes solo de available_images.")
    if template.kind == "ficha":
        headings = ", ".join(f"«{h}»" for h in FICHA["va" if brief.get("language") == "va" else "es"])
        return (f"{base}\n\nEste proyecto es una ficha imprimible. Modifica SOLO ficha.md: conserva el título y las "
                f"secciones de nivel 2 {headings} y rellénalas en {language}. En «Actividades» propone de 3 a 6 ejercicios "
                "numerados con espacio para responder (líneas ____ o tablas). Markdown limpio, sin HTML.")
    return (f"{base}\n\nEste proyecto es una infografía: modifica infografia.html conservando su estructura (HTML con "
            "SVG en línea, iconos ya incluidos y el aviso de licencia de Lucide), sin recursos externos.")


def check_proposal(template_id: str, changes: list) -> dict:
    """Grounding report for a proposal on a template project."""
    template = get(template_id)
    paths = {change.path for change in changes}
    problems: list[str] = []
    if template.kind == "interactiva":
        touched = sorted(paths & set(ENGINE_FILES))
        if touched:
            problems.append("modifica el motor de la plantilla: " + ", ".join(touched))
        data = next((change.content for change in changes if change.path == DATA_PATH), None)
        if data is None:
            problems.append(f"no modifica {DATA_PATH}")
        else:
            problems += validate_data(template_id, data)
    elif template.kind == "ficha" and "ficha.md" not in paths:
        problems.append("no modifica ficha.md")
    return {"mode": "template", "kind": "plantilla", "template": template_id, "sources": [], "passages_used": [],
            "citations": [], "verified": 0, "unverified": 0, "not_covered": [], "template_problems": problems,
            "supported": not problems}
