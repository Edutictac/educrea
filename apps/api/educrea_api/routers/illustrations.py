from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProjectAsset, ProjectFile, User
from ..security import require_csrf
from ..services.ai import engine, illustrations, quotas
from ..services.ai.providers import registry
from ..services.ai.providers.base import ProviderError
from ..services.ai.providers.gemini import GeminiProvider, get_gemini_provider
from ..services.ai.schemas import PreferredModel
from .ai import (_retry_skips, _streaming, ai_events, first_free_request, included_events, included_request,
                 wants_included)
from .projects import project_for_owner

router = APIRouter(tags=["illustrations"])


class IllustrationRequest(BaseModel):
    count: int = Field(ge=1, le=illustrations.MAX_ILLUSTRATIONS)
    style: illustrations.Style = "plana"
    # «Ilustrar este recurso»: describe the images from the current content too, not only the brief.
    from_content: bool = False
    model_config = ConfigDict(extra="forbid")


class PlacementInput(PreferredModel):
    paths: list[str] = Field(min_length=1, max_length=illustrations.MAX_ILLUSTRATIONS)


def _brief(db: Session, project_id: UUID) -> dict:
    brief = engine.read_brief(db, project_id)
    if not brief:
        raise HTTPException(409, "El proyecto no tiene encargo (activity.json)")
    return brief


@router.post("/projects/{project_id}/ai/illustrations/prompts")
async def illustration_prompts(project_id: UUID, data: IllustrationRequest, user: User = Depends(require_csrf),
                               db: Session = Depends(get_db),
                               provider: GeminiProvider = Depends(get_gemini_provider)) -> list[dict]:
    """Free text AI (automatic mode, with fallback) writes the image descriptions; nothing is paid here."""
    user_id = user.id
    project_for_owner(db, project_id, user_id)
    brief = _brief(db, project_id)
    content = ""
    if data.from_content:
        path = illustrations.main_path(brief)
        stored = db.scalar(select(ProjectFile.content).where(ProjectFile.project_id == project_id,
                                                             ProjectFile.path == path))
        content = illustrations.readable(stored or "", path)
    available = registry.first_free(db, user_id)
    if available is None:
        raise HTTPException(409, "Configura una IA gratuita para que pueda describir las ilustraciones")
    prompt = illustrations.instruction(brief, data.count, content)
    skip_providers: set[str] = set()
    skip_models: set[tuple[str, str]] = set()
    while True:
        name, model, key = available
        adapter = provider if name == "gemini" else registry.adapter(name)
        reservation = quotas.reserve(db, user_id, name, model)
        result = None
        try:
            result = await adapter.generate(key, model, prompt)
            prompts = illustrations.parse(result.text, name, data.count, data.style)
            quotas.reconcile(db, reservation, result.usage)
            return prompts
        except (ProviderError, HTTPException, ValueError) as exc:
            db.rollback()
            quotas.reconcile(db, reservation, result.usage if result else None, failed=True)
            if isinstance(exc, ValueError):  # unparseable answer: try another model
                skip_models.add((name, model))
            elif not _retry_skips(exc, name, model, skip_providers, skip_models):
                raise HTTPException(exc.status_code, str(exc.detail if isinstance(exc, HTTPException) else exc)) from None
            available = registry.next_free(db, user_id, skip_providers, skip_models, prefer_provider=name)
            if available is None:
                if isinstance(exc, HTTPException):
                    raise
                raise HTTPException(502, "Ninguna IA gratuita ha podido describir las ilustraciones ahora. "
                                         "Vuelve a intentarlo en unos minutos.") from None
        except BaseException:
            db.rollback()
            quotas.reconcile(db, reservation, result.usage if result else None, failed=True)
            raise


@router.post("/projects/{project_id}/ai/illustrations/place/stream")
async def place_illustrations(project_id: UUID, data: PlacementInput, user: User = Depends(require_csrf),
                              db: Session = Depends(get_db),
                              provider: GeminiProvider = Depends(get_gemini_provider)) -> StreamingResponse:
    """Teacher shortcut: a proposal (applied, with history and «Deshacer») that inserts the new images."""
    project_for_owner(db, project_id, user.id)
    brief = _brief(db, project_id)
    if not illustrations.can_illustrate(brief):
        raise HTTPException(409, "Este tipo de recurso no admite ilustraciones")
    wanted = list(dict.fromkeys(data.paths))
    found = {asset.path: asset.alt for asset in db.scalars(
        select(ProjectAsset).where(ProjectAsset.project_id == project_id, ProjectAsset.path.in_(wanted)))}
    if set(found) != set(wanted):
        raise HTTPException(422, "Alguna imagen no está en la biblioteca del proyecto")
    instruction = illustrations.placement_instruction(brief, [{"path": path, "alt": found[path]} for path in wanted])
    choice = PreferredModel(provider=data.provider, model=data.model)
    if wants_included(db, user.id, choice):
        return _streaming(included_events(db, project_id, user.id, included_request(instruction, True)))
    request, key, prompt, snapshot, selected, passages = first_free_request(db, project_id, user.id, instruction,
                                                                           True, choice)
    return _streaming(ai_events(db, project_id, user.id, request, provider, key, prompt, snapshot, selected, passages))
