from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CapabilityCall, User
from ..security import current_user, require_csrf
from ..services import capabilities
from .projects import project_for_owner

router = APIRouter(tags=["capabilities"])


class InvokeInput(BaseModel):
    arguments: dict = Field(default_factory=dict)
    approved: bool = False


@router.get("/capabilities")
def list_capabilities(_user: User = Depends(current_user)) -> list[dict]:
    return capabilities.catalog()


@router.post("/projects/{project_id}/capabilities/{name}/invoke")
def invoke_capability(project_id: UUID, name: str, data: InvokeInput, user: User = Depends(require_csrf),
                      db: Session = Depends(get_db)) -> dict:
    project_for_owner(db, project_id, user.id)
    return capabilities.invoke(db, user.id, project_id, name, data.arguments, data.approved)


@router.get("/projects/{project_id}/capabilities/audit")
def audit_log(project_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    project_for_owner(db, project_id, user.id)
    rows = db.scalars(select(CapabilityCall).where(CapabilityCall.project_id == project_id,
                                                   CapabilityCall.user_id == user.id)
                      .order_by(CapabilityCall.created_at.desc()).limit(50))
    return [{"capability": r.capability, "status": r.status, "detail": r.detail, "input_bytes": r.input_bytes,
             "output_bytes": r.output_bytes, "duration_ms": r.duration_ms, "created_at": r.created_at} for r in rows]
