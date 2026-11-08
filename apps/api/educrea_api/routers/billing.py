from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user, require_csrf
from ..services import billing

router = APIRouter(prefix="/billing", tags=["billing-test"])


class CheckoutInput(BaseModel):
    request_id: UUID
    model_config = ConfigDict(extra="forbid")


@router.get("/wallet")
def wallet(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return billing.wallet(db, user)


@router.post("/checkout")
def checkout(data: CheckoutInput, response: Response, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return billing.checkout(db, user, data.request_id)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    _key, secret, _base = billing.configuration()
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 262144:
            raise HTTPException(413, "Webhook demasiado grande")
    event = billing.verified_event(bytes(payload), request.headers.get("Stripe-Signature", ""), secret)
    billing.fulfill(db, event)
    return {"received": True}
