"""Attendance planning, slot booking, actual attendance, reward tokens and coupons.

Rules
- Advance confirmations: one row per (student, date, meal) (unique constraint). Allowed only for
  dates covered by an active, non-suspended mess pass and for meals that are not closed.
  Tokens for planning ahead are paid once per student per date (ledger ref_key is unique).
- Bookings: need an active pass, an open meal and a free seat (checked on the server), and must be
  made / changed / cancelled before the booking cut-off (N minutes before the slot starts).
  After the cut-off a booking is "locked"; when served it becomes "completed".
- Actual attendance (MealAttendance) is recorded only at the counter or when a booking is marked
  served. A booking alone is never treated as attendance and never earns attendance tokens.
- Tokens: User.token_balance changes only via UPDATE ... WHERE token_balance >= cost, inside the
  same transaction as the ledger row, so balances can never go negative and a ref_key never pays twice.
- Coupons: tokens are deducted in the same transaction that creates the coupon; a coupon can be
  redeemed once (conditional UPDATE on status='active'); cancelling an active coupon refunds tokens.
"""
from __future__ import annotations

import secrets
import string
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (Attendance, MealAttendance, MealSlot, Redemption, Reward, RewardTransaction, SlotBooking, User)
from . import mess
from .forecast import deadline_for, get_settings

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid misreading codes


def new_code(prefix: str = "", n: int = 6) -> str:
    return prefix + "".join(secrets.choice(_ALPHABET) for _ in range(n))


def closed_dates(db: Session, start: date, end: date) -> dict[date, str]:
    """Days on which every meal is closed (kept for older callers)."""
    cl = mess.closures(db, start, end)
    return {d: r for d in cl if (r := mess.day_closed(cl, d))}


# --- Token ledger -----------------------------------------------------------------------------------

def balance(db: Session, user_id: int) -> int:
    return int(db.query(User.token_balance).filter(User.id == user_id).scalar() or 0)


def post_tokens(db: Session, user_id: int, points: int, kind: str, desc: str, ref_key: str) -> bool:
    """Append to the ledger and move the balance atomically. Returns False if ref_key already paid.
    Raises 400 if a deduction would make the balance negative. Uses a savepoint so a duplicate
    ref_key never leaves a half-applied balance change."""
    if points == 0 or db.query(RewardTransaction.id).filter_by(ref_key=ref_key).first():
        return False
    sp = db.begin_nested()
    try:
        q = update(User).where(User.id == user_id)
        if points < 0:
            q = q.where(User.token_balance >= -points)
        if db.execute(q.values(token_balance=User.token_balance + points)
                      .execution_options(synchronize_session=False)).rowcount != 1:
            sp.rollback()
            raise HTTPException(400, "Not enough tokens")
        db.add(RewardTransaction(user_id=user_id, points=points, kind=kind, description=desc[:200], ref_key=ref_key,
                                 created_at=datetime.now()))
        db.flush()
        sp.commit()
        return True
    except IntegrityError:
        sp.rollback()
        return False


# --- Advance attendance (planning) ----------------------------------------------------------------

def submit_attendance(db: Session, user: User, items: list, now: datetime | None = None) -> dict:
    s = get_settings(db)
    now = now or datetime.now()
    today = now.date()
    last = today + timedelta(days=s.attendance_window_days)
    cl = mess.closures(db, today, last)
    errors, saved, points, touched = [], 0, 0, set()
    seen = set()
    for it in items:
        key = (it.date, it.meal_type)
        if key in seen:
            errors.append(f"{it.date} {it.meal_type}: duplicate in request")
            continue
        seen.add(key)
        if it.date <= today or it.date > last:
            errors.append(f"{it.date}: outside the confirmation window (tomorrow to {last})")
            continue
        if reason := mess.meal_closed(cl, it.date, it.meal_type):
            errors.append(f"{it.date} {it.meal_type}: unavailable ({reason})")
            continue
        if user.suspended:
            errors.append("Your mess pass is suspended")
            break
        if not mess.pass_covers(db, user, it.date):
            errors.append(f"{it.date}: your mess pass does not cover this date")
            continue
        dl = deadline_for(s, it.date)
        if now >= dl:
            errors.append(f"{it.date}: deadline passed ({dl:%d %b %H:%M})")
            continue
        row = db.query(Attendance).filter_by(user_id=user.id, date=it.date, meal_type=it.meal_type).with_for_update().first()
        if row is None:
            db.add(Attendance(user_id=user.id, date=it.date, meal_type=it.meal_type, status=it.status,
                              confirmed_at=now, updated_at=now))
        elif row.status != it.status:
            if row.status == "coming" and it.status == "not_coming":
                row.cancelled, row.cancelled_at = True, now
                for b in db.query(SlotBooking).filter_by(user_id=user.id, date=it.date, meal_type=it.meal_type, status="booked"):
                    b.status, b.cancelled_at = "cancelled", now
            elif it.status == "coming":
                row.cancelled, row.cancelled_at = False, None
            row.status, row.updated_at = it.status, now
        saved += 1
        touched.add(it.date)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Attendance was submitted twice at the same time. Please refresh.")

    for d in sorted(touched):
        if post_tokens(db, user.id, s.points_per_confirmation, "earn", f"Planned meals in advance for {d:%a %d %b}",
                       f"confirm:{user.id}:{d.isoformat()}"):
            points += s.points_per_confirmation
    for d in sorted(touched):
        monday = d - timedelta(days=d.weekday())
        wcl = mess.closures(db, monday, monday + timedelta(days=6))
        open_days = [monday + timedelta(days=i) for i in range(7)
                     if not mess.day_closed(wcl, monday + timedelta(days=i)) and mess.pass_covers(db, user, monday + timedelta(days=i))]
        answered = {r[0] for r in db.query(Attendance.date).filter(Attendance.user_id == user.id, Attendance.date >= monday,
                                                                   Attendance.date <= monday + timedelta(days=6))}
        if open_days and all(x in answered for x in open_days):
            iso = monday.isocalendar()
            if post_tokens(db, user.id, s.weekly_streak_bonus, "bonus", f"Full-week planning bonus (week of {monday:%d %b})",
                           f"streak:{user.id}:{iso.year}-{iso.week}"):
                points += s.weekly_streak_bonus
    db.commit()
    return {"saved": saved, "errors": errors, "points_awarded": points, "balance": balance(db, user.id)}


# --- Bookings ------------------------------------------------------------------------------------

def slot_counts(db: Session, d: date) -> dict[int, int]:
    return dict(db.query(SlotBooking.slot_id, func.count()).filter(
        SlotBooking.date == d, SlotBooking.status != "cancelled").group_by(SlotBooking.slot_id).all())


def cutoff(s, d: date, slot: MealSlot) -> datetime:
    return datetime.combine(d, slot.start_time) - timedelta(minutes=s.booking_cancel_minutes)


def booking_state(b: SlotBooking, s, now: datetime | None = None) -> str:
    now = now or datetime.now()
    if b.status == "cancelled":
        return "cancelled"
    if b.status == "served":
        return "completed"
    return "locked" if now >= cutoff(s, b.date, b.slot) else "confirmed"


def _check_bookable(db: Session, user: User, slot: MealSlot | None, d: date, now: datetime):
    s = get_settings(db)
    if slot is None or not slot.active:
        raise HTTPException(404, "Slot not available")
    if d < now.date() or d > now.date() + timedelta(days=s.attendance_window_days):
        raise HTTPException(400, "Bookings are open from today up to the confirmation window.")
    if reason := mess.meal_closed(mess.closures(db, d, d), d, slot.meal_type):
        raise HTTPException(400, f"{slot.meal_type.capitalize()} is unavailable on {d:%d %b}: {reason}.")
    mess.require_pass(db, user, d)
    co = cutoff(s, d, slot)
    if now >= co:
        raise HTTPException(400, f"Booking closed at {co:%d %b %I:%M %p} ({s.booking_cancel_minutes} min before the slot).")


def _take_seat(db: Session, slot: MealSlot, d: date):
    taken = db.query(func.count(SlotBooking.id)).filter(SlotBooking.slot_id == slot.id, SlotBooking.date == d,
                                                        SlotBooking.status != "cancelled").scalar()
    if taken >= slot.capacity:
        raise HTTPException(409, "This slot is full. Please choose another time.")


def book_slot(db: Session, user: User, slot_id: int, d: date, now: datetime | None = None) -> SlotBooking:
    now = now or datetime.now()
    slot = db.query(MealSlot).filter_by(id=slot_id).with_for_update().first()  # serialises seat checks on PostgreSQL
    _check_bookable(db, user, slot, d, now)
    if db.query(SlotBooking).filter_by(user_id=user.id, date=d, meal_type=slot.meal_type, status="booked").first():
        raise HTTPException(409, f"You already have a {slot.meal_type} booking on this date. Change or cancel it instead.")
    att = db.query(Attendance).filter_by(user_id=user.id, date=d, meal_type=slot.meal_type).first()
    if att and att.status == "not_coming":
        raise HTTPException(409, f"You marked yourself 'Not attending' for {slot.meal_type}. Update your attendance first.")
    _take_seat(db, slot, d)
    b = SlotBooking(user_id=user.id, slot_id=slot.id, date=d, meal_type=slot.meal_type, status="booked",
                    code=new_code("EB-"), created_at=now)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def change_slot(db: Session, user: User, booking_id: int, new_slot_id: int, now: datetime | None = None) -> SlotBooking:
    now = now or datetime.now()
    s = get_settings(db)
    old = db.query(SlotBooking).filter_by(id=booking_id, user_id=user.id).first()
    if old is None or old.status != "booked":
        raise HTTPException(404, "Active booking not found")
    if now >= cutoff(s, old.date, old.slot):
        raise HTTPException(400, "This booking is locked: the change deadline has passed.")
    slot = db.query(MealSlot).filter_by(id=new_slot_id).with_for_update().first()
    if slot is None or slot.meal_type != old.meal_type:
        raise HTTPException(400, "Choose a slot for the same meal")
    if slot.id == old.slot_id:
        raise HTTPException(400, "You are already booked in this slot")
    _check_bookable(db, user, slot, old.date, now)
    _take_seat(db, slot, old.date)
    old.status, old.cancelled_at = "cancelled", now
    b = SlotBooking(user_id=user.id, slot_id=slot.id, date=old.date, meal_type=old.meal_type, status="booked",
                    code=new_code("EB-"), created_at=now)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def cancel_booking(db: Session, user: User, booking_id: int, now: datetime | None = None) -> SlotBooking:
    s = get_settings(db)
    now = now or datetime.now()
    b = db.query(SlotBooking).filter_by(id=booking_id, user_id=user.id).first()
    if b is None:
        raise HTTPException(404, "Booking not found")
    if b.status != "booked":
        raise HTTPException(400, f"Booking is already {b.status}.")
    co = cutoff(s, b.date, b.slot)
    if now >= co:
        raise HTTPException(400, f"This booking is locked: cancellation closed at {co:%d %b %I:%M %p}.")
    b.status, b.cancelled_at = "cancelled", now
    db.commit()
    return b


# --- Actual attendance ---------------------------------------------------------------------------

def mark_present(db: Session, user_id: int, d: date, meal: str, present: bool, admin_id: int | None,
                 source: str = "counter") -> bool:
    """Record (or remove) actual attendance. Attendance tokens follow verified attendance only."""
    s = get_settings(db)
    row = db.query(MealAttendance).filter_by(user_id=user_id, date=d, meal_type=meal).first()
    base = f"{user_id}:{d.isoformat()}:{meal}"
    revokes = db.query(func.count(RewardTransaction.id)).filter(RewardTransaction.ref_key.like(f"unattend:{base}:%")).scalar()
    award_key = f"attend:{base}" + (f":r{revokes}" if revokes else "")
    if present and row is None:
        db.add(MealAttendance(user_id=user_id, date=d, meal_type=meal, recorded_at=datetime.now(), recorded_by=admin_id, source=source))
        db.flush()
        post_tokens(db, user_id, s.tokens_per_attended_meal, "earn", f"Attended {meal} on {d:%a %d %b}", award_key)
        return True
    if not present and row is not None:
        db.delete(row)
        award = db.query(RewardTransaction).filter_by(ref_key=award_key).first()
        if award:
            take = min(award.points, balance(db, user_id))
            if take > 0:
                post_tokens(db, user_id, -take, "revoke", f"Attendance correction: {meal} on {d:%a %d %b}", f"unattend:{base}:{revokes}")
            else:  # balance already spent: record the correction without going negative
                db.add(RewardTransaction(user_id=user_id, points=0, kind="revoke", description=f"Attendance correction: {meal} on {d:%a %d %b}",
                                         ref_key=f"unattend:{base}:{revokes}", created_at=datetime.now()))
        return True
    return False


# --- Coupons -------------------------------------------------------------------------------------

def expire_coupons(db: Session, user_id: int | None = None):
    q = db.query(Redemption).filter(Redemption.status == "active", Redemption.expires_at.isnot(None),
                                    Redemption.expires_at < datetime.now())
    if user_id:
        q = q.filter(Redemption.user_id == user_id)
    n = 0
    for r in q:
        r.status = "expired"
        n += 1
    if n:
        db.commit()


def redeem(db: Session, user: User, reward_id: int) -> Redemption:
    s = get_settings(db)
    r = db.query(Reward).filter_by(id=reward_id).first()
    if r is None or not r.active:
        raise HTTPException(404, "Reward not available")
    if balance(db, user.id) < r.points_cost:
        raise HTTPException(400, f"You need {r.points_cost - balance(db, user.id)} more tokens for this reward.")
    code = new_code("RW-")
    now = datetime.now()
    try:
        # Stock: conditional decrement (never below zero).
        if db.execute(update(Reward).where(Reward.id == r.id, Reward.stock > 0).values(stock=Reward.stock - 1)
                      .execution_options(synchronize_session=False)).rowcount != 1:
            raise HTTPException(409, "This reward is out of stock.")
        red = Redemption(user_id=user.id, reward_id=r.id, points=r.points_cost, code=code, status="active",
                         created_at=now, expires_at=now + timedelta(days=s.coupon_validity_days))
        db.add(red)
        db.flush()
        if not post_tokens(db, user.id, -r.points_cost, "redeem", f"Coupon {code}: {r.name}", f"redeem:{code}"):
            raise HTTPException(409, "Duplicate redemption")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    db.refresh(red)
    return red


def validate_coupon(db: Session, code: str, admin_id: int) -> Redemption:
    expire_coupons(db)
    red = db.query(Redemption).filter(func.upper(Redemption.code) == code.strip().upper()).first()
    if red is None:
        raise HTTPException(404, "No coupon with this code")
    done = db.execute(update(Redemption).where(Redemption.id == red.id, Redemption.status == "active")
                      .values(status="redeemed", redeemed_at=datetime.now(), redeemed_by=admin_id)
                      .execution_options(synchronize_session=False)).rowcount
    if done != 1:
        db.rollback()
        db.refresh(red)
        raise HTTPException(409, f"Coupon is {red.status}" + (f" (redeemed {red.redeemed_at:%d %b %I:%M %p})" if red.redeemed_at else ""))
    db.commit()
    db.refresh(red)
    mess.notify_student(db, red.user_id, "reward", f"Coupon {red.code} redeemed", f"{red.reward.name} served. Enjoy!",
                        "/student/rewards", f"coupon:redeemed:{red.id}")
    db.commit()
    return red


def cancel_coupon(db: Session, red: Redemption) -> Redemption:
    done = db.execute(update(Redemption).where(Redemption.id == red.id, Redemption.status == "active")
                      .values(status="cancelled", cancelled_at=datetime.now()).execution_options(synchronize_session=False)).rowcount
    if done != 1:
        db.rollback()
        raise HTTPException(409, "Only active coupons can be cancelled")
    post_tokens(db, red.user_id, red.points, "refund", f"Refund for cancelled coupon {red.code}", f"refund:{red.code}")
    db.execute(update(Reward).where(Reward.id == red.reward_id).values(stock=Reward.stock + 1).execution_options(synchronize_session=False))
    mess.notify_student(db, red.user_id, "reward", f"Coupon {red.code} cancelled", f"{red.points} tokens were refunded.",
                        "/student/rewards", f"coupon:cancelled:{red.id}")
    db.commit()
    db.refresh(red)
    return red
