"""Public, login-free endpoints for NGOs. Access is by secret single-use token only."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AcceptIn, DeclineIn
from ..services import donations as D
from ..services.forecast import get_settings

router = APIRouter(prefix="/api/public", tags=["public"])


def _view(db: Session, inv, d) -> dict:
    x = D.serialize(d)
    mine = next((a for a in d.allocations if a.invite_id == inv.id), None)
    return {
        "canteen_name": get_settings(db).canteen_name,
        "ngo": inv.ngo.name if inv.ngo else None,
        "response": inv.response,
        "my_allocation": {"quantity": mine.quantity, "status": mine.status, "organisation": mine.organisation} if mine else None,
        # Only what an NGO needs: no other NGOs' names or phone numbers.
        "donation": {k: x[k] for k in ("code", "food_name", "category", "is_veg", "quantity", "unit", "remaining", "prepared_at",
                                       "safe_until", "pickup_location", "pickup_deadline", "instructions", "image", "status",
                                       "accepting")},
    }


@router.get("/donations/{token}")
def view(token: str, db: Session = Depends(get_db)):
    inv, d = D.public_view(db, token)
    return _view(db, inv, d)


@router.post("/donations/{token}/accept")
def accept(token: str, body: AcceptIn, db: Session = Depends(get_db)):
    D.accept(db, token, body.quantity, body.organisation, body.contact_name, body.contact_phone, body.pickup_eta)
    inv, d = D.public_view(db, token)
    return _view(db, inv, d)


@router.post("/donations/{token}/decline")
def decline(token: str, body: DeclineIn, db: Session = Depends(get_db)):
    D.decline(db, token, body.reason)
    inv, d = D.public_view(db, token)
    return _view(db, inv, d)
