from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class CredentialInput(BaseModel):
    api_key: SecretStr = Field(min_length=10, max_length=512)


class GeminiStatus(BaseModel):
    configured: bool
    verified_free_models: list[str]
    confirmed_free_models: list[str]


class FreeConfirmation(BaseModel):
    acknowledged: Literal[True]


class GenerateInput(BaseModel):
    task_type: str = Field(default="unknown", max_length=60)
    output_type: str = Field(default="", max_length=40)
    generator_type: str = Field(default="", max_length=60)
    instruction: str = Field(min_length=10, max_length=4000)
    provider: Literal["gemini", "mistral", "openrouter", "groq", "ollama", "openai", "anthropic", "deepseek", "educrea"] = "gemini"
    model: str = Field(default="", max_length=100)
    context_paths: list[str] = Field(default_factory=list, max_length=30)
    automatic: bool = False  # the backend picks the context files; context_paths is ignored
    source_ids: list[UUID] = Field(default_factory=list, max_length=5)  # work only with these sources
    auto_apply: bool = False  # teacher mode: apply the proposal right away (still undoable and kept in history)
    whole_sources: bool = False  # send the whole material when it fits (content created from the teacher's material)
    allow_fallback: bool = False
    mode: Literal["free", "paid", "included"] = "free"
    paid_authorized: bool = False
    approved_max_cost_microusd: int | None = Field(default=None, ge=0)
    approved_estimate_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def require_byok_model(self):
        if self.mode != "included" and not self.model:
            raise ValueError("Indica el modelo de tu API propia")
        return self


class BudgetInput(BaseModel):
    monthly_limit_microusd: int = Field(ge=0)


class DraftChange(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str
    # Models sometimes copy the «version» field from the project context. Path and content are validated
    # anyway, so unknown keys are ignored instead of rejecting an otherwise valid proposal.
    model_config = ConfigDict(extra="ignore")


class Citation(BaseModel):
    quote: str = Field(min_length=1, max_length=800)
    chunk: str = Field(default="", max_length=20)
    used_for: str = Field(default="", max_length=300)
    model_config = ConfigDict(extra="ignore")


DuaPrinciple = Literal["representacion", "accion_expresion", "implicacion"]


class DuaMeasure(BaseModel):
    principle: DuaPrinciple
    barrier: str = Field(default="", max_length=400)
    measure: str = Field(min_length=1, max_length=600)
    model_config = ConfigDict(extra="ignore")


class DuaReport(BaseModel):
    barriers: list[str] = Field(default_factory=list, max_length=20)
    measures: list[DuaMeasure] = Field(default_factory=list, max_length=30)
    model_config = ConfigDict(extra="ignore")


class PreferredModel(BaseModel):
    """The AI chosen in the project selector; both empty means «Automática» (first confirmed free model)."""
    provider: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=100)


class SectionsInput(PreferredModel):
    """Write or develop a learning situation section by section. Empty sections = all nine, in order."""
    sections: list[str] = Field(default_factory=list, max_length=9)
    request: str = Field(default="", max_length=1500)  # e.g. «desarrolla más la evaluación»
    auto_apply: bool = True


class DuaInput(PreferredModel):
    path: str = Field(min_length=1, max_length=200)  # the material to adapt (.html or .md)
    needs: str = Field(default="", max_length=1500)  # group needs or barriers the teacher already knows
    auto_apply: bool = False


class DraftProposal(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    changes: list[DraftChange] = Field(min_length=1, max_length=10)
    citations: list[Citation] = Field(default_factory=list, max_length=40)
    not_covered: list[str] = Field(default_factory=list, max_length=20)
    dua: DuaReport | None = None  # only for DUA adaptations
    tool_calls: list[dict] = Field(default_factory=list, max_length=10)  # ignored here; see ToolRound
    # Free models often add keys they copied from the context. They are ignored (path and content are validated).
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _tolerate_common_shapes(cls, data):
        """Salvage two frequent mistakes: citations nested in a change and not_covered sent as a plain string."""
        if isinstance(data, dict):
            changes = data.get("changes")
            nested: list = []
            if isinstance(changes, list):
                for change in changes:
                    if isinstance(change, dict):
                        value = change.get("citations")
                        if isinstance(value, list):
                            nested.extend(value)
            if nested:
                top = data.get("citations")
                data["citations"] = (top if isinstance(top, list) else []) + nested
            if isinstance(data.get("not_covered"), str):
                text = data["not_covered"].strip()
                data["not_covered"] = [text] if text else []
        return data


class ToolCall(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    arguments_json: str = Field(default="{}", max_length=16 * 1024)
    model_config = ConfigDict(extra="ignore")


class ToolRound(BaseModel):
    """Answer of the consultation step: capabilities the model wants before writing the proposal."""
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=10)
    model_config = ConfigDict(extra="ignore")


class ProposalChangeOut(BaseModel):
    path: str
    before_content: str | None
    after_content: str
    base_version: int


class ProposalOut(BaseModel):
    id: UUID
    project_id: UUID
    provider: str
    model: str
    summary: str
    changes: list[ProposalChangeOut]
    status: Literal["pending", "applied", "rejected", "restored"]
    usage: dict
    created_at: datetime
    applied_at: datetime | None
    grounding: dict | None = None
    agent_trace: list[dict] | None = None
    model_config = ConfigDict(from_attributes=True)



class WaitlistInput(BaseModel):
    teaching_context: str = Field(min_length=2, max_length=300)
    intended_use: str = Field(min_length=10, max_length=1000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("teaching_context", "intended_use", mode="before")
    @classmethod
    def trim_fields(cls, value):
        return value.strip() if isinstance(value, str) else value
