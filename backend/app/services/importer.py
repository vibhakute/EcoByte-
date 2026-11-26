"""Excel historical-data importer with column validation.

Column names are matched case/space/punctuation-insensitively against an alias list, so
real canteen spreadsheets with slightly different headers can be imported. Each row is
validated; invalid rows are skipped with a reason rather than silently coerced.
"""
from __future__ import annotations

import io
import re
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from ..config import MEAL_TYPES
from ..models import AppSettings, ImportLog, MealRecord, WasteRecord


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


ALIASES: dict[str, list[str]] = {
    "date": ["date", "servicedate", "day_date", "recorddate"],
    "meal_type": ["mealtype", "meal", "mealcategory", "service", "mealslot"],
    "main_dish": ["maindish", "dish", "mainitem", "menu_main", "specialdish"],
    "menu_items": ["menuitems", "menu", "items", "fooditems"],
    "is_holiday": ["isholiday", "holiday"],
    "event": ["event", "specialevent", "occasion", "collegeevent", "remarks"],
    "advance_confirmations": ["advanceconfirmations", "confirmations", "advanceconfirmation",
                              "confirmedstudents", "preconfirmed", "advancebookings"],
    "slot_bookings": ["slotbookings", "bookings", "slotsbooked"],
    "actual_attendance": ["actualattendance", "attendance", "studentsattended", "actualstudents", "footfall"],
    "meals_prepared": ["mealsprepared", "prepared", "platesprepared", "quantityprepared"],
    "meals_served": ["mealsserved", "served", "platesserved", "quantityserved"],
    "prepared_kg": ["preparedkg", "foodpreparedkg", "totalfoodpreparedkg"],
    "served_kg": ["servedkg", "foodservedkg", "totalfoodservedkg"],
    "leftover_kg": ["leftoverfoodkg", "leftoverkg", "remainingediblefoodkg", "remainingfoodkg", "leftover"],
    "plate_waste_kg": ["platewastekg", "platewaste"],
    "total_waste_kg": ["totalwastekg", "foodwastekg", "wastekg", "totalfoodwastekg", "waste"],
    "cost_per_kg": ["costperkg", "costperkginr", "ratekg", "costkg"],
    "waste_cost": ["wastecostinr", "wastecost", "costofwaste", "wastecostrs"],
}
REQUIRED = ["date", "actual_attendance", "meals_prepared"]
MEAL_MAP = {"b": "breakfast", "bf": "breakfast", "breakfast": "breakfast", "morning": "breakfast",
            "l": "lunch", "lunch": "lunch", "afternoon": "lunch",
            "d": "dinner", "dinner": "dinner", "night": "dinner", "supper": "dinner"}


def map_columns(columns) -> dict[str, str]:
    """Return canonical -> original column name."""
    lookup = {_norm(c): c for c in columns}
    mapping = {}
    for canon, aliases in ALIASES.items():
        for a in [canon] + aliases:
            if _norm(a) in lookup:
                mapping[canon] = lookup[_norm(a)]
                break
    return mapping


def _pick_sheet(xls: pd.ExcelFile) -> tuple[str, pd.DataFrame, dict]:
    best = None
    for name in xls.sheet_names:
        df = xls.parse(name)
        mapping = map_columns(df.columns)
        score = len(mapping)
        if all(r in mapping for r in REQUIRED) and (best is None or score > best[2]):
            best = (name, df, score, mapping)
    if best is None:
        found = {n: list(xls.parse(n, nrows=0).columns) for n in xls.sheet_names}
        raise ValueError(
            "No sheet contains the required columns "
            f"{REQUIRED} (aliases accepted). Columns found: {found}")
    return best[0], best[1], best[3]


def _int(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    f = float(v)
    if f < 0:
        raise ValueError("negative value")
    return int(round(f))


def _float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    f = float(v)
    if f < 0:
        raise ValueError("negative value")
    return f


def _bool(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _text(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def detect_synthetic(xls: pd.ExcelFile, filename: str) -> bool:
    if "synthetic" in filename.lower():
        return True
    for name in xls.sheet_names:
        if "readme" in name.lower() or "about" in name.lower():
            text = " ".join(str(x) for x in xls.parse(name, header=None).fillna("").values.ravel())
            if "synthetic" in text.lower():
                return True
    return False


def import_excel(db: Session, content: bytes, filename: str, synthetic: bool | None = None,
                 source: str | None = None) -> dict:
    xls = pd.ExcelFile(io.BytesIO(content))
    sheet, df, mapping = _pick_sheet(xls)
    is_syn = detect_synthetic(xls, filename) if synthetic is None else synthetic
    src = source or ("excel_synthetic" if is_syn else "excel_import")
    settings = db.query(AppSettings).first()
    default_cost = settings.cost_per_kg if settings else 120.0

    messages: list[str] = []
    if "meal_type" not in mapping:
        messages.append("No meal-type column found: every row imported as 'lunch'.")
    if "total_waste_kg" not in mapping and not ("leftover_kg" in mapping or "plate_waste_kg" in mapping):
        messages.append("No waste columns found: demand data imported, waste records skipped.")

    existing_m = {(r.date, r.meal_type): r for r in db.query(MealRecord).all()}
    existing_w: dict = {}
    for r in db.query(WasteRecord).all():
        existing_w.setdefault((r.date, r.meal_type), []).append(r)
    imported = skipped = cost_mismatch = 0
    seen = set()

    def g(row, key):
        col = mapping.get(key)
        return row[col] if col is not None else None

    for idx, row in df.iterrows():
        line = idx + 2  # Excel line number (header is line 1)
        try:
            d = pd.to_datetime(g(row, "date"), dayfirst=False, errors="raise").date()
            meal_raw = _text(g(row, "meal_type")) or "lunch"
            meal = MEAL_MAP.get(meal_raw.lower())
            if meal not in MEAL_TYPES:
                raise ValueError(f"unknown meal type '{meal_raw}'")
            if (d, meal) in seen:
                raise ValueError("duplicate date + meal in file")
            att = _int(g(row, "actual_attendance"))
            prepared = _int(g(row, "meals_prepared"))
            served = _int(g(row, "meals_served"))
            if att is None or prepared is None:
                raise ValueError("attendance and meals prepared are required")
            if served is None:
                served = min(att, prepared)
            if served > prepared:
                raise ValueError(f"meals served ({served}) exceeds meals prepared ({prepared})")
        except Exception as e:  # noqa: BLE001 - report every row-level problem
            skipped += 1
            if len(messages) < 60:
                messages.append(f"Row {line}: skipped - {e}")
            continue
        seen.add((d, meal))

        rec = existing_m.get((d, meal)) or MealRecord(date=d, meal_type=meal)
        rec.main_dish = _text(g(row, "main_dish"))
        rec.menu_items = _text(g(row, "menu_items"))
        rec.is_holiday = _bool(g(row, "is_holiday"))
        rec.event = _text(g(row, "event"))
        rec.advance_confirmations = _int(g(row, "advance_confirmations"))
        rec.slot_bookings = _int(g(row, "slot_bookings"))
        rec.actual_attendance = att
        rec.meals_prepared = prepared
        rec.meals_served = served
        rec.source = src
        rec.is_synthetic = is_syn
        if rec.id is None:
            db.add(rec)

        leftover = _float(g(row, "leftover_kg"))
        plate = _float(g(row, "plate_waste_kg"))
        total = _float(g(row, "total_waste_kg"))
        if total is None and (leftover is not None or plate is not None):
            total = (leftover or 0) + (plate or 0)
        if total is not None:
            cpk = _float(g(row, "cost_per_kg")) or default_cost
            cost = round(total * cpk, 2)
            file_cost = _float(g(row, "waste_cost"))
            if file_cost is not None and abs(file_cost - cost) > max(1.0, 0.01 * cost):
                cost_mismatch += 1
            for old_w in existing_w.pop((d, meal), []):  # the file replaces earlier entries for this service
                db.delete(old_w)
            w = WasteRecord(date=d, meal_type=meal, food_name=rec.main_dish)
            w.prepared_kg = _float(g(row, "prepared_kg"))
            w.served_kg = _float(g(row, "served_kg"))
            w.leftover_kg = leftover if leftover is not None else max(total - (plate or 0), 0)
            w.plate_waste_kg = plate or 0.0
            w.total_waste_kg = total
            w.cost_per_kg = cpk
            w.waste_cost = cost
            w.source = src
            w.is_synthetic = is_syn
            db.add(w)
        imported += 1

    if cost_mismatch:
        messages.append(f"{cost_mismatch} rows had a waste-cost value that did not equal kg x cost/kg; "
                        "EcoByte recalculated those so every cost is traceable.")
    log = ImportLog(filename=filename, imported_at=datetime.now(), rows_read=len(df),
                    rows_imported=imported, rows_skipped=skipped, is_synthetic=is_syn,
                    messages="\n".join(messages))
    db.add(log)
    db.commit()
    return {
        "sheet": sheet, "filename": filename, "rows_read": len(df), "rows_imported": imported,
        "rows_skipped": skipped, "is_synthetic": is_syn,
        "column_mapping": mapping, "messages": messages,
    }
