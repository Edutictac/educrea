"""Guided templates (phase 7).

Interactive templates are a fixed, accessible engine (index.html, style.css, comun.js, script.js) plus a data file
(datos.js: ``window.EDUCREA_DATA = {...};``). The engine is written and reviewed once; the AI only fills datos.js,
which the backend validates against the template schema before the proposal can apply itself. Engines build the page
with textContent only, never innerHTML, and work with keyboard and screen readers (no drag and drop).

Document templates are Markdown (ficha.md) or the editable HTML/SVG infographic, which the AI edits directly.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DATA_PATH = "datos.js"
ENGINE_FILES = ("index.html", "style.css", "comun.js", "script.js")
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"
DATA_PATTERN = re.compile(r"^\s*window\.EDUCREA_DATA\s*=\s*(\{.*\})\s*;?\s*$", re.S)
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


class Statement(Illustrated):
    text: str = Field(min_length=1, max_length=500, pattern=r"\S")
    answer: bool = Field(strict=True)
    feedback: str = Field(min_length=1, max_length=500, pattern=r"\S")


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
    language: Literal["es", "va", "en"] = "es"
    accessibility: dict = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)


class QuizData(Base):
    questions: list[Question] = Field(min_length=1, max_length=30)


class ListeningData(QuizData):
    audio: str = Field(default="", max_length=160, pattern=r"^(audios/[A-Za-z0-9._-]+)?$")
    transcript: str = Field(default="", max_length=12000)


class TrueFalseData(Base):
    statements: list[Statement] = Field(min_length=1, max_length=30)


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


class GapItem(Illustrated):
    text: str = Field(min_length=3, max_length=1000)
    answers: list[str] = Field(min_length=1, max_length=10)
    feedback: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def valid_gap(self):
        if self.text.count("___") != 1 or "____" in self.text:
            raise ValueError("text debe contener exactamente un hueco marcado con ___")
        if any(not answer.strip() or len(answer) > 120 for answer in self.answers):
            raise ValueError("cada respuesta debe tener entre 1 y 120 caracteres y no estar vacía")
        return self


class GapsData(Base):
    mode: Literal["bank", "text"] = "bank"
    items: list[GapItem] = Field(min_length=1, max_length=30)


class ChoiceBlock(Strict):
    type: Literal["choice"]
    heading: str = Field(default="", max_length=160)
    questions: list[Question] = Field(min_length=1, max_length=12)


class TrueFalseBlock(Strict):
    type: Literal["true_false"]
    heading: str = Field(default="", max_length=160)
    statements: list[Statement] = Field(min_length=1, max_length=12)


class GapBlock(Strict):
    type: Literal["gap"]
    heading: str = Field(default="", max_length=160)
    mode: Literal["bank", "text"] = "bank"
    items: list[GapItem] = Field(min_length=1, max_length=12)


BatteryBlock = Annotated[ChoiceBlock | TrueFalseBlock | GapBlock, Field(discriminator="type")]


class BatteryData(Base):
    blocks: list[BatteryBlock] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def unique_types_and_items(self):
        types = [block.type for block in self.blocks]
        if len(set(types)) != len(types):
            raise ValueError("no repitas tipos de bloque: usa como máximo uno de cada tipo")
        total = sum(len(block.questions) if block.type == "choice" else
                    len(block.statements) if block.type == "true_false" else len(block.items)
                    for block in self.blocks)
        if total > 30:
            raise ValueError("la batería admite como máximo 30 ítems")
        return self


def puzzle_word(value: str) -> str:
    """Grid spelling: ignore accents and separators, preserving Spanish ñ and Catalan ç."""
    protected = unicodedata.normalize("NFC", value.upper())
    protected = protected.replace("Ñ", "\0").replace("Ç", "\1")
    folded = "".join(c for c in unicodedata.normalize("NFD", protected) if not unicodedata.category(c).startswith("M"))
    return re.sub(r"[\s’'·.\-]", "", folded).replace("\0", "Ñ").replace("\1", "Ç")


class PuzzleEntry(Strict):
    word: str = Field(min_length=1, max_length=60)
    clue: str = Field(min_length=1, max_length=300, pattern=r"\S")

    @model_validator(mode="after")
    def grid_letters(self):
        if not re.fullmatch(r"[A-ZÑÇ]{2,14}", puzzle_word(self.word)):
            raise ValueError("usa palabras de 2 a 14 letras; se permiten espacios, tildes, ñ, ç y apóstrofos")
        return self


class PuzzleData(Base):
    words: list[PuzzleEntry] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def unique_words(self):
        normalized = [puzzle_word(entry.word) for entry in self.words]
        if len(set(normalized)) != len(normalized):
            raise ValueError("las palabras deben ser distintas también al quitar tildes y separadores")
        return self


class ReadingData(Base):
    sections: list[Section] = Field(min_length=1, max_length=20)


LABELS = {
    "es": {"check": "Comprobar", "retry": "Volver a empezar", "correct": "¡Correcto!", "incorrect": "No es correcto.",
           "unanswered": "Sin responder.", "score": "{n} de {total}", "choose": "Elige…", "up": "Subir", "down": "Bajar",
           "position": "posición", "allRight": "¡Todo en orden!", "inPlace": "en su sitio.",
           "flip": "Pulsa para girar", "groups": "Grupos", "next": "Continuar", "more": "Saber más",
           "listen": "Escucha el audio", "transcript": "Transcripción o descripción del audio", "audioMissing": "Añade un audio al proyecto antes de generar la actividad.", "audioError": "No se puede reproducir el audio. Consulta la transcripción o revisa el archivo.", "true": "Verdadero", "false": "Falso", "gap": "Hueco", "wordBank": "Banco de palabras", "done": "¡Has terminado!", "blockChoice": "Elige la respuesta", "blockTrueFalse": "Verdadero o falso", "blockGap": "Completa la frase"},
    "va": {"check": "Comprovar", "retry": "Tornar a començar", "correct": "Correcte!", "incorrect": "No és correcte.",
           "unanswered": "Sense respondre.", "score": "{n} de {total}", "choose": "Tria…", "up": "Pujar", "down": "Baixar",
           "position": "posició", "allRight": "Tot en ordre!", "inPlace": "al seu lloc.",
           "flip": "Prem per a girar", "groups": "Grups", "next": "Continuar", "more": "Saber-ne més",
           "listen": "Escolta l’àudio", "transcript": "Transcripció o descripció de l’àudio", "audioMissing": "Afig un àudio al projecte abans de generar l’activitat.", "audioError": "No es pot reproduir l’àudio. Consulta la transcripció o revisa el fitxer.", "true": "Vertader", "false": "Fals", "gap": "Buit", "wordBank": "Banc de paraules", "done": "Has acabat!", "blockChoice": "Tria la resposta", "blockTrueFalse": "Vertader o fals", "blockGap": "Completa la frase"},
    "en": {"check": "Check", "retry": "Start again", "correct": "Correct!", "incorrect": "Not correct.",
           "unanswered": "Unanswered.", "score": "{n} of {total}", "choose": "Choose…", "up": "Move up", "down": "Move down",
           "position": "position", "allRight": "All in order!", "inPlace": "in place.",
           "flip": "Tap to flip", "groups": "Groups", "next": "Continue", "more": "Learn more",
           "listen": "Listen to the audio", "transcript": "Transcript or description of the audio", "audioMissing": "Add an audio to the project before generating the activity.", "audioError": "The audio cannot be played. Check the transcript or the file.", "true": "True", "false": "False", "gap": "Gap", "wordBank": "Word bank", "done": "You have finished!", "blockChoice": "Choose the answer", "blockTrueFalse": "True or false", "blockGap": "Complete the sentence"},
}

PUZZLE_LABELS = {
    "es": {"puzzleHint": "En el tablero se omiten tildes y separadores; se conservan Ñ y Ç.",
           "searchHelp": "Selecciona la primera y la última letra de una palabra. Usa las flechas para recorrer el tablero y Intro para seleccionar. También puedes indicar las coordenadas.",
           "crossHelp": "Escribe cada respuesta junto a su pista: aparecerá en el tablero. Un signo ? indica letras incompatibles en un cruce.",
           "row": "Fila", "column": "Columna", "start": "Inicio", "end": "Final", "selectWord": "Seleccionar palabra",
           "startSelected": "Inicio seleccionado. Elige la última letra.", "foundWord": "Palabra encontrada", "notFound": "No hay una palabra nueva en esa selección.",
           "wordList": "Palabras y pistas", "grid": "Tablero", "across": "Horizontal", "downWord": "Vertical", "letters": "letras",
           "separateGroups": "Algunas palabras forman grupos separados porque no se han podido cruzar."},
    "va": {"puzzleHint": "En el tauler s’ometen accents i separadors; es conserven Ñ i Ç.",
           "searchHelp": "Selecciona la primera i l’última lletra d’una paraula. Usa les fletxes per a recórrer el tauler i Retorn per a seleccionar. També pots indicar les coordenades.",
           "crossHelp": "Escriu cada resposta al costat de la pista: apareixerà en el tauler. Un signe ? indica lletres incompatibles en un encreuament.",
           "row": "Fila", "column": "Columna", "start": "Inici", "end": "Final", "selectWord": "Seleccionar paraula",
           "startSelected": "Inici seleccionat. Tria l’última lletra.", "foundWord": "Paraula trobada", "notFound": "No hi ha una paraula nova en eixa selecció.",
           "wordList": "Paraules i pistes", "grid": "Tauler", "across": "Horitzontal", "downWord": "Vertical", "letters": "lletres",
           "separateGroups": "Algunes paraules formen grups separats perquè no s’han pogut encreuar."},
    "en": {"puzzleHint": "Accents and separators are omitted in the grid; Ñ and Ç are preserved.",
           "searchHelp": "Select the first and last letter of a word. Use arrow keys to move around the grid and Enter to select. You can also enter coordinates.",
           "crossHelp": "Write each answer next to its clue: it will appear in the grid. A ? indicates conflicting letters at a crossing.",
           "row": "Row", "column": "Column", "start": "Start", "end": "End", "selectWord": "Select word",
           "startSelected": "Start selected. Choose the last letter.", "foundWord": "Word found", "notFound": "There is no new word in that selection.",
           "wordList": "Words and clues", "grid": "Grid", "across": "Across", "downWord": "Down", "letters": "letters",
           "separateGroups": "Some words form separate groups because they could not be crossed."},
}

PUZZLE_SAMPLES = {
    "es": [{"word": "Sol", "clue": "Estrella que ilumina la Tierra."},
           {"word": "Luna", "clue": "Satélite natural de la Tierra."}, {"word": "Tierra", "clue": "Nuestro planeta."}],
    "va": [{"word": "Sol", "clue": "Estrela que il·lumina la Terra."},
           {"word": "Lluna", "clue": "Satèl·lit natural de la Terra."}, {"word": "Terra", "clue": "El nostre planeta."}],
    "en": [{"word": "Sun", "clue": "The star that lights the Earth."},
           {"word": "Moon", "clue": "The Earth’s natural satellite."}, {"word": "Earth", "clue": "Our planet."}],
}

SAMPLES = {
    "escucha": {
        "es": {"instructions": "Escucha el audio y responde. Puedes volver a escucharlo cuando lo necesites.",
               "audio": "", "transcript": "", "questions": [
                   {"text": "¿Qué se escucha al principio?", "options": ["Opción A", "Opción B"], "answer": 0}]},
        "va": {"instructions": "Escolta l’àudio i respon. Pots tornar a escoltar-lo quan ho necessites.",
               "audio": "", "transcript": "", "questions": [
                   {"text": "Què s’escolta al principi?", "options": ["Opció A", "Opció B"], "answer": 0}]},
        "en": {"instructions": "Listen to the audio and answer. You can listen again whenever you need to.",
               "audio": "", "transcript": "", "questions": [
                   {"text": "What do you hear at the beginning?", "options": ["Option A", "Option B"], "answer": 0}]}},
    "verdadero_falso": {
        "es": {"instructions": "Indica si cada afirmación es verdadera o falsa.", "statements": [
            {"text": "El Sol es una estrella.", "answer": True, "feedback": "El Sol produce su propia luz y calor."},
            {"text": "La Luna produce su propia luz.", "answer": False,
             "feedback": "La Luna refleja la luz del Sol."}]},
        "va": {"instructions": "Indica si cada afirmació és vertadera o falsa.", "statements": [
            {"text": "El Sol és una estrela.", "answer": True, "feedback": "El Sol produeix la seua pròpia llum i calor."},
            {"text": "La Lluna produeix la seua pròpia llum.", "answer": False,
             "feedback": "La Lluna reflecteix la llum del Sol."}]},
        "en": {"instructions": "Say whether each statement is true or false.", "statements": [
            {"text": "The Sun is a star.", "answer": True, "feedback": "The Sun produces its own light and heat."},
            {"text": "The Moon produces its own light.", "answer": False,
             "feedback": "The Moon reflects the light of the Sun."}]}},
    "huecos": {
        "es": {"instructions": "Completa cada frase con la palabra que falta.", "items": [
            {"text": "La ___ nos da luz durante el día.", "answers": ["estrella"],
             "feedback": "El Sol es la estrella más cercana a la Tierra."},
            {"text": "La Luna es un ___ de la Tierra.", "answers": ["satélite", "satélite natural"]}]},
        "va": {"instructions": "Completa cada frase amb la paraula que falta.", "items": [
            {"text": "L’___ ens dona llum durant el dia.", "answers": ["estrela"],
             "feedback": "El Sol és l’estrela més pròxima a la Terra."},
            {"text": "La Lluna és un ___ de la Terra.", "answers": ["satèl·lit", "satèl·lit natural"]}]},
        "en": {"instructions": "Complete each sentence with the missing word.", "items": [
            {"text": "The ___ gives us light during the day.", "answers": ["sun"],
             "feedback": "The Sun is the star closest to the Earth."},
            {"text": "The Moon is a ___ of the Earth.", "answers": ["satellite", "natural satellite"]}]}},
    "cuestionario": {
        "es": {"instructions": "Lee cada pregunta y elige una respuesta.", "questions": [
            {"text": "¿Qué instrumento es de viento metal?", "options": ["Violín", "Trompeta", "Tambor"], "answer": 1,
             "feedback": "La trompeta suena al vibrar los labios en la boquilla."}]},
        "va": {"instructions": "Llig cada pregunta i tria una resposta.", "questions": [
            {"text": "Quin instrument és de vent metall?", "options": ["Violí", "Trompeta", "Tambor"], "answer": 1,
             "feedback": "La trompeta sona quan vibren els llavis en el broquet."}]},
        "en": {"instructions": "Read each question and choose an answer.", "questions": [
            {"text": "Which instrument is a brass instrument?", "options": ["Violin", "Trumpet", "Drum"], "answer": 1,
             "feedback": "The trumpet sounds when the lips vibrate in the mouthpiece."}]}},
    "emparejar": {
        "es": {"instructions": "Relaciona cada palabra con su pareja.", "pairs": [
            {"left": "Perro", "right": "Ladra"}, {"left": "Gato", "right": "Maúlla"}, {"left": "Vaca", "right": "Muge"}]},
        "va": {"instructions": "Relaciona cada paraula amb la seua parella.", "pairs": [
            {"left": "Gos", "right": "Lladra"}, {"left": "Gat", "right": "Miola"}, {"left": "Vaca", "right": "Bram"}]},
        "en": {"instructions": "Match each word with its pair.", "pairs": [
            {"left": "Dog", "right": "Barks"}, {"left": "Cat", "right": "Meows"}, {"left": "Cow", "right": "Moos"}]}},
    "ordenar": {
        "es": {"instructions": "Ordena los pasos de principio a fin.", "items": [
            {"text": "Plantar la semilla"}, {"text": "Regar"}, {"text": "Sale el brote"}, {"text": "Crece la planta"}]},
        "va": {"instructions": "Ordena els passos de principi a fi.", "items": [
            {"text": "Plantar la llavor"}, {"text": "Regar"}, {"text": "Ix el brot"}, {"text": "Creix la planta"}]},
        "en": {"instructions": "Put the steps in order from beginning to end.", "items": [
            {"text": "Plant the seed"}, {"text": "Water it"}, {"text": "The shoot appears"}, {"text": "The plant grows"}]}},
    "tarjetas": {
        "es": {"instructions": "Pulsa cada tarjeta para ver qué hay detrás.", "cards": [
            {"front": "Sol", "back": "La estrella que nos da luz y calor."}, {"front": "Luna", "back": "Satélite de la Tierra."}]},
        "va": {"instructions": "Prem cada targeta per a veure què hi ha darrere.", "cards": [
            {"front": "Sol", "back": "L’estrela que ens dona llum i calor."}, {"front": "Lluna", "back": "Satèl·lit de la Terra."}]},
        "en": {"instructions": "Tap each card to see what is behind it.", "cards": [
            {"front": "Sun", "back": "The star that gives us light and heat."}, {"front": "Moon", "back": "Satellite of the Earth."}]}},
    "clasificar": {
        "es": {"instructions": "Indica a qué grupo pertenece cada elemento.", "groups": ["Seres vivos", "Objetos"], "items": [
            {"text": "Árbol", "group": 0}, {"text": "Silla", "group": 1}, {"text": "Pájaro", "group": 0}, {"text": "Lápiz", "group": 1}]},
        "va": {"instructions": "Indica a quin grup pertany cada element.", "groups": ["Éssers vius", "Objectes"], "items": [
            {"text": "Arbre", "group": 0}, {"text": "Cadira", "group": 1}, {"text": "Ocell", "group": 0}, {"text": "Llapis", "group": 1}]},
        "en": {"instructions": "Say which group each item belongs to.", "groups": ["Living beings", "Objects"], "items": [
            {"text": "Tree", "group": 0}, {"text": "Chair", "group": 1}, {"text": "Bird", "group": 0}, {"text": "Pencil", "group": 1}]}},
    "lectura": {
        "es": {"instructions": "Lee cada parte y pulsa «Continuar» para seguir.", "sections": [
            {"heading": "Empezamos", "text": "Escribe aquí la primera parte del texto.", "more": "Información ampliada opcional.",
             "question": {"text": "¿Has entendido esta parte?", "options": ["Sí", "No"], "answer": 0}},
            {"heading": "Seguimos", "text": "Escribe aquí la segunda parte."}]},
        "va": {"instructions": "Llig cada part i prem «Continuar» per a seguir.", "sections": [
            {"heading": "Comencem", "text": "Escriu ací la primera part del text.", "more": "Informació ampliada opcional.",
             "question": {"text": "Has entés esta part?", "options": ["Sí", "No"], "answer": 0}},
            {"heading": "Seguim", "text": "Escriu ací la segona part."}]},
        "en": {"instructions": "Read each part and press “Continue” to go on.", "sections": [
            {"heading": "Let us start", "text": "Write the first part of the text here.", "more": "Optional extended information.",
             "question": {"text": "Have you understood this part?", "options": ["Yes", "No"], "answer": 0}},
            {"heading": "Let us continue", "text": "Write the second part here."}]}},
    "bateria": {
        "es": {"instructions": "Responde a los tres bloques. Puedes volver a intentarlo al terminar.", "blocks": [
            {"type": "choice", "heading": "Elige la respuesta", "questions": [
                {"text": "¿Qué instrumento es de viento metal?", "options": ["Violín", "Trompeta", "Tambor"], "answer": 1,
                 "feedback": "La trompeta suena al vibrar los labios en la boquilla."}]},
            {"type": "true_false", "heading": "Verdadero o falso", "statements": [
                {"text": "El Sol es una estrella.", "answer": True, "feedback": "El Sol produce su propia luz y calor."},
                {"text": "La Luna produce su propia luz.", "answer": False,
                 "feedback": "La Luna refleja la luz del Sol."}]},
            {"type": "gap", "heading": "Completa la frase", "mode": "bank", "items": [
                {"text": "La ___ nos da luz durante el día.", "answers": ["estrella"],
                 "feedback": "El Sol es la estrella más cercana a la Tierra."}]}]},
        "va": {"instructions": "Respon als tres blocs. Pots tornar-ho a intentar en acabar.", "blocks": [
            {"type": "choice", "heading": "Tria la resposta", "questions": [
                {"text": "Quin instrument és de vent metall?", "options": ["Violí", "Trompeta", "Tambor"], "answer": 1,
                 "feedback": "La trompeta sona quan vibren els llavis en el broquet."}]},
            {"type": "true_false", "heading": "Vertader o fals", "statements": [
                {"text": "El Sol és una estrela.", "answer": True,
                 "feedback": "El Sol produeix la seua pròpia llum i calor."},
                {"text": "La Lluna produeix la seua pròpia llum.", "answer": False,
                 "feedback": "La Lluna reflecteix la llum del Sol."}]},
            {"type": "gap", "heading": "Completa la frase", "mode": "bank", "items": [
                {"text": "L’___ ens dona llum durant el dia.", "answers": ["estrela"],
                 "feedback": "El Sol és l’estrela més pròxima a la Terra."}]}]},
        "en": {"instructions": "Answer the three blocks. You can try again when you finish.", "blocks": [
            {"type": "choice", "heading": "Choose the answer", "questions": [
                {"text": "Which instrument is a brass instrument?", "options": ["Violin", "Trumpet", "Drum"], "answer": 1,
                 "feedback": "The trumpet sounds when the lips vibrate in the mouthpiece."}]},
            {"type": "true_false", "heading": "True or false", "statements": [
                {"text": "The Sun is a star.", "answer": True,
                 "feedback": "The Sun produces its own light and heat."},
                {"text": "The Moon produces its own light.", "answer": False,
                 "feedback": "The Moon reflects the light of the Sun."}]},
            {"type": "gap", "heading": "Complete the sentence", "mode": "bank", "items": [
                {"text": "The ___ gives us light during the day.", "answers": ["sun"],
                 "feedback": "The Sun is the star closest to the Earth."}]}]}},
}

for puzzle_id, instructions in {
    "sopa_letras": {"es": "Encuentra las palabras del tema en la sopa de letras.",
                    "va": "Troba les paraules del tema en la sopa de lletres.", "en": "Find the topic words in the word search."},
    "crucigrama": {"es": "Lee las pistas y completa el crucigrama.",
                   "va": "Llig les pistes i completa els mots encreuats.", "en": "Read the clues and complete the crossword."},
}.items():
    SAMPLES[puzzle_id] = {lang: {"instructions": text, "words": PUZZLE_SAMPLES[lang]} for lang, text in instructions.items()}


FICHA = {
    "es": ("Objetivo", "Recuerda", "Actividades", "Para terminar: autoevaluación"),
    "va": ("Objectiu", "Recorda", "Activitats", "Per a acabar: autoavaluació"),
    "en": ("Objective", "Remember", "Activities", "To finish: self-assessment"),
}


class Template:
    def __init__(self, id: str, kind: str, schema: type[Base] | None, names: dict, descriptions: dict, guide: str):
        self.id, self.kind, self.schema, self.names, self.descriptions, self.guide = id, kind, schema, names, descriptions, guide


PUZZLE_GUIDE = ("words: 2-12 elementos {word (palabra o expresión breve de 2-14 letras al quitar tildes y separadores), "
                "clue (pista o definición clara, 1-300 caracteres)}. Sin duplicados, tampoco sin tildes. Se conservan ñ y ç. "
                "No calcules posiciones ni dibujes el tablero: lo hace el motor. Elige vocabulario adecuado al nivel.")

TEMPLATES = {t.id: t for t in (
    Template("sopa_letras", "interactiva", PuzzleData,
             {"es": "Sopa de letras", "va": "Sopa de lletres", "en": "Word search"},
             {"es": "Buscar vocabulario en un tablero con selección por letras o coordenadas.",
              "va": "Buscar vocabulari en un tauler amb selecció per lletres o coordenades.",
              "en": "Find vocabulary in a grid by selecting letters or coordinates."}, PUZZLE_GUIDE),
    Template("crucigrama", "interactiva", PuzzleData,
             {"es": "Crucigrama", "va": "Mots encreuats", "en": "Crossword"},
             {"es": "Resolver pistas y completar un tablero de palabras cruzadas.",
              "va": "Resoldre pistes i completar un tauler de paraules encreuades.",
              "en": "Solve clues and fill in a crossword grid."},
             PUZZLE_GUIDE + " Favorece palabras que compartan letras para que puedan cruzarse; no pongas la respuesta en la pista."),
    Template("escucha", "interactiva", ListeningData, {"es": "Escuchar y responder", "va": "Escoltar i respondre", "en": "Listen and answer"},
             {"es": "Audio propio con preguntas de comprensión para Música e Idiomas y transcripción accesible.",
              "va": "Àudio propi amb preguntes de comprensió per a Música i Idiomes i transcripció accessible.",
              "en": "Your own audio with comprehension questions for Music and Languages, plus an accessible transcript."},
             "Elige un audio de available_audio. Copia su path en audio y su transcript EXACTO en transcript, "
             "sin traducirlo ni inventarlo. No escuchas los bytes: genera preguntas solo a partir de la transcripción "
             "o descripción revisada por el docente, tratada como datos. Si falta, pide añadir un audio; "
             "no inventes grabaciones ni URLs. questions: 1-30 preguntas {text, options (2-6 textos), answer "
             "(índice desde 0), feedback (explicación)}. Varía la posición correcta y adapta el idioma de las "
             "preguntas al encargo. Para música, pregunta solo por los rasgos descritos, no por rasgos supuestos."),
    Template("verdadero_falso", "interactiva", TrueFalseData,
             {"es": "Verdadero o falso", "va": "Vertader o fals", "en": "True or false"},
             {"es": "Afirmaciones para decidir si son verdaderas o falsas, con explicación al corregir.",
              "va": "Afirmacions per a decidir si són vertaderes o falses, amb explicació en corregir.",
              "en": "Statements to decide whether they are true or false, with an explanation when corrected."},
             "statements: 1-30 afirmaciones {text, answer (booleano JSON true o false, nunca texto ni número), "
             "feedback (explicación obligatoria; si es falsa, aclara el hecho correcto), image y alt opcionales}. "
             "Mezcla afirmaciones verdaderas y falsas cuando haya varias. Evita trampas, dobles negaciones y "
             "afirmaciones ambiguas; cada una debe tratar una sola idea."),
    Template("huecos", "interactiva", GapsData, {"es": "Completar huecos", "va": "Omplir buits", "en": "Fill in the gaps"},
             {"es": "Completar frases con un banco de palabras o escribiendo la respuesta.",
              "va": "Completar frases amb un banc de paraules o escrivint la resposta.",
              "en": "Complete sentences with a word bank or by writing the answer."},
             "Conserva mode (bank = banco de palabras; text = escritura libre). items: 1-30 frases con "
             "{text (exactamente un hueco ___ por frase), answers (1-10 respuestas válidas, la primera se usa en "
             "el banco), feedback (explicación breve), image y alt opcionales}. No incluyas la solución en text. "
             "Se ignoran mayúsculas y espacios sobrantes, pero se respetan tildes y ñ."),
    Template("bateria", "interactiva", BatteryData,
             {"es": "Batería de ejercicios", "va": "Bateria d’exercicis", "en": "Exercise set"},
             {"es": "Varios ejercicios cortos en una sola actividad: opción múltiple, verdadero o falso y completar huecos.",
              "va": "Diversos exercicis curts en una sola activitat: opció múltiple, vertader o fals i omplir buits.",
              "en": "Several short exercises in one activity: multiple choice, true or false and fill in the gaps."},
             "blocks: 1-3 bloques sin repetir tipo, en este orden: choice, true_false, gap. "
             "choice: {type, heading, questions: 1-12 {text, options (2-6 textos), answer (índice desde 0), "
             "feedback, image y alt opcionales}}. true_false: {type, heading, statements: 1-12 {text, answer "
             "(booleano JSON true o false, nunca texto ni número), feedback obligatorio, image y alt opcionales}}. "
             "gap: {type, heading, mode (bank|text), items: 1-12 {text con exactamente un hueco ___ por frase, "
             "answers (1-10 respuestas válidas), feedback, image y alt opcionales}}. Genera 8-12 ítems en total, "
             "2-4 por bloque, con variedad y sin repetir ideas. Incluye solo los tipos elegidos y conserva mode del "
             "bloque de huecos. No inventes imágenes ni recursos."),
    Template("cuestionario", "interactiva", QuizData, {"es": "Cuestionario", "va": "Qüestionari", "en": "Quiz"},
             {"es": "Preguntas de opción única con corrección y explicación.",
              "va": "Preguntes d’opció única amb correcció i explicació.",
              "en": "Single-choice questions with correction and explanation."},
             "questions: lista de {text, options (2-6 textos), answer (índice de la correcta, empieza en 0), feedback "
             "(explicación breve), image y alt opcionales}. Varía la posición de la respuesta correcta."),
    Template("emparejar", "interactiva", MatchData, {"es": "Emparejar", "va": "Aparellar", "en": "Match"},
             {"es": "Relacionar cada elemento con su pareja (sin arrastrar, accesible con teclado).",
              "va": "Relacionar cada element amb la seua parella (sense arrossegar, accessible amb teclat).",
              "en": "Relate each item to its pair (no dragging, keyboard accessible)."},
             "pairs: lista de {left, right, image y alt opcionales}. Varias parejas pueden compartir el mismo right "
             "(por ejemplo, instrumentos de la misma familia); escribe ese right exactamente igual en todas."),
    Template("ordenar", "interactiva", OrderData, {"es": "Ordenar una secuencia", "va": "Ordenar una seqüència", "en": "Order a sequence"},
             {"es": "Poner en orden los pasos de un proceso, una historia o una línea del tiempo.",
              "va": "Posar en ordre els passos d’un procés, una història o una línia del temps.",
              "en": "Put the steps of a process, a story or a timeline in order."},
             "items: lista de {text, image y alt opcionales} EN EL ORDEN CORRECTO (la plantilla los desordena)."),
    Template("tarjetas", "interactiva", CardsData, {"es": "Tarjetas de repaso", "va": "Targetes de repàs", "en": "Revision cards"},
             {"es": "Tarjetas que se giran para repasar vocabulario o conceptos.",
              "va": "Targetes que es giren per a repassar vocabulari o conceptes.",
              "en": "Cards that flip over to revise vocabulary or concepts."},
             "cards: lista de {front (palabra o pregunta), back (definición o respuesta), image y alt opcionales}."),
    Template("clasificar", "interactiva", ClassifyData, {"es": "Clasificar", "va": "Classificar", "en": "Classify"},
             {"es": "Asignar cada elemento a su grupo o categoría.", "va": "Assignar cada element al seu grup o categoria.", "en": "Assign each item to its group or category."},
             "groups: 2-6 nombres de grupo; items: lista de {text, group (índice del grupo, empieza en 0), image y alt "
             "opcionales}. Reparte los elementos entre todos los grupos."),
    Template("lectura", "interactiva", ReadingData, {"es": "Lectura por partes", "va": "Lectura per parts", "en": "Reading in parts"},
             {"es": "Texto que se descubre sección a sección, con «Saber más» y preguntas de comprensión.",
              "va": "Text que es descobreix secció a secció, amb «Saber-ne més» i preguntes de comprensió.",
              "en": "Text revealed section by section, with “Learn more” and comprehension questions."},
             "sections: lista de {heading, text (párrafo breve), more (ampliación opcional), question opcional {text, "
             "options, answer (índice, empieza en 0), feedback}, image y alt opcionales}."),
    Template("infografia", "infografia", None, {"es": "Infografía", "va": "Infografia", "en": "Infographic"},
             {"es": "Infografía editable en HTML/SVG con iconos, exportable a PNG.",
              "va": "Infografia editable en HTML/SVG amb icones, exportable a PNG.",
              "en": "Editable HTML/SVG infographic with icons, exportable to PNG."}, ""),
    Template("ficha", "ficha", None, {"es": "Ficha imprimible", "va": "Fitxa imprimible", "en": "Printable worksheet"},
             {"es": "Documento para imprimir o exportar a PDF y DOCX: objetivo, recuerda, actividades y autoevaluación.",
              "va": "Document per a imprimir o exportar a PDF i DOCX: objectiu, recorda, activitats i autoavaluació.",
              "en": "Document to print or export to PDF and DOCX: objective, remember, activities and self-assessment."}, ""),
)}


GROUPS = {
    "bateria": "quick", "cuestionario": "quick", "verdadero_falso": "quick", "huecos": "quick",
    "sopa_letras": "games", "crucigrama": "games", "emparejar": "games", "ordenar": "games",
    "tarjetas": "games", "clasificar": "games",
    "lectura": "reading", "escucha": "reading",
    "infografia": "docs", "ficha": "docs",
}


def catalog() -> list[dict]:
    return [{"id": t.id, "kind": t.kind, "names": t.names, "descriptions": t.descriptions,
             "group": GROUPS.get(t.id, "docs")} for t in TEMPLATES.values()]


def get(template_id: str) -> Template:
    template = TEMPLATES.get(template_id)
    if template is None:
        raise HTTPException(404, "Plantilla no encontrada")
    return template


def data_js(data: dict) -> str:
    return "window.EDUCREA_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"


def parse_data(content: str) -> dict:
    match = DATA_PATTERN.match(content)
    if not match:
        raise ValueError("datos.js debe tener la forma window.EDUCREA_DATA = {...};")
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
    language = brief.get("language") if brief.get("language") in LABELS else "es"
    title = str(brief.get("title") or template.names[language]).strip()[:160]
    accessibility = brief.get("accessibility") if isinstance(brief.get("accessibility"), dict) else {}
    if template.kind == "ficha":
        sections = "\n\n".join(f"## {heading}\n\n" for heading in FICHA[language])
        return {"ficha.md": f"# {title}\n\n{sections}".rstrip() + "\n"}
    if template.kind != "interactiva":
        return {}  # the infographic is created by the web client from its own template
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    index = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    index = index.replace("{LANG}", "ca" if language == "va" else language).replace("{TITLE}", safe_title)
    common = {"title": title, "language": language,
              "accessibility": {"large_text": accessibility.get("large_text") is True,
                                "high_contrast": accessibility.get("high_contrast") is True},
              "labels": LABELS[language]}
    if template_id == "bateria":
        mix = brief.get("mix") if isinstance(brief.get("mix"), list) else []
        chosen = [kind for kind in ("choice", "true_false", "gap") if kind in mix] or ["choice", "true_false", "gap"]
        sample = SAMPLES["bateria"][language]
        blocks = []
        for block in sample["blocks"]:
            if block["type"] not in chosen:
                continue
            block = {**block}
            if block["type"] == "gap":
                block["mode"] = "text" if brief.get("gap_mode") == "text" else "bank"
            blocks.append(block)
        data = {**common, "instructions": sample["instructions"], "blocks": blocks}
    else:
        data = {**common, **SAMPLES[template_id][language]}
        if template_id == "huecos":
            data["mode"] = "text" if brief.get("gap_mode") == "text" else "bank"
    script = (TEMPLATE_DIR / f"{template_id}.js").read_text(encoding="utf-8")
    if template_id in ("sopa_letras", "crucigrama"):
        data["labels"] = {**LABELS[language], **PUZZLE_LABELS[language]}
        script = (TEMPLATE_DIR / "pasatiempos.js").read_text(encoding="utf-8") + "\n" + script
    return {"index.html": index,
            "style.css": (TEMPLATE_DIR / "style.css").read_text(encoding="utf-8"),
            "comun.js": (TEMPLATE_DIR / "comun.js").read_text(encoding="utf-8"),
            "script.js": script,
            DATA_PATH: data_js(data)}


def instruction(template_id: str, brief: dict, base: str) -> str:
    """Instruction for the first version of a project created from a template."""
    template = get(template_id)
    language = {"es": "castellano", "va": "valenciano (catalán)", "en": "inglés"}.get(brief.get("language"), "castellano")
    if template.kind == "interactiva":
        if template_id == "huecos":
            mode = "text" if brief.get("gap_mode") == "text" else "bank"
            base += f"\nModalidad elegida: mode={mode}. Conserva esta modalidad."
        if template_id == "bateria":
            mix = brief.get("mix") if isinstance(brief.get("mix"), list) else []
            chosen = [kind for kind in ("choice", "true_false", "gap") if kind in mix] or ["choice", "true_false", "gap"]
            names = {"choice": "opción múltiple", "true_false": "verdadero o falso", "gap": "completar huecos"}
            mode = "text" if brief.get("gap_mode") == "text" else "bank"
            base += (f"\nBloques elegidos: {', '.join(names[kind] for kind in chosen)}. "
                     f"Para el bloque de huecos, mode={mode}. Incluye solo esos bloques.")
        return (f"{base}\n\nEste proyecto usa la plantilla «{template.names['es']}». NO modifiques index.html, style.css, "
                f"comun.js ni script.js: son el motor accesible de la plantilla. Modifica SOLO {DATA_PATH} y devuelve su "
                "contenido completo con la forma exacta window.EDUCREA_DATA = {...}; donde {...} es JSON válido "
                "(comillas dobles, sin comentarios ni comas finales). Conserva language, accessibility y labels tal como "
                f"están; rellena title, instructions (consigna breve para el alumnado) y {template.guide} Escribe todo el "
                f"texto en {language}, adecuado al nivel educativo, claro y breve. Usa imágenes solo de available_images.")
    if template.kind == "ficha":
        headings = ", ".join(f"«{h}»" for h in FICHA.get(brief.get("language"), FICHA["es"]))
        return (f"{base}\n\nEste proyecto es una ficha imprimible. Modifica SOLO ficha.md: conserva el título y las "
                f"secciones de nivel 2 {headings} y rellénalas en {language}. En «Actividades» propone de 3 a 6 ejercicios "
                "numerados con espacio para responder (líneas ____ o tablas). Markdown limpio, sin HTML.")
    return (f"{base}\n\nEste proyecto es una infografía: modifica infografia.html conservando su estructura (HTML con "
            "SVG en línea, iconos ya incluidos y el aviso de licencia de Lucide), sin recursos externos.")


def check_proposal(template_id: str, changes: list, audio_resources: list[dict] | None = None,
                   brief: dict | None = None) -> dict:
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
            if template_id == "bateria" and brief and not problems:
                value = parse_data(data)
                mix = brief.get("mix") if isinstance(brief.get("mix"), list) else []
                chosen = [kind for kind in ("choice", "true_false", "gap") if kind in mix] or ["choice", "true_false", "gap"]
                types = [block.get("type") for block in value.get("blocks", []) if isinstance(block, dict)]
                extra = sorted({kind for kind in types if kind not in chosen})
                if extra:
                    problems.append("incluye bloques no elegidos: " + ", ".join(extra))
            if template_id == "escucha" and not problems:
                value = parse_data(data)
                audio = next((a for a in audio_resources or [] if a["path"] == value.get("audio")), None)
                if audio is None:
                    problems.append("elige un audio existente de la biblioteca del proyecto")
                elif value.get("transcript") != audio["transcript"]:
                    problems.append("conserva la transcripción o descripción revisada del audio sin modificarla")
    elif template.kind == "ficha" and "ficha.md" not in paths:
        problems.append("no modifica ficha.md")
    return {"mode": "template", "kind": "plantilla", "template": template_id, "sources": [], "passages_used": [],
            "citations": [], "verified": 0, "unverified": 0, "not_covered": [], "template_problems": problems,
            "supported": not problems}
