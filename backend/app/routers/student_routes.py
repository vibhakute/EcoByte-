"""Student APIs. Every query is scoped to the authenticated student (user.id from the token);
nothing here returns predictions, costs, other students' data or admin statistics."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import hash_password, require_student, verify_password
from ..config import MEAL_TYPES
from ..database import get_db
from ..models import (Attendance, CalendarEvent, Meal, MealAttendance, MealSlot, PassExtension, Product, Redemption, RenewalRequest,
                      Reward, RewardTransaction, SlotBooking, StoreOrder, StudentNotification, User)
from ..schemas import AttendanceIn, BookingIn, ChangeSlotIn, OrderIn, PasswordIn, ProfileIn, RedeemIn, RenewalRequestIn
from ..services import mess, store
from ..services import student_ops as ops
from ..services.forecast import deadline_for, get_settings
from ..services.history import attendance_calendar
from ..services.summary import upcoming_holidays
from .auth_routes import user_out

router = APIRouter(prefix="/api/student", tags=["student"])


def meal_out(m: Meal) -> dict:
    return {"id": m.id, "date": str(m.date), "meal_type": m.meal_type, "name": m.name,
            "items": [x.strip() for x in (m.items or "").splitlines() if x.strip()],
            "description": m.description, "is_veg": m.is_veg, "price": m.price, "available": m.available,
            "image": f"/api/uploads/{m.image}" if m.image else None}


def _menu(db: Session, d: date) -> dict:
    out = {m: [] for m in MEAL_TYPES}
    for m in db.query(Meal).filter(Meal.date == d, Meal.published.is_(True)).order_by(Meal.id):
        out[m.meal_type].append(meal_out(m))
    return out


def _slot_times(db: Session) -> dict:
    out = {}
    for s in db.query(MealSlot).filter(MealSlot.active.is_(True)).order_by(MealSlot.start_time):
        cur = out.setdefault(s.meal_type, [s.start_time, s.end_time])
        cur[0], cur[1] = min(cur[0], s.start_time), max(cur[1], s.end_time)
    return {k: f"{v[0]:%I:%M %p} - {v[1]:%I:%M %p}" for k, v in out.items()}


def _slot_ends(db: Session) -> dict:
    out = {}
    for s in db.query(MealSlot).filter(MealSlot.active.is_(True)):
        out[s.meal_type] = max(out.get(s.meal_type, s.end_time), s.end_time)
    return out


def _booking_out(db: Session, b: SlotBooking, s=None) -> dict:
    s = s or get_settings(db)
    co = ops.cutoff(s, b.date, b.slot)
    return {"id": b.id, "date": str(b.date), "meal_type": b.meal_type, "status": b.status, "state": ops.booking_state(b, s),
            "code": b.code, "slot_id": b.slot_id, "start": b.slot.start_time.strftime("%I:%M %p"), "end": b.slot.end_time.strftime("%I:%M %p"),
            "deadline": co.isoformat(timespec="minutes"), "created_at": b.created_at.isoformat(timespec="minutes"),
            "cancelled_at": b.cancelled_at.isoformat(timespec="minutes") if b.cancelled_at else None}


def _pass(db: Session, user: User) -> dict:
    s = get_settings(db)
    return mess.pass_status(mess.current_subscription(db, user.id), user, date.today(), s.expiring_soon_days)


def _week(db: Session, user: User, week_start: date) -> dict:
    s = get_settings(db)
    now = datetime.now()
    days = [week_start + timedelta(days=i) for i in range(7)]
    cl = mess.closures(db, days[0], days[-1])
    events = {e.date: e.name for e in db.query(CalendarEvent).filter(CalendarEvent.date >= days[0], CalendarEvent.date <= days[-1],
                                                                       CalendarEvent.published.is_(True))}
    rows = db.query(Attendance).filter(Attendance.user_id == user.id, Attendance.date >= days[0], Attendance.date <= days[-1]).all()
    by = {(r.date, r.meal_type): r for r in rows}
    present = {(r.date, r.meal_type) for r in db.query(MealAttendance).filter(
        MealAttendance.user_id == user.id, MealAttendance.date >= days[0], MealAttendance.date <= days[-1])}
    last = now.date() + timedelta(days=s.attendance_window_days)
    out = []
    for d in days:
        dl = deadline_for(s, d)
        covered = mess.pass_covers(db, user, d)
        meals = {}
        for m in MEAL_TYPES:
            r = by.get((d, m))
            meals[m] = {"status": r.status if r else None, "cancelled": r.cancelled if r else False,
                        "arrived": (d, m) in present, "closed": mess.meal_closed(cl, d, m),
                        "confirmed_at": r.confirmed_at.isoformat(timespec="minutes") if r else None}
        full = mess.day_closed(cl, d)
        out.append({
            "date": str(d), "weekday": d.strftime("%a"), "closed": full is not None, "closed_reason": full,
            "event": events.get(d), "deadline": dl.isoformat(timespec="minutes"), "covered": covered,
            "locked": full is not None or now >= dl or d > last or not covered, "too_far": d > last, "past": d < now.date(),
            "meals": meals,
        })
    open_days = [x for x in out if not x["closed"] and x["covered"]]
    confirmed_days = sum(1 for x in open_days if any(v["status"] == "coming" for v in x["meals"].values()))
    return {"week_start": str(week_start), "days": out, "deadline_time": s.attendance_deadline.strftime("%H:%M"),
            "points_per_confirmation": s.points_per_confirmation, "weekly_bonus": s.weekly_streak_bonus,
            "open_days": len(open_days), "confirmed_days": confirmed_days}


def _next_reward(db: Session, bal: int) -> dict | None:
    rewards = db.query(Reward).filter(Reward.active.is_(True), Reward.stock > 0).order_by(Reward.points_cost).all()
    nxt = next((r for r in rewards if r.points_cost > bal), None) or (rewards[-1] if rewards else None)
    if nxt is None:
        return None
    return {"id": nxt.id, "name": nxt.name, "points_cost": nxt.points_cost,
            "progress": min(100, round(bal / nxt.points_cost * 100)), "remaining": max(0, nxt.points_cost - bal)}


def _activity(db: Session, user: User, limit: int = 6) -> list[dict]:
    items = []
    for t in db.query(RewardTransaction).filter_by(user_id=user.id).order_by(RewardTransaction.created_at.desc()).limit(limit):
        items.append({"kind": "points", "text": t.description, "points": t.points, "at": t.created_at.isoformat(timespec="minutes")})
    for b in db.query(SlotBooking).filter_by(user_id=user.id).order_by(SlotBooking.created_at.desc()).limit(limit):
        verb = {"booked": "Booked", "served": "Ate", "cancelled": "Cancelled"}[b.status]
        items.append({"kind": "booking", "text": f"{verb} {b.meal_type} slot {b.slot.start_time:%I:%M %p} on {b.date:%a %d %b}",
                      "at": (b.cancelled_at or b.created_at).isoformat(timespec="minutes")})
    for a in db.query(Attendance).filter_by(user_id=user.id).order_by(Attendance.updated_at.desc()).limit(limit):
        verb = "Confirmed" if a.status == "coming" else "Declined"
        items.append({"kind": "attendance", "text": f"{verb} {a.meal_type} for {a.date:%a %d %b}", "at": a.updated_at.isoformat(timespec="minutes")})
    return sorted(items, key=lambda x: x["at"], reverse=True)[:limit]


def _today_meals(db: Session, user: User, d: date) -> list[dict]:
    """Three cards (breakfast, lunch, dinner) with menu + booking availability for this student."""
    s = get_settings(db)
    now = datetime.now()
    menu = _menu(db, d)
    hours = _slot_times(db)
    cl = mess.closures(db, d, d)
    counts = ops.slot_counts(db, d)
    slots = db.query(MealSlot).filter(MealSlot.active.is_(True)).all()
    mine = {b.meal_type: b for b in db.query(SlotBooking).filter_by(user_id=user.id, date=d).filter(SlotBooking.status != "cancelled")}
    covered = mess.pass_covers(db, user, d)
    out = []
    for m in MEAL_TYPES:
        ms = [x for x in slots if x.meal_type == m]
        open_slots = [x for x in ms if now < ops.cutoff(s, d, x)]
        seats = sum(max(0, x.capacity - counts.get(x.id, 0)) for x in open_slots)
        closed = mess.meal_closed(cl, d, m)
        b = mine.get(m)
        if closed:
            availability, label = "closed", f"Unavailable · {closed}"
        elif b:
            availability, label = ops.booking_state(b, s), f"Booked {b.slot.start_time:%I:%M %p}"
        elif not covered:
            availability, label = "no_pass", "Needs an active mess pass"
        elif not open_slots:
            availability, label = "booking_closed", "Booking closed for today"
        elif seats == 0:
            availability, label = "full", "All slots full"
        else:
            availability, label = "open", f"{seats} seats left"
        out.append({"meal_type": m, "hours": hours.get(m), "items": menu[m], "availability": availability, "label": label,
                    "booking": _booking_out(db, b, s) if b else None})
    return out


@router.get("/dashboard")
def dashboard(user: User = Depends(require_student), db: Session = Depends(get_db)):
    now = datetime.now()
    today = now.date()
    s = get_settings(db)
    ends = _slot_ends(db)
    meals = _today_meals(db, user, today)
    current = next((m["meal_type"] for m in meals if m["meal_type"] in ends and now.time() <= ends[m["meal_type"]] and m["items"]), None) \
        or next((m["meal_type"] for m in reversed(meals) if m["items"]), None)
    bal = ops.balance(db, user.id)
    upcoming = (db.query(SlotBooking).filter(SlotBooking.user_id == user.id, SlotBooking.date >= today, SlotBooking.status == "booked")
                .order_by(SlotBooking.date).limit(5).all())
    monday = today - timedelta(days=today.weekday())
    week = _week(db, user, monday)
    nxt = _week(db, user, monday + timedelta(days=7))
    pending = sum(1 for d in week["days"] + nxt["days"] if not d["locked"] and any(v["status"] is None and not v["closed"] for v in d["meals"].values()))
    notes = db.query(StudentNotification).filter_by(user_id=user.id).order_by(StudentNotification.created_at.desc()).limit(5).all()
    return {
        "user": user_out(user), "today": str(today), "balance": bal, "next_reward": _next_reward(db, bal),
        "pass": _pass(db, user), "today_meals": meals, "current_meal": current, "service_hours": _slot_times(db),
        "menu_today": {m["meal_type"]: m["items"] for m in meals},
        "upcoming_bookings": [_booking_out(db, b, s) for b in upcoming], "this_week": week, "pending_days": pending,
        "tomorrow_deadline": deadline_for(s, today + timedelta(days=1)).isoformat(timespec="minutes"),
        "activity": _activity(db, user), "holidays": upcoming_holidays(db, 45, 3),
        "notifications": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "read": n.read,
                           "created_at": n.created_at.isoformat(timespec="minutes")} for n in notes],
        "unread": mess.unread_count(db, user.id),
        "active_coupons": db.query(Redemption).filter_by(user_id=user.id, status="active").count(),
    }


# --- Mess pass -------------------------------------------------------------------------------------

@router.get("/subscription")
def subscription(user: User = Depends(require_student), db: Session = Depends(get_db)):
    s = get_settings(db)
    exts = db.query(PassExtension).filter_by(user_id=user.id).order_by(PassExtension.created_at.desc()).all()
    req = db.query(RenewalRequest).filter_by(user_id=user.id).order_by(RenewalRequest.created_at.desc()).first()
    return {"pass": _pass(db, user), "prices": {"monthly": s.price_monthly, "six_month": s.price_six_month},
            "extensions": [{"added_days": e.added_days, "reason": mess.REASONS.get(e.reason, e.reason), "previous_expiry": str(e.previous_expiry),
                            "new_expiry": str(e.new_expiry), "created_at": e.created_at.isoformat(timespec="minutes")} for e in exts],
            "renewal_request": {"pass_type": req.pass_type, "status": req.status, "created_at": req.created_at.isoformat(timespec="minutes")} if req else None}


@router.post("/renewal-request")
def renewal_request(body: RenewalRequestIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if db.query(RenewalRequest).filter_by(user_id=user.id, status="pending").first():
        raise HTTPException(409, "You already have a pending renewal request.")
    from ..models import Notification
    db.add(RenewalRequest(user_id=user.id, pass_type=body.pass_type, note=body.note, created_at=datetime.now()))
    db.add(Notification(kind="pass", title=f"Pass renewal request: {user.name}",
                        body=f"{mess.PASS_LABEL[body.pass_type]} pass · {user.student_code}", link="/admin/students",
                        created_at=datetime.now()))
    db.commit()
    return {"ok": True}


# --- Notifications & holidays -----------------------------------------------------------------------

@router.get("/notifications")
def notifications(user: User = Depends(require_student), db: Session = Depends(get_db)):
    rows = db.query(StudentNotification).filter_by(user_id=user.id).order_by(StudentNotification.created_at.desc()).limit(50).all()
    return {"unread": mess.unread_count(db, user.id), "items": [
        {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read,
         "created_at": n.created_at.isoformat(timespec="minutes")} for n in rows]}


@router.post("/notifications/read")
def read_notifications(user: User = Depends(require_student), db: Session = Depends(get_db)):
    db.query(StudentNotification).filter_by(user_id=user.id, read=False).update({StudentNotification.read: True})
    db.commit()
    return {"ok": True}


@router.get("/holidays")
def holidays(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return upcoming_holidays(db, 120, 20)


# --- Attendance ------------------------------------------------------------------------------------

@router.get("/attendance")
def get_attendance(week_start: date | None = None, user: User = Depends(require_student), db: Session = Depends(get_db)):
    today = date.today()
    ws = week_start or (today - timedelta(days=today.weekday()))
    return _week(db, user, ws - timedelta(days=ws.weekday()))


@router.post("/attendance")
def post_attendance(body: AttendanceIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return ops.submit_attendance(db, user, body.items)


@router.get("/attendance/calendar")
def attendance_cal(start: date | None = None, end: date | None = None, user: User = Depends(require_student),
                   db: Session = Depends(get_db)):
    end = end or date.today()
    start = start or end - timedelta(days=30)
    if start > end:
        raise HTTPException(400, "Start date must be before end date")
    return attendance_calendar(db, user, start, end)


@router.get("/history")
def history(start: date | None = None, end: date | None = None, user: User = Depends(require_student), db: Session = Depends(get_db)):
    end = end or date.today() + timedelta(days=14)
    start = start or date.today() - timedelta(days=30)
    if start > end:
        raise HTTPException(400, "Start date must be before end date")
    s = get_settings(db)
    att = (db.query(Attendance).filter(Attendance.user_id == user.id, Attendance.date >= start, Attendance.date <= end)
           .order_by(Attendance.date.desc(), Attendance.meal_type).all())
    books = (db.query(SlotBooking).filter(SlotBooking.user_id == user.id, SlotBooking.date >= start, SlotBooking.date <= end)
             .order_by(SlotBooking.date.desc()).all())
    present = {(r.date, r.meal_type) for r in db.query(MealAttendance).filter(
        MealAttendance.user_id == user.id, MealAttendance.date >= start, MealAttendance.date <= end)}
    s_dt, e_dt = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())
    ledger = (db.query(RewardTransaction).filter(RewardTransaction.user_id == user.id, RewardTransaction.created_at >= s_dt,
                                                 RewardTransaction.created_at <= e_dt).order_by(RewardTransaction.created_at.desc()).all())
    return {
        "range": {"start": str(start), "end": str(end)},
        "attendance": [{"date": str(a.date), "meal_type": a.meal_type, "status": a.status, "cancelled": a.cancelled,
                        "arrived": (a.date, a.meal_type) in present, "confirmed_at": a.confirmed_at.isoformat(timespec="minutes"),
                        "updated_at": a.updated_at.isoformat(timespec="minutes")} for a in att],
        "bookings": [_booking_out(db, b, s) for b in books],
        "ledger": [{"id": t.id, "points": t.points, "kind": t.kind, "description": t.description,
                    "created_at": t.created_at.isoformat(timespec="minutes")} for t in ledger],
        "participation": {"meals_confirmed": sum(1 for a in att if a.status == "coming"),
                          "meals_declined": sum(1 for a in att if a.status == "not_coming"),
                          "meals_attended": len(present), "bookings": sum(1 for b in books if b.status != "cancelled"),
                          "points_earned": sum(t.points for t in ledger if t.points > 0)},
    }


# --- Menu & bookings --------------------------------------------------------------------------------

@router.get("/menu")
def menu(d: date | None = Query(None, alias="date"), user: User = Depends(require_student), db: Session = Depends(get_db)):
    d = d or date.today()
    cl = mess.closures(db, d, d)
    full = mess.day_closed(cl, d)
    return {"date": str(d), "closed": full is not None, "closed_reason": full, "closed_meals": cl.get(d, {}),
            "meals": _menu(db, d), "service_hours": _slot_times(db)}


@router.get("/slots")
def slots(d: date | None = Query(None, alias="date"), user: User = Depends(require_student), db: Session = Depends(get_db)):
    d = d or date.today()
    now = datetime.now()
    s = get_settings(db)
    counts = ops.slot_counts(db, d)
    mine = {b.slot_id: b for b in db.query(SlotBooking).filter_by(user_id=user.id, date=d).filter(SlotBooking.status != "cancelled")}
    att = {a.meal_type: a.status for a in db.query(Attendance).filter_by(user_id=user.id, date=d)}
    cl = mess.closures(db, d, d)
    out = {m: [] for m in MEAL_TYPES}
    for sl in db.query(MealSlot).filter(MealSlot.active.is_(True)).order_by(MealSlot.start_time):
        taken = counts.get(sl.id, 0)
        co = ops.cutoff(s, d, sl)
        out[sl.meal_type].append({
            "id": sl.id, "start": sl.start_time.strftime("%I:%M %p"), "end": sl.end_time.strftime("%I:%M %p"),
            "capacity": sl.capacity, "booked": taken, "available": max(0, sl.capacity - taken),
            "deadline": co.isoformat(timespec="minutes"), "past": now >= co,
            "mine": _booking_out(db, mine[sl.id], s) if sl.id in mine else None,
        })
    return {"date": str(d), "closed": mess.day_closed(cl, d) is not None, "closed_reason": mess.day_closed(cl, d),
            "closed_meals": cl.get(d, {}), "slots": out, "attendance": att, "cancel_minutes": s.booking_cancel_minutes,
            "has_pass": mess.pass_covers(db, user, d), "pass": _pass(db, user), "menu": {k: [x["name"] for x in v] for k, v in _menu(db, d).items()}}


@router.post("/bookings")
def create_booking(body: BookingIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return _booking_out(db, ops.book_slot(db, user, body.slot_id, body.date))


@router.get("/bookings")
def bookings(user: User = Depends(require_student), db: Session = Depends(get_db)):
    s = get_settings(db)
    rows = (db.query(SlotBooking).filter(SlotBooking.user_id == user.id)
            .order_by(SlotBooking.date.desc(), SlotBooking.created_at.desc()).limit(200).all())
    return [_booking_out(db, b, s) for b in rows]


@router.post("/bookings/{booking_id}/change")
def change_booking(booking_id: int, body: ChangeSlotIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return _booking_out(db, ops.change_slot(db, user, booking_id, body.slot_id))


@router.post("/bookings/{booking_id}/cancel")
def cancel(booking_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return _booking_out(db, ops.cancel_booking(db, user, booking_id))


# --- Rewards & coupons ------------------------------------------------------------------------------

@router.get("/rewards")
def rewards(user: User = Depends(require_student), db: Session = Depends(get_db)):
    ops.expire_coupons(db, user.id)
    ledger = (db.query(RewardTransaction).filter_by(user_id=user.id)
              .order_by(RewardTransaction.created_at.desc(), RewardTransaction.id.desc()).limit(300).all())
    bal = ops.balance(db, user.id)
    reds = db.query(Redemption).filter_by(user_id=user.id).order_by(Redemption.created_at.desc()).all()
    s = get_settings(db)
    return {
        "balance": bal, "earned": sum(t.points for t in ledger if t.points > 0 and t.kind != "refund"),
        "redeemed": -sum(t.points for t in ledger if t.kind == "redeem") - sum(t.points for t in ledger if t.kind == "refund"),
        "next_reward": _next_reward(db, bal),
        "rules": {"per_attended_meal": s.tokens_per_attended_meal, "per_planned_day": s.points_per_confirmation,
                  "weekly_bonus": s.weekly_streak_bonus, "coupon_validity_days": s.coupon_validity_days},
        "points_per_confirmation": s.points_per_confirmation, "weekly_bonus": s.weekly_streak_bonus,
        "ledger": [{"id": t.id, "points": t.points, "kind": t.kind, "description": t.description,
                    "created_at": t.created_at.isoformat(timespec="minutes")} for t in ledger],
        "catalog": [{"id": r.id, "name": r.name, "description": r.description, "points_cost": r.points_cost, "in_stock": r.stock > 0}
                    for r in db.query(Reward).filter(Reward.active.is_(True)).order_by(Reward.points_cost)],
        "redemptions": [{"id": r.id, "reward": r.reward.name, "points": r.points, "code": r.code, "status": r.status,
                         "created_at": r.created_at.isoformat(timespec="minutes"),
                         "expires_at": r.expires_at.isoformat(timespec="minutes") if r.expires_at else None,
                         "redeemed_at": r.redeemed_at.isoformat(timespec="minutes") if r.redeemed_at else None} for r in reds],
    }


@router.post("/rewards/redeem")
def redeem(body: RedeemIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    r = ops.redeem(db, user, body.reward_id)
    return {"code": r.code, "reward": r.reward.name, "points": r.points, "balance": ops.balance(db, user.id),
            "expires_at": r.expires_at.isoformat(timespec="minutes") if r.expires_at else None}


# --- Canteen store ------------------------------------------------------------------------------------

@router.get("/store/products")
def store_products(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return [store.product_out(p) for p in db.query(Product).order_by(Product.category, Product.name)]


@router.post("/store/orders")
def place_order(body: OrderIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if user.suspended:
        raise HTTPException(403, "Your account is suspended. Please contact the canteen office.")
    return store.order_out(store.place_order(db, user, body.items, body.note))


@router.get("/store/orders")
def my_orders(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return [store.order_out(o) for o in db.query(StoreOrder).filter_by(user_id=user.id).order_by(StoreOrder.created_at.desc()).limit(50)]


@router.post("/store/orders/{oid}/cancel")
def cancel_order(oid: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    o = db.query(StoreOrder).filter_by(id=oid, user_id=user.id).first()
    if not o:
        raise HTTPException(404, "Order not found")
    return store.order_out(store.set_status(db, o, "cancelled", by_student=True))


# --- Profile ------------------------------------------------------------------------------------------

@router.get("/profile")
def profile(user: User = Depends(require_student), db: Session = Depends(get_db)):
    total = db.query(Attendance).filter_by(user_id=user.id).count()
    return {**user_out(user), "member_since": user.created_at.date().isoformat() if user.created_at else None,
            "total_responses": total, "balance": ops.balance(db, user.id), "pass": _pass(db, user)}


@router.patch("/profile")
def update_profile(body: ProfileIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return user_out(user)


@router.post("/password")
def change_password(body: PasswordIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@router.get("/impact")
def my_impact(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Small live numbers for the student sidebar."""
    today = date.today()
    meals = db.query(MealAttendance).filter(MealAttendance.user_id == user.id, MealAttendance.date >= today - timedelta(days=6),
                                            MealAttendance.date <= today).count()
    st = mess.pass_status(mess.current_subscription(db, user.id), user, today, mess.settings(db).expiring_soon_days)
    return {"meals_week": meals, "tokens": ops.balance(db, user.id), "pass_days": st["remaining_days"], "pass_status": st["status"]}
