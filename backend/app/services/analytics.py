"""Aggregations for dashboards, waste monitoring, cost tracking and savings.

All figures are computed from stored meal_records / waste_records, never hardcoded.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..models import AppSettings, MealRecord, SavingsRecord, WasteRecord


def frame(db: Session, start: date | None = None, end: date | None = None, meal: str | None = None) -> pd.DataFrame:
    mq = db.query(MealRecord)
    wq = db.query(WasteRecord)
    if start:
        mq, wq = mq.filter(MealRecord.date >= start), wq.filter(WasteRecord.date >= start)
    if end:
        mq, wq = mq.filter(MealRecord.date <= end), wq.filter(WasteRecord.date <= end)
    if meal:
        mq, wq = mq.filter(MealRecord.meal_type == meal), wq.filter(WasteRecord.meal_type == meal)
    m = pd.DataFrame([{
        "date": r.date, "meal_type": r.meal_type, "dish": r.main_dish, "event": r.event,
        "conf": r.advance_confirmations, "booked": r.slot_bookings, "att": r.actual_attendance,
        "predicted": r.predicted_demand, "prepared": r.meals_prepared, "served": r.meals_served,
        "synthetic": r.is_synthetic,
    } for r in mq.all()])
    w = pd.DataFrame([{
        "date": r.date, "meal_type": r.meal_type, "prepared_kg": r.prepared_kg, "served_kg": r.served_kg,
        "leftover_kg": r.leftover_kg, "plate_kg": r.plate_waste_kg, "waste_kg": r.total_waste_kg,
        "cost_per_kg": r.cost_per_kg, "waste_cost": r.waste_cost, "w_synthetic": r.is_synthetic,
    } for r in wq.all()])
    if not w.empty:
        # Several waste entries (one per food item) can exist per service: sum them.
        num = ["prepared_kg", "served_kg", "leftover_kg", "plate_kg", "waste_kg", "waste_cost"]
        w[num] = w[num].apply(pd.to_numeric, errors="coerce")
        w = w.groupby(["date", "meal_type"], as_index=False).agg(
            **{k: (k, lambda s: s.sum(min_count=1)) for k in num}, w_synthetic=("w_synthetic", "max"))
        w["cost_per_kg"] = np.where(w["waste_kg"] > 0, w["waste_cost"] / w["waste_kg"], np.nan)
    if m.empty and w.empty:
        return pd.DataFrame()
    if m.empty:
        df = w
    elif w.empty:
        df = m
    else:
        df = m.merge(w, on=["date", "meal_type"], how="outer")
    df["date"] = pd.to_datetime(df["date"])
    for c in ["conf", "booked", "att", "predicted", "prepared", "served", "prepared_kg", "served_kg",
              "leftover_kg", "plate_kg", "waste_kg", "waste_cost"]:
        if c not in df:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["synthetic", "w_synthetic"]:
        if c not in df:
            df[c] = False
    df["is_synthetic"] = df["synthetic"].fillna(False).astype(bool) | df["w_synthetic"].fillna(False).astype(bool)
    return df.sort_values(["date", "meal_type"]).reset_index(drop=True)


def _num(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(v), 2)


PERIOD = {"day": "D", "week": "W-SUN", "month": "MS", "year": "YS"}


def series(df: pd.DataFrame, granularity: str = "day") -> list[dict]:
    if df.empty:
        return []
    cols = ["conf", "booked", "att", "predicted", "prepared", "served", "prepared_kg", "served_kg",
            "leftover_kg", "plate_kg", "waste_kg", "waste_cost"]
    g = df.set_index("date")[cols]
    # min_count=1 keeps "no data" as null instead of 0.
    agg = g.resample(PERIOD[granularity]).sum(min_count=1)
    services = df.set_index("date")["att"].resample(PERIOD[granularity]).count()
    out = []
    for idx, row in agg.iterrows():
        if services.get(idx, 0) == 0 and pd.isna(row["waste_kg"]):
            continue
        start = idx if granularity != "week" else idx - pd.Timedelta(days=6)
        rec = {"period": str(start.date()), "label": _label(start, granularity),
               "services": int(services.get(idx, 0))}
        rec.update({k: _num(row[k]) for k in cols})
        pk = row["prepared_kg"]
        rec["waste_pct"] = _num(row["waste_kg"] / pk * 100) if pk and not pd.isna(pk) and pk > 0 else None
        out.append(rec)
    return out


def _label(ts: pd.Timestamp, gran: str) -> str:
    if gran == "day":
        return ts.strftime("%d %b")
    if gran == "week":
        return "Wk of " + ts.strftime("%d %b")
    if gran == "month":
        return ts.strftime("%b %Y")
    return ts.strftime("%Y")


def weekday_demand(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    d = df.dropna(subset=["att"]).copy()
    d = d[~d["event"].fillna("").str.contains("vacation|break", case=False)]
    d["wd"] = d["date"].dt.weekday
    out = []
    for wd in range(7):
        sub = d[d["wd"] == wd]
        if sub.empty:
            continue
        per_day = sub.groupby("date")["att"].sum()
        rec = {"weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wd],
               "avg_total": _num(per_day.mean()), "days": int(per_day.size)}
        for meal, g in sub.groupby("meal_type"):
            rec[meal] = _num(g["att"].mean())
        out.append(rec)
    return out


def year_comparison(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"years": [], "months": []}
    d = df.copy()
    d["year"], d["month"] = d["date"].dt.year, d["date"].dt.month
    years = sorted(d["year"].unique().tolist())
    agg = d.groupby(["year", "month"]).agg(att=("att", "sum"), waste_kg=("waste_kg", "sum"),
                                            waste_cost=("waste_cost", "sum"), days=("date", "nunique"))
    months = []
    for m in range(1, 13):
        rec = {"month": datetime(2000, m, 1).strftime("%b")}
        for y in years:
            if (y, m) in agg.index:
                r = agg.loc[(y, m)]
                rec[f"att_{y}"] = _num(r["att"] / r["days"]) if r["days"] else None  # avg daily
                rec[f"waste_kg_{y}"] = _num(r["waste_kg"])
                rec[f"waste_cost_{y}"] = _num(r["waste_cost"])
        months.append(rec)
    totals = {}
    for y in years:
        sub = d[d["year"] == y]
        totals[str(y)] = {"services": int(sub["att"].notna().sum()), "attendance": _num(sub["att"].sum()),
                          "waste_kg": _num(sub["waste_kg"].sum()), "waste_cost": _num(sub["waste_cost"].sum()),
                          "days": int(sub["date"].nunique())}
    return {"years": [int(y) for y in years], "months": months, "totals": totals}


def waste_summary(df: pd.DataFrame, today: date) -> dict:
    """Totals for the day / week / month / year that contain `today` (or the latest data)."""
    if df.empty:
        return {}
    t = pd.Timestamp(today)
    windows = {
        "day": (t, t),
        "week": (t - pd.Timedelta(days=t.weekday()), t),
        "month": (t.replace(day=1), t),
        "year": (t.replace(month=1, day=1), t),
    }
    out = {}
    for k, (a, b) in windows.items():
        sub = df[(df["date"] >= a) & (df["date"] <= b)]
        pk = sub["prepared_kg"].sum()
        out[k] = {
            "from": str(a.date()), "to": str(b.date()),
            "waste_kg": _num(sub["waste_kg"].sum(min_count=1)),
            "leftover_kg": _num(sub["leftover_kg"].sum(min_count=1)),
            "plate_kg": _num(sub["plate_kg"].sum(min_count=1)),
            "waste_cost": _num(sub["waste_cost"].sum(min_count=1)),
            "waste_pct": _num(sub["waste_kg"].sum() / pk * 100) if pk > 0 else None,
            "services": int(sub["waste_kg"].notna().sum()),
        }
    return out


def top_waste_days(df: pd.DataFrame, n: int = 8) -> list[dict]:
    if df.empty:
        return []
    g = df.groupby("date").agg(waste_kg=("waste_kg", "sum"), waste_cost=("waste_cost", "sum"),
                               prepared=("prepared", "sum"), served=("served", "sum"),
                               event=("event", "first"))
    g = g[g["waste_kg"] > 0].sort_values("waste_cost", ascending=False).head(n)
    return [{"date": str(i.date()), "weekday": i.strftime("%a"), "waste_kg": _num(r.waste_kg),
             "waste_cost": _num(r.waste_cost), "prepared": _num(r.prepared), "served": _num(r.served),
             "event": r.event if isinstance(r.event, str) else None} for i, r in g.iterrows()]


def costliest_meals(df: pd.DataFrame, n: int = 8) -> list[dict]:
    """Rank dishes by average waste cost per service (min 3 services so one bad day doesn't dominate)."""
    if df.empty or "dish" not in df:
        return []
    d = df.dropna(subset=["dish", "waste_cost"])
    g = d.groupby(["meal_type", "dish"]).agg(services=("waste_cost", "size"), total=("waste_cost", "sum"),
                                              avg=("waste_cost", "mean"), plate=("plate_kg", "mean"),
                                              leftover=("leftover_kg", "mean"))
    g = g[g["services"] >= 3].sort_values("avg", ascending=False).head(n)
    return [{"meal_type": m, "dish": dish, "services": int(r.services), "total_cost": _num(r.total),
             "avg_cost": _num(r.avg), "avg_plate_kg": _num(r.plate), "avg_leftover_kg": _num(r.leftover)}
            for (m, dish), r in g.iterrows()]


# --- Savings ---------------------------------------------------------------------------------

def baseline(db: Session, s: AppSettings) -> dict:
    """Baseline = waste cost per meal served during the reference period (or a manual daily value).

    Normalising per meal served means a quiet vacation month is not mistaken for a saving.
    """
    if s.baseline_mode == "manual":
        return {"mode": "manual", "daily_cost": s.baseline_manual_daily, "cost_per_meal": None,
                "description": f"Manual baseline of Rs {s.baseline_manual_daily:,.0f} per operating day"}
    df = frame(db, s.baseline_start, s.baseline_end)
    if df.empty or df["waste_cost"].isna().all():
        return {"mode": "period", "daily_cost": None, "cost_per_meal": None,
                "description": "No waste records in the baseline period"}
    d = df.dropna(subset=["waste_cost"])
    served = d["served"].sum()
    days = d["date"].nunique()
    return {
        "mode": "period", "start": str(s.baseline_start), "end": str(s.baseline_end),
        "total_cost": _num(d["waste_cost"].sum()), "meals_served": _num(served), "days": int(days),
        "daily_cost": _num(d["waste_cost"].sum() / days) if days else None,
        "cost_per_meal": round(float(d["waste_cost"].sum() / served), 4) if served else None,
        "description": (f"Average waste cost per meal served between {s.baseline_start:%d %b %Y} "
                        f"and {s.baseline_end:%d %b %Y}"),
    }


def recompute_savings(db: Session, s: AppSettings) -> dict:
    base = baseline(db, s)
    after = s.baseline_end if s.baseline_mode == "period" else None
    df = frame(db, after + timedelta(days=1) if after else None, None)
    existing = {r.period: r for r in db.query(SavingsRecord).all()}
    keep = set()
    months = []
    if not df.empty and (base.get("cost_per_meal") or base.get("daily_cost")):
        d = df.dropna(subset=["waste_cost"]).copy()
        d["period"] = d["date"].dt.strftime("%Y-%m")
        for period, g in d.groupby("period"):
            days = int(g["date"].nunique())
            served = float(g["served"].sum())
            actual = float(g["waste_cost"].sum())
            if base.get("cost_per_meal") is not None:
                bcost = base["cost_per_meal"] * served
            else:
                bcost = base["daily_cost"] * days
            rec = existing.get(period) or SavingsRecord(period=period)
            rec.operating_days = days
            rec.baseline_cost = round(bcost, 2)
            rec.actual_cost = round(actual, 2)
            rec.estimated_saving = round(bcost - actual, 2)
            rec.computed_at = datetime.now()
            if rec.id is None:
                db.add(rec)
            keep.add(period)
    for p, r in existing.items():
        if p not in keep and r.verified_amount is None:
            db.delete(r)
    db.commit()
    rows = db.query(SavingsRecord).order_by(SavingsRecord.period).all()
    for r in rows:
        months.append({"period": r.period, "label": datetime.strptime(r.period, "%Y-%m").strftime("%b %Y"),
                       "operating_days": r.operating_days, "baseline_cost": r.baseline_cost,
                       "actual_cost": r.actual_cost, "estimated_saving": r.estimated_saving,
                       "verified_amount": r.verified_amount, "verified_note": r.verified_note})
    years: dict[str, dict] = {}
    cum = 0.0
    for m in months:
        y = m["period"][:4]
        yy = years.setdefault(y, {"year": y, "baseline_cost": 0.0, "actual_cost": 0.0,
                                  "estimated_saving": 0.0, "verified_amount": 0.0, "months": 0})
        yy["baseline_cost"] += m["baseline_cost"]
        yy["actual_cost"] += m["actual_cost"]
        yy["estimated_saving"] += m["estimated_saving"]
        yy["verified_amount"] += m["verified_amount"] or 0
        yy["months"] += 1
        cum += m["estimated_saving"]
        m["cumulative_estimated"] = round(cum, 2)
    for yy in years.values():
        for k in ("baseline_cost", "actual_cost", "estimated_saving", "verified_amount"):
            yy[k] = round(yy[k], 2)
    return {"baseline": base, "months": months, "years": list(years.values()),
            "total_estimated": round(cum, 2),
            "total_verified": round(sum(m["verified_amount"] or 0 for m in months), 2)}
