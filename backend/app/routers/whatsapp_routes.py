"""Automatic WhatsApp: setup, test messages, sending donations to NGOs, the message log, NGO removal and
the provider webhooks (delivery receipts)."""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import SessionLocal, get_db
from ..models import Donation, DonationAllocation, DonationInvite, NgoContact, WhatsAppMessage
from ..services import donations as D
from ..services import whatsapp as W
from ..services.forecast import get_settings

admin = APIRouter(prefix="/api/admin", tags=["whatsapp"], dependencies=[Depends(require_admin)])
public = APIRouter(prefix="/api/public/whatsapp", tags=["whatsapp-webhooks"])


class ConfigIn(BaseModel):
    provider: Literal["off", "meta", "twilio"]
    auto_send: bool = False
    meta_phone_number_id: str = Field(default="", max_length=40, pattern=r"^\d*$")
    meta_token: str | None = Field(default=None, max_length=1000)  # None or "" = keep the saved value
    meta_app_secret: str | None = Field(default=None, max_length=80)
    meta_verify_token: str = Field(default="", max_length=80)
    meta_template: str = Field(default="", max_length=80, pattern=r"^[a-z0-9_]*$")
    meta_template_lang: str = Field(default="en_US", max_length=12)
    twilio_sid: str = Field(default="", max_length=40, pattern=r"^(AC[0-9a-fA-F]{32})?$")
    twilio_token: str | None = Field(default=None, max_length=80)
    twilio_from: str = Field(default="", max_length=20)


class TestIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    mode: Literal["text", "hello_world"] = "text"


class SendIn(BaseModel):
    ngo_ids: list[int] = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=8, max_length=200, pattern=r"^https?://[^\s]+$")


def public_base(db: Session, request: Request | None = None, fallback: str = "") -> str:
    s = get_settings(db)
    return (s.public_base_url or fallback or (str(request.base_url) if request else "")).rstrip("/")


# --- setup ----------------------------------------------------------------------------------------

@admin.get("/whatsapp/config")
def get_config(request: Request, db: Session = Depends(get_db)):
    return W.config_out(W.config(db), public_base(db, request))


@admin.put("/whatsapp/config")
def put_config(body: ConfigIn, request: Request, db: Session = Depends(get_db)):
    c = W.config(db)
    data = body.model_dump()
    for secret in ("meta_token", "meta_app_secret", "twilio_token"):
        v = (data.pop(secret) or "").strip()
        if v:
            setattr(c, secret, v)
    for k, v in data.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)
    c.twilio_from = "".join(ch for ch in c.twilio_from if ch.isdigit())
    c.updated_at = datetime.now()
    db.commit()
    return W.config_out(c, public_base(db, request))


@admin.post("/whatsapp/test")
def test_message(body: TestIn, db: Session = Depends(get_db)):
    phone = D.normalize_phone(body.phone)
    s = get_settings(db)
    text = (f"EcoByte test message from {s.canteen_name}, sent {datetime.now():%d %b %Y at %I:%M %p}.\n\n"
            "If you can read this, automatic WhatsApp messages are working.")
    ngo = db.query(NgoContact).filter_by(phone=phone).first()
    m = W.send(db, phone, text, kind="test", ngo_id=ngo.id if ngo else None, ngo_name=ngo.name if ngo else None,
               use_template="hello_world" if body.mode == "hello_world" else "")
    return W.message_out(m)


# --- sending donations ------------------------------------------------------------------------------

def _params(d: Donation, link: str, canteen: str) -> list[str]:
    return [canteen, f"{d.food_name} ({'veg' if d.is_veg else 'non-veg'})", D.fmt_qty(d.quantity - d.allocated_qty, d.unit),
            d.pickup_location, f"{d.pickup_deadline:%d %b, %I:%M %p}", link]


def send_to_ngos(db: Session, d: Donation, ngos: list[NgoContact], base: str) -> list[dict]:
    s = get_settings(db)
    out = []
    for n in ngos:
        inv = D.get_or_create_invite(db, d, n.id)
        db.commit()
        link = f"{base}/d/{inv.token}"
        m = W.send(db, n.phone, D.message_for(d, link, s.canteen_name), kind="donation", ngo_id=n.id, ngo_name=n.name,
                   donation_id=d.id, template_params=_params(d, link, s.canteen_name), public_base=base)
        out.append(W.message_out(m))
    db.expire(d)
    D.refresh_status(db, d)
    db.commit()
    return out


@admin.post("/donations/{donation_id}/whatsapp")
def send_donation(donation_id: int, body: SendIn, db: Session = Depends(get_db)):
    d = db.get(Donation, donation_id)
    if not d:
        raise HTTPException(404, "Donation not found")
    D.refresh_status(db, d)
    if not D.acceptance_open(d, datetime.now()):
        raise HTTPException(400, f"This donation is {d.status.replace('_', ' ')} and can no longer be shared.")
    ok, why = W.ready(W.config(db))
    if not ok:
        raise HTTPException(400, why)
    ngos = [n for n in db.query(NgoContact).filter(NgoContact.id.in_(body.ngo_ids)) if n.active]
    if not ngos:
        raise HTTPException(400, "Select at least one active NGO.")
    results = send_to_ngos(db, d, ngos, public_base(db, fallback=body.base_url))
    return {"donation": D.serialize(d), "results": results,
            "sent": sum(r["status"] != "failed" for r in results), "failed": sum(r["status"] == "failed" for r in results)}


def auto_send(donation_id: int, base: str) -> None:
    """Background task after a donation is created (when auto-send is on): message every active NGO."""
    db = SessionLocal()
    try:
        d = db.get(Donation, donation_id)
        ngos = db.query(NgoContact).filter_by(active=True).all()
        if d and ngos and W.ready(W.config(db))[0]:
            send_to_ngos(db, d, ngos, base)
    finally:
        db.close()


# --- message log ----------------------------------------------------------------------------------

@admin.get("/whatsapp/messages")
def messages(donation_id: int | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    q = db.query(WhatsAppMessage)
    if donation_id:
        q = q.filter(WhatsAppMessage.donation_id == donation_id)
    rows = q.order_by(WhatsAppMessage.id.desc()).limit(limit).all()
    recent = datetime.now() - timedelta(days=2)
    for m in [m for m in rows if m.provider == "twilio" and m.status not in W.FINAL and m.created_at > recent][:15]:
        W.refresh(db, m)
    return [W.message_out(m) for m in rows]


@admin.post("/whatsapp/messages/{message_id}/refresh")
def refresh_message(message_id: int, db: Session = Depends(get_db)):
    m = db.get(WhatsAppMessage, message_id)
    if not m:
        raise HTTPException(404, "Message not found")
    return W.message_out(W.refresh(db, m))


# --- NGO removal ----------------------------------------------------------------------------------

@admin.delete("/ngos/{ngo_id}")
def delete_ngo(ngo_id: int, db: Session = Depends(get_db)):
    """Remove an NGO. Links it has not answered stop working; past allocations keep the organisation's name."""
    n = db.get(NgoContact, ngo_id)
    if not n:
        raise HTTPException(404, "NGO not found")
    revoked = 0
    for inv in db.query(DonationInvite).filter_by(ngo_id=n.id).all():
        if inv.response is None and not db.query(DonationAllocation.id).filter_by(invite_id=inv.id).first():
            db.delete(inv)
            revoked += 1
        else:
            inv.ngo_id = None
    db.query(DonationAllocation).filter_by(ngo_id=n.id).update({"ngo_id": None})
    name = n.name
    db.delete(n)
    db.commit()
    return {"deleted": name, "links_revoked": revoked}


# --- provider webhooks (public) ---------------------------------------------------------------------

@public.get("/webhook", response_class=PlainTextResponse)
def meta_verify(request: Request, db: Session = Depends(get_db)):
    q = request.query_params
    c = W.config(db)
    if q.get("hub.mode") == "subscribe" and c.meta_verify_token and q.get("hub.verify_token") == c.meta_verify_token:
        return q.get("hub.challenge", "")
    raise HTTPException(403, "Verification failed")


@public.post("/webhook")
async def meta_events(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if len(raw) > 512_000:
        raise HTTPException(413, "Payload too large")
    c = W.config(db)
    if not W.meta_signature_ok(c, raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "Bad signature")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Invalid JSON")
    return {"updated": W.handle_meta(db, payload)}


@public.post("/twilio-status")
async def twilio_status(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if len(raw) > 64_000:
        raise HTTPException(413, "Payload too large")
    params = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode(), keep_blank_values=True).items()}
    url = public_base(db, request) + "/api/public/whatsapp/twilio-status"
    if not W.twilio_signature_ok(W.config(db), url, params, request.headers.get("X-Twilio-Signature")):
        raise HTTPException(403, "Bad signature")
    W.handle_twilio_status(db, params)
    return PlainTextResponse("")
