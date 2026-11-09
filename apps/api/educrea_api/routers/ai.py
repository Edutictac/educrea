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
from ..services.ai import agent, engine, sections as section_service
from ..services import sources as source_service
from ..services.ai import quotas
from ..services.ai import pricing
from ..services.ai import included, videos
from ..services.ai.routing import TaskContext, get_router
from ..services.ai.credentials import encrypt_key, personal_credential
from ..services.ai.providers.base import ProviderError
from ..services.ai.providers.gemini import GeminiProvider, get_gemini_provider
from ..services.ai.providers import registry
from ..services.ai.schemas import (BudgetInput, CredentialInput, DuaInput, FreeConfirmation, GenerateInput,
                                   PreferredModel, ProposalOut, SectionsInput, WaitlistInput)

router = APIRouter(tags=["ai"])


@router.get("/ai/included")
def included_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    user_id = user.id
    result = included.summary(db, user_id)
    # An unavailable optional media catalog must not hide the account's text quota.
    for name, load in (("images", included.image_status), ("videos", videos.quota_status)):
        try:
            result[name] = load(db, user_id)
        except HTTPException:
            result[name] = None
    return result


@router.get("/ai/included/history")
def included_history(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    return included.history(db, user.id)


@router.get("/ai/included/waitlist")
def waitlist_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return included.access.waitlist_status(db, user.id)


@router.post("/ai/included/waitlist")
def join_waitlist(data: WaitlistInput, user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> dict:
    return included.access.join_waitlist(db, user.id, data.teaching_context, data.intended_use)


def wants_included(db, user_id, choice=None):
    # Explicit BYOK stays BYOK, even when the included service is paused.
    return (choice is not None and choice.provider == "educrea") or (
        (choice is None or not choice.provider) and included.get_settings().free_ai_enabled
        and included.access.status(db, user_id) == "invited")


def included_request(instruction, auto_apply, source_ids=None):
    return GenerateInput.model_construct(instruction=instruction, provider="educrea", model="",
        mode="included", automatic=True, auto_apply=auto_apply, source_ids=source_ids or [],
        whole_sources=bool(source_ids))


async def included_events(db, project_id, user_id, data, *, dua_target=None):
    try:
        # Same context, structured output, ownership, proposal history and apply/undo as BYOK.
        _, prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)
        brief = engine.read_brief(db, project_id)
        path = dua_target or (data.context_paths[0] if len(data.context_paths) == 1 else "")
        chosen = get_router().select(TaskContext.from_project(data.task_type, data.output_type, data.generator_type, path, brief))
    except HTTPException as exc:
        yield _sse("error", {"status_code": exc.status_code, "message": exc.detail, "provider": "educrea"})
        return

    def finish(content, _usage):
        return engine.persist(db, project_id, user_id, "", content, {}, snapshot, selected,
            provider="educrea", source_ids=data.source_ids, passages_used=passages, dua_target=dua_target)

    try:
        async for name, value in included.run(db, user_id, chosen, prompt, finish, task_type=data.task_type):
            if name == "result":
                proposal = engine.apply_if_requested(db, project_id, value, data.auto_apply)
                yield _sse("proposal", ProposalOut.model_validate(proposal).model_dump(mode="json"))
            else:
                yield _sse(name, value)
    except HTTPException as exc:
        yield _sse("error", {"status_code": exc.status_code, "message": exc.detail, "provider": "educrea"})


async def included_proposal(db, project_id, user_id, data, *, dua_target=None):
    _, prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)
    chosen = get_router().select(TaskContext.from_project(data.task_type, data.output_type, data.generator_type,
        dua_target or (data.context_paths[0] if len(data.context_paths) == 1 else ""),
        engine.read_brief(db, project_id)))

    def finish(content, _usage):
        return engine.persist(db, project_id, user_id, "", content, {}, snapshot, selected,
            provider="educrea", source_ids=data.source_ids, passages_used=passages, dua_target=dua_target)

    async for name, value in included.run(db, user_id, chosen, prompt, finish,
                                         task_type=data.task_type, streaming=False):
        if name == "result":
            return engine.apply_if_requested(db, project_id, value, data.auto_apply)


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
    if user.is_guest:
        raise HTTPException(403, "Regístrate para guardar claves de API. Sin cuenta puedes usarlas de forma temporal.")
    if provider_name not in ("gemini", "openrouter", "groq", "mistral", "openai", "anthropic", "deepseek"):
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
    if user.is_guest:
        raise HTTPException(403, "Regístrate para guardar claves de API. Sin cuenta puedes usarlas de forma temporal.")
    if provider_name not in ("gemini", "openrouter", "groq") or model not in registry.free_models(provider_name):
        raise HTTPException(403, "Modelo no autorizado en modo gratuito")
    credential = personal_credential(db, user.id, provider_name)
    if credential is None:
        raise HTTPException(409, "Configura tu clave antes de confirmar")
    credential.free_confirmations = {**credential.free_confirmations, model: utcnow().isoformat()}
    db.commit()


@router.delete("/ai/providers/{provider_name}/free-models/{model:path}/confirm", status_code=204)
def disable_provider_model(provider_name: str, model: str, user: User = Depends(require_csrf),
                           db: Session = Depends(get_db)) -> None:
    """Stop using a confirmed free model (e.g. the key now has billing): «IA automática» skips it from now on."""
    if user.is_guest:
        raise HTTPException(403, "Sin cuenta la confirmación es temporal: se desactiva en tu navegador.")
    credential = personal_credential(db, user.id, provider_name)
    if credential is None or model not in credential.free_confirmations:
        return  # idempotent: already disabled
    credential.free_confirmations = {k: v for k, v in credential.free_confirmations.items() if k != model}
    db.commit()


@router.delete("/ai/providers/{provider_name}/key", status_code=204)
def revoke_provider_key(provider_name: str, user: User = Depends(require_csrf),
                        db: Session = Depends(get_db)) -> None:
    if user.is_guest:
        raise HTTPException(403, "Regístrate para guardar claves de API. Sin cuenta puedes usarlas de forma temporal.")
    if provider_name not in ("gemini", "openrouter", "groq", "mistral", "openai", "anthropic", "deepseek"):
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


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ProviderError):
        if exc.truncated:
            return "provider_truncated"
        if exc.status_code == 429:
            return "provider_quota"
        if exc.status_code in (503, 504):
            return "provider_busy"
        return "provider_error"
    if isinstance(exc, HTTPException) and exc.status_code == 502:
        return "provider_invalid"
    return "ai_error"


def _retry_skips(exc: Exception, name: str, model: str, skip_providers: set[str],
                 skip_models: set[tuple[str, str]]) -> bool:
    """Whether another free attempt can help. Truncated or invalid drafts skip only that model;
    quota, saturation or communication failures skip the whole provider."""
    if isinstance(exc, HTTPException):
        if exc.status_code != 502:
            return False
        skip_models.add((name, model))
        return True
    if getattr(exc, "truncated", False):
        skip_models.add((name, model))
        return True
    if exc.status_code in (429, 500, 502, 503, 504):
        skip_providers.add(name)
        return True
    return False


@router.post("/projects/{project_id}/ai/proposals", response_model=ProposalOut, status_code=201)
async def generate_proposal(project_id: UUID, data: GenerateInput,
                            user: User = Depends(require_csrf), db: Session = Depends(get_db),
                            provider: GeminiProvider = Depends(get_gemini_provider)) -> AiProposal:
    user_id = user.id
    if data.mode == "included":
        return await included_proposal(db, project_id, user_id, data)
    key, prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)
    maximum_cost, price, maximum_tokens = paid_terms(data, prompt)
    name, model = data.provider, data.model
    prompt, selected, trace = await consult(db, user_id, project_id, data,
                                            provider if name == "gemini" else registry.adapter(name),
                                            key, name, model, prompt, snapshot, selected)
    skip_providers: set[str] = set()
    skip_models: set[tuple[str, str]] = set()
    while True:
        reservation = quotas.reserve(db, user_id, name, model, maximum_cost, price, maximum_tokens)
        result = None
        try:
            adapter = provider if name == "gemini" else registry.adapter(name)
            result = await adapter.generate(key, model, prompt)
            proposal = engine.persist(db, project_id, user_id, model, result.text, result.usage,
                                      snapshot, selected, provider=name, source_ids=data.source_ids,
                                      passages_used=passages, agent_trace=trace)
            quotas.reconcile(db, reservation, result.usage)
            return engine.apply_if_requested(db, project_id, proposal, data.auto_apply)
        except (ProviderError, HTTPException) as exc:
            db.rollback()
            quotas.reconcile(db, reservation, result.usage if result else None, failed=True)
            rescued = (engine.salvage(db, project_id, user_id, model, name, result.text, snapshot, selected, result.usage)
                       if result is not None else None)
            if rescued is not None:
                return rescued  # keep the long work for review instead of starting again elsewhere
            retryable = _retry_skips(exc, name, model, skip_providers, skip_models)
            alternative = (registry.next_free(db, user_id, skip_providers, skip_models, prefer_provider=name)
                           if data.mode == "free" and retryable and data.allow_fallback else None)
            if alternative is None:
                if isinstance(exc, HTTPException):
                    raise
                raise HTTPException(exc.status_code, str(exc)) from exc
            name, model, key = alternative
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
    instruction, source_ids = brief_request(db, project_id)
    return await generate_with_first_free(db, project_id, user_id, provider, instruction, True, source_ids=source_ids,
                                          choice=choice)


@router.post("/projects/{project_id}/ai/dua", response_model=ProposalOut, status_code=201)
async def adapt_dua(project_id: UUID, data: DuaInput, user: User = Depends(require_csrf),
                    db: Session = Depends(get_db),
                    provider: GeminiProvider = Depends(get_gemini_provider)) -> AiProposal:
    """Reviews one material with the UDL principles and proposes an adapted version plus a barrier/measure report.

    Teacher mode applies it (undoable); a report missing a principle, or one that leaves the material unchanged,
    always waits for review."""
    user_id = user.id
    instruction = dua_request(db, project_id, user_id, data)
    return await generate_with_first_free(db, project_id, user_id, provider, instruction, data.auto_apply,
                                          dua_target=data.path, choice=data)


async def generate_with_first_free(db: Session, project_id: UUID, user_id: UUID, provider: GeminiProvider,
                                   instruction: str, auto_apply: bool, dua_target: str | None = None,
                                   source_ids: list[UUID] | None = None,
                                   choice: PreferredModel | None = None) -> AiProposal:
    """One generation with the AI picked in the selector (or the first confirmed free one); the backend chooses
    the context files and falls back to the next free AI if the chosen one is saturated."""
    if wants_included(db, user_id, choice):
        return await included_proposal(db, project_id, user_id,
            included_request(instruction, auto_apply, source_ids), dua_target=dua_target)
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
    skip_providers: set[str] = set()
    skip_models: set[tuple[str, str]] = set()
    while True:
        reservation = quotas.reserve(db, user_id, name, model)
        result = None
        try:
            result = await adapter.generate(key, model, prompt)
            proposal = engine.persist(db, project_id, user_id, model, result.text, result.usage, snapshot, selected,
                                      provider=name, dua_target=dua_target, agent_trace=trace,
                                      source_ids=source_ids or None, passages_used=passages)
            quotas.reconcile(db, reservation, result.usage)
            return engine.apply_if_requested(db, project_id, proposal, auto_apply)
        except (ProviderError, HTTPException) as exc:
            db.rollback()
            quotas.reconcile(db, reservation, result.usage if result else None, failed=True)
            rescued = (engine.salvage(db, project_id, user_id, model, name, result.text, snapshot, selected, result.usage)
                       if result is not None and not dua_target else None)
            if rescued is not None:
                return rescued
            # Saturated, out of quota, truncated or an unusable draft: with «IA automática» try the teacher's next
            # free model; an AI chosen explicitly in the selector is respected and the teacher decides.
            explicit = bool(choice and choice.provider and choice.model)
            retryable = _retry_skips(exc, name, model, skip_providers, skip_models)
            alternative = (registry.next_free(db, user_id, skip_providers, skip_models, prefer_provider=name)
                           if retryable and not explicit else None)
            if alternative is None and explicit and retryable:
                label = engine.PROVIDER_LABELS.get(name, name)
                raise HTTPException(exc.status_code, f"{label} ({model}) no ha podido responder ahora (saturada, sin cuota "
                                    "o con una respuesta no válida). Elige otra IA o «IA automática» en el selector y "
                                    "vuelve a intentarlo.") from exc
            if alternative is None:
                if isinstance(exc, HTTPException):
                    raise
                raise HTTPException(exc.status_code, str(exc)) from exc
            name, model, key = alternative
            adapter = provider if name == "gemini" else registry.adapter(name)
        except BaseException:
            db.rollback()
            quotas.reconcile(db, reservation, failed=True)
            raise


def _sse(name: str, value: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"


def _streaming(events) -> StreamingResponse:
    return StreamingResponse(events, media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


async def ai_events(db: Session, project_id: UUID, user_id: UUID, data: GenerateInput, provider: GeminiProvider,
                    key: str, prompt: str, snapshot: dict, selected: set[str], passages: list[dict],
                    maximum_cost: int = 0, price=None, maximum_tokens: int = quotas.RESERVED_TOKENS,
                    dua_target: str | None = None):
    """Server-sent events of one generation: consultation, generation with real stages, automatic switch to the next
    free AI when allowed, rescue of cut documents and the final proposal (applied when requested)."""
    event = _sse
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
    skip_providers: set[str] = set()
    skip_models: set[tuple[str, str]] = set()
    while True:
        parts: list[str] = []
        response_bytes = 0
        usage: dict = {}
        reservation = None
        yield event("status", {"stage": "generating", "provider": name, "model": model,
                               "passages": len(passages), "retry": bool(skip_providers or skip_models)})
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
                                      passages_used=passages, agent_trace=trace, dua_target=dua_target)
            quotas.reconcile(db, reservation, usage)
            proposal = engine.apply_if_requested(db, project_id, proposal, data.auto_apply)
            yield event("proposal", ProposalOut.model_validate(proposal).model_dump(mode="json"))
            return
        except (ProviderError, HTTPException) as exc:
            db.rollback()
            if reservation:
                quotas.reconcile(db, reservation, usage, failed=True)
            discard = ((isinstance(exc, ProviderError) and exc.truncated)
                       or (isinstance(exc, HTTPException) and exc.status_code == 502))
            rescued = (engine.salvage(db, project_id, user_id, model, name, "".join(parts), snapshot, allowed, usage)
                       if discard and parts and not dua_target else None)
            if rescued is not None:
                reservation = None
                yield event("proposal", ProposalOut.model_validate(rescued).model_dump(mode="json"))
                return
            retryable = _retry_skips(exc, name, model, skip_providers, skip_models)
            alternative = (registry.next_free(db, user_id, skip_providers, skip_models, prefer_provider=name)
                           if data.mode == "free" and retryable and data.allow_fallback
                           and (not parts or discard) else None)
            if alternative:
                name, model, credential = alternative
                db.rollback()
                continue
            message = exc.detail if isinstance(exc, HTTPException) else str(exc)
            yield event("error", {"status_code": exc.status_code, "message": message,
                                  "code": _error_code(exc), "provider": name, "explicit": not data.allow_fallback})
            return
        finally:
            if reservation:
                db.rollback()
                quotas.reconcile(db, reservation, usage, failed=True)


@router.post("/projects/{project_id}/ai/proposals/stream")
async def stream_proposal(project_id: UUID, data: GenerateInput,
                          user: User = Depends(require_csrf), db: Session = Depends(get_db),
                          provider: GeminiProvider = Depends(get_gemini_provider)) -> StreamingResponse:
    user_id = user.id
    if data.mode == "included":
        from .projects import project_for_owner
        project_for_owner(db, project_id, user_id)
        return _streaming(included_events(db, project_id, user_id, data))
    key, prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)
    maximum_cost, price, maximum_tokens = paid_terms(data, prompt)
    return _streaming(ai_events(db, project_id, user_id, data, provider, key, prompt, snapshot, selected, passages,
                                maximum_cost, price, maximum_tokens))


def first_free_request(db: Session, project_id: UUID, user_id: UUID, instruction: str, auto_apply: bool,
                       choice: PreferredModel | None, source_ids: list[UUID] | None = None):
    """Request built by the backend for teacher shortcuts (first version, DUA) with the AI of the selector.
    «IA automática» may switch to the next free AI; an AI chosen explicitly is respected."""
    explicit = bool(choice and choice.provider and choice.model)
    available = registry.preferred_free(db, user_id, choice.provider if choice else None, choice.model if choice else None)
    if available is None:
        raise HTTPException(409, "Configura un proveedor gratuito y confirma un modelo antes de generar")
    name, model, key = available
    data = engine.GenerateInput.model_construct(
        **{**engine.GenerateInput.model_construct().model_dump(), "instruction": instruction, "provider": name,
           "model": model, "automatic": True, "auto_apply": auto_apply, "mode": "free",
           "source_ids": source_ids or [], "whole_sources": bool(source_ids), "allow_fallback": not explicit})
    prompt, snapshot, selected, passages = engine.prepare(db, project_id, user_id, data)[1:]
    return data, key, prompt, snapshot, selected, passages


def brief_request(db: Session, project_id: UUID) -> tuple[str, list[UUID]]:
    brief = engine.read_brief(db, project_id)
    if brief is None:
        raise HTTPException(409, "Guarda primero el encargo de la actividad (activity.json)")
    source_ids = list(db.scalars(select(Source.id).where(Source.project_id == project_id).order_by(Source.created_at)))
    instruction = engine.instruction_for(brief) + (engine.MATERIAL_INSTRUCTION if source_ids else "")
    return instruction, source_ids


def dua_request(db: Session, project_id: UUID, user_id: UUID, data: DuaInput) -> str:
    from .projects import project_for_owner

    project_for_owner(db, project_id, user_id)
    if not (data.path.lower().endswith(engine.DUA_EXTENSIONS) or data.path == engine.template_service.DATA_PATH):
        raise HTTPException(422, "Solo se pueden adaptar actividades HTML o documentos Markdown")
    exists = db.scalar(select(ProjectFile.id).where(ProjectFile.project_id == project_id, ProjectFile.path == data.path))
    if exists is None:
        raise HTTPException(404, "Archivo no encontrado")
    language = str((engine.read_brief(db, project_id) or {}).get("language") or "") or None
    return engine.dua_instruction(data.path, data.needs, language)


@router.post("/projects/{project_id}/ai/from-brief/stream")
async def stream_from_brief(project_id: UUID, choice: PreferredModel | None = None,
                            user: User = Depends(require_csrf), db: Session = Depends(get_db),
                            provider: GeminiProvider = Depends(get_gemini_provider)) -> StreamingResponse:
    from .projects import project_for_owner

    project_for_owner(db, project_id, user.id)
    instruction, source_ids = brief_request(db, project_id)
    if wants_included(db, user.id, choice):
        return _streaming(included_events(db, project_id, user.id, included_request(instruction, True, source_ids)))
    data, key, prompt, snapshot, selected, passages = first_free_request(db, project_id, user.id, instruction, True,
                                                                        choice, source_ids)
    return _streaming(ai_events(db, project_id, user.id, data, provider, key, prompt, snapshot, selected, passages))


@router.post("/projects/{project_id}/ai/dua/stream")
async def stream_dua(project_id: UUID, data: DuaInput, user: User = Depends(require_csrf),
                     db: Session = Depends(get_db),
                     provider: GeminiProvider = Depends(get_gemini_provider)) -> StreamingResponse:
    instruction = dua_request(db, project_id, user.id, data)
    if wants_included(db, user.id, data):
        return _streaming(included_events(db, project_id, user.id,
            included_request(instruction, data.auto_apply), dua_target=data.path))
    request, key, prompt, snapshot, selected, passages = first_free_request(db, project_id, user.id, instruction,
                                                                           data.auto_apply, data)
    return _streaming(ai_events(db, project_id, user.id, request, provider, key, prompt, snapshot, selected, passages,
                                dua_target=data.path))


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



SECTION_ATTEMPTS = 3
SECTION_PASSAGE_BUDGET = 30_000


@router.post("/projects/{project_id}/ai/sections/stream")
async def stream_sections(project_id: UUID, data: SectionsInput, user: User = Depends(require_csrf),
                          db: Session = Depends(get_db),
                          provider: GeminiProvider = Depends(get_gemini_provider)) -> StreamingResponse:
    """Learning situation written (or developed) one section at a time, saved as a single proposal."""
    from .projects import project_for_owner

    user_id = user.id
    project = project_for_owner(db, project_id, user_id)
    brief = engine.read_brief(db, project_id) or {}
    if engine.brief_kind(brief) != "situacion":
        raise HTTPException(409, "La redacción por secciones es para situaciones de aprendizaje")
    unknown = [name for name in data.sections if name not in engine.SITUATION_SECTIONS]
    if unknown:
        raise HTTPException(422, "Sección desconocida")
    targets = [name for name in engine.SITUATION_SECTIONS if not data.sections or name in data.sections]
    explicit = bool(data.provider and data.model)
    institutional = wants_included(db, user_id, data)
    explicit = explicit or institutional
    available = (("educrea", "", "") if institutional else
                 registry.preferred_free(db, user_id, data.provider, data.model))
    if available is None:
        raise HTTPException(409, "Configura un proveedor gratuito y confirma un modelo antes de generar")
    files = list(db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id)))
    snapshot = {row.path: {"content": row.content, "version": row.version} for row in files}
    current = snapshot.get(engine.SITUATION_PATH, {}).get("content", "")
    source_ids = list(db.scalars(select(Source.id).where(Source.project_id == project_id).order_by(Source.created_at)))
    language = brief.get("language") if brief.get("language") in ("es", "ca", "va", "en") else "es"
    local = section_service.titles(language)
    title = str(brief.get("title") or project.title)
    db.rollback()

    async def events():
        name, model, key = available
        preamble, parts_by_section = section_service.split(current)
        citations: list[dict] = []
        not_covered: list[str] = []
        used: dict[str, dict] = {}
        failed: list[str] = []
        rescued: list[str] = []
        written = 0
        skip_providers: set[str] = set()
        skip_models: set[tuple[str, str]] = set()
        for index, section in enumerate(targets, 1):
            passages = None
            if source_ids:
                query = " ".join([section, title, str(brief.get("area") or ""), str(brief.get("challenge") or ""),
                                  data.request])
                passages = source_service.retrieve(db, project_id, source_ids, query, budget=SECTION_PASSAGE_BUDGET,
                                                   whole_if_fits=True)
            document = section_service.join(title, preamble, parts_by_section, language)
            prompt = section_service.section_prompt(brief, section, document, passages, data.request)
            db.rollback()
            done = False
            for _attempt in range(SECTION_ATTEMPTS):
                yield _sse("status", {"stage": "generating", "provider": name, "model": model,
                                      "passages": len(passages or []), "retry": bool(skip_providers or skip_models),
                                      "section": local[section], "index": index, "total": len(targets)})
                pieces: list[str] = []
                usage: dict = {}
                reservation = None if institutional else quotas.reserve(db, user_id, name, model)
                try:
                    if institutional:
                        def validate_section(content, _usage):
                            parsed = engine.parse_draft(content, "educrea")
                            if len(section_service.clean(parsed.changes[0].content, local[section])) < section_service.MIN_SECTION_CHARS:
                                raise HTTPException(502, "La sección de IA EduCrea llegó vacía.")
                            return parsed
                        if len(prompt.encode()) + 512 > included.get_settings().free_ai_max_context_tokens:
                            raise HTTPException(413, "El contexto supera el límite de IA EduCrea.")
                        async for event, value in included.run(db, user_id, get_router().select(TaskContext(task_type="planning")), prompt,
                                                              validate_section, task_type="planning"):
                            if event == "token":
                                pieces.append(value["text"])
                                yield _sse("token", value)
                    else:
                        adapter = provider if name == "gemini" else registry.adapter(name)
                        async for chunk in adapter.stream(key, model, prompt):
                            if chunk.text:
                                pieces.append(chunk.text)
                                yield _sse("token", {"text": chunk.text})
                            if chunk.usage:
                                usage = chunk.usage
                    draft = engine.parse_draft("".join(pieces), name)
                    content = section_service.clean(draft.changes[0].content, local[section])
                    if len(content) < section_service.MIN_SECTION_CHARS:
                        raise HTTPException(502, "La sección llegó vacía")
                    if reservation:
                        quotas.reconcile(db, reservation, usage)
                    parts_by_section[section] = content
                    citations += [c.model_dump() for c in draft.citations]
                    not_covered += draft.not_covered
                    done = True
                except (ProviderError, HTTPException) as exc:
                    db.rollback()
                    if reservation:
                        quotas.reconcile(db, reservation, usage, failed=True)
                    salvaged = engine.salvage_document("".join(pieces), "seccion.md") if pieces and not institutional else None
                    if salvaged:
                        parts_by_section[section] = section_service.clean(salvaged, local[section])
                        rescued.append(local[section])
                        done = True
                    else:
                        retryable = _retry_skips(exc, name, model, skip_providers, skip_models)
                        alternative = (registry.next_free(db, user_id, skip_providers, skip_models,
                                                          prefer_provider=name)
                                       if retryable and not explicit else None)
                        if alternative is not None:
                            name, model, key = alternative
                            continue
                        if institutional or (explicit and retryable):
                            yield _sse("error", {"status_code": getattr(exc, "status_code", 502),
                                                 "message": str(getattr(exc, "detail", exc)),
                                                 "code": _error_code(exc), "provider": name, "explicit": True})
                            return
                break
            if done:
                written += 1
                for passage in passages or []:
                    used.setdefault(passage["chunk_id"], {key_: passage[key_] for key_ in ("label", "source", "page", "heading")})
                yield _sse("section", {"index": index, "total": len(targets), "section": local[section],
                                       "chars": len(parts_by_section.get(section, ""))})
            else:
                failed.append(local[section])
        if not written:
            yield _sse("error", {"status_code": 502, "message": "No se ha podido redactar ninguna sección. "
                                 "Vuelve a intentarlo o elige otra IA.", "code": "provider_error", "provider": name})
            return
        document = section_service.join(title, preamble, parts_by_section, language)
        names = ", ".join(local[s] for s in targets)
        draft = json.dumps({"summary": f"Redactada por secciones ({written} de {len(targets)}): {names}"[:1000],
                            "changes": [{"path": engine.SITUATION_PATH, "content": document}],
                            "citations": citations[:40], "not_covered": not_covered[:20]}, ensure_ascii=False)
        try:
            proposal = engine.persist(db, project_id, user_id, model, draft, {}, snapshot, {engine.SITUATION_PATH},
                                      provider=name, source_ids=source_ids or None, passages_used=list(used.values()))
        except HTTPException as exc:
            yield _sse("error", {"status_code": exc.status_code, "message": exc.detail})
            return
        if failed or rescued:
            grounding = dict(proposal.grounding or {"mode": "template", "kind": "situacion", "sources": [],
                                                    "passages_used": [], "citations": [], "verified": 0,
                                                    "unverified": 0, "not_covered": []})
            problems = list(grounding.get("template_problems", []))
            if failed:
                problems.append("no se han podido redactar: " + ", ".join(failed) + " (se conserva el texto anterior)")
            if rescued:
                problems.append("respuesta cortada en: " + ", ".join(rescued) + " (revisa su final)")
            grounding.update(template_problems=problems, supported=False, salvaged=bool(rescued))
            proposal.grounding = grounding
            db.commit()
            db.refresh(proposal)
        proposal = engine.apply_if_requested(db, project_id, proposal, data.auto_apply)
        yield _sse("proposal", ProposalOut.model_validate(proposal).model_dump(mode="json"))

    return _streaming(events())
