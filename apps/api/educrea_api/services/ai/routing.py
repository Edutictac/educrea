"""Replaceable task classification boundary, ready for a future EduPrompt Core adapter.

No network, billing, credentials, database sessions or gateway dependencies. Replacing get_router's
implementation changes classification without changing execution or accounting.
"""
from dataclasses import dataclass
from typing import Literal, Protocol

ModelRole = Literal["qwen", "deepseek"]


@dataclass(frozen=True)
class TaskContext:
    task_type: str = "unknown"
    output_type: str = ""
    generator_type: str = ""
    target_path: str = ""
    project_kind: str = ""
    template: str = ""

    @classmethod
    def from_project(cls, task_type="unknown", output_type="", generator_type="", path="", brief=None):
        # Convert project metadata into a provider-independent classification input.
        return cls(task_type, output_type, generator_type, path,
                   str((brief or {}).get("kind", "actividad")) if brief else "",
                   str((brief or {}).get("template") or ""))


class AIRouter(Protocol):
    def select(self, context: TaskContext) -> ModelRole: ...


class DeterministicRouter:
    code_tasks = frozenset({"code", "html", "css", "javascript", "interactive-app", "interactive-game",
                            "threejs", "programming", "debugging", "refactoring", "repair-code"})
    general_tasks = frozenset({"general", "material", "text", "explanation", "summary", "questions", "quiz",
                               "rubric", "adaptation", "translation", "json", "planning", "teacher-guide"})
    code_outputs = frozenset({"html", "css", "javascript", "js", "application"})

    def select(self, context: TaskContext) -> ModelRole:
        if (context.output_type.lower().lstrip('.') in self.code_outputs
                or context.generator_type in self.code_tasks or context.task_type in self.code_tasks):
            return "deepseek"
        if (context.task_type in self.general_tasks
                or context.output_type in {"markdown", "md", "json", "text"}):
            return "qwen"
        if context.template == "infografia":
            return "deepseek"
        # Template engines generate validated data, not application source.
        if context.template and (not context.target_path or context.target_path == "datos.js"):
            return "qwen"
        if context.target_path:
            return "deepseek" if context.target_path.lower().endswith((".html", ".css", ".js")) else "qwen"
        if context.project_kind in {"situacion", "ficha"}:
            return "qwen"
        if context.project_kind == "actividad":
            return "deepseek"
        return "qwen"


_router: AIRouter = DeterministicRouter()


def get_router() -> AIRouter:
    """Composition root: replace with an EduPrompt Core adapter implementing AIRouter when ready."""
    return _router
