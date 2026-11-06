from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CredentialInput(BaseModel):
    api_key: SecretStr = Field(min_length=10, max_length=512)


class GeminiStatus(BaseModel):
    configured: bool
    verified_free_models: list[str]
    confirmed_free_models: list[str]


class FreeConfirmation(BaseModel):
    acknowledged: Literal[True]


class GenerateInput(BaseModel):
    instruction: str = Field(min_length=10, max_length=4000)
    provider: Literal["gemini", "openrouter", "groq", "ollama", "openai", "anthropic"] = "gemini"
    model: str = Field(min_length=1, max_length=100)
    context_paths: list[str] = Field(default_factory=list, max_length=30)
    automatic: bool = False  # the backend picks the context files; context_paths is ignored
    source_ids: list[UUID] = Field(default_factory=list, max_length=5)  # work only with these sources
    auto_apply: bool = False  # teacher mode: apply the proposal right away (still undoable and kept in history)
    allow_fallback: bool = False
    mode: Literal["free", "paid"] = "free"
    paid_authorized: bool = False
    approved_max_cost_microusd: int | None = Field(default=None, ge=0)
    approved_estimate_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class BudgetInput(BaseModel):
    monthly_limit_microusd: int = Field(ge=0)


class DraftChange(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str
    model_config = ConfigDict(extra="forbid")


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


class DuaInput(BaseModel):
    path: str = Field(min_length=1, max_length=200)  # the material to adapt (.html or .md)
    needs: str = Field(default="", max_length=1500)  # group needs or barriers the teacher already knows
    auto_apply: bool = False


class DraftProposal(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    changes: list[DraftChange] = Field(min_length=1, max_length=10)
    citations: list[Citation] = Field(default_factory=list, max_length=40)
    not_covered: list[str] = Field(default_factory=list, max_length=20)
    dua: DuaReport | None = None  # only for DUA adaptations
    model_config = ConfigDict(extra="forbid")


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
    model_config = ConfigDict(from_attributes=True)

