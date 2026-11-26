"""Attendance calendar for one student.

Past days show only RECORDED attendance (MealAttendance): present if any meal was recorded,
absent if the day was a mess day covered by the pass and nothing was recorded, grey if the
canteen was closed. Today stays "today" until something is recorded. Future days show the plan
(booked / confirmed / open) - never present or absent. Days outside the pass are "outside".
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..config import MEAL_TYPES
from ..models import Attendance, MealAttendance, MessSubscription, SlotBooking, User
from . import mess


def covered_days(db: Session, user_id: int, start: date, end: date) -> set[date]:
    out = set()
    for s in db.query(MessSubscription).filter(MessSubscription.user_id == user_id, MessSubscription.cancelled.is_(False),
                                               MessSubscription.start_date <= end, MessSubscription.expiry_date >= start):
        d = max(s.start_date, start)
        while d <= min(s.expiry_date, end):
            out.add(d)
            d += timedelta(days=1)
    return out


def attendance_calendar(db: Session, user: User, start: date, end: date) -> dict:
    today = date.today()
    if (end - start).days > 400:
        start = end - timedelta(days=400)
    cl = mess.closures(db, start, end)
    cov = covered_days(db, user.id, start, end)
    present = {(r.date, r.meal_type) for r in db.query(MealAttendance).filter(
        MealAttendance.user_id == user.id, MealAttendance.date >= start, MealAttendance.date <= end)}
    plans = {(a.date, a.meal_type): a.status for a in db.query(Attendance).filter(
        Attendance.user_id == user.id, Attendance.date >= start, Attendance.date <= end)}
    books = {}
    for b in db.query(SlotBooking).filter(SlotBooking.user_id == user.id, SlotBooking.date >= start, SlotBooking.date <= end,
                                          SlotBooking.status != "cancelled"):
        books[(b.date, b.meal_type)] = {"status": b.status, "time": b.slot.start_time.strftime("%I:%M %p"), "code": b.code}
    days = []
    summ = {"mess_days": 0, "present_days": 0, "absent_days": 0, "closed_days": 0, "meals_attended": 0, "upcoming_booked": 0}
    d = start
    while d <= end:
        meals = {}
        for m in MEAL_TYPES:
            meals[m] = {"present": (d, m) in present, "plan": plans.get((d, m)), "booking": books.get((d, m)),
                        "closed": mess.meal_closed(cl, d, m)}
        full_closed = mess.day_closed(cl, d)
        any_present = any(v["present"] for v in meals.values())
        covered = d in cov
        if d < today or (d == today and any_present):
            status = "present" if any_present else "closed" if full_closed else "outside" if not covered else "absent"
        elif d == today:
            status = "closed" if full_closed else "outside" if not covered else "today"
        else:
            if full_closed:
                status = "closed"
            elif not covered:
                status = "outside"
            elif any(v["booking"] or v["plan"] == "coming" for v in meals.values()):
                status = "booked"
            else:
                status = "open"
        summ["meals_attended"] += sum(v["present"] for v in meals.values())
        if status in ("present", "absent"):
            summ["mess_days"] += 1
            summ["present_days" if status == "present" else "absent_days"] += 1
        if status == "closed" and d <= today and covered:
            summ["closed_days"] += 1
        if status == "booked":
            summ["upcoming_booked"] += 1
        days.append({"date": str(d), "weekday": d.strftime("%a"), "status": status, "covered": covered,
                     "closed_reason": full_closed, "meals": meals})
        d += timedelta(days=1)
    summ["attendance_pct"] = round(summ["present_days"] / summ["mess_days"] * 100, 1) if summ["mess_days"] else None
    sub = mess.current_subscription(db, user.id)
    first = db.query(MessSubscription.start_date).filter(MessSubscription.user_id == user.id, MessSubscription.cancelled.is_(False)) \
        .order_by(MessSubscription.start_date).first()
    return {"range": {"start": str(start), "end": str(end)}, "days": days, "summary": summ,
            "pass": {"first_start": str(first[0]) if first else None, "expiry": str(sub.expiry_date) if sub else None}}
