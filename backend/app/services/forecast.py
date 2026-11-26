"""Live meal-demand forecast for upcoming services.

DEFAULT LOGIC ("confirmations" mode) - every number starts at zero
------------------------------------------------------------------
For a service (date D, meal m):

  Confirmed  C = distinct students who ticked "coming" for m on D OR hold a confirmed slot booking
  Turnout    k = sum(actual attendance) / sum(confirmations) over the last 60 days of REAL
                 services the admin recorded (needs >= 5 of them; otherwise k = 1.0).
                 k > 1 means walk-ins outnumber no-shows; k < 1 the opposite. Clipped to 0.5-2.0.
  Predicted demand  P = round(C x k)                       -> 0 until students confirm
  Buffer            B = ceil(P x buffer%)  (0 when P = 0)
  Recommended       R = P + B

So the forecast moves the moment a student ticks attendance, and it improves automatically
as the admin records what actually happened after each service (actual attendance is compared
with the confirmations that existed at that time).

"Historical average" is shown beside it for reference: the same-weekday average for that
meal around the same week last year (or the last 4 same-weekday services) from the imported
historical dataset and recorded services. It never inflates the prediction in this mode.

HYBRID MODE (optional, Settings)
--------------------------------
Uses the history model in services/prediction.py (same-weekday level x trend x menu x calendar,
blended 50/50 with confirmations once the deadline passes; confirmations/bookings as floors
before). Useful once a full year of real records exists.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import MEAL_TYPES
from ..models import AppSettings, Attendance, CalendarEvent, Meal, MealRecord, SlotBooking, User, WasteRecord
from . import prediction as P

STANDARD_PORTION_KG = {"breakfast": 0.25, "lunch": 0.40, "dinner": 0.38}


def get_settings(db: Session) -> AppSettings:
    s = db.query(AppSettings).first()
    if s is None:
        s = AppSettings()
        db.add(s)
        db.commit()
    return s


def cost_for_meal(s: AppSettings, meal: str) -> float:
    return {"breakfast": s.cost_breakfast, "lunch": s.cost_lunch, "dinner": s.cost_dinner}.get(meal) or s.cost_per_kg


def deadline_for(s: AppSettings, d: date) -> datetime:
    return datetime.combine(d - timedelta(days=1), s.attendance_deadline)


def registered_students(db: Session) -> int:
    return db.query(func.count(User.id)).filter(User.role == "student", User.is_active.is_(True)).scalar() or 0


def live_counts(db: Session, start: date, end: date) -> dict:
    """Per (date, meal): coming = distinct students who ticked "coming" OR hold a confirmed booking
    (a booking is a commitment to eat); booked = active bookings; arrived = recorded actual attendance."""
    from ..models import MealAttendance
    blank = lambda: {"coming": 0, "not_coming": 0, "booked": 0, "arrived": 0, "ticked": 0}  # noqa: E731
    coming: dict = {}
    out: dict = {}
    for uid, d, m, st in db.query(Attendance.user_id, Attendance.date, Attendance.meal_type, Attendance.status).filter(
            Attendance.date >= start, Attendance.date <= end):
        c = out.setdefault((d, m), blank())
        if st == "coming":
            coming.setdefault((d, m), set()).add(uid)
            c["ticked"] += 1
        else:
            c["not_coming"] += 1
    for uid, d, m in db.query(SlotBooking.user_id, SlotBooking.date, SlotBooking.meal_type).filter(
            SlotBooking.date >= start, SlotBooking.date <= end, SlotBooking.status != "cancelled"):
        out.setdefault((d, m), blank())["booked"] += 1
        coming.setdefault((d, m), set()).add(uid)
    for k, users in coming.items():
        out[k]["coming"] = len(users)
    for d, m, n in (db.query(MealAttendance.date, MealAttendance.meal_type, func.count())
                    .filter(MealAttendance.date >= start, MealAttendance.date <= end)
                    .group_by(MealAttendance.date, MealAttendance.meal_type)):
        out.setdefault((d, m), blank())["arrived"] = n
    return out


def main_dishes(db: Session, start: date, end: date) -> dict:
    rows = (db.query(Meal).filter(Meal.date >= start, Meal.date <= end)
            .order_by(Meal.published.desc(), Meal.id).all())
    out = {}
    for r in rows:
        out.setdefault((r.date, r.meal_type), r.name)
    return out


def consumption_kg_per_meal(db: Session) -> dict:
    """Served kg per meal served from the last 90 recorded services; standard portion otherwise."""
    out = {}
    for meal in MEAL_TYPES:
        w = dict(db.query(WasteRecord.date, func.sum(WasteRecord.served_kg))
                 .filter(WasteRecord.meal_type == meal, WasteRecord.served_kg.isnot(None))
                 .group_by(WasteRecord.date).order_by(WasteRecord.date.desc()).limit(90).all())
        m = dict(db.query(MealRecord.date, MealRecord.meals_served)
                 .filter(MealRecord.meal_type == meal, MealRecord.meals_served > 0, MealRecord.date.in_(list(w))).all()) if w else {}
        kg = sum(w[d] for d in m)
        n = sum(m.values())
        out[meal] = (round(kg / n, 3), "recorded consumption") if n >= 50 else (STANDARD_PORTION_KG[meal], "standard portion")
    return out


def turnout_ratio(db: Session, meal: str, before: date | None = None) -> dict:
    """Learned from REAL recorded services only (never from synthetic data)."""
    before = before or date.today() + timedelta(days=1)
    rows = (db.query(MealRecord.actual_attendance, MealRecord.advance_confirmations)
            .filter(MealRecord.meal_type == meal, MealRecord.is_synthetic.is_(False),
                    MealRecord.actual_attendance.isnot(None), MealRecord.advance_confirmations > 0,
                    MealRecord.date < before, MealRecord.date >= before - timedelta(days=60)).all())
    if len(rows) < 5:
        return {"k": 1.0, "services": len(rows),
                "source": f"Not learned yet ({len(rows)}/5 recorded services) - using confirmed count as-is"}
    k = float(np.clip(sum(a for a, _ in rows) / sum(c for _, c in rows), 0.5, 2.0))
    return {"k": round(k, 3), "services": len(rows),
            "source": f"Learned from {len(rows)} recorded services (actual / confirmed)"}


def historical_reference(hist: pd.DataFrame, d: date, meal: str) -> dict:
    if hist.empty:
        return {"value": None, "label": "No history"}
    h = hist[(hist["meal_type"] == meal) & (hist["weekday"] == d.weekday()) & (hist["date"] < pd.Timestamp(d))]
    h = h[~h["kind"].isin(["holiday"])]
    if h.empty:
        return {"value": None, "label": "No same-weekday history"}
    ly = pd.Timestamp(d - timedelta(days=364))
    near = h[(h["date"] >= ly - pd.Timedelta(days=21)) & (h["date"] <= ly + pd.Timedelta(days=21))]
    if len(near) >= 2:
        return {"value": int(round(near["att"].mean())), "label": f"Same week last year ({len(near)} {d:%a}s)"}
    last = h.tail(4)
    return {"value": int(round(last["att"].mean())), "label": f"Last {len(last)} {d:%a} services"}


def forecast_range(db: Session, start: date, days: int) -> list[dict]:
    s = get_settings(db)
    end = start + timedelta(days=days - 1)
    hist = P.hist_cached(db)
    hybrid = s.forecast_mode == "hybrid" and not hist.empty
    f = P.factors_cached(db, hist) if hybrid else None
    from . import mess
    cal = P.calendar_lookup(db, start, end)
    cl = mess.closures(db, start, end)
    eligible_cache: dict = {}
    counts = live_counts(db, start, end)
    dishes = main_dishes(db, start, end)
    kgm = consumption_kg_per_meal(db)
    recs = {(r.date, r.meal_type): r for r in db.query(MealRecord).filter(MealRecord.date >= start, MealRecord.date <= end)}
    ratios = {m: turnout_ratio(db, m) for m in MEAL_TYPES}
    reg = registered_students(db)
    now = datetime.now()
    out = []
    d = start
    while d <= end:
        e = cal.get(d)
        eligible = eligible_cache.setdefault(d, len(mess.students_with_pass(db, d)))
        for meal in MEAL_TYPES:
            closed_reason = mess.meal_closed(cl, d, meal)
            closed = closed_reason is not None
            c = counts.get((d, meal), {"coming": 0, "not_coming": 0, "booked": 0, "arrived": 0, "ticked": 0})
            wclosed = now >= deadline_for(s, d)
            rec = recs.get((d, meal))
            ref = historical_reference(hist, d, meal)
            r = ratios[meal]
            detail = None
            if closed:
                pred = 0
                method = "Canteen closed"
            elif hybrid:
                detail = P.baseline_predict(hist, f, d, meal, dish=dishes.get((d, meal)), kind=e.kind if e else None,
                                            event_name=e.name if e else None, confirmations=c["coming"] or None,
                                            window_closed=wclosed, bookings=c["booked"] or None)
                pred = detail["predicted"] or 0
                method = "Hybrid: " + detail["method"]
            else:
                pred = int(round(c["coming"] * r["k"]))
                method = f"Confirmed {c['coming']} x turnout {r['k']:g}"
            buf = math.ceil(pred * s.buffer_pct / 100) if pred > 0 else 0
            per_kg, kg_src = kgm[meal]
            prepared = rec.meals_prepared if rec else None
            served = rec.meals_served if rec else None
            out.append({
                "date": str(d), "weekday": d.strftime("%A"), "meal_type": meal, "closed": closed,
                "closed_reason": closed_reason,
                "event": e.name if e else None, "event_kind": e.kind if e else None,
                "main_dish": dishes.get((d, meal)), "registered": reg, "eligible": eligible,
                "confirmed": c["coming"], "ticked": c["ticked"], "not_coming": c["not_coming"],
                "pending": max(0, eligible - c["coming"] - c["not_coming"]), "bookings": c["booked"], "arrived": c["arrived"],
                "historical_avg": ref["value"], "historical_label": ref["label"],
                "turnout_ratio": r["k"], "turnout_source": r["source"],
                "predicted": pred, "expected": pred, "buffer_pct": s.buffer_pct, "buffer": buf, "recommended": pred + buf,
                "recommended_kg": round((pred + buf) * per_kg, 1), "kg_per_meal": per_kg, "kg_source": kg_src,
                "prepared": prepared, "served": served,
                "remaining": (prepared - served) if prepared is not None and served is not None else None,
                "actual_attendance": rec.actual_attendance if rec else None,
                "locked_prediction": rec.predicted_demand if rec else None,
                "method": method, "mode": "hybrid" if hybrid else "confirmations", "history_model": detail,
                "confirmation_deadline": deadline_for(s, d).isoformat(timespec="minutes"),
                "confirmation_window_closed": wclosed,
            })
        d += timedelta(days=1)
    return out


def summarize_day(items: list[dict]) -> dict:
    keys = ["confirmed", "not_coming", "bookings", "predicted", "buffer", "recommended"]
    out = {k: sum(i[k] or 0 for i in items) for k in keys}
    out["recommended_kg"] = round(sum(i["recommended_kg"] or 0 for i in items), 1)
    out.update({"date": items[0]["date"], "weekday": items[0]["weekday"], "closed": all(i["closed"] for i in items),
                "event": next((i["event"] for i in items if i["event"]), None),
                "prepared": sum(i["prepared"] or 0 for i in items) if any(i["prepared"] is not None for i in items) else None})
    return out


def recommendation_text(day: dict, buffer_pct: float) -> str:
    if day.get("closed"):
        return f"The canteen is closed on {day['weekday']}. No preparation needed."
    if not day.get("predicted"):
        return (f"No students have confirmed for {day['weekday']} yet, so predicted demand is 0. "
                "It updates as soon as students tick their attendance.")
    return (f"{day['weekday']}'s estimated demand is {day['predicted']} meals. Prepare approximately "
            f"{day['recommended']} meals after applying the {buffer_pct:g}% buffer.")


def confirmation_accuracy(db: Session) -> dict:
    """Accuracy of stored predictions vs actual attendance, real services only. No fake numbers."""
    rows = (db.query(MealRecord.predicted_demand, MealRecord.actual_attendance)
            .filter(MealRecord.is_synthetic.is_(False), MealRecord.predicted_demand.isnot(None),
                    MealRecord.actual_attendance.isnot(None)).all())
    if len(rows) < 5:
        return {"available": False, "services": len(rows),
                "message": f"Accuracy appears after 5 recorded services with a locked prediction ({len(rows)} so far)."}
    pred = np.array([p for p, _ in rows], float)
    act = np.array([a for _, a in rows], float)
    err = pred - act
    nz = act > 0
    return {"available": True, "services": len(rows), "mae": round(float(np.mean(np.abs(err))), 2),
            "mape": round(float(np.mean(np.abs(err[nz]) / act[nz]) * 100), 2) if nz.any() else None,
            "bias": round(float(np.mean(err)), 2)}
