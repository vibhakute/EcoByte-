"""Admin APIs added in the operations upgrade: students & passes, renewals, holidays,
attendance recording, canteen store, coupons, direct donation assignment. All require admin."""
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..config import MEAL_TYPES
from ..database import get_db
from ..models import (Attendance, CalendarEvent, Donation, MealAttendance, MessSubscription, NgoContact, PassExtension,
                      Product, Redemption, RenewalRequest, SlotBooking, StoreOrder, StoreOrderItem, User)
from ..schemas import (AssignIn, CouponCodeIn, ExtendIn, HolidayIn, MarkAttendanceIn, OrderStatusIn, ProductIn, RenewalActionIn,
                       RenewIn, StudentCreateIn, StudentUpdateIn, SuspendIn)
from ..services import donations as D
from ..services import mess, store
from ..services import student_ops as ops
from ..services.history import attendance_calendar
from .admin_routes import _save_image
from .auth_routes import user_out

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# --- Student management -------------------------------------------------------------------------

def _student_row(db: Session, u: User, today: date, soon: int) -> dict:
    st = mess.pass_status(mess.current_subscription(db, u.id, today), u, today, soon)
    return {"id": u.id, "name": u.name, "student_code": u.student_code, "email": u.email, "phone": u.phone,
            "department": u.department, "year_of_study": u.year_of_study, "is_active": u.is_active,
            "token_balance": u.token_balance, "pass": st}


@router.get("/students")
def students(q: str | None = None, status: str | None = None, pass_type: str | None = None,
             sort: str = "name", direction: str = "asc", page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200),
             db: Session = Depends(get_db)):
    today = date.today()
    soon = mess.settings(db).expiring_soon_days
    base = db.query(User).filter(User.role == "student")
    if q:
        like = f"%{q.strip()}%"
        base = base.filter(or_(User.name.ilike(like), User.student_code.ilike(like), User.email.ilike(like)))
    rows = [_student_row(db, u, today, soon) for u in base.all()]
    if status == "valid":
        rows = [r for r in rows if r["pass"]["status"] in ("active", "expiring_soon")]
    elif status:
        rows = [r for r in rows if r["pass"]["status"] == status]
    if pass_type:
        rows = [r for r in rows if r["pass"].get("pass_type") == pass_type]
    keys = {
        "name": lambda r: r["name"].lower(), "student_code": lambda r: r["student_code"] or "",
        "expiry_date": lambda r: r["pass"].get("expiry_date") or "", "remaining_days": lambda r: r["pass"].get("remaining_days", -1),
        "status": lambda r: r["pass"]["status"], "purchase_date": lambda r: r["pass"].get("purchase_date") or "",
    }
    rows.sort(key=keys.get(sort, keys["name"]), reverse=direction == "desc")
    counts: dict = {}
    for u in db.query(User).filter(User.role == "student"):
        stt = mess.pass_status(mess.current_subscription(db, u.id, today), u, today, soon)["status"]
        counts[stt] = counts.get(stt, 0) + 1
    return {"total": len(rows), "page": page, "size": size, "counts": counts, "items": rows[(page - 1) * size: page * size]}


def _get_student(db: Session, user_id: int) -> User:
    u = db.query(User).filter_by(id=user_id, role="student").first()
    if not u:
        raise HTTPException(404, "Student not found")
    return u


@router.post("/students")
def create_student(body: StudentCreateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    email = body.email.strip().lower()
    code = body.student_code.strip().upper()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "A user with this email already exists")
    if db.query(User).filter(User.student_code == code).first():
        raise HTTPException(409, "This student ID is already registered")
    temp = None if body.password else secrets.token_urlsafe(8)
    u = User(role="student", email=email, name=body.name.strip(), student_code=code, phone=body.phone,
             department=body.department, year_of_study=body.year_of_study, password_hash=hash_password(body.password or temp))
    db.add(u)
    db.flush()
    if body.pass_type:
        mess.create_subscription(db, u, body.pass_type, body.start_date, admin.id)
    db.commit()
    return {"student": _student_row(db, u, date.today(), mess.settings(db).expiring_soon_days), "temporary_password": temp}


@router.get("/students/{user_id}")
def student_profile(user_id: int, db: Session = Depends(get_db)):
    u = _get_student(db, user_id)
    today = date.today()
    soon = mess.settings(db).expiring_soon_days
    subs = mess.subscriptions(db, u.id)
    admins = {a.id: a.name for a in db.query(User).filter(User.role == "admin")}
    exts = (db.query(PassExtension).filter(PassExtension.user_id == u.id).order_by(PassExtension.created_at.desc()).all())
    cal = attendance_calendar(db, u, (subs[-1].start_date if subs else today - timedelta(days=30)), today)
    return {
        **user_out(u), "is_active": u.is_active, "suspended": u.suspended, "token_balance": u.token_balance,
        "created_at": u.created_at.isoformat(timespec="minutes") if u.created_at else None,
        "pass": mess.pass_status(mess.current_subscription(db, u.id, today), u, today, soon),
        "subscriptions": [{"id": s.id, "pass_type": s.pass_type, "pass_label": mess.PASS_LABEL[s.pass_type],
                           "purchase_date": str(s.purchase_date), "start_date": str(s.start_date), "expiry_date": str(s.expiry_date),
                           "base_days": s.base_days, "price": s.price,
                           "state": "current" if s.start_date <= today <= s.expiry_date else "upcoming" if s.start_date > today else "past"}
                          for s in subs],
        "extensions": [{"id": e.id, "previous_expiry": str(e.previous_expiry), "added_days": e.added_days, "new_expiry": str(e.new_expiry),
                        "reason": e.reason, "reason_label": mess.REASONS.get(e.reason, e.reason), "note": e.note,
                        "leave_from": str(e.leave_from) if e.leave_from else None, "leave_to": str(e.leave_to) if e.leave_to else None,
                        "admin": admins.get(e.admin_id, "System"), "created_at": e.created_at.isoformat(timespec="minutes")} for e in exts],
        "renewals": [{"id": r.id, "pass_type": r.pass_type, "status": r.status, "created_at": r.created_at.isoformat(timespec="minutes")}
                     for r in db.query(RenewalRequest).filter_by(user_id=u.id).order_by(RenewalRequest.created_at.desc()).limit(10)],
        "attendance_summary": cal["summary"],
    }


@router.patch("/students/{user_id}")
def update_student(user_id: int, body: StudentUpdateIn, db: Session = Depends(get_db)):
    u = _get_student(db, user_id)
    data = body.model_dump(exclude_unset=True)
    if "email" in data:
        data["email"] = data["email"].strip().lower()
        if db.query(User).filter(User.email == data["email"], User.id != u.id).first():
            raise HTTPException(409, "Another account uses this email")
    for k, v in data.items():
        setattr(u, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    return {"ok": True}


@router.post("/students/{user_id}/extend")
def extend(user_id: int, body: ExtendIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = _get_student(db, user_id)
    if body.leave_from and body.leave_to and body.leave_to < body.leave_from:
        raise HTTPException(400, "Leave end date must be after the start date")
    ext, created = mess.extend_pass(db, u, body.days, body.reason, body.note, admin.id, body.request_key,
                                    body.leave_from, body.leave_to)
    db.commit()
    return {"created": created, "previous_expiry": str(ext.previous_expiry), "new_expiry": str(ext.new_expiry),
            "added_days": ext.added_days, "duplicate": not created}


@router.post("/students/{user_id}/renew")
def renew(user_id: int, body: RenewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = _get_student(db, user_id)
    sub = mess.create_subscription(db, u, body.pass_type, body.start_date, admin.id)
    db.query(RenewalRequest).filter_by(user_id=u.id, status="pending").update({RenewalRequest.status: "approved",
                                                                              RenewalRequest.handled_at: datetime.now()})
    db.commit()
    return {"start_date": str(sub.start_date), "expiry_date": str(sub.expiry_date)}


@router.post("/students/{user_id}/suspend")
def suspend(user_id: int, body: SuspendIn, db: Session = Depends(get_db)):
    u = _get_student(db, user_id)
    u.suspended = body.suspended
    cancelled = 0
    if body.suspended:
        now = datetime.now()
        for b in db.query(SlotBooking).filter(SlotBooking.user_id == u.id, SlotBooking.date >= date.today(), SlotBooking.status == "booked"):
            b.status, b.cancelled_at = "cancelled", now
            cancelled += 1
        mess.notify_student(db, u.id, "pass", "Mess pass suspended", body.reason or "Please contact the canteen office.", "/student")
    else:
        mess.notify_student(db, u.id, "pass", "Mess pass reactivated", "You can book meals again.", "/student")
    db.commit()
    return {"suspended": u.suspended, "bookings_cancelled": cancelled}


@router.post("/students/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_db)):
    u = _get_student(db, user_id)
    temp = secrets.token_urlsafe(8)
    u.password_hash = hash_password(temp)
    db.commit()
    return {"temporary_password": temp}


@router.get("/students/{user_id}/attendance")
def student_attendance(user_id: int, start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    u = _get_student(db, user_id)
    end = end or date.today()
    start = start or end - timedelta(days=30)
    if start > end:
        raise HTTPException(400, "Start date must be before end date")
    return attendance_calendar(db, u, start, end)


@router.get("/renewals")
def renewals(status: str = "pending", db: Session = Depends(get_db)):
    rows = (db.query(RenewalRequest, User).join(User, User.id == RenewalRequest.user_id)
            .filter(RenewalRequest.status == status).order_by(RenewalRequest.created_at).all())
    return [{"id": r.id, "user_id": u.id, "name": u.name, "student_code": u.student_code, "pass_type": r.pass_type,
             "pass_label": mess.PASS_LABEL[r.pass_type], "note": r.note, "created_at": r.created_at.isoformat(timespec="minutes")}
            for r, u in rows]


@router.post("/renewals/{req_id}")
def handle_renewal(req_id: int, body: RenewalActionIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    r = db.get(RenewalRequest, req_id)
    if not r or r.status != "pending":
        raise HTTPException(404, "Pending request not found")
    u = _get_student(db, r.user_id)
    if body.action == "approve":
        mess.create_subscription(db, u, r.pass_type, body.start_date, admin.id)
        r.status = "approved"
    else:
        r.status = "rejected"
        mess.notify_student(db, u.id, "pass", "Pass renewal request declined", body.note or "Please contact the canteen office.", "/student")
    r.handled_at = datetime.now()
    db.commit()
    return {"status": r.status}


# --- Holidays ---------------------------------------------------------------------------------------

def _holiday_out(e: CalendarEvent) -> dict:
    svc = mess.services_of(e)
    return {"id": e.id, "name": e.name, "date": str(e.date), "holiday_type": e.holiday_type or "college", "description": e.description,
            "services": [m for m in MEAL_TYPES if m in svc], "services_label": mess.services_label(svc), "message": e.message,
            "published": e.published, "published_at": e.published_at.isoformat(timespec="minutes") if e.published_at else None,
            "past": e.date < date.today()}


@router.get("/holidays")
def holidays(scope: str = "upcoming", db: Session = Depends(get_db)):
    q = db.query(CalendarEvent).filter(CalendarEvent.kind == "holiday")
    today = date.today()
    if scope == "upcoming":
        q = q.filter(CalendarEvent.date >= today).order_by(CalendarEvent.date)
    elif scope == "past":
        q = q.filter(CalendarEvent.date < today).order_by(CalendarEvent.date.desc())
    else:
        q = q.order_by(CalendarEvent.date.desc())
    return [_holiday_out(e) for e in q.limit(200)]


def _apply(e: CalendarEvent, body: HolidayIn):
    e.name, e.date, e.holiday_type = body.name.strip(), body.date, body.holiday_type
    e.description, e.message = body.description, body.message
    e.services = ",".join(m for m in MEAL_TYPES if m in body.services)


@router.post("/holidays")
def add_holiday(body: HolidayIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.date < date.today():
        raise HTTPException(400, "Holidays can only be created for today or a future date")
    if db.query(CalendarEvent).filter_by(date=body.date, name=body.name.strip()).first():
        raise HTTPException(409, "A holiday with this name already exists on that date")
    e = CalendarEvent(kind="holiday", published=False, canteen_closed=False, created_at=datetime.now())
    _apply(e, body)
    db.add(e)
    db.flush()
    result = mess.publish_holiday(db, e, admin.id) if body.publish else None
    db.commit()
    from ..services import prediction as P
    P.invalidate()
    return {"holiday": _holiday_out(e), "published": result}


@router.put("/holidays/{hid}")
def edit_holiday(hid: int, body: HolidayIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    e = db.query(CalendarEvent).filter_by(id=hid, kind="holiday").first()
    if not e:
        raise HTTPException(404, "Holiday not found")
    if e.date < date.today():
        raise HTTPException(400, "Past holidays cannot be edited")
    if body.date < date.today():
        raise HTTPException(400, "Choose today or a future date")
    _apply(e, body)
    result = None
    if e.published or body.publish:
        result = mess.publish_holiday(db, e, admin.id, update=e.published)
    db.commit()
    from ..services import prediction as P
    P.invalidate()
    return {"holiday": _holiday_out(e), "published": result}


@router.post("/holidays/{hid}/publish")
def publish(hid: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    e = db.query(CalendarEvent).filter_by(id=hid, kind="holiday").first()
    if not e:
        raise HTTPException(404, "Holiday not found")
    if e.published:
        raise HTTPException(409, "This holiday has already been published")
    if e.date < date.today():
        raise HTTPException(400, "Cannot publish a holiday in the past")
    result = mess.publish_holiday(db, e, admin.id)
    db.commit()
    from ..services import prediction as P
    P.invalidate()
    return {"holiday": _holiday_out(e), "published": result}


@router.delete("/holidays/{hid}")
def delete_holiday(hid: int, db: Session = Depends(get_db)):
    e = db.query(CalendarEvent).filter_by(id=hid, kind="holiday").first()
    if not e:
        raise HTTPException(404, "Holiday not found")
    if e.date < date.today():
        raise HTTPException(400, "Past holidays are kept for the record")
    if e.published:
        for (uid,) in db.query(User.id).filter(User.role == "student", User.is_active.is_(True)):
            mess.notify_student(db, uid, "holiday", f"Cancelled: {e.name} ({e.date:%a %d %b})",
                                "The canteen will be open as usual. You can confirm and book meals again.", "/student",
                                f"holiday:{e.id}:deleted:{uid}")
    db.delete(e)
    db.commit()
    from ..services import prediction as P
    P.invalidate()
    return {"ok": True}


# --- Attendance recording ---------------------------------------------------------------------------

@router.get("/attendance/roll")
def roll(d: date = Query(default_factory=date.today, alias="date"), meal: str = "lunch", q: str | None = None,
         db: Session = Depends(get_db)):
    if meal not in MEAL_TYPES:
        raise HTTPException(400, "Unknown meal")
    closed = mess.meal_closed(mess.closures(db, d, d), d, meal)
    eligible = mess.students_with_pass(db, d)
    plans = {a.user_id: a.status for a in db.query(Attendance).filter_by(date=d, meal_type=meal)}
    books = {b.user_id: b for b in db.query(SlotBooking).filter(SlotBooking.date == d, SlotBooking.meal_type == meal,
                                                                 SlotBooking.status != "cancelled")}
    present = {r.user_id: r for r in db.query(MealAttendance).filter_by(date=d, meal_type=meal)}
    base = db.query(User).filter(User.role == "student", User.is_active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        base = base.filter(or_(User.name.ilike(like), User.student_code.ilike(like)))
    rows = []
    for u in base.order_by(User.name):
        if u.id not in eligible and u.id not in present and u.id not in books:
            continue
        b = books.get(u.id)
        rows.append({"user_id": u.id, "name": u.name, "student_code": u.student_code, "has_pass": u.id in eligible,
                     "plan": plans.get(u.id), "booking": {"code": b.code, "status": b.status, "time": b.slot.start_time.strftime("%I:%M %p")} if b else None,
                     "present": u.id in present,
                     "recorded_at": present[u.id].recorded_at.isoformat(timespec="minutes") if u.id in present else None})
    return {"date": str(d), "meal_type": meal, "closed": closed, "rows": rows,
            "totals": {"eligible": len(eligible), "planned": sum(1 for s in plans.values() if s == "coming"),
                       "booked": len(books), "present": len(present)}}


@router.post("/attendance/mark")
def mark(body: MarkAttendanceIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.date > date.today():
        raise HTTPException(400, "Attendance can only be recorded for today or past dates")
    if reason := mess.meal_closed(mess.closures(db, body.date, body.date), body.date, body.meal_type):
        raise HTTPException(400, f"{body.meal_type.capitalize()} was closed on that date ({reason})")
    changed = 0
    for uid in set(body.user_ids):
        if db.query(User.id).filter_by(id=uid, role="student").first():
            changed += int(ops.mark_present(db, uid, body.date, body.meal_type, body.present, admin.id))
    db.commit()
    return {"changed": changed}


# --- Canteen store -------------------------------------------------------------------------------------

@router.get("/products")
def products(db: Session = Depends(get_db)):
    return [store.product_out(p) for p in db.query(Product).order_by(Product.category, Product.name)]


@router.post("/products")
def add_product(body: ProductIn, db: Session = Depends(get_db)):
    p = Product(**body.model_dump())
    db.add(p)
    db.commit()
    return store.product_out(p)


@router.put("/products/{pid}")
def edit_product(pid: int, body: ProductIn, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return store.product_out(p)


@router.delete("/products/{pid}")
def delete_product(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    if db.query(StoreOrderItem.id).filter_by(product_id=pid).first():
        raise HTTPException(409, "This item appears in past orders. Mark it unavailable instead of deleting it.")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/products/{pid}/image")
async def product_image(pid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    p.image = await _save_image(file)
    db.commit()
    return store.product_out(p)


@router.get("/orders")
def orders(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(StoreOrder, User).join(User, User.id == StoreOrder.user_id)
    if status == "active":
        q = q.filter(StoreOrder.status.in_(("placed", "accepted", "preparing", "ready")))
    elif status:
        q = q.filter(StoreOrder.status == status)
    rows = q.order_by(StoreOrder.created_at.desc()).limit(200).all()
    today = datetime.combine(date.today(), datetime.min.time())
    sales = db.query(func.coalesce(func.sum(StoreOrder.total), 0)).filter(StoreOrder.status == "completed", StoreOrder.updated_at >= today).scalar()
    return {"items": [store.order_out(o, u) for o, u in rows], "sales_today": round(float(sales), 2)}


@router.post("/orders/{oid}/status")
def order_status(oid: int, body: OrderStatusIn, db: Session = Depends(get_db)):
    o = db.get(StoreOrder, oid)
    if not o:
        raise HTTPException(404, "Order not found")
    return store.order_out(store.set_status(db, o, body.status), db.get(User, o.user_id))


# --- Coupons --------------------------------------------------------------------------------------------

def _coupon_out(r: Redemption, u: User) -> dict:
    return {"id": r.id, "code": r.code, "status": r.status, "reward": r.reward.name, "tokens": r.points,
            "student": u.name, "student_code": u.student_code, "created_at": r.created_at.isoformat(timespec="minutes"),
            "expires_at": r.expires_at.isoformat(timespec="minutes") if r.expires_at else None,
            "redeemed_at": r.redeemed_at.isoformat(timespec="minutes") if r.redeemed_at else None}


@router.get("/coupons")
def coupons(status: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    ops.expire_coupons(db)
    qry = db.query(Redemption, User).join(User, User.id == Redemption.user_id)
    if status:
        qry = qry.filter(Redemption.status == status)
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(Redemption.code.ilike(like), User.name.ilike(like), User.student_code.ilike(like)))
    return [_coupon_out(r, u) for r, u in qry.order_by(Redemption.created_at.desc()).limit(200)]


@router.post("/coupons/lookup")
def coupon_lookup(body: CouponCodeIn, db: Session = Depends(get_db)):
    ops.expire_coupons(db)
    r = db.query(Redemption).filter(func.upper(Redemption.code) == body.code.strip().upper()).first()
    if not r:
        raise HTTPException(404, "No coupon with this code")
    return _coupon_out(r, db.get(User, r.user_id))


@router.post("/coupons/redeem")
def coupon_redeem(body: CouponCodeIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    r = ops.validate_coupon(db, body.code, admin.id)
    return _coupon_out(r, db.get(User, r.user_id))


@router.post("/coupons/{cid}/cancel")
def coupon_cancel(cid: int, db: Session = Depends(get_db)):
    r = db.get(Redemption, cid)
    if not r:
        raise HTTPException(404, "Coupon not found")
    return _coupon_out(ops.cancel_coupon(db, r), db.get(User, r.user_id))


# --- Donations: direct assignment & completion ---------------------------------------------------------

@router.post("/donations/{did}/assign")
def assign(did: int, body: AssignIn, db: Session = Depends(get_db)):
    d = db.get(Donation, did)
    n = db.get(NgoContact, body.ngo_id)
    if not d or not n:
        raise HTTPException(404, "Donation or NGO not found")
    D.refresh_status(db, d)
    D.assign(db, d, n, body.quantity, body.pickup_eta)
    db.refresh(d)
    return D.serialize(d)


@router.post("/donations/{did}/complete")
def complete(did: int, db: Session = Depends(get_db)):
    d = db.get(Donation, did)
    if not d:
        raise HTTPException(404, "Donation not found")
    D.refresh_status(db, d)
    if d.status != "collected":
        raise HTTPException(400, "Mark every NGO allocation as collected before completing the donation")
    d.status = "completed"
    db.commit()
    return D.serialize(d)


# --- Sidebar impact card -------------------------------------------------------------------------

@router.get("/impact")
def impact(db: Session = Depends(get_db)):
    """Small live numbers for the sidebar: the last 7 days of real (non-synthetic) activity."""
    from ..models import WasteRecord
    today = date.today()
    since = today - timedelta(days=7)
    served = db.query(func.count(MealAttendance.id)).filter(MealAttendance.date >= since, MealAttendance.date <= today).scalar() or 0
    waste = db.query(func.coalesce(func.sum(WasteRecord.total_waste_kg), 0)).filter(
        WasteRecord.is_synthetic.is_(False), WasteRecord.date >= since).scalar() or 0
    dons = db.query(Donation).filter(Donation.status.in_(("collected", "completed")),
                                     Donation.created_at >= datetime.combine(since, datetime.min.time())).all()
    return {"meals_served": served, "waste_kg": round(float(waste), 1),
            "donated_portions": round(sum(d.collected_qty or d.quantity for d in dons if d.unit == "portions")),
            "donated_kg": round(sum(d.collected_qty or d.quantity for d in dons if d.unit == "kg"), 1)}
