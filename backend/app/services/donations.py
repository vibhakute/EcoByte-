"""Surplus-food donations to NGOs, managed entirely by the canteen admin.

NGOs have no accounts. Each NGO receives a secret, single-use link (DonationInvite.token)
by WhatsApp / SMS / copy-paste. Opening it shows the donation and the *live* remaining
quantity; accepting runs one conditional UPDATE:

    UPDATE donations SET allocated_qty = allocated_qty + :q
    WHERE id = :id AND allocated_qty + :q <= quantity AND status IN (open) AND deadlines in future

The database applies that check-and-increment atomically, so two NGOs accepting at the same
moment can never over-allocate (the loser gets "only N remaining"). Each link can respond once.

WhatsApp: wa.me links open a pre-filled chat; they cannot report back whether the NGO replied.
Acceptance is therefore tracked through the secure link. Automated WhatsApp notifications need
the WhatsApp Business Cloud API (approved templates + webhook), which is not configured here.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from ..models import Donation, DonationAllocation, DonationInvite, NgoContact, Notification

OPEN = ("available", "request_sent", "partially_accepted")
EPS = 1e-6


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:  # Indian mobile without country code
        digits = "91" + digits
    if not 10 <= len(digits) <= 15:
        raise HTTPException(400, "Enter a valid phone number with country code, e.g. +91 98765 43210")
    return digits


def next_code(db: Session, now: datetime) -> str:
    prefix = f"ECO-DON-{now.year}-"
    last = (db.query(Donation.code).filter(Donation.code.like(prefix + "%"))
            .order_by(Donation.id.desc()).first())
    n = int(last[0].rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:03d}"


def acceptance_open(d: Donation, now: datetime) -> bool:
    return d.status in OPEN and now < d.pickup_deadline and now < d.safe_until and d.quantity - d.allocated_qty > EPS


def refresh_status(db: Session, d: Donation, now: datetime | None = None) -> str:
    """Derive status from allocations and deadlines. Terminal states are kept."""
    now = now or datetime.now()
    if d.status in ("cancelled", "collected", "expired", "completed"):
        return d.status
    active = [a for a in d.allocations if a.status != "cancelled"]
    allocated = sum(a.quantity for a in active)
    prev = d.status
    if active and all(a.status == "collected" for a in active) and (allocated >= d.quantity - EPS or now >= d.pickup_deadline):
        d.status = "collected"
    elif active and all(a.status in ("pickup_confirmed", "collected") for a in active) and allocated >= d.quantity - EPS:
        d.status = "pickup_confirmed"
    elif allocated >= d.quantity - EPS:
        d.status = "fully_accepted"
    elif now >= d.pickup_deadline or now >= d.safe_until:
        d.status = "expired" if not active else ("pickup_confirmed" if all(a.status != "accepted" for a in active) else "partially_accepted")
    elif allocated > EPS:
        d.status = "partially_accepted"
    else:
        d.status = "request_sent" if d.invites else "available"
    if d.status == "expired" and prev != "expired":
        notify(db, "donation", f"{d.code} expired", f"{d.food_name}: no NGO accepted before the pickup deadline.", "/admin/donations")
    return d.status


def notify(db: Session, kind: str, title: str, body: str = "", link: str | None = None):
    db.add(Notification(kind=kind, title=title, body=body, link=link, created_at=datetime.now()))


def fmt_qty(q: float, unit: str) -> str:
    q = int(q) if abs(q - round(q)) < EPS else round(q, 1)
    return f"{q} {'meal portions' if unit == 'portions' else 'kg'}"


def message_for(d: Donation, link: str, canteen: str) -> str:
    return (
        "EcoByte Food Donation Alert!\n\n"
        f"Fresh surplus food is available for collection from {canteen}.\n\n"
        f"Donation ID: {d.code}\n"
        f"Food: {d.food_name} ({'Vegetarian' if d.is_veg else 'Non-vegetarian'})\n"
        f"Quantity: {fmt_qty(d.quantity - d.allocated_qty, d.unit)} available\n"
        f"Pickup Location: {d.pickup_location}\n"
        f"Pickup Deadline: {d.pickup_deadline:%d %b, %I:%M %p}\n"
        f"Safe to eat until: {d.safe_until:%d %b, %I:%M %p}\n\n"
        f"If your organization can collect this food, please confirm using the link below:\n{link}"
    )


def get_or_create_invite(db: Session, d: Donation, ngo_id: int | None) -> DonationInvite:
    if ngo_id is not None:
        inv = db.query(DonationInvite).filter_by(donation_id=d.id, ngo_id=ngo_id).first()
        if inv:
            return inv
    inv = DonationInvite(donation_id=d.id, ngo_id=ngo_id, token=secrets.token_urlsafe(24), created_at=datetime.now())
    db.add(inv)
    db.flush()
    return inv


def share_links(d: Donation, inv: DonationInvite, base_url: str, canteen: str) -> dict:
    link = f"{base_url.rstrip('/')}/d/{inv.token}"
    msg = message_for(d, link, canteen)
    phone = inv.ngo.phone if inv.ngo else None
    return {
        "invite_id": inv.id, "ngo_id": inv.ngo_id, "ngo": inv.ngo.name if inv.ngo else "Shareable link",
        "phone": phone, "link": link, "message": msg, "response": inv.response,
        "whatsapp_url": f"https://wa.me/{phone}?text={quote(msg)}" if phone else f"https://wa.me/?text={quote(msg)}",
        "sms_url": f"sms:+{phone}?body={quote(msg)}" if phone else f"sms:?body={quote(msg)}",
    }


def public_view(db: Session, token: str) -> tuple[DonationInvite, Donation]:
    inv = db.query(DonationInvite).filter_by(token=token).first()
    if inv is None:
        raise HTTPException(404, "This donation link is not valid.")
    d = inv.donation
    refresh_status(db, d)
    if inv.opened_at is None:
        inv.opened_at = datetime.now()
    db.commit()
    return inv, d


def accept(db: Session, token: str, quantity: float, organisation: str, contact_name: str, contact_phone: str,
           pickup_eta: str | None) -> DonationAllocation:
    now = datetime.now()
    inv = db.query(DonationInvite).filter_by(token=token).first()
    if inv is None:
        raise HTTPException(404, "This donation link is not valid.")
    d = inv.donation
    if d.unit == "portions" and abs(quantity - round(quantity)) > EPS:
        raise HTTPException(400, "Meal portions must be a whole number.")
    if quantity <= 0:
        raise HTTPException(400, "Enter a quantity greater than zero.")
    phone = normalize_phone(contact_phone)
    org = (inv.ngo.name if inv.ngo else organisation or "").strip()
    if len(org) < 2:
        raise HTTPException(400, "Enter your organisation name.")
    if len((contact_name or "").strip()) < 2:
        raise HTTPException(400, "Enter the name of the person collecting the food.")

    # 1) The link can be used once: claim it atomically.
    claimed = db.execute(update(DonationInvite).where(DonationInvite.id == inv.id, DonationInvite.response.is_(None))
                         .values(response="accepted", responded_at=now)
                         .execution_options(synchronize_session=False)).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(409, "This link has already been used to respond.")
    # 2) Atomic check-and-increment: can never exceed the available quantity.
    ok = db.execute(update(Donation).where(
        Donation.id == d.id, Donation.status.in_(OPEN), Donation.pickup_deadline > now, Donation.safe_until > now,
        Donation.allocated_qty + quantity <= Donation.quantity + EPS,
    ).values(allocated_qty=Donation.allocated_qty + quantity).execution_options(synchronize_session=False)).rowcount
    if ok != 1:
        db.rollback()
        db.refresh(d)
        remaining = max(0.0, d.quantity - d.allocated_qty)
        if not acceptance_open(d, now):
            raise HTTPException(409, "This donation is no longer accepting requests (fully allocated, expired or cancelled).")
        raise HTTPException(409, f"Only {fmt_qty(remaining, d.unit)} remain. Please request that amount or less.")
    a = DonationAllocation(donation_id=d.id, invite_id=inv.id, ngo_id=inv.ngo_id, organisation=org,
                           contact_name=contact_name.strip(), contact_phone=phone, quantity=quantity,
                           pickup_eta=(pickup_eta or "").strip() or None, created_at=now)
    db.add(a)
    db.flush()
    db.expire(d)  # reload allocated_qty and the allocations list after the bulk update
    db.expire(inv)
    refresh_status(db, d, now)
    notify(db, "donation", f"{org} accepted {fmt_qty(quantity, d.unit)}",
           f"{d.code} - {d.food_name}. Remaining: {fmt_qty(max(0, d.quantity - d.allocated_qty), d.unit)}. "
           f"Contact {contact_name} (+{phone}).", "/admin/donations")
    db.commit()
    return a


def decline(db: Session, token: str, reason: str | None):
    inv = db.query(DonationInvite).filter_by(token=token).first()
    if inv is None:
        raise HTTPException(404, "This donation link is not valid.")
    done = db.execute(update(DonationInvite).where(DonationInvite.id == inv.id, DonationInvite.response.is_(None))
                      .values(response="declined", responded_at=datetime.now())
                      .execution_options(synchronize_session=False)).rowcount
    if done != 1:
        db.rollback()
        raise HTTPException(409, "This link has already been used to respond.")
    who = inv.ngo.name if inv.ngo else "An NGO"
    notify(db, "donation", f"{who} declined {inv.donation.code}", reason or "", "/admin/donations")
    db.commit()


def release_allocation(db: Session, a: DonationAllocation):
    """Cancel an allocation and return its quantity to the pool (atomic decrement)."""
    if a.status == "cancelled":
        return
    if a.status == "collected":
        raise HTTPException(400, "Collected allocations cannot be cancelled.")
    db.execute(update(Donation).where(Donation.id == a.donation_id)
               .values(allocated_qty=func.max(Donation.allocated_qty - a.quantity, 0) if db.bind.dialect.name == "sqlite"
                       else func.greatest(Donation.allocated_qty - a.quantity, 0))
               .execution_options(synchronize_session=False))
    a.status = "cancelled"
    d = a.donation
    db.flush()
    db.expire(d)
    if d.status in ("fully_accepted", "pickup_confirmed"):
        d.status = "partially_accepted"
    refresh_status(db, d)


def serialize(d: Donation, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    active = [a for a in d.allocations if a.status != "cancelled"]
    return {
        "id": d.id, "code": d.code, "food_name": d.food_name, "category": d.category, "is_veg": d.is_veg,
        "quantity": d.quantity, "unit": d.unit, "allocated": round(d.allocated_qty, 2),
        "remaining": round(max(0.0, d.quantity - d.allocated_qty), 2),
        "collected": round(sum(a.collected_qty or 0 for a in active if a.status == "collected"), 2),
        "prepared_at": d.prepared_at.isoformat(timespec="minutes"), "safe_until": d.safe_until.isoformat(timespec="minutes"),
        "pickup_location": d.pickup_location, "pickup_deadline": d.pickup_deadline.isoformat(timespec="minutes"),
        "instructions": d.instructions, "image": f"/api/uploads/{d.image}" if d.image else None, "meal_type": d.meal_type, "status": d.status,
        "accepting": acceptance_open(d, now), "created_at": d.created_at.isoformat(timespec="minutes"),
        "invites_sent": len(d.invites), "responses": sum(1 for i in d.invites if i.response),
        "simple_status": {"available": "Available", "request_sent": "Available", "partially_accepted": "Assigned",
                          "fully_accepted": "Assigned", "pickup_confirmed": "Assigned", "collected": "Collected",
                          "completed": "Completed", "expired": "Expired", "cancelled": "Cancelled"}.get(d.status, d.status),
        "allocations": [{
            "id": a.id, "organisation": a.organisation, "contact_name": a.contact_name, "contact_phone": a.contact_phone,
            "quantity": a.quantity, "pickup_eta": a.pickup_eta, "status": a.status, "collected_qty": a.collected_qty,
            "created_at": a.created_at.isoformat(timespec="minutes"),
            "collected_at": a.collected_at.isoformat(timespec="minutes") if a.collected_at else None,
        } for a in sorted(d.allocations, key=lambda x: x.created_at)],
        "invites": [{"id": i.id, "ngo": i.ngo.name if i.ngo else "Shareable link", "ngo_id": i.ngo_id,
                     "opened": i.opened_at is not None, "response": i.response,
                     "responded_at": i.responded_at.isoformat(timespec="minutes") if i.responded_at else None}
                    for i in d.invites],
    }


def assign(db: Session, d: Donation, ngo: NgoContact, quantity: float, pickup_eta: str | None) -> DonationAllocation:
    """Admin assigns surplus food directly to an NGO (e.g. after a phone call). Same atomic rule as
    NGO self-acceptance: the allocation can never exceed what is left."""
    now = datetime.now()
    if d.unit == "portions" and abs(quantity - round(quantity)) > EPS:
        raise HTTPException(400, "Meal portions must be a whole number.")
    ok = db.execute(update(Donation).where(
        Donation.id == d.id, Donation.status.in_(OPEN), Donation.pickup_deadline > now, Donation.safe_until > now,
        Donation.allocated_qty + quantity <= Donation.quantity + EPS,
    ).values(allocated_qty=Donation.allocated_qty + quantity).execution_options(synchronize_session=False)).rowcount
    if ok != 1:
        db.rollback()
        db.refresh(d)
        if not acceptance_open(d, now):
            raise HTTPException(409, "This donation can no longer be assigned (fully allocated, expired or cancelled).")
        raise HTTPException(409, f"Only {fmt_qty(max(0, d.quantity - d.allocated_qty), d.unit)} remain.")
    a = DonationAllocation(donation_id=d.id, invite_id=None, ngo_id=ngo.id, organisation=ngo.name,
                           contact_name=ngo.contact_person or ngo.name, contact_phone=ngo.phone, quantity=quantity,
                           pickup_eta=(pickup_eta or "").strip() or None, created_at=now)
    db.add(a)
    db.flush()
    db.expire(d)
    refresh_status(db, d, now)
    db.commit()
    return a
