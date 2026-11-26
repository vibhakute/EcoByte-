"""Mess passes, holiday closures and student notifications.

Pass validity is always computed from real dates:
  valid from start_date to expiry_date (inclusive); expiry_date moves only through recorded
  PassExtension rows (each with a unique request_key, so a double click can never extend twice).
  remaining = expiry - today + 1 (0 once expired); total = base_days + sum(extensions).

Holidays: a published holiday closes the selected meals ("services") on its date. Closed meals
cannot be confirmed or booked; existing bookings for them are cancelled and the students notified.
Passes are NOT changed by holidays unless Settings > "Extend passes for full-day holidays" is on.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import MEAL_TYPES
from ..models import (AppSettings, CalendarEvent, MessSubscription, PassExtension, SlotBooking, StudentNotification, User)

PASS_DAYS = {"monthly": 30, "six_month": 180}
PASS_LABEL = {"monthly": "Monthly", "six_month": "Six-Month"}
REASONS = {"student_leave": "Student leave", "medical_leave": "Medical leave", "college_holiday": "College holiday",
           "special_permission": "Special permission", "other": "Other"}
HOLIDAY_TYPES = ("national", "festival", "college", "special")


def settings(db: Session) -> AppSettings:
    from .forecast import get_settings
    return get_settings(db)


# --- Subscriptions -------------------------------------------------------------------------------

def subscriptions(db: Session, user_id: int) -> list[MessSubscription]:
    return (db.query(MessSubscription).filter(MessSubscription.user_id == user_id, MessSubscription.cancelled.is_(False))
            .order_by(MessSubscription.start_date.desc(), MessSubscription.id.desc()).all())


def current_subscription(db: Session, user_id: int, on: date | None = None) -> MessSubscription | None:
    """The pass covering `on` (today by default); else the next upcoming one; else the latest."""
    on = on or date.today()
    subs = subscriptions(db, user_id)
    covering = [s for s in subs if s.start_date <= on <= s.expiry_date]
    if covering:
        return max(covering, key=lambda s: s.expiry_date)
    upcoming = [s for s in subs if s.start_date > on]
    if upcoming:
        return min(upcoming, key=lambda s: s.start_date)
    return subs[0] if subs else None


def pass_status(sub: MessSubscription | None, user: User, today: date | None = None, soon_days: int = 7) -> dict:
    today = today or date.today()
    if sub is None:
        return {"has_pass": False, "status": "none", "color": "red", "remaining_days": 0, "label": "No active pass",
                "suspended": user.suspended}
    ext_days = sum(e.added_days for e in sub.extensions)
    total = sub.base_days + ext_days
    if today < sub.start_date:
        remaining, used = total, 0
    elif today > sub.expiry_date:
        remaining, used = 0, total
    else:
        remaining = (sub.expiry_date - today).days + 1
        used = total - remaining
    if user.suspended:
        status = "suspended"
    elif today > sub.expiry_date:
        status = "expired"
    elif today < sub.start_date:
        status = "upcoming"
    elif remaining <= soon_days:
        status = "expiring_soon"
    else:
        status = "active"
    color = "red" if status in ("expired", "suspended") else "orange" if 1 <= remaining <= soon_days and status == "expiring_soon" else "green"
    label = {"active": "Active", "expiring_soon": "Expiring Soon", "expired": "Expired", "suspended": "Suspended",
             "upcoming": "Starts soon"}[status]
    return {
        "has_pass": True, "id": sub.id, "pass_type": sub.pass_type, "pass_label": PASS_LABEL.get(sub.pass_type, sub.pass_type),
        "purchase_date": str(sub.purchase_date), "start_date": str(sub.start_date), "expiry_date": str(sub.expiry_date),
        "base_days": sub.base_days, "extension_days": ext_days, "total_days": total, "used_days": used,
        "remaining_days": remaining, "progress_pct": round(remaining / total * 100, 1) if total else 0,
        "status": status, "label": label, "color": color, "suspended": user.suspended,
    }


def pass_covers(db: Session, user: User, d: date) -> bool:
    if user.suspended:
        return False
    return db.query(MessSubscription.id).filter(
        MessSubscription.user_id == user.id, MessSubscription.cancelled.is_(False),
        MessSubscription.start_date <= d, MessSubscription.expiry_date >= d).first() is not None


def require_pass(db: Session, user: User, d: date):
    if user.suspended:
        raise HTTPException(403, "Your mess pass is suspended. Please contact the canteen office.")
    if not pass_covers(db, user, d):
        raise HTTPException(403, f"Your mess pass does not cover {d:%d %b %Y}. Renew your pass to book meals.")


def students_with_pass(db: Session, d: date) -> set[int]:
    rows = (db.query(MessSubscription.user_id).join(User, User.id == MessSubscription.user_id)
            .filter(MessSubscription.cancelled.is_(False), MessSubscription.start_date <= d, MessSubscription.expiry_date >= d,
                    User.suspended.is_(False), User.is_active.is_(True), User.role == "student").distinct())
    return {r[0] for r in rows}


def create_subscription(db: Session, user: User, pass_type: str, start: date | None, admin_id: int | None) -> MessSubscription:
    if pass_type not in PASS_DAYS:
        raise HTTPException(400, "Pass type must be monthly or six_month")
    today = date.today()
    if start is None:
        cur = current_subscription(db, user.id)
        start = cur.expiry_date + timedelta(days=1) if cur and cur.expiry_date >= today else today
    overlap = db.query(MessSubscription).filter(
        MessSubscription.user_id == user.id, MessSubscription.cancelled.is_(False),
        MessSubscription.start_date <= start, MessSubscription.expiry_date >= start).first()
    if overlap:
        raise HTTPException(409, f"The student already has a pass until {overlap.expiry_date:%d %b %Y}. "
                                 f"Start the new pass on {overlap.expiry_date + timedelta(days=1):%d %b %Y} or later.")
    s = settings(db)
    days = PASS_DAYS[pass_type]
    sub = MessSubscription(user_id=user.id, pass_type=pass_type, purchase_date=today, start_date=start, base_days=days,
                           expiry_date=start + timedelta(days=days - 1),
                           price=s.price_monthly if pass_type == "monthly" else s.price_six_month,
                           created_at=datetime.now(), created_by=admin_id)
    db.add(sub)
    db.flush()
    notify_student(db, user.id, "pass", f"{PASS_LABEL[pass_type]} mess pass activated",
                   f"Valid {start:%d %b %Y} – {sub.expiry_date:%d %b %Y}.", "/student", f"pass:new:{sub.id}")
    return sub


def extend_pass(db: Session, user: User, days: int, reason: str, note: str, admin_id: int | None, request_key: str,
                leave_from: date | None = None, leave_to: date | None = None) -> tuple[PassExtension, bool]:
    """Returns (extension, created). Re-sending the same request_key returns the original extension."""
    existing = db.query(PassExtension).filter_by(request_key=request_key).first()
    if existing:
        return existing, False
    if not 1 <= days <= 90:
        raise HTTPException(400, "Extension must be between 1 and 90 days")
    if reason not in REASONS:
        raise HTTPException(400, "Choose a valid reason")
    sub = current_subscription(db, user.id)
    if sub is None:
        raise HTTPException(400, "This student has no mess pass to extend. Create or renew a pass first.")
    sub = db.query(MessSubscription).filter_by(id=sub.id).with_for_update().first()
    prev = sub.expiry_date
    ext = PassExtension(subscription_id=sub.id, user_id=user.id, previous_expiry=prev, added_days=days,
                        new_expiry=prev + timedelta(days=days), reason=reason, note=note or "", leave_from=leave_from,
                        leave_to=leave_to, admin_id=admin_id, request_key=request_key, created_at=datetime.now())
    db.add(ext)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.query(PassExtension).filter_by(request_key=request_key).one(), False
    sub.expiry_date = ext.new_expiry
    notify_student(db, user.id, "pass", f"Mess pass extended by {days} day{'s' if days > 1 else ''}",
                   f"{REASONS[reason]}. New expiry: {ext.new_expiry:%d %b %Y} (was {prev:%d %b %Y}).", "/student",
                   f"pass:ext:{ext.id}")
    return ext, True


# --- Closures & holidays -------------------------------------------------------------------------

def services_of(ev: CalendarEvent) -> set[str]:
    if ev.services:
        return {x for x in ev.services.split(",") if x in MEAL_TYPES}
    return set(MEAL_TYPES) if ev.canteen_closed else set()


def closures(db: Session, start: date, end: date) -> dict[date, dict]:
    """date -> {meal: reason} for every closed meal (Sundays + published holidays / closed events)."""
    out: dict[date, dict] = {}
    d = start
    while d <= end:
        if d.weekday() == 6:
            out[d] = {m: "Sunday – canteen closed" for m in MEAL_TYPES}
        d += timedelta(days=1)
    q = db.query(CalendarEvent).filter(CalendarEvent.date >= start, CalendarEvent.date <= end,
                                       CalendarEvent.published.is_(True))
    for ev in q:
        for m in services_of(ev):
            out.setdefault(ev.date, {}).setdefault(m, ev.name)
    return out


def meal_closed(cl: dict, d: date, meal: str) -> str | None:
    return cl.get(d, {}).get(meal)


def day_closed(cl: dict, d: date) -> str | None:
    x = cl.get(d, {})
    return next(iter(x.values())) if len(x) == len(MEAL_TYPES) else None


def services_label(services: set[str]) -> str:
    if services >= set(MEAL_TYPES):
        return "Full day (breakfast, lunch and dinner)"
    return ", ".join(m.capitalize() for m in MEAL_TYPES if m in services) or "No meals"


def publish_holiday(db: Session, ev: CalendarEvent, admin_id: int | None, update: bool = False) -> dict:
    """Apply a holiday: close meals, cancel affected bookings, notify students, optionally extend passes."""
    now = datetime.now()
    svc = services_of(ev)
    ev.published = True
    ev.published_at = ev.published_at or now
    ev.canteen_closed = svc >= set(MEAL_TYPES)
    cancelled = 0
    for b in db.query(SlotBooking).filter(SlotBooking.date == ev.date, SlotBooking.status == "booked",
                                          SlotBooking.meal_type.in_(svc)):
        b.status, b.cancelled_at = "cancelled", now
        cancelled += 1
        notify_student(db, b.user_id, "holiday", f"Booking cancelled: {ev.name}",
                       f"Your {b.meal_type} booking on {ev.date:%a %d %b} was cancelled because the canteen is closed.",
                       "/student/booking", f"holiday:{ev.id}:booking:{b.id}")
    students = [u for (u,) in db.query(User.id).filter(User.role == "student", User.is_active.is_(True))]
    title = f"{'Updated: ' if update else ''}{ev.name} – {ev.date:%a %d %b %Y}"
    body = (ev.message or f"The canteen is closed for: {services_label(svc)}.") + f" Unavailable: {services_label(svc)}."
    stamp = now.strftime("%Y%m%d%H%M%S") if update else "v1"
    for uid in students:
        notify_student(db, uid, "holiday", title, body, "/student", f"holiday:{ev.id}:{stamp}:{uid}")
    extended = 0
    s = settings(db)
    if s.holiday_extends_pass and ev.canteen_closed:
        for sub in db.query(MessSubscription).filter(MessSubscription.cancelled.is_(False),
                                                     MessSubscription.start_date <= ev.date, MessSubscription.expiry_date >= ev.date):
            user = db.get(User, sub.user_id)
            _, created = extend_pass(db, user, 1, "college_holiday", f"Holiday: {ev.name} ({ev.date:%d %b})", admin_id,
                                     f"holiday:{ev.id}:sub:{sub.id}")
            extended += int(created)
    return {"students_notified": len(students), "bookings_cancelled": cancelled, "passes_extended": extended}


def notify_student(db: Session, user_id: int, kind: str, title: str, body: str = "", link: str | None = None,
                   ref_key: str | None = None):
    if ref_key and db.query(StudentNotification.id).filter_by(ref_key=ref_key).first():
        return
    db.add(StudentNotification(user_id=user_id, kind=kind, title=title[:160], body=body, link=link, ref_key=ref_key,
                               created_at=datetime.now()))


def unread_count(db: Session, user_id: int) -> int:
    return db.query(func.count(StudentNotification.id)).filter(StudentNotification.user_id == user_id,
                                                                StudentNotification.read.is_(False)).scalar() or 0
