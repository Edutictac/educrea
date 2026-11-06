import json
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AiCredential, AiProposal, ProjectFile, Source, User
from ..models.entities import utcnow
from ..security import current_user, require_csrf
from ..services.ai import agent, engine
from ..services.ai import quotas
from ..services.ai import pricing
from ..services.ai.credentials import encrypt_key, personal_credential
from ..services.ai.providers.base import ProviderError
from ..services.ai.providers.gemini import GeminiProvider, get_gemini_provider
from ..services.ai.providers import registry
from ..services.ai.schemas import (BudgetInput, CredentialInput, DuaInput, FreeConfirmation, GenerateInput,
                                   PreferredModel, ProposalOut)

router = APIRouter(tags=["ai"])


@router.get("/ai/quota")
def quota_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return quotas.summary(db, user.id)


@router.get("/ai/budget")
def budget_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return quotas.budget_summary(db, user.id)


@router.put("/ai/budget")
def update_budget(data: BudgetInput, user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> dict:
    return quotas.set_budget(db, user.id, data.monthly_limit_microusd)


@router.get("/ai/providers")
def providers_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {name: registry.status(db, user.id, name) for name in registry.PROVIDERS}


@router.get("/ai/providers/{provider_name}")
def provider_status(provider_name: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if provider_name not in registry.PROVIDERS:
        raise HTTPException(404, "Proveedor no encontrado")
    return registry.status(db, user.id, provider_name)


@router.put("/ai/providers/{provider_name}/key", status_code=204)
def save_provider_key(provider_name: str, data: CredentialInput, user: User = Depends(require_csrf),
                      db: Session = Depends(get_db)) -> None:
    if provider_name not in ("gemini", "openrouter", "groq", "mistral", "nvidia", "openai", "anthropic"):
        raise HTTPException(404, "Proveedor no encontrado")
    value = data.api_key.get_secret_value().strip()
    if len(value) < 10:
        raise HTTPException(422, "Clave no válida")
    credential = personal_credential(db, user.id, provider_name)
    if credential is None:
        db.add(AiCredential(user_id=user.id, provider=provider_name, ciphertext=encrypt_key(value),
                            free_confirmations={}))
    else:
        credential.ciphertext = encrypt_key(value)
        credential.free_confirmations = {}
    db.commit()


@router.post("/ai/providers/{provider_name}/free-models/{model:path}/confirm", status_code=204)
def confirm_provider_model(provider_name: str, model: str, data: FreeConfirmation,
                           user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> None:
    if provider_name not in ("gemini", "openrouter", "groq", "mistral", "nvidia") or model not in registry.free_models(provider_name):
        raise HTTPException(403, "Modelo no autorizado en modo gratuito")
    credential = personal_credential(db, user.id, provider_name)
    if credential is None:
        raise HTTPException(409, "Configura tu clave antes de confirmar")
    credential.free_confirmations = {**credential.free_confirmations, model: utcnow().isoformat()}
    db.commit()


@router.delete("/ai/providers/{provider_name}/key", status_code=204)
def revoke_provider_key(provider_name: str, user: User = Depends(require_csrf),
                        db: Session = Depends(get_db)) -> None:
    if provider_name not in ("gemini", "openrouter", "groq", "mistral", "nvidia", "openai", "anthropic"):
        raise HTTPException(404, "Proveedor no encontrado")
    credential = personal_credential(db, user.id, provider_name)
    if credential:
        db.delete(credential)
        db.commit()


@router.get("/projects/{project_id}/ai/proposals", response_model=list[ProposalOut])
def list_proposals(project_id: UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> list[AiProposal]:
    from .projects import project_for_owner

    project_for_owner(db, project_id, user.id)
    return list(db.scalars(select(AiProposal).where(AiProposal.project_id == project_id,
                                                    AiProposal.user_id == user.id)
                           .order_by(AiProposal.created_at.desc()).limit(30)))


@router.get("/projects/{project_id}/ai/proposals/{proposal_id}", response_model=ProposalOut)
def get_proposal(project_id: UUID, proposal_id: UUID, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> AiProposal:
    return engine.proposal_for_owner(db, project_id, proposal_id, user.id)


@router.post("/projects/{project_id}/ai/estimate")
def estimate_paid(project_id: UUID, data: GenerateInput, user: User = Depends(require_csrf),
                  db: Session = Depends(get_db)) -> dict:
    if data.mode != "paid":
        raise HTTPException(422, "La estimación requiere un modelo de pago")
    _, prompt, _, _, _ = engine.prepare(db, project_id, user.id, data)
    price = pricing.price_for(data.provider, data.model)
    return {"provider": data.provider, "model": data.model,
            **pricing.estimate(prompt, price), "fingerprint": estimate_fingerprint(data, prompt, price)}


def estimate_fingerprint(data: GenerateInput, prompt: str, price: pricing.Price) -> str:
    value = json.dumps({"provider": data.provider, "model": data.model, "prompt": prompt,
                        "input_rate": price.input_rate, "output_rate": price.output_rate},
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(value.encode()).hexdigest()


def paid_terms(data: GenerateInput, prompt: str) -> tuple[int, pricing.Price | None, int]:
    if data.mode == "free":
        return 0, None, quotas.RESERVED_TOKENS
    price = pricing.price_for(data.provider, data.model)
    estimate = pricing.estimate(prompt, price)
    maximum = estimate["maximum_cost_microusd"]
    if (not data.paid_authorized or data.approved_max_cost_microusd != maximum or
            data.approved_estimate_fingerprint != estimate_fingerprint(data, prompt, price)):
        raise HTTPException(403, "Confirma la estimación actual antes de usar un modelo de pago")
    return maximum, price, estimate["max_input_tokens"] + estimate["max_output_tokens"]


async def consult(db: Session, user_id: UUID, project_id: UUID, data: GenerateInput, adapter, key: str, name: str,
                  model: str, prompt: str, snapshot: dict, selected: set[str]) -> tuple[str, set[str], list[dict]]:
    """Optional consultation step (free automatic mode): the model asks for capabilities, the backend runs the
    read-only ones and adds their results to the prompt. A failed consultation never blocks the generation."""
    if not agent.should_consult(data, snapshot, selected):
        return prompt, selected, []
    tools = agent.tools_for_prompt()
    reservation = quotas.reserve(db, user_id, name, model)
    try:
        result = await adapter.generate(key, model, agent.consult_prompt(prompt, tools))
    except ProviderError:
        db.rollback()
        quotas.reconcile(db, reservation, failed=True)
        return prompt, selected, []
    quotas.reconcile(db, reservation, result.usage)
    calls = agent.parse_round(result.text)
    if not calls:
        return prompt, selected, []
    addition, trace, selected = agent.execute(db, user_id, project_id, calls, tools, snapshot, selected)
    db.rollback()
    return prompt + addition, selected, trace


@router.post("/projects/{project_id}/ai/proposals", response_model=ProposalOut, status_code=201)
async def generate_proposal(project_id: UUID, data: GenerateInput,
                            user: User = Depends(require_csrf), db: Session = Depends(get_db),
                            provider: GeminiProvider = Depends(get_gemini_provider)) -> AiProposal:
    user_id = user.id
    key, prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)
    maximum_cost, price, maximum_tokens = paid_terms(data, prompt)
    name, model = data.provider, data.model
    prompt, selected, trace = await consult(db, user_id, project_id, data,
                                            provider if name == "gemini" else registry.adapter(name),
                                            key, name, model, prompt, snapshot, selected)
    used = {name}
    while True:
        reservation = quotas.reserve(db, user_id, name, model, maximum_cost, price, maximum_tokens)
        try:
            adapter = provider if name == "gemini" else registry.adapter(name)
            result = await adapter.generate(key, model, prompt)
            proposal = engine.persist(db, project_id, user_id, model, result.text, result.usage,
                                      snapshot, selected, provider=name, source_ids=data.source_ids,
                                      passages_used=passages, agent_trace=trace)
            quotas.reconcile(db, reservation, result.usage)
            return engine.apply_if_requested(db, project_id, proposal, data.auto_apply)
        except ProviderError as exc:
            db.rollback()
            quotas.reconcile(db, reservation, failed=True)
            alternative = (registry.fallback(db, user_id, used)
                           if data.mode == "free" and exc.status_code in (429, 503, 504) and data.allow_fallback else None)
            if alternative is None:
                raise HTTPException(exc.status_code, str(exc)) from exc
            name, model, key = alternative
            used.add(name)
            db.rollback()
        except BaseException:
            db.rollback()
            quotas.reconcile(db, reservation, failed=True)
            raise


@router.post("/projects/{project_id}/ai/from-brief", response_model=ProposalOut, status_code=201)
async def generate_from_brief(project_id: UUID, choice: PreferredModel | None = None,
                              user: User = Depends(require_csrf), db: Session = Depends(get_db),
                              provider: GeminiProvider = Depends(get_gemini_provider)) -> AiProposal:
    """Teacher mode shortcut: builds the instruction from activity.json and applies the first version."""
    user_id = user.id
    brief = engine.read_brief(db, project_id)
    if brief is None:
        raise HTTPException(409, "Guarda primero el encargo de la actividad (activity.json)")
    source_ids = list(db.scalars(select(Source.id).where(Source.project_id == project_id).order_by(Source.created_at)))
    instruction = engine.instruction_for(brief)
    if source_ids:
        instruction += engine.MATERIAL_INSTRUCTION
    return await generate_with_first_free(db, project_id, user_id, provider, instruction, True, source_ids=source_ids,
                                          choice=choice)


@router.post("/projects/{project_id}/ai/dua", response_model=ProposalOut, status_code=201)
async def adapt_dua(project_id: UUID, data: DuaInput, user: User = Depends(require_csrf),
                    db: Session = Depends(get_db),
                    provider: GeminiProvider = Depends(get_gemini_provider)) -> AiProposal:
    """Reviews one material with the UDL principles and proposes an adapted version plus a barrier/measure report.

    Teacher mode applies it (undoable); a report missing a principle, or one that leaves the material unchanged,
    always waits for review."""
    from .projects import project_for_owner

    user_id = user.id
    project_for_owner(db, project_id, user_id)
    if not (data.path.lower().endswith(engine.DUA_EXTENSIONS) or data.path == engine.template_service.DATA_PATH):
        raise HTTPException(422, "Solo se pueden adaptar actividades HTML o documentos Markdown")
    exists = db.scalar(select(ProjectFile.id).where(ProjectFile.project_id == project_id,
                                                    ProjectFile.path == data.path))
    if exists is None:
        raise HTTPException(404, "Archivo no encontrado")
    language = str((engine.read_brief(db, project_id) or {}).get("language") or "") or None
    instruction = engine.dua_instruction(data.path, data.needs, language)
    return await generate_with_first_free(db, project_id, user_id, provider, instruction, data.auto_apply,
                                          dua_target=data.path, choice=data)


async def generate_with_first_free(db: Session, project_id: UUID, user_id: UUID, provider: GeminiProvider,
                                   instruction: str, auto_apply: bool, dua_target: str | None = None,
                                   source_ids: list[UUID] | None = None,
                                   choice: PreferredModel | None = None) -> AiProposal:
    """One generation with the AI picked in the selector (or the first confirmed free one); the backend chooses
    the context files and falls back to the next free AI if the chosen one is saturated."""
    available = registry.preferred_free(db, user_id, choice.provider if choice else None, choice.model if choice else None)
    if available is None:
        raise HTTPException(409, "Configura un proveedor gratuito y confirma un modelo antes de generar")
    name, model, key = available
    # Built by the backend (brief + template rules + material), so the 4000-character limit for text typed in the
    # assistant does not apply; model_construct keeps the other defaults.
    data = engine.GenerateInput.model_construct(
        **{**engine.GenerateInput.model_construct().model_dump(), "instruction": instruction, "provider": name,
           "model": model, "automatic": True, "auto_apply": auto_apply, "mode": "free",
           "source_ids": source_ids or [], "whole_sources": bool(source_ids)})
    prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)[1:]
    adapter = provider if name == "gemini" else registry.adapter(name)
    prompt, selected, trace = await consult(db, user_id, project_id, data, adapter, key, name, model, prompt,
                                            snapshot, selected)
    used = {name}
    while True:
        reservation = quotas.reserve(db, user_id, name, model)
        try:
            result = await adapter.generate(key, model, prompt)
            proposal = engine.persist(db, project_id, user_id, model, result.text, result.usage, snapshot, selected,
                                      provider=name, dua_target=dua_target, agent_trace=trace,
                                      source_ids=source_ids or None, passages_used=passages)
            quotas.reconcile(db, reservation, result.usage)
            return engine.apply_if_requested(db, project_id, proposal, auto_apply)
        except ProviderError as exc:
            db.rollback()
            quotas.reconcile(db, reservation, failed=True)
            # Saturated or out of quota: try the teacher's next confirmed free provider (only free ones).
            alternative = registry.fallback(db, user_id, used) if exc.status_code in (429, 503, 504) else None
            if alternative is None:
                raise HTTPException(exc.status_code, str(exc)) from exc
            name, model, key = alternative
            used.add(name)
            adapter = provider if name == "gemini" else registry.adapter(name)
        except BaseException:
            db.rollback()
            quotas.reconcile(db, reservation, failed=True)
            raise


@router.post("/projects/{project_id}/ai/proposals/stream")
async def stream_proposal(project_id: UUID, data: GenerateInput,
                          user: User = Depends(require_csrf), db: Session = Depends(get_db),
                          provider: GeminiProvider = Depends(get_gemini_provider)) -> StreamingResponse:
    user_id = user.id
    key, prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)
    maximum_cost, price, maximum_tokens = paid_terms(data, prompt)

    def event(name: str, value: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"

    async def events():
        name, model, credential = data.provider, data.model, key
        final_prompt, allowed, trace = prompt, selected, []
        if agent.should_consult(data, snapshot, selected):
            yield event("status", {"stage": "consulting", "provider": name, "model": model})
            try:
                final_prompt, allowed, trace = await consult(
                    db, user_id, project_id, data, provider if name == "gemini" else registry.adapter(name),
                    credential, name, model, prompt, snapshot, selected)
            except HTTPException as exc:
                yield event("error", {"status_code": exc.status_code, "message": exc.detail})
                return
            if trace:
                yield event("consulted", {"capabilities": trace})
        used = {name}
        while True:
            parts: list[str] = []
            response_bytes = 0
            usage: dict = {}
            reservation = None
            yield event("status", {"stage": "generating", "provider": name, "model": model})
            try:
                reservation = quotas.reserve(db, user_id, name, model, maximum_cost, price, maximum_tokens)
                adapter = provider if name == "gemini" else registry.adapter(name)
                async for chunk in adapter.stream(credential, model, final_prompt):
                    if chunk.text:
                        parts.append(chunk.text)
                        response_bytes += len(chunk.text.encode())
                        if response_bytes > engine.MAX_RESPONSE_BYTES:
                            raise HTTPException(502, "El proveedor devolvió una propuesta demasiado grande")
                        yield event("token", {"text": chunk.text})
                    if chunk.usage:
                        usage = chunk.usage
                proposal = engine.persist(db, project_id, user_id, model, "".join(parts), usage,
                                          snapshot, allowed, provider=name, source_ids=data.source_ids,
                                          passages_used=passages, agent_trace=trace)
                quotas.reconcile(db, reservation, usage)
                proposal = engine.apply_if_requested(db, project_id, proposal, data.auto_apply)
                yield event("proposal", ProposalOut.model_validate(proposal).model_dump(mode="json"))
                return
            except (ProviderError, HTTPException) as exc:
                db.rollback()
                if reservation:
                    quotas.reconcile(db, reservation, usage, failed=True)
                alternative = (registry.fallback(db, user_id, used)
                               if data.mode == "free" and isinstance(exc, ProviderError) and exc.status_code in (429, 503, 504)
                               and data.allow_fallback and not parts else None)
                if alternative:
                    name, model, credential = alternative
                    used.add(name)
                    db.rollback()
                    continue
                message = exc.detail if isinstance(exc, HTTPException) else str(exc)
                yield event("error", {"status_code": exc.status_code, "message": message})
                return
            finally:
                if reservation:
                    db.rollback()
                    quotas.reconcile(db, reservation, usage, failed=True)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/projects/{project_id}/ai/proposals/{proposal_id}/apply", response_model=ProposalOut)
def apply_proposal(project_id: UUID, proposal_id: UUID, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> AiProposal:
    return engine.apply(db, project_id, proposal_id, user.id)


@router.post("/projects/{project_id}/ai/proposals/{proposal_id}/reject", response_model=ProposalOut)
def reject_proposal(project_id: UUID, proposal_id: UUID, user: User = Depends(require_csrf),
                    db: Session = Depends(get_db)) -> AiProposal:
    return engine.reject(db, project_id, proposal_id, user.id)


@router.post("/projects/{project_id}/ai/proposals/{proposal_id}/restore", response_model=ProposalOut)
def restore_proposal(project_id: UUID, proposal_id: UUID, user: User = Depends(require_csrf),
                     db: Session = Depends(get_db)) -> AiProposal:
    return engine.restore(db, project_id, proposal_id, user.id)

