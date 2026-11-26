"""At-a-glance operational numbers for the admin overview (all computed from live tables)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CalendarEvent, Donation, Redemption, RenewalRequest, StoreOrder, User
from . import mess


def pass_summary(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    soon = mess.settings(db).expiring_soon_days
    counts = {"active": 0, "expiring_soon": 0, "expired": 0, "suspended": 0, "none": 0, "upcoming": 0}
    for u in db.query(User).filter(User.role == "student", User.is_active.is_(True)):
        st = mess.pass_status(mess.current_subscription(db, u.id, today), u, today, soon)["status"]
        counts[st] = counts.get(st, 0) + 1
    counts["total"] = sum(counts.values())
    counts["with_valid_pass"] = counts["active"] + counts["expiring_soon"]
    return counts


def upcoming_holidays(db: Session, days: int = 60, limit: int = 5) -> list[dict]:
    today = date.today()
    rows = (db.query(CalendarEvent).filter(CalendarEvent.kind == "holiday", CalendarEvent.published.is_(True),
                                           CalendarEvent.date >= today, CalendarEvent.date <= today + timedelta(days=days))
            .order_by(CalendarEvent.date).limit(limit).all())
    return [{"id": e.id, "name": e.name, "date": str(e.date), "type": e.holiday_type,
             "services": mess.services_label(mess.services_of(e)), "message": e.message} for e in rows]


def ops_summary(db: Session) -> dict:
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    open_states = ("available", "request_sent", "partially_accepted", "fully_accepted", "pickup_confirmed")
    dons = db.query(Donation).filter(Donation.status.in_(open_states)).all()
    surplus_today = db.query(Donation).filter(Donation.created_at >= start).all()
    return {
        "passes": pass_summary(db, today),
        "renewals_pending": db.query(func.count(RenewalRequest.id)).filter(RenewalRequest.status == "pending").scalar(),
        "holidays": upcoming_holidays(db),
        "orders_pending": db.query(func.count(StoreOrder.id)).filter(StoreOrder.status.in_(("placed", "accepted", "preparing", "ready"))).scalar(),
        "orders_today": db.query(func.count(StoreOrder.id)).filter(StoreOrder.created_at >= start).scalar(),
        "coupons_active": db.query(func.count(Redemption.id)).filter(Redemption.status == "active").scalar(),
        "coupons_redeemed_today": db.query(func.count(Redemption.id)).filter(Redemption.redeemed_at >= start).scalar(),
        "donations_pending": len(dons),
        "surplus_today": {"entries": len(surplus_today),
                          "portions": round(sum(d.quantity for d in surplus_today if d.unit == "portions"), 1),
                          "kg": round(sum(d.quantity for d in surplus_today if d.unit == "kg"), 1)},
    }
