"""Admin APIs. Every route depends on require_admin, enforced server-side."""
import io
import json
import secrets
from datetime import date, datetime, time, timedelta

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..config import DATA_DIR, MEAL_TYPES
from ..database import get_db
from ..models import (Attendance, CalendarEvent, Donation, DonationAllocation, ImportLog, Meal, MealAttendance, MealRecord, MealSlot,
                      ModelRun, NgoContact, Notification, Redemption, Reward, RewardTransaction, SavingsRecord,
                      SlotBooking, User, WasteRecord)
from ..schemas import (ActualsIn, AdjustPointsIn, AllocationStatusIn, ArrivalIn, CopyMenuIn, DonationIn, EventIn,
                       InviteIn, MealIn, MealPatch, NgoIn, PreparationIn, PublishIn, RewardIn, SettingsIn, SlotIn,
                       SlotPatch, VerifySavingIn, WasteIn)
from ..services import analytics as A
from ..services import donations as D
from ..services import forecast as F
from ..services import prediction as P
from ..services import mess, summary
from ..services import student_ops as ops
from ..services.importer import import_excel

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)


def _range(start: date | None, end: date | None, default_days: int = 90) -> tuple[date, date]:
    end = end or date.today()
    start = start or end - timedelta(days=default_days)
    if start > end:
        raise HTTPException(400, "Start date must be before end date")
    return start, end


def _data_flags(db: Session) -> dict:
    syn = db.query(func.count(MealRecord.id)).filter(MealRecord.is_synthetic.is_(True)).scalar()
    total = db.query(func.count(MealRecord.id)).scalar()
    return {"synthetic_records": syn, "total_records": total, "has_synthetic": syn > 0}


async def _save_image(file: UploadFile) -> str:
    data = await file.read()
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 4 MB)")
    if data[:3] == b"\xff\xd8\xff":
        ext = "jpg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = "png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = "webp"
    else:
        raise HTTPException(400, "Upload a JPG, PNG or WEBP image")
    name = f"{secrets.token_hex(12)}.{ext}"
    (UPLOADS / name).write_bytes(data)
    return name


def _xlsx(sheets: dict[str, pd.DataFrame], filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            (df if not df.empty else pd.DataFrame({"Info": ["No records in this range"]})).to_excel(xw, sheet_name=name[:31], index=False)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/data-status")
def data_status(db: Session = Depends(get_db)):
    return _data_flags(db)


# --- Overview ------------------------------------------------------------------------------------

def _insights(db: Session, d: date, meals: list[dict]) -> list[dict]:
    out = []
    preds = [m for m in meals if m["predicted"] > 0]
    if all(m["closed"] for m in meals):
        out.append({"tone": "info", "text": "The canteen is closed on this date."})
        return out
    if preds:
        top = max(preds, key=lambda m: m["predicted"])
        out.append({"tone": "good", "text": f"{top['meal_type'].capitalize()} has the highest expected demand ({top['predicted']} meals)."})
    else:
        out.append({"tone": "info", "text": "No student has confirmed yet, so predicted demand is 0. It updates as students tick attendance."})
    prev = F.live_counts(db, d - timedelta(days=7), d - timedelta(days=7))
    for m in meals:
        last = prev.get((d - timedelta(days=7), m["meal_type"]), {}).get("coming", 0)
        if last and m["confirmed"] != last:
            ch = (m["confirmed"] - last) / last * 100
            if abs(ch) >= 10:
                out.append({"tone": "good" if ch > 0 else "warn",
                            "text": f"{m['meal_type'].capitalize()} confirmations are {'up' if ch > 0 else 'down'} {abs(ch):.0f}% vs last {d:%A} ({last} → {m['confirmed']})."})
    wk = d - timedelta(days=d.weekday())
    this_w = db.query(func.sum(WasteRecord.total_waste_kg)).filter(WasteRecord.date >= wk, WasteRecord.date <= d).scalar() or 0
    last_w = db.query(func.sum(WasteRecord.total_waste_kg)).filter(WasteRecord.date >= wk - timedelta(days=7),
                                                                   WasteRecord.date <= d - timedelta(days=7)).scalar() or 0
    if last_w > 0 and this_w > 0:
        ch = (this_w - last_w) / last_w * 100
        out.append({"tone": "good" if ch < 0 else "warn",
                    "text": f"Food waste so far this week is {'down' if ch < 0 else 'up'} {abs(ch):.0f}% vs the same days last week."})
    for m in meals:
        past = [db.query(func.count(SlotBooking.id)).filter(SlotBooking.date == d - timedelta(days=7 * i),
                SlotBooking.meal_type == m["meal_type"], SlotBooking.status != "cancelled").scalar() for i in range(1, 5)]
        past = [p for p in past if p]
        if len(past) >= 2:
            avg = sum(past) / len(past)
            if m["bookings"] < 0.8 * avg:
                out.append({"tone": "warn", "text": f"{m['meal_type'].capitalize()} bookings ({m['bookings']}) are lower than usual (avg {avg:.0f})."})
    return out[:5]


@router.get("/overview")
def overview(d: date | None = Query(None, alias="date"), db: Session = Depends(get_db)):
    d = d or date.today()
    s = F.get_settings(db)
    meals = F.forecast_range(db, d, 1)
    reg = F.registered_students(db)
    rows = db.query(Attendance.user_id, Attendance.status).filter(Attendance.date == d).all()
    coming = {u for u, st in rows if st == "coming"}
    responded = {u for u, _ in rows}
    caps = dict(db.query(MealSlot.meal_type, func.sum(MealSlot.capacity)).filter(MealSlot.active.is_(True))
                .group_by(MealSlot.meal_type).all())
    waste = {m: {"kg": 0.0, "cost": 0.0} for m in MEAL_TYPES}
    for m, kgv, cost in (db.query(WasteRecord.meal_type, func.sum(WasteRecord.total_waste_kg), func.sum(WasteRecord.waste_cost))
                         .filter(WasteRecord.date == d).group_by(WasteRecord.meal_type)):
        waste[m] = {"kg": round(kgv or 0, 1), "cost": round(cost or 0, 2)}
    prepared_kg = db.query(func.sum(WasteRecord.prepared_kg)).filter(WasteRecord.date == d).scalar() or 0
    total_w = sum(v["kg"] for v in waste.values())
    active_don = [x for x in db.query(Donation).filter(Donation.status.in_(D.OPEN + ("fully_accepted", "pickup_confirmed"))).all()
                  if D.refresh_status(db, x) not in ("expired",)]
    db.commit()
    day = F.summarize_day(meals)
    return {
        "date": str(d), "today": str(date.today()), "canteen_name": s.canteen_name, "buffer_pct": s.buffer_pct,
        "forecast_mode": s.forecast_mode, "meals": meals, "day": day,
        "recommendation": F.recommendation_text(day, s.buffer_pct),
        "attendance": {"registered": reg, "confirmed_students": len(coming), "expected": day["predicted"],
                       "absent_students": len(responded - coming), "pending_students": max(0, reg - len(responded)),
                       "attendance_pct": round(len(coming) / reg * 100, 1) if reg else 0},
        "slots": [{"meal_type": m["meal_type"], "booked": m["bookings"], "capacity": caps.get(m["meal_type"], 0)} for m in meals],
        "waste": {"by_meal": waste, "total_kg": round(total_w, 1), "total_cost": round(sum(v["cost"] for v in waste.values()), 2),
                  "pct": round(total_w / prepared_kg * 100, 1) if prepared_kg else None},
        "donations": {"active": len(active_don),
                      "open_qty": [{"code": x.code, "food": x.food_name, "remaining": round(x.quantity - x.allocated_qty, 1),
                                    "unit": x.unit, "status": x.status} for x in active_don[:3]]},
        "insights": _insights(db, d, meals),
        "operations": summary.ops_summary(db),
        "unread_notifications": db.query(func.count(Notification.id)).filter(Notification.read.is_(False)).scalar(),
    }


# --- Forecast & model ---------------------------------------------------------------------------

@router.get("/forecast")
def forecast(days: int = Query(7, ge=1, le=14), start: date | None = None, db: Session = Depends(get_db)):
    s = F.get_settings(db)
    start = start or date.today()
    items = F.forecast_range(db, start, days)
    by_day: dict = {}
    for it in items:
        by_day.setdefault(it["date"], []).append(it)
    out = []
    for its in by_day.values():
        sm = F.summarize_day(its)
        sm["meals"] = its
        sm["recommendation"] = F.recommendation_text(sm, s.buffer_pct)
        out.append(sm)
    return {"buffer_pct": s.buffer_pct, "mode": s.forecast_mode, "days": out, "methodology": F.__doc__,
            "accuracy": F.confirmation_accuracy(db), "turnout": {m: F.turnout_ratio(db, m) for m in MEAL_TYPES}}


@router.get("/model")
def model_info(db: Session = Depends(get_db)):
    runs = db.query(ModelRun).order_by(ModelRun.trained_at.desc()).limit(5).all()
    return {"history_backtest": P.evaluation(db), "active_model": F.get_settings(db).active_model,
            "rf_trained": P.MODEL_PATH.exists() and len(runs) > 0, "methodology": P.__doc__,
            "runs": [{"id": r.id, "trained_at": r.trained_at.isoformat(timespec="minutes"), "train_rows": r.train_rows,
                      "test_rows": r.test_rows, "test_start": str(r.test_start), "test_end": str(r.test_end), "mae": r.mae,
                      "mape": r.mape, "baseline_mae": r.baseline_mae, "baseline_mape": r.baseline_mape,
                      "features": json.loads(r.features)} for r in runs]}


@router.post("/model/train")
def train(db: Session = Depends(get_db)):
    try:
        return P.train_random_forest(db)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/preparation")
def set_preparation(body: PreparationIn, db: Session = Depends(get_db)):
    """Record how many meals the kitchen is preparing. Freezes the prediction at that moment so it can
    be compared with actual attendance later (this is how the forecast learns)."""
    it = next(i for i in F.forecast_range(db, body.date, 1) if i["meal_type"] == body.meal_type)
    if it["closed"]:
        raise HTTPException(400, f"The canteen is closed on {body.date}")
    rec = db.query(MealRecord).filter_by(date=body.date, meal_type=body.meal_type).first()
    if rec is None:
        rec = MealRecord(date=body.date, meal_type=body.meal_type, source="admin_entry")
        db.add(rec)
    if rec.actual_attendance is None:  # don't rewrite history once actuals exist
        rec.predicted_demand = it["predicted"]
        rec.advance_confirmations = it["confirmed"]
        rec.slot_bookings = it["bookings"]
    rec.main_dish = rec.main_dish or it["main_dish"]
    rec.meals_prepared = body.meals_prepared
    rec.is_synthetic = False
    db.commit()
    return {"ok": True, "predicted": rec.predicted_demand, "prepared": rec.meals_prepared}


@router.post("/actuals")
def record_actuals(body: ActualsIn, db: Session = Depends(get_db)):
    if body.date > date.today():
        raise HTTPException(400, "Cannot record actuals for a future date")
    rec = db.query(MealRecord).filter_by(date=body.date, meal_type=body.meal_type).first()
    if rec is None:
        rec = MealRecord(date=body.date, meal_type=body.meal_type, source="admin_entry")
        db.add(rec)
    if rec.predicted_demand is None or rec.advance_confirmations is None:
        it = next(i for i in F.forecast_range(db, body.date, 1) if i["meal_type"] == body.meal_type)
        rec.predicted_demand = rec.predicted_demand if rec.predicted_demand is not None else it["predicted"]
        rec.advance_confirmations = it["confirmed"]
        rec.slot_bookings = it["bookings"]
        rec.main_dish = rec.main_dish or it["main_dish"]
    rec.actual_attendance = body.actual_attendance
    rec.meals_prepared = body.meals_prepared
    rec.meals_served = body.meals_served
    rec.source, rec.is_synthetic = "admin_entry", False
    db.commit()
    P.invalidate()
    return {"ok": True, "predicted_demand": rec.predicted_demand, "confirmations": rec.advance_confirmations}


# --- Meal planning ----------------------------------------------------------------------------

def _meal_out(m: Meal) -> dict:
    return {"id": m.id, "date": str(m.date), "meal_type": m.meal_type, "name": m.name, "items": m.items,
            "description": m.description, "is_veg": m.is_veg, "price": m.price, "quantity_available": m.quantity_available,
            "prep_cost": m.prep_cost, "available": m.available, "published": m.published,
            "image": f"/api/uploads/{m.image}" if m.image else None}


@router.get("/meals")
def meals(d: date = Query(default_factory=date.today, alias="date"), db: Session = Depends(get_db)):
    rows = db.query(Meal).filter(Meal.date == d).order_by(Meal.id).all()
    return {"date": str(d), "meals": [_meal_out(m) for m in rows], "forecast": F.forecast_range(db, d, 1)}


@router.post("/meals")
def add_meal(body: MealIn, db: Session = Depends(get_db)):
    if body.date < date.today() - timedelta(days=1):
        raise HTTPException(400, "Meals can only be planned for today or future dates")
    m = Meal(**body.model_dump())
    db.add(m)
    db.commit()
    return _meal_out(m)


@router.patch("/meals/{meal_id}")
def patch_meal(meal_id: int, body: MealPatch, db: Session = Depends(get_db)):
    m = db.get(Meal, meal_id)
    if not m:
        raise HTTPException(404, "Meal not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    return _meal_out(m)


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    m = db.get(Meal, meal_id)
    if not m:
        raise HTTPException(404, "Meal not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.post("/meals/{meal_id}/image")
async def meal_image(meal_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    m = db.get(Meal, meal_id)
    if not m:
        raise HTTPException(404, "Meal not found")
    m.image = await _save_image(file)
    db.commit()
    return _meal_out(m)


@router.post("/meals/publish")
def publish_day(body: PublishIn, db: Session = Depends(get_db)):
    n = db.query(Meal).filter(Meal.date == body.date).update({Meal.published: body.published})
    db.commit()
    return {"updated": n}


@router.post("/meals/copy")
def copy_meals(body: CopyMenuIn, db: Session = Depends(get_db)):
    src = db.query(Meal).filter_by(date=body.from_date).all()
    if not src:
        raise HTTPException(404, "No meals on the source date")
    for m in src:
        db.add(Meal(date=body.to_date, meal_type=m.meal_type, name=m.name, items=m.items, description=m.description,
                    is_veg=m.is_veg, price=m.price, quantity_available=m.quantity_available, prep_cost=m.prep_cost,
                    image=m.image, available=True, published=False))
    db.commit()
    return {"copied": len(src)}


# --- Waste ------------------------------------------------------------------------------------

@router.post("/waste")
def record_waste(body: WasteIn, db: Session = Depends(get_db)):
    if body.date > date.today():
        raise HTTPException(400, "Cannot record waste for a future date")
    if body.served_kg > body.prepared_kg:
        raise HTTPException(400, "Quantity served cannot exceed quantity prepared")
    if body.leftover_kg > body.prepared_kg - body.served_kg + 0.05:
        raise HTTPException(400, "Leftover food cannot exceed prepared minus served")
    s = F.get_settings(db)
    cpk = body.cost_per_kg or F.cost_for_meal(s, body.meal_type)
    total = round(body.leftover_kg + body.plate_waste_kg, 2)
    w = WasteRecord(date=body.date, meal_type=body.meal_type, food_name=body.food_name.strip(),
                    recorded_at=datetime.combine(body.date, body.recorded_at or datetime.now().time().replace(microsecond=0)),
                    prepared_kg=body.prepared_kg, served_kg=body.served_kg, leftover_kg=body.leftover_kg,
                    plate_waste_kg=body.plate_waste_kg, total_waste_kg=total, cost_per_kg=cpk,
                    waste_cost=round(total * cpk, 2), notes=body.notes, source="admin_entry", is_synthetic=False)
    db.add(w)
    db.commit()
    return {"ok": True, "id": w.id, "total_waste_kg": total, "waste_cost": w.waste_cost,
            "calculation": f"({body.leftover_kg:g} + {body.plate_waste_kg:g}) kg x Rs {cpk:g}/kg = Rs {w.waste_cost:,.2f}"}


@router.get("/waste/entries")
def waste_entries(d: date = Query(default_factory=date.today, alias="date"), db: Session = Depends(get_db)):
    rows = db.query(WasteRecord).filter(WasteRecord.date == d).order_by(WasteRecord.recorded_at, WasteRecord.id).all()
    return [{"id": w.id, "meal_type": w.meal_type, "food_name": w.food_name,
             "recorded_at": w.recorded_at.isoformat(timespec="minutes") if w.recorded_at else None,
             "prepared_kg": w.prepared_kg, "served_kg": w.served_kg, "leftover_kg": w.leftover_kg,
             "plate_kg": w.plate_waste_kg, "waste_kg": w.total_waste_kg, "cost_per_kg": w.cost_per_kg,
             "waste_cost": w.waste_cost, "notes": w.notes, "synthetic": w.is_synthetic} for w in rows]


@router.delete("/waste/{waste_id}")
def delete_waste(waste_id: int, db: Session = Depends(get_db)):
    w = db.get(WasteRecord, waste_id)
    if not w:
        raise HTTPException(404, "Entry not found")
    if w.is_synthetic:
        raise HTTPException(400, "Imported historical records are managed through Excel import")
    db.delete(w)
    db.commit()
    return {"ok": True}


@router.get("/waste")
def waste(start: date | None = None, end: date | None = None, granularity: str = "day", meal: str | None = None,
          db: Session = Depends(get_db)):
    if granularity not in A.PERIOD:
        raise HTTPException(400, "granularity must be day, week, month or year")
    start, end = _range(start, end, 30)
    df = A.frame(db, start, end, meal)
    by_meal = []
    if not df.empty:
        for m, g in df.groupby("meal_type"):
            pk = g["prepared_kg"].sum()
            by_meal.append({"meal_type": m, "waste_kg": A._num(g["waste_kg"].sum()), "leftover_kg": A._num(g["leftover_kg"].sum()),
                            "plate_kg": A._num(g["plate_kg"].sum()), "waste_cost": A._num(g["waste_cost"].sum()),
                            "waste_pct": A._num(g["waste_kg"].sum() / pk * 100) if pk else None})
    today = date.today()
    return {"series": A.series(df, granularity), "summary": A.waste_summary(A.frame(db, date(today.year, 1, 1), today), today),
            "by_meal": by_meal, "top_days": A.top_waste_days(df), "data": _data_flags(db)}


def _costliest_foods(db: Session, start: date, end: date, n: int = 10) -> list[dict]:
    rows = (db.query(WasteRecord.meal_type, WasteRecord.food_name, func.count(WasteRecord.id), func.sum(WasteRecord.waste_cost),
                     func.sum(WasteRecord.total_waste_kg))
            .filter(WasteRecord.date >= start, WasteRecord.date <= end)
            .group_by(WasteRecord.meal_type, WasteRecord.food_name).all())
    out = [{"meal_type": m, "dish": f or "Unnamed", "services": c, "total_cost": round(t or 0, 2),
            "avg_cost": round((t or 0) / c, 2), "total_kg": round(k or 0, 1)} for m, f, c, t, k in rows if c]
    return sorted(out, key=lambda x: -x["total_cost"])[:n]


@router.get("/costs")
def costs(start: date | None = None, end: date | None = None, granularity: str = "month", db: Session = Depends(get_db)):
    if granularity not in A.PERIOD:
        raise HTTPException(400, "granularity must be day, week, month or year")
    start, end = _range(start, end, 365)
    df = A.frame(db, start, end)
    s = F.get_settings(db)
    today = date.today()
    return {"series": A.series(df, granularity),
            "summary": A.waste_summary(A.frame(db, date(today.year, 1, 1), today), today),
            "top_days": A.top_waste_days(df, 10), "costliest_meals": _costliest_foods(db, start, end),
            "total_cost": A._num(df["waste_cost"].sum()) if not df.empty else 0,
            "rates": {"breakfast": s.cost_breakfast, "lunch": s.cost_lunch, "dinner": s.cost_dinner, "default": s.cost_per_kg},
            "formula": "Waste cost = waste quantity (kg) x cost per kg (stored on each entry)"}


@router.get("/savings")
def savings(db: Session = Depends(get_db)):
    res = A.recompute_savings(db, F.get_settings(db))
    b = sum(m["baseline_cost"] for m in res["months"])
    res["reduction_pct"] = round((b - sum(m["actual_cost"] for m in res["months"])) / b * 100, 1) if b else None
    return res


@router.patch("/savings/{period}")
def verify_saving(period: str, body: VerifySavingIn, db: Session = Depends(get_db)):
    r = db.query(SavingsRecord).filter_by(period=period).first()
    if r is None:
        raise HTTPException(404, "No savings record for that month")
    r.verified_amount, r.verified_note = body.verified_amount, body.verified_note
    db.commit()
    return {"ok": True}


# --- Analytics -----------------------------------------------------------------------------------

@router.get("/analytics")
def analytics(start: date | None = None, end: date | None = None, granularity: str = "week", meal: str | None = None,
              db: Session = Depends(get_db)):
    if granularity not in A.PERIOD:
        raise HTTPException(400, "granularity must be day, week, month or year")
    start, end = _range(start, end, 365)
    df = A.frame(db, start, end, meal)
    meal_split = []
    slot_hist = []
    avp = []
    if not df.empty:
        for m, g in df.groupby("meal_type"):
            meal_split.append({"meal_type": m, "avg_attendance": A._num(g["att"].mean()), "total": A._num(g["att"].sum()),
                               "avg_prepared": A._num(g["prepared"].mean()), "avg_served": A._num(g["served"].mean())})
        caps = dict(db.query(MealSlot.meal_type, func.sum(MealSlot.capacity)).filter(MealSlot.active.is_(True))
                    .group_by(MealSlot.meal_type).all())
        for m, g in df.dropna(subset=["booked"]).groupby("meal_type"):
            if caps.get(m):
                slot_hist.append({"meal_type": m, "avg_bookings": A._num(g["booked"].mean()), "capacity": caps[m],
                                  "avg_utilization": A._num(g["booked"].mean() / caps[m] * 100)})
        x = df.dropna(subset=["att", "predicted"])
        if not x.empty:
            gg = x.groupby("date").agg(actual=("att", "sum"), predicted=("predicted", "sum"))
            avp = [{"label": i.strftime("%d %b"), "actual": A._num(r.actual), "predicted": A._num(r.predicted)} for i, r in gg.iterrows()]
    sv = A.recompute_savings(db, F.get_settings(db))
    return {"series": A.series(df, granularity), "weekday": A.weekday_demand(df), "meal_split": meal_split,
            "year_comparison": A.year_comparison(A.frame(db, None, None, meal)), "slot_history": slot_hist,
            "actual_vs_predicted": avp, "savings": sv["months"], "data": _data_flags(db),
            "range": {"start": str(start), "end": str(end)}}


# --- Attendance --------------------------------------------------------------------------------

@router.get("/attendance")
def attendance_week(week_start: date | None = None, db: Session = Depends(get_db)):
    today = date.today()
    ws = week_start or today - timedelta(days=today.weekday())
    ws -= timedelta(days=ws.weekday())
    counts = F.live_counts(db, ws, ws + timedelta(days=6))
    closed = ops.closed_dates(db, ws, ws + timedelta(days=6))
    reg = F.registered_students(db)
    days = []
    for i in range(7):
        d = ws + timedelta(days=i)
        elig = len(mess.students_with_pass(db, d))
        meals = {m: {**counts.get((d, m), {"coming": 0, "not_coming": 0, "booked": 0, "arrived": 0, "ticked": 0})} for m in MEAL_TYPES}
        for v in meals.values():
            v["pending"] = max(0, elig - v["coming"] - v["not_coming"])
        days.append({"date": str(d), "weekday": d.strftime("%a"), "closed": d in closed, "closed_reason": closed.get(d), "meals": meals})
    return {"week_start": str(ws), "registered": reg, "days": days}


def _attendance_rows(db: Session, start: date, end: date, q: str | None, meal: str | None, status: str | None):
    qry = (db.query(Attendance, User).join(User, User.id == Attendance.user_id)
           .filter(Attendance.date >= start, Attendance.date <= end))
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(User.name.ilike(like), User.student_code.ilike(like), User.email.ilike(like)))
    if meal:
        qry = qry.filter(Attendance.meal_type == meal)
    if status in ("coming", "not_coming"):
        qry = qry.filter(Attendance.status == status)
    grouped: dict = {}
    present = {(r.user_id, r.date, r.meal_type) for r in db.query(MealAttendance).filter(
        MealAttendance.date >= start, MealAttendance.date <= end)}
    for a, u in qry.order_by(Attendance.date.desc(), User.name).all():
        row = grouped.setdefault((a.date, u.id), {"date": str(a.date), "user_id": u.id, "name": u.name,
                                                  "student_code": u.student_code, "meals": {}})
        row["meals"][a.meal_type] = {"status": a.status, "cancelled": a.cancelled,
                                     "arrived": (u.id, a.date, a.meal_type) in present,
                                     "confirmed_at": a.confirmed_at.isoformat(timespec="minutes"),
                                     "updated_at": a.updated_at.isoformat(timespec="minutes")}
    return list(grouped.values())


@router.get("/attendance/records")
def attendance_records(start: date | None = None, end: date | None = None, q: str | None = None, meal: str | None = None,
                       status: str | None = None, page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=100),
                       db: Session = Depends(get_db)):
    start = start or date.today() - timedelta(days=7)
    end = end or date.today() + timedelta(days=7)
    rows = _attendance_rows(db, start, end, q, meal, status)
    return {"total": len(rows), "page": page, "size": size, "items": rows[(page - 1) * size: page * size]}


@router.post("/attendance/arrival")
def mark_arrival(body: ArrivalIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.date > date.today():
        raise HTTPException(400, "Attendance can only be recorded on or after the meal date")
    ops.mark_present(db, body.user_id, body.date, body.meal_type, body.arrived, admin.id)
    db.commit()
    return {"ok": True}


@router.get("/attendance/no-shows")
def no_shows(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    """Confirmed 'coming' but not arrived - only for services where arrivals were actually recorded."""
    end = min(end or date.today(), date.today())
    start = start or end - timedelta(days=14)
    present = {(r.user_id, r.date, r.meal_type) for r in db.query(MealAttendance).filter(
        MealAttendance.date >= start, MealAttendance.date <= end)}
    tracked = {(d, m) for _, d, m in present}
    out = []
    for a, u in (db.query(Attendance, User).join(User, User.id == Attendance.user_id)
                 .filter(Attendance.date >= start, Attendance.date <= end, Attendance.status == "coming")
                 .order_by(Attendance.date.desc(), User.name)):
        if (a.date, a.meal_type) in tracked and (u.id, a.date, a.meal_type) not in present:
            out.append({"date": str(a.date), "meal_type": a.meal_type, "name": u.name, "student_code": u.student_code,
                        "user_id": u.id, "confirmed_at": a.confirmed_at.isoformat(timespec="minutes")})
    return {"tracked_services": len(tracked), "items": out}


# --- Slots -------------------------------------------------------------------------------------

@router.get("/slots")
def slots(d: date = Query(default_factory=date.today, alias="date"), db: Session = Depends(get_db)):
    st = {}
    for sid, status, n in (db.query(SlotBooking.slot_id, SlotBooking.status, func.count())
                           .filter(SlotBooking.date == d).group_by(SlotBooking.slot_id, SlotBooking.status)):
        st.setdefault(sid, {})[status] = n
    out = []
    for s in db.query(MealSlot).order_by(MealSlot.meal_type, MealSlot.start_time):
        c = st.get(s.id, {})
        taken = c.get("booked", 0) + c.get("served", 0)
        out.append({"id": s.id, "meal_type": s.meal_type, "start": s.start_time.strftime("%H:%M"),
                    "end": s.end_time.strftime("%H:%M"), "capacity": s.capacity, "active": s.active,
                    "confirmed": c.get("booked", 0), "completed": c.get("served", 0), "cancelled": c.get("cancelled", 0),
                    "booked": taken, "remaining": max(0, s.capacity - taken),
                    "utilization": round(taken / s.capacity * 100, 1) if s.capacity else 0})
    return {"date": str(d), "slots": out}


def _overlaps(db: Session, meal: str, st: time, en: time, exclude: int | None = None) -> bool:
    q = db.query(MealSlot).filter(MealSlot.meal_type == meal, MealSlot.active.is_(True),
                                  MealSlot.start_time < en, MealSlot.end_time > st)
    if exclude:
        q = q.filter(MealSlot.id != exclude)
    return q.first() is not None


@router.post("/slots")
def add_slot(body: SlotIn, db: Session = Depends(get_db)):
    if _overlaps(db, body.meal_type, body.start_time, body.end_time):
        raise HTTPException(409, "This slot overlaps an existing active slot")
    s = MealSlot(**body.model_dump())
    db.add(s)
    db.commit()
    return {"id": s.id}


@router.patch("/slots/{slot_id}")
def patch_slot(slot_id: int, body: SlotPatch, db: Session = Depends(get_db)):
    s = db.get(MealSlot, slot_id)
    if not s:
        raise HTTPException(404, "Slot not found")
    if body.capacity is not None:
        future_max = (db.query(func.count(SlotBooking.id)).filter(SlotBooking.slot_id == slot_id, SlotBooking.date >= date.today(),
                      SlotBooking.status == "booked").group_by(SlotBooking.date).order_by(func.count(SlotBooking.id).desc()).first())
        if future_max and future_max[0] > body.capacity:
            raise HTTPException(409, f"{future_max[0]} students are already booked on a future date; capacity cannot go below that.")
        s.capacity = body.capacity
    if body.start_time or body.end_time:
        st, en = body.start_time or s.start_time, body.end_time or s.end_time
        if en <= st:
            raise HTTPException(400, "End time must be after start time")
        if _overlaps(db, s.meal_type, st, en, exclude=s.id):
            raise HTTPException(409, "New timing overlaps another active slot")
        s.start_time, s.end_time = st, en
    if body.active is not None:
        s.active = body.active
    db.commit()
    return {"ok": True}


@router.get("/slots/{slot_id}/bookings")
def slot_bookings(slot_id: int, d: date = Query(default_factory=date.today, alias="date"), db: Session = Depends(get_db)):
    rows = (db.query(SlotBooking, User).join(User, User.id == SlotBooking.user_id)
            .filter(SlotBooking.slot_id == slot_id, SlotBooking.date == d).order_by(User.name).all())
    return [{"id": b.id, "code": b.code, "status": b.status, "student": u.name, "student_code": u.student_code} for b, u in rows]


@router.post("/bookings/{booking_id}/served")
def mark_served(booking_id: int, db: Session = Depends(get_db)):
    b = db.get(SlotBooking, booking_id)
    if not b or b.status != "booked":
        raise HTTPException(400, "Only active bookings can be marked served")
    b.status = "served"
    ops.mark_present(db, b.user_id, b.date, b.meal_type, True, None, source="booking")
    db.commit()
    return {"ok": True}


# --- Rewards -----------------------------------------------------------------------------------

@router.get("/rewards")
def rewards(db: Session = Depends(get_db)):
    reds = (db.query(Redemption, User).join(User, User.id == Redemption.user_id)
            .order_by(Redemption.created_at.desc()).limit(50).all())
    issued = db.query(func.coalesce(func.sum(RewardTransaction.points), 0)).filter(RewardTransaction.points > 0).scalar()
    spent = -db.query(func.coalesce(func.sum(RewardTransaction.points), 0)).filter(RewardTransaction.kind == "redeem").scalar()
    s = F.get_settings(db)
    return {
        "catalog": [{"id": r.id, "name": r.name, "description": r.description, "points_cost": r.points_cost,
                     "stock": r.stock, "active": r.active} for r in db.query(Reward).order_by(Reward.points_cost)],
        "redemptions": [{"id": r.id, "student": u.name, "student_code": u.student_code, "reward": r.reward.name,
                         "points": r.points, "code": r.code, "status": r.status,
                         "created_at": r.created_at.isoformat(timespec="minutes")} for r, u in reds],
        "points_issued": int(issued), "points_redeemed": int(spent),
        "rules_tokens": {"per_attended_meal": F.get_settings(db).tokens_per_attended_meal,
                         "coupon_validity_days": F.get_settings(db).coupon_validity_days},
        "rules": {"points_per_confirmation": s.points_per_confirmation, "weekly_streak_bonus": s.weekly_streak_bonus},
    }


@router.get("/rewards/students")
def reward_students(q: str | None = None, page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=100),
                    db: Session = Depends(get_db)):
    base = db.query(User).filter(User.role == "student")
    if q:
        like = f"%{q.strip()}%"
        base = base.filter(or_(User.name.ilike(like), User.email.ilike(like), User.student_code.ilike(like)))
    total = base.count()
    users = base.order_by(User.name).offset((page - 1) * size).limit(size).all()
    ids = [u.id for u in users]
    earned = dict(db.query(RewardTransaction.user_id, func.sum(RewardTransaction.points)).filter(
        RewardTransaction.user_id.in_(ids), RewardTransaction.points > 0).group_by(RewardTransaction.user_id)) if ids else {}
    spent = dict(db.query(RewardTransaction.user_id, func.sum(RewardTransaction.points)).filter(
        RewardTransaction.user_id.in_(ids), RewardTransaction.kind == "redeem").group_by(RewardTransaction.user_id)) if ids else {}
    bal = {u.id: u.token_balance for u in users}
    return {"total": total, "page": page, "size": size, "items": [
        {"id": u.id, "name": u.name, "email": u.email, "student_code": u.student_code, "is_active": u.is_active,
         "earned": int(earned.get(u.id) or 0), "redeemed": -int(spent.get(u.id) or 0), "balance": int(bal.get(u.id) or 0)}
        for u in users]}


@router.get("/rewards/students/{user_id}/history")
def reward_history(user_id: int, db: Session = Depends(get_db)):
    rows = db.query(RewardTransaction).filter_by(user_id=user_id).order_by(RewardTransaction.created_at.desc()).limit(200).all()
    return [{"id": t.id, "points": t.points, "kind": t.kind, "description": t.description,
             "created_at": t.created_at.isoformat(timespec="minutes")} for t in rows]


@router.post("/rewards")
def add_reward(body: RewardIn, db: Session = Depends(get_db)):
    r = Reward(**body.model_dump())
    db.add(r)
    db.commit()
    return {"id": r.id}


@router.patch("/rewards/{reward_id}")
def patch_reward(reward_id: int, body: RewardIn, db: Session = Depends(get_db)):
    r = db.get(Reward, reward_id)
    if not r:
        raise HTTPException(404, "Reward not found")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return {"ok": True}


@router.post("/redemptions/{red_id}/use")
def use_redemption(red_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    r = db.get(Redemption, red_id)
    if not r:
        raise HTTPException(404, "Coupon not found")
    ops.validate_coupon(db, r.code, admin.id)
    return {"ok": True}


@router.post("/points/adjust")
def adjust_points(body: AdjustPointsIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(id=body.user_id, role="student").first()
    if not u:
        raise HTTPException(404, "Student not found")
    if body.points < 0 and ops.balance(db, u.id) + body.points < 0:
        raise HTTPException(400, "Adjustment would make the balance negative")
    ops.post_tokens(db, u.id, body.points, "adjust", body.reason, f"adjust:{u.id}:{datetime.now().isoformat()}:{ops.new_code()}")
    mess.notify_student(db, u.id, "reward", f"{'+' if body.points > 0 else ''}{body.points} tokens", body.reason, "/student/rewards")
    db.commit()
    return {"balance": ops.balance(db, u.id)}



# --- NGO donations ------------------------------------------------------------------------------

def _ngo_out(n: NgoContact) -> dict:
    return {"id": n.id, "name": n.name, "contact_person": n.contact_person, "phone": n.phone, "email": n.email,
            "address": n.address, "active": n.active}


@router.get("/ngos")
def ngos(db: Session = Depends(get_db)):
    return [_ngo_out(n) for n in db.query(NgoContact).order_by(NgoContact.name)]


@router.post("/ngos")
def add_ngo(body: NgoIn, db: Session = Depends(get_db)):
    n = NgoContact(**{**body.model_dump(), "phone": D.normalize_phone(body.phone)})
    db.add(n)
    db.commit()
    return _ngo_out(n)


@router.patch("/ngos/{ngo_id}")
def patch_ngo(ngo_id: int, body: NgoIn, db: Session = Depends(get_db)):
    n = db.get(NgoContact, ngo_id)
    if not n:
        raise HTTPException(404, "NGO not found")
    for k, v in body.model_dump().items():
        setattr(n, k, D.normalize_phone(v) if k == "phone" else v)
    db.commit()
    return _ngo_out(n)


@router.get("/donations")
def donations(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Donation).order_by(Donation.created_at.desc())
    rows = q.all()
    for d in rows:
        D.refresh_status(db, d)
    db.commit()
    if status:
        rows = [d for d in rows if d.status == status]
    return [D.serialize(d) for d in rows]


def _queue_auto_whatsapp(db: Session, d: Donation, request: Request, background: BackgroundTasks) -> int:
    """When automatic WhatsApp is on, message every active NGO in the background. Returns how many."""
    from ..services import whatsapp as W
    from .whatsapp_routes import auto_send, public_base
    c = W.config(db)
    if not (c.auto_send and W.ready(c)[0]):
        return 0
    n = db.query(NgoContact).filter_by(active=True).count()
    if n:
        background.add_task(auto_send, d.id, public_base(db, request, request.headers.get("origin") or ""))
    return n


@router.post("/donations")
def create_donation(body: DonationIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    now = datetime.now()
    if not body.food_safety_confirmed:
        raise HTTPException(400, "Confirm that the food was handled hygienically and is safe to donate.")
    if body.prepared_at > now + timedelta(minutes=5):
        raise HTTPException(400, "Preparation time cannot be in the future.")
    if body.safe_until <= now:
        raise HTTPException(400, "This food is past its safe consumption time and cannot be donated.")
    if body.safe_until <= body.prepared_at:
        raise HTTPException(400, "Safe-until must be after the preparation time.")
    if body.pickup_deadline <= now:
        raise HTTPException(400, "Pickup deadline must be in the future.")
    if body.pickup_deadline > body.safe_until:
        raise HTTPException(400, "Pickup deadline must be before the food's safe consumption deadline.")
    if body.unit == "portions" and body.quantity != int(body.quantity):
        raise HTTPException(400, "Meal portions must be a whole number.")
    data = body.model_dump(exclude={"food_safety_confirmed"})
    for _ in range(3):
        d = Donation(**data, code=D.next_code(db, now), status="available", created_at=now)
        db.add(d)
        try:
            db.commit()
            out = D.serialize(d)
            out["whatsapp_auto"] = _queue_auto_whatsapp(db, d, request, background)
            return out
        except Exception:  # noqa: BLE001 - code collision under concurrency: retry with the next number
            db.rollback()
    raise HTTPException(500, "Could not allocate a donation ID, please retry")


@router.get("/donations/{donation_id}")
def donation(donation_id: int, db: Session = Depends(get_db)):
    d = db.get(Donation, donation_id)
    if not d:
        raise HTTPException(404, "Donation not found")
    D.refresh_status(db, d)
    db.commit()
    return D.serialize(d)


@router.post("/donations/{donation_id}/image")
async def donation_image(donation_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    d = db.get(Donation, donation_id)
    if not d:
        raise HTTPException(404, "Donation not found")
    d.image = await _save_image(file)
    db.commit()
    return D.serialize(d)


@router.post("/donations/{donation_id}/invites")
def invites(donation_id: int, body: InviteIn, db: Session = Depends(get_db)):
    d = db.get(Donation, donation_id)
    if not d:
        raise HTTPException(404, "Donation not found")
    D.refresh_status(db, d)
    if not D.acceptance_open(d, datetime.now()):
        raise HTTPException(400, f"This donation is {d.status.replace('_', ' ')} and can no longer be shared.")
    s = F.get_settings(db)
    base = s.public_base_url or body.base_url
    out = []
    for nid in body.ngo_ids:
        n = db.get(NgoContact, nid)
        if n and n.active:
            out.append(D.share_links(d, D.get_or_create_invite(db, d, n.id), base, s.canteen_name))
    if body.generic:
        generic = next((i for i in d.invites if i.ngo_id is None and i.response is None), None) or D.get_or_create_invite(db, d, None)
        out.append(D.share_links(d, generic, base, s.canteen_name))
    if not out:
        raise HTTPException(400, "Select at least one active NGO contact or create a shareable link.")
    db.flush()
    db.expire(d)
    D.refresh_status(db, d)
    db.commit()
    return {"donation": D.serialize(d), "links": out}


@router.post("/donations/{donation_id}/cancel")
def cancel_donation(donation_id: int, db: Session = Depends(get_db)):
    d = db.get(Donation, donation_id)
    if not d:
        raise HTTPException(404, "Donation not found")
    if d.status == "collected":
        raise HTTPException(400, "Collected donations cannot be cancelled")
    d.status = "cancelled"
    db.commit()
    return D.serialize(d)


@router.post("/allocations/{alloc_id}/status")
def allocation_status(alloc_id: int, body: AllocationStatusIn, db: Session = Depends(get_db)):
    a = db.get(DonationAllocation, alloc_id)
    if not a:
        raise HTTPException(404, "Allocation not found")
    if body.status == "cancelled":
        D.release_allocation(db, a)
    elif body.status == "pickup_confirmed":
        if a.status != "accepted":
            raise HTTPException(400, f"Allocation is already {a.status.replace('_', ' ')}")
        a.status = "pickup_confirmed"
    else:
        if a.status not in ("accepted", "pickup_confirmed"):
            raise HTTPException(400, f"Allocation is already {a.status.replace('_', ' ')}")
        qty = a.quantity if body.collected_qty is None else body.collected_qty
        if qty > a.quantity + D.EPS:
            raise HTTPException(400, "Collected quantity cannot exceed the accepted quantity")
        a.status, a.collected_qty, a.collected_at = "collected", qty, datetime.now()
    db.flush()
    d = a.donation
    d.collected_qty = sum(x.collected_qty or 0 for x in d.allocations if x.status == "collected")
    D.refresh_status(db, d)
    db.commit()
    return D.serialize(d)


# --- Notifications ------------------------------------------------------------------------------

@router.get("/notifications")
def notifications(db: Session = Depends(get_db)):
    rows = db.query(Notification).order_by(Notification.created_at.desc()).limit(30).all()
    return {"unread": sum(1 for n in rows if not n.read), "items": [
        {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": n.read,
         "created_at": n.created_at.isoformat(timespec="minutes")} for n in rows]}


@router.post("/notifications/read")
def read_notifications(db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.read.is_(False)).update({Notification.read: True})
    db.commit()
    return {"ok": True}


# --- Calendar & settings ------------------------------------------------------------------------

@router.get("/events")
def events(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    start = start or date.today() - timedelta(days=7)
    end = end or date.today() + timedelta(days=60)
    rows = db.query(CalendarEvent).filter(CalendarEvent.date >= start, CalendarEvent.date <= end).order_by(CalendarEvent.date)
    return [{"id": e.id, "date": str(e.date), "kind": e.kind, "name": e.name, "canteen_closed": e.canteen_closed} for e in rows]


@router.post("/events")
def add_event(body: EventIn, db: Session = Depends(get_db)):
    if db.query(CalendarEvent).filter_by(date=body.date, name=body.name).first():
        raise HTTPException(409, "Event already exists on that date")
    e = CalendarEvent(**body.model_dump())
    db.add(e)
    db.commit()
    P.invalidate()
    return {"id": e.id}


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    e = db.get(CalendarEvent, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    db.delete(e)
    db.commit()
    P.invalidate()
    return {"ok": True}


SETTING_FIELDS = ["canteen_name", "buffer_pct", "forecast_mode", "attendance_window_days", "points_per_confirmation",
                  "weekly_streak_bonus", "cost_per_kg", "cost_breakfast", "cost_lunch", "cost_dinner",
                  "booking_cancel_minutes", "baseline_mode", "baseline_manual_daily", "active_model",
                  "public_base_url", "pickup_location", "tokens_per_attended_meal", "coupon_validity_days",
                  "holiday_extends_pass", "expiring_soon_days", "price_monthly", "price_six_month"]


def _settings_out(s) -> dict:
    out = {k: getattr(s, k) for k in SETTING_FIELDS}
    out.update({"attendance_deadline": s.attendance_deadline.strftime("%H:%M"),
                "baseline_start": str(s.baseline_start), "baseline_end": str(s.baseline_end)})
    return out


@router.get("/settings")
def get_settings_route(db: Session = Depends(get_db)):
    return _settings_out(F.get_settings(db))


@router.patch("/settings")
def patch_settings(body: SettingsIn, db: Session = Depends(get_db)):
    s = F.get_settings(db)
    data = body.model_dump(exclude_unset=True)
    if data.get("active_model") == "random_forest" and not P.MODEL_PATH.exists():
        raise HTTPException(400, "Train the Random Forest model before activating it.")
    for k, v in data.items():
        setattr(s, k, v)
    if s.baseline_start > s.baseline_end:
        raise HTTPException(400, "Baseline start must be before baseline end")
    db.commit()
    return _settings_out(s)


# --- Import / reports ---------------------------------------------------------------------------

@router.post("/import")
async def upload(file: UploadFile = File(...), synthetic: bool | None = None, db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Please upload an Excel file (.xlsx)")
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 15 MB)")
    try:
        res = import_excel(db, content, file.filename, synthetic=synthetic)
    except ValueError as e:
        raise HTTPException(400, str(e))
    P.invalidate()
    return res


@router.get("/imports")
def import_logs(db: Session = Depends(get_db)):
    return [{"id": l.id, "filename": l.filename, "imported_at": l.imported_at.isoformat(timespec="minutes"),
             "rows_read": l.rows_read, "rows_imported": l.rows_imported, "rows_skipped": l.rows_skipped,
             "is_synthetic": l.is_synthetic, "messages": l.messages.splitlines() if l.messages else []}
            for l in db.query(ImportLog).order_by(ImportLog.imported_at.desc()).limit(20)]


@router.get("/reports/export")
def export(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    start, end = _range(start, end, 365)
    df = A.frame(db, start, end)
    s = F.get_settings(db)
    flags = _data_flags(db)
    sheets = {"About": pd.DataFrame({"EcoByte report": [
        f"Period: {start} to {end}", f"Generated: {datetime.now():%d %b %Y %H:%M}",
        "Waste cost = waste kg x cost per kg (stored per entry)",
        "WARNING: includes SYNTHETIC demonstration history." if flags["has_synthetic"] else "All records are admin-entered."]})}
    if not df.empty:
        cols = {"date": "Date", "meal_type": "Meal", "dish": "Main dish", "conf": "Advance confirmations", "booked": "Slot bookings",
                "att": "Actual attendance", "predicted": "Predicted demand", "prepared": "Meals prepared", "served": "Meals served",
                "prepared_kg": "Prepared kg", "served_kg": "Served kg", "leftover_kg": "Leftover kg", "plate_kg": "Plate waste kg",
                "waste_kg": "Total waste kg", "waste_cost": "Waste cost (Rs)", "is_synthetic": "Synthetic"}
        out = df[list(cols)].rename(columns=cols)
        out["Date"] = out["Date"].dt.date
        sheets["Daily records"] = out
        for g, n in (("week", "Weekly summary"), ("month", "Monthly summary"), ("year", "Annual summary")):
            sheets[n] = pd.DataFrame(A.series(df, g))
    sheets["Savings"] = pd.DataFrame(A.recompute_savings(db, s)["months"])
    return _xlsx(sheets, f"EcoByte_Report_{start}_{end}.xlsx")


@router.get("/reports/attendance")
def export_attendance(start: date | None = None, end: date | None = None, q: str | None = None, db: Session = Depends(get_db)):
    start = start or date.today() - timedelta(days=30)
    end = end or date.today() + timedelta(days=14)
    rows = []
    for r in _attendance_rows(db, start, end, q, None, None):
        rec = {"Date": r["date"], "Student": r["name"], "Student ID": r["student_code"]}
        for m in MEAL_TYPES:
            x = r["meals"].get(m)
            rec[m.capitalize()] = ("Coming" if x["status"] == "coming" else "Not coming") if x else "Pending"
            rec[f"{m.capitalize()} confirmed at"] = x["confirmed_at"] if x else ""
            rec[f"{m.capitalize()} arrived"] = ("Yes" if x["arrived"] else "No") if x else ""
        rows.append(rec)
    return _xlsx({"Attendance": pd.DataFrame(rows)}, f"EcoByte_Attendance_{start}_{end}.xlsx")


@router.get("/reports/waste")
def export_waste(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    start, end = _range(start, end, 90)
    rows = [{"Date": w.date, "Meal": w.meal_type, "Food": w.food_name, "Recorded at": w.recorded_at,
             "Prepared kg": w.prepared_kg, "Served kg": w.served_kg, "Leftover kg": w.leftover_kg,
             "Plate waste kg": w.plate_waste_kg, "Total waste kg": w.total_waste_kg, "Cost per kg": w.cost_per_kg,
             "Waste cost (Rs)": w.waste_cost, "Notes": w.notes, "Synthetic": w.is_synthetic}
            for w in db.query(WasteRecord).filter(WasteRecord.date >= start, WasteRecord.date <= end).order_by(WasteRecord.date)]
    return _xlsx({"Waste": pd.DataFrame(rows)}, f"EcoByte_Waste_{start}_{end}.xlsx")


@router.get("/reports/donations")
def export_donations(db: Session = Depends(get_db)):
    rows, allocs = [], []
    for d in db.query(Donation).order_by(Donation.created_at):
        D.refresh_status(db, d)
        x = D.serialize(d)
        rows.append({"Donation ID": d.code, "Food": d.food_name, "Category": d.category, "Veg": d.is_veg,
                     "Quantity": d.quantity, "Unit": d.unit, "Accepted": x["allocated"], "Collected": x["collected"],
                     "Prepared at": d.prepared_at, "Safe until": d.safe_until, "Pickup deadline": d.pickup_deadline,
                     "Requested": d.created_at, "Status": d.status})
        for a in d.allocations:
            allocs.append({"Donation ID": d.code, "NGO": a.organisation, "Contact": a.contact_name, "Phone": a.contact_phone,
                           "Quantity": a.quantity, "Status": a.status, "Collected": a.collected_qty, "Accepted at": a.created_at})
    db.commit()
    return _xlsx({"Donations": pd.DataFrame(rows), "NGO allocations": pd.DataFrame(allocs)}, "EcoByte_Donations.xlsx")
