"""Food-demand prediction.

BASELINE MODEL (always available, fully documented, no training required)
-------------------------------------------------------------------------
For a target service (date D, meal m):

1. Normalise history. Every past service is divided by its own menu factor and calendar
   factor so that a "Biryani + exam week" Monday and a "Dal + regular" Monday are comparable.
2. Weekday level  A = mean of the last 4 normalised same-weekday services of meal m
   (from the previous 10 weeks; falls back to 26 weeks, then all history).
3. Recent trend   T = (last 7 services) / (previous 8 weeks), weekday-adjusted, half-weighted,
   clipped to +/-10%.
4. Menu factor    M = how the planned main dish has historically performed relative to the
   regular level (shrunk towards 1.0 when it has few observations).
5. Calendar factor E = learned effect of the event on D (exam, vacation, festival, ...),
   by event name if seen before, otherwise by event kind. Closed days -> 0.
   History-based estimate  B = A x T x M x E.
6. Advance confirmations. k = median(actual / confirmed) over the last 8 weeks.
   - Confirmation window closed: prediction = 0.5 x B + 0.5 x (confirmed x k)
   - Window still open: confirmations are a floor -> max(B, 0.9 x confirmed, 0.9 x booked)
7. Uncertainty: +/-1.28 sigma of walk-forward backtest residuals (~80% interval).

Factors (M, E, weekday index) are learned only from rows *before* the evaluation window,
so backtests never peek at the future.

RANDOM FOREST (optional)
------------------------
Trained on demand when an admin presses "Train model". Time-ordered split: the last 60
operating days are held out. Its MAE/MAPE is compared against the baseline on the same
hold-out, and stored in `model_runs`. It is only reported as trained when a run exists.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import MEAL_TYPES, MODEL_PATH
from ..models import CalendarEvent, MealRecord, ModelRun

DEFAULT_EVENT_FACTOR = {"vacation": 0.5, "holiday": 0.6, "exam": 1.0, "event": 1.05}


def event_kind(name: str | None, is_holiday: bool = False) -> str | None:
    if is_holiday:
        return "holiday"
    if not isinstance(name, str) or not name:
        return None
    n = name.lower()
    if "vacation" in n or "break" in n:
        return "vacation"
    if "exam" in n:
        return "exam"
    if "holiday" in n:
        return "holiday"
    return "event"


# --- Data access ---------------------------------------------------------------------------

def history_frame(db: Session) -> pd.DataFrame:
    rows = db.query(MealRecord).filter(MealRecord.actual_attendance.isnot(None)).all()
    df = pd.DataFrame([{
        "date": pd.Timestamp(r.date), "meal_type": r.meal_type, "att": float(r.actual_attendance),
        "conf": r.advance_confirmations, "booked": r.slot_bookings, "dish": r.main_dish,
        "event": r.event, "is_holiday": bool(r.is_holiday),
        "prepared": r.meals_prepared, "served": r.meals_served, "predicted": r.predicted_demand,
    } for r in rows])
    if df.empty:
        return df
    df["kind"] = [event_kind(e, h) for e, h in zip(df["event"], df["is_holiday"])]
    df["weekday"] = df["date"].dt.weekday
    return df.sort_values(["date", "meal_type"]).reset_index(drop=True)


def data_version(db: Session) -> tuple:
    return (
        db.query(func.count(MealRecord.id)).scalar(),
        str(db.query(func.max(MealRecord.updated_at)).scalar()),
        db.query(func.count(CalendarEvent.id)).scalar(),
    )


def calendar_lookup(db: Session, start: date, end: date) -> dict[date, CalendarEvent]:
    evs = db.query(CalendarEvent).filter(CalendarEvent.date >= start, CalendarEvent.date <= end).all()
    out: dict[date, CalendarEvent] = {}
    for e in evs:
        # A closed day dominates; otherwise keep the first event.
        if e.date not in out or e.canteen_closed:
            out[e.date] = e
    return out


# --- Baseline model ---------------------------------------------------------------------------

@dataclass
class Factors:
    dish: dict
    event_name: dict
    event_kind: dict
    weekday_index: dict
    conf_ratio: dict
    learned_until: date | None
    rows_used: int


def _regular_reference(df: pd.DataFrame) -> np.ndarray:
    """For each row: median attendance of regular (no event) services with the same meal and
    weekday within +/-42 days, excluding the row itself. NaN when fewer than 2 exist."""
    ref = np.full(len(df), np.nan)
    for (_, _), g in df.groupby(["meal_type", "weekday"]):
        reg = g[g["kind"].isna()]
        if reg.empty:
            continue
        rd = reg["date"].values.astype("datetime64[D]").astype(np.int64)
        ra = reg["att"].values
        for i, (d, idx) in enumerate(zip(g["date"].values.astype("datetime64[D]").astype(np.int64), g.index)):
            lo, hi = np.searchsorted(rd, d - 42), np.searchsorted(rd, d + 42, side="right")
            window = [(rd[j], ra[j]) for j in range(lo, hi) if rd[j] != d]
            if len(window) >= 2:
                ref[df.index.get_loc(idx)] = float(np.median([w[1] for w in window]))
    return ref


def _shrink(values: pd.Series, k: float = 5.0, lo=0.0, hi=5.0) -> float:
    n = len(values)
    if n == 0:
        return 1.0
    return float(np.clip((values.sum() + k * 1.0) / (n + k), lo, hi))


def learn_factors(hist: pd.DataFrame, until: date | None = None) -> Factors:
    df = hist if until is None else hist[hist["date"] < pd.Timestamp(until)]
    df = df.copy()
    if df.empty:
        return Factors({}, {}, {}, {}, {}, until, 0)
    df["ref"] = _regular_reference(df)
    df["ratio"] = df["att"] / df["ref"]
    valid = df[df["ratio"].notna() & np.isfinite(df["ratio"])]

    dish = {}
    reg = valid[valid["kind"].isna() & valid["dish"].notna()]
    for (meal, d), g in reg.groupby(["meal_type", "dish"]):
        dish[(meal, d)] = _shrink(g["ratio"], k=5, lo=0.8, hi=1.25)

    ev_name, ev_kind = {}, {}
    evr = valid[valid["kind"].notna()]
    for (meal, name), g in evr.groupby(["meal_type", "event"]):
        if len(g) >= 3:
            ev_name[(meal, name)] = float(np.clip(g["ratio"].mean(), 0.05, 2.0))
    for (meal, kind), g in evr.groupby(["meal_type", "kind"]):
        ev_kind[(meal, kind)] = float(np.clip(g["ratio"].mean(), 0.05, 2.0))

    wk = {}
    regall = df[df["kind"].isna()]
    for meal, g in regall.groupby("meal_type"):
        overall = g["att"].mean()
        for wd, gg in g.groupby("weekday"):
            wk[(meal, wd)] = float(gg["att"].mean() / overall) if overall else 1.0

    conf_ratio = {}
    recent = df[df["date"] >= df["date"].max() - pd.Timedelta(days=56)]
    for meal, g in recent[recent["conf"].fillna(0) > 0].groupby("meal_type"):
        conf_ratio[meal] = float(np.median(g["att"] / g["conf"].astype(float)))
    return Factors(dish, ev_name, ev_kind, wk, conf_ratio, until, len(df))


def _row_factor(f: Factors, meal: str, dish, kind, name) -> tuple[float, float]:
    m = f.dish.get((meal, dish), 1.0) if isinstance(dish, str) else 1.0
    if kind is None:
        e = 1.0
    else:
        e = f.event_name.get((meal, name)) or f.event_kind.get((meal, kind)) or DEFAULT_EVENT_FACTOR.get(kind, 1.0)
    return m, e


def baseline_predict(hist: pd.DataFrame, f: Factors, target: date, meal: str, *,
                     dish: str | None = None, kind: str | None = None, event_name: str | None = None,
                     closed: bool = False, confirmations: int | None = None,
                     window_closed: bool = False, bookings: int | None = None) -> dict:
    """Return prediction + every intermediate component so the result is traceable."""
    if closed:
        return {"predicted": 0, "history_estimate": 0, "components": {"closed": True},
                "method": "Canteen closed on this date"}
    t = pd.Timestamp(target)
    h = hist[(hist["meal_type"] == meal) & (hist["date"] < t)]
    usable = h[~h["kind"].isin(["vacation", "holiday"])]
    if usable.empty:
        return {"predicted": None, "history_estimate": None, "components": {},
                "method": "Not enough history"}

    mf, ef = zip(*[_row_factor(f, meal, d, k, n) for d, k, n in zip(usable["dish"], usable["kind"], usable["event"])])
    norm = usable["att"].values / (np.array(mf) * np.array(ef))
    usable = usable.assign(norm=norm)

    wd = target.weekday()
    same = usable[usable["weekday"] == wd]
    level_src = "last 4 same-weekday services (10 weeks)"
    s = same[same["date"] >= t - pd.Timedelta(weeks=10)]
    if len(s) < 2:
        s = same[same["date"] >= t - pd.Timedelta(weeks=26)]
        level_src = "same-weekday services (26 weeks, fallback)"
    if len(s) < 2:
        s = same
        level_src = "all same-weekday history (fallback)"
    if s.empty:
        # No same weekday at all: use overall level scaled by weekday index.
        level = usable["norm"].tail(28).mean() * f.weekday_index.get((meal, wd), 1.0)
        level_src = "overall recent level x weekday index (fallback)"
        n_level = min(len(usable), 28)
    else:
        level = s["norm"].tail(4).mean()
        n_level = min(len(s), 4)

    # Trend: last 7 services vs previous 8 weeks, weekday-adjusted.
    widx = np.array([f.weekday_index.get((meal, w), 1.0) for w in usable["weekday"]])
    adj = usable["norm"].values / np.where(widx > 0, widx, 1.0)
    last7 = adj[-7:]
    prev = adj[(usable["date"].values >= np.datetime64(t - pd.Timedelta(weeks=9))) &
               (usable["date"].values < np.datetime64(t - pd.Timedelta(days=7)))] if len(adj) > 7 else []
    trend = 1.0
    if len(last7) >= 4 and len(prev) >= 10:
        raw = float(np.mean(last7) / np.mean(prev))
        trend = float(np.clip(1 + 0.5 * (raw - 1), 0.9, 1.1))

    m, e = _row_factor(f, meal, dish, kind, event_name)
    hist_est = level * trend * m * e

    k = f.conf_ratio.get(meal)
    conf_est = None
    pred = hist_est
    method = "History estimate (A x T x M x E)"
    if confirmations:
        if window_closed and k:
            conf_est = confirmations * k
            pred = 0.5 * hist_est + 0.5 * conf_est
            method = "50% history estimate + 50% confirmations x show-up ratio"
        else:
            floor = 0.9 * confirmations
            if floor > pred:
                pred = floor
                method = "Confirmations floor (0.9 x confirmed) exceeded history estimate"
    if bookings and 0.9 * bookings > pred:
        pred = 0.9 * bookings
        method = "Bookings floor (0.9 x booked) exceeded estimate"

    return {
        "predicted": int(round(pred)),
        "history_estimate": int(round(hist_est)),
        "method": method,
        "components": {
            "weekday_level": round(float(level), 1), "weekday_level_source": level_src,
            "weekday_level_samples": int(n_level), "trend_factor": round(trend, 3),
            "menu_factor": round(m, 3), "menu_dish": dish,
            "calendar_factor": round(e, 3), "calendar_event": event_name, "calendar_kind": kind,
            "confirmations": confirmations, "confirmation_window_closed": window_closed,
            "show_up_ratio": round(k, 3) if k else None,
            "confirmation_estimate": round(conf_est, 1) if conf_est is not None else None,
            "bookings": bookings,
        },
    }


# --- Backtesting & metrics ----------------------------------------------------------------------

def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    if len(actual) == 0:
        return {"mae": None, "mape": None, "n": 0, "bias": None, "sigma": None}
    err = pred - actual
    nz = actual > 0
    return {
        "mae": round(float(np.mean(np.abs(err))), 2),
        "mape": round(float(np.mean(np.abs(err[nz]) / actual[nz]) * 100), 2) if nz.any() else None,
        "bias": round(float(np.mean(err)), 2),
        "sigma": round(float(np.std(err, ddof=1)), 2) if len(err) > 1 else None,
        "n": int(len(actual)),
    }


def test_window(hist: pd.DataFrame, days: int = 60) -> date | None:
    if hist.empty:
        return None
    dates = sorted(hist["date"].dt.date.unique())
    if len(dates) < days + 60:
        return None
    return dates[-days]


def backtest_baseline(hist: pd.DataFrame, start: date) -> pd.DataFrame:
    f = learn_factors(hist, until=start)
    test = hist[hist["date"] >= pd.Timestamp(start)]
    out = []
    for r in test.itertuples():
        p = baseline_predict(hist, f, r.date.date(), r.meal_type, dish=r.dish, kind=r.kind,
                             event_name=r.event, confirmations=None if pd.isna(r.conf) else int(r.conf),
                             window_closed=True)
        if p["predicted"] is not None:
            out.append({"date": r.date.date(), "meal_type": r.meal_type, "actual": r.att, "pred": p["predicted"]})
    return pd.DataFrame(out)


# --- Random forest ------------------------------------------------------------------------------

RF_FEATURES = ["meal_b", "meal_l", "meal_d", "weekday", "month", "doy", "is_exam", "is_event",
               "is_vacation", "is_holiday", "menu_factor", "lag_wd_1", "lag_wd_mean4", "recent7",
               "conf", "has_conf"]


def rf_features(hist: pd.DataFrame, f: Factors, future: pd.DataFrame | None = None) -> pd.DataFrame:
    """Lag features use only strictly earlier services of the same meal."""
    base = hist[["date", "meal_type", "att", "conf", "dish", "kind", "event", "weekday"]].copy()
    base["is_future"] = False
    if future is not None and not future.empty:
        fut = future.copy()
        fut["is_future"] = True
        fut["att"] = np.nan
        base = pd.concat([base, fut], ignore_index=True)
    base = base.sort_values(["meal_type", "date"]).reset_index(drop=True)
    g_wd = base.groupby(["meal_type", "weekday"])["att"]
    base["lag_wd_1"] = g_wd.transform(lambda s: s.shift(1).ffill())
    base["lag_wd_mean4"] = g_wd.transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean().ffill())
    base["recent7"] = base.groupby("meal_type")["att"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).mean().ffill())
    base["meal_b"] = (base["meal_type"] == "breakfast").astype(int)
    base["meal_l"] = (base["meal_type"] == "lunch").astype(int)
    base["meal_d"] = (base["meal_type"] == "dinner").astype(int)
    base["month"] = base["date"].dt.month
    base["doy"] = base["date"].dt.dayofyear
    for k in ("exam", "event", "vacation", "holiday"):
        base[f"is_{k}"] = (base["kind"] == k).astype(int)
    base["menu_factor"] = [f.dish.get((m, d), 1.0) if isinstance(d, str) else 1.0 for m, d in zip(base["meal_type"], base["dish"])]
    base["has_conf"] = base["conf"].notna().astype(int)
    base["conf"] = base["conf"].fillna(0).astype(float)
    return base


def train_random_forest(db: Session, test_days: int = 60) -> dict:
    from sklearn.ensemble import RandomForestRegressor  # imported lazily: heavy
    import joblib

    hist = history_frame(db)
    start = test_window(hist, test_days)
    if start is None:
        raise ValueError(f"Need at least {test_days + 60} operating days of history to train and evaluate.")
    f = learn_factors(hist, until=start)
    feats = rf_features(hist, f).dropna(subset=["lag_wd_1", "lag_wd_mean4", "recent7"])
    train = feats[feats["date"] < pd.Timestamp(start)]
    test = feats[feats["date"] >= pd.Timestamp(start)]
    model = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42, n_jobs=-1)
    model.fit(train[RF_FEATURES], train["att"])
    rf_pred = model.predict(test[RF_FEATURES])
    rf_m = _metrics(test["att"].values, rf_pred)

    bt = backtest_baseline(hist, start)
    base_m = _metrics(bt["actual"].values, bt["pred"].values)

    # Refit on all data for live use (evaluation numbers above stay on the hold-out).
    full_f = learn_factors(hist)
    full = rf_features(hist, full_f).dropna(subset=["lag_wd_1", "lag_wd_mean4", "recent7"])
    final = RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42, n_jobs=-1)
    final.fit(full[RF_FEATURES], full["att"])
    resid_sigma = rf_m["sigma"]
    joblib.dump({"model": final, "sigma": resid_sigma, "trained_at": datetime.now().isoformat()}, MODEL_PATH)

    importances = sorted(zip(RF_FEATURES, final.feature_importances_), key=lambda x: -x[1])
    run = ModelRun(model="random_forest", trained_at=datetime.now(), train_rows=len(train), test_rows=len(test),
                   test_start=start, test_end=hist["date"].max().date(), mae=rf_m["mae"], mape=rf_m["mape"] or 0,
                   baseline_mae=base_m["mae"], baseline_mape=base_m["mape"] or 0,
                   features=json.dumps([[n, round(float(v), 4)] for n, v in importances]))
    db.add(run)
    db.commit()
    _CACHE.clear()
    return {"run_id": run.id, "random_forest": rf_m, "baseline": base_m, "train_rows": len(train),
            "test_rows": len(test), "test_start": str(start),
            "feature_importance": [[n, round(float(v), 4)] for n, v in importances]}


def load_rf():
    if not MODEL_PATH.exists():
        return None
    import joblib
    try:
        return joblib.load(MODEL_PATH)
    except Exception:  # noqa: BLE001 - a corrupt model file must not take the API down
        return None


# --- Cached evaluation used by dashboards ----------------------------------------------------------

_CACHE: dict = {}


def evaluation(db: Session) -> dict:
    """Walk-forward baseline backtest over the last 60 operating days (cached per data version)."""
    ver = data_version(db)
    if _CACHE.get("eval_ver") == ver:
        return _CACHE["eval"]
    hist = history_frame(db)
    start = test_window(hist)
    result = {"available": False}
    if start is not None:
        bt = backtest_baseline(hist, start)
        per_meal = {m: _metrics(g["actual"].values, g["pred"].values) for m, g in bt.groupby("meal_type")}
        daily = bt.groupby("date")[["actual", "pred"]].sum()
        result = {
            "available": True, "test_start": str(start), "test_end": str(hist["date"].max().date()),
            "overall": _metrics(bt["actual"].values, bt["pred"].values),
            "daily_total": _metrics(daily["actual"].values, daily["pred"].values),
            "per_meal": per_meal,
        }
    _CACHE["eval_ver"], _CACHE["eval"] = ver, result
    return result


def factors_cached(db: Session, hist: pd.DataFrame) -> Factors:
    ver = data_version(db)
    if _CACHE.get("f_ver") != ver:
        _CACHE["f_ver"], _CACHE["f"] = ver, learn_factors(hist)
    return _CACHE["f"]


def hist_cached(db: Session) -> pd.DataFrame:
    ver = data_version(db)
    if _CACHE.get("h_ver") != ver:
        _CACHE["h_ver"], _CACHE["h"] = ver, history_frame(db)
    return _CACHE["h"]


def invalidate():
    _CACHE.clear()


def interval(pred: int | None, sigma: float | None) -> tuple[int, int] | None:
    if pred is None or sigma is None or math.isnan(sigma):
        return None
    half = 1.2816 * sigma
    return max(0, int(round(pred - half))), int(round(pred + half))
