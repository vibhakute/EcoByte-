"""Synthetic demonstration data generator.

Everything produced here is SYNTHETIC. It exists so the platform can be demonstrated
before real canteen records are available. Rows are always tagged `is_synthetic=True`.

The generator models a college canteen (~620 enrolled diners, Mon-Sat, three meals)
with weekday, seasonal, menu, holiday, vacation, exam and event effects plus noise.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

# --- Calendar -------------------------------------------------------------------------

def _span(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def academic_calendar(year: int) -> dict[date, dict]:
    """date -> {kind, name, closed, factor}. factor multiplies expected attendance."""
    cal: dict[date, dict] = {}

    def add(d, kind, name, closed=False, factor=1.0):
        cal[d] = {"kind": kind, "name": name, "closed": closed, "factor": factor}

    def add_span(a, b, kind, name, factor):
        for d in _span(a, b):
            if d not in cal:
                add(d, kind, name, False, factor)

    if year == 2025:
        closed = {
            date(2025, 1, 26): "Republic Day", date(2025, 3, 14): "Holi",
            date(2025, 5, 1): "Maharashtra Day", date(2025, 8, 15): "Independence Day",
            date(2025, 10, 2): "Gandhi Jayanti", date(2025, 10, 21): "Diwali (Lakshmi Puja)",
            date(2025, 10, 22): "Diwali (Padwa)", date(2025, 12, 25): "Christmas",
        }
        for d, n in closed.items():
            add(d, "holiday", n, closed=True, factor=0.0)
        add(date(2025, 8, 27), "holiday", "Ganesh Chaturthi", factor=0.55)
        add_span(date(2025, 10, 18), date(2025, 10, 25), "vacation", "Diwali break", 0.45)
        add_span(date(2025, 5, 17), date(2025, 6, 29), "vacation", "Summer vacation", 0.35)
        add_span(date(2025, 12, 22), date(2025, 12, 31), "vacation", "Winter break", 0.40)
        add_span(date(2025, 3, 3), date(2025, 3, 8), "exam", "Mid-semester exams", 1.05)
        add_span(date(2025, 4, 21), date(2025, 5, 10), "exam", "End-semester exams", 1.07)
        add_span(date(2025, 9, 22), date(2025, 9, 27), "exam", "Mid-semester exams", 1.05)
        add_span(date(2025, 11, 17), date(2025, 12, 5), "exam", "End-semester exams", 1.07)
        add_span(date(2025, 2, 20), date(2025, 2, 22), "event", "Annual tech fest", 1.15)
        add_span(date(2025, 1, 27), date(2025, 1, 31), "event", "Sports week", 1.06)
    elif year == 2026:
        closed = {
            date(2026, 1, 26): "Republic Day", date(2026, 3, 4): "Holi",
            date(2026, 5, 1): "Maharashtra Day", date(2026, 8, 15): "Independence Day",
            date(2026, 10, 2): "Gandhi Jayanti", date(2026, 11, 9): "Diwali (Lakshmi Puja)",
            date(2026, 11, 10): "Diwali (Padwa)", date(2026, 12, 25): "Christmas",
        }
        for d, n in closed.items():
            add(d, "holiday", n, closed=True, factor=0.0)
        add(date(2026, 9, 14), "holiday", "Ganesh Chaturthi", factor=0.55)
        add_span(date(2026, 11, 6), date(2026, 11, 13), "vacation", "Diwali break", 0.45)
        add_span(date(2026, 5, 16), date(2026, 6, 28), "vacation", "Summer vacation", 0.35)
        add_span(date(2026, 12, 21), date(2026, 12, 31), "vacation", "Winter break", 0.40)
        add_span(date(2026, 3, 9), date(2026, 3, 14), "exam", "Mid-semester exams", 1.05)
        add_span(date(2026, 4, 20), date(2026, 5, 9), "exam", "End-semester exams", 1.07)
        add_span(date(2026, 9, 21), date(2026, 9, 26), "exam", "Mid-semester exams", 1.05)
        add_span(date(2026, 11, 23), date(2026, 12, 11), "exam", "End-semester exams", 1.07)
        add_span(date(2026, 2, 19), date(2026, 2, 21), "event", "Annual tech fest", 1.15)
        add_span(date(2026, 1, 27), date(2026, 1, 31), "event", "Sports week", 1.06)
        add(date(2026, 12, 2), "event", "Alumni day", factor=1.08)
    return cal


# --- Menu -------------------------------------------------------------------------------

DISHES = {
    "breakfast": [("Poha", 1.00), ("Upma", 0.90), ("Idli Sambar", 1.05), ("Aloo Paratha", 1.12),
                  ("Masala Dosa", 1.10), ("Misal Pav", 1.06), ("Sabudana Khichdi", 0.95)],
    "lunch": [("Paneer Butter Masala", 1.08), ("Chole Bhature", 1.10), ("Veg Biryani", 1.12),
              ("Rajma Chawal", 1.00), ("Dal Tadka & Jeera Rice", 0.94), ("Mix Veg & Roti", 0.92),
              ("Kadhi Pakora", 0.96), ("Aloo Gobi & Roti", 0.95), ("Pav Bhaji", 1.05),
              ("Veg Pulao & Raita", 0.98)],
    "dinner": [("Dal Makhani", 1.02), ("Veg Kolhapuri", 0.98), ("Veg Fried Rice & Manchurian", 1.10),
               ("Palak Paneer", 1.04), ("Khichdi & Kadhi", 0.85), ("Sev Bhaji & Chapati", 0.95),
               ("Baingan Bharta", 0.90)],
}
DISH_FACTOR = {name: f for meal in DISHES.values() for name, f in meal}

SIDES = {
    "breakfast": [("Tea / Coffee", "beverage", 0), ("Banana", "side", 0), ("Boiled Egg (add-on)", "side", 12)],
    "lunch": [("Chapati (3)", "side", 0), ("Steamed Rice", "side", 0), ("Dal", "side", 0),
              ("Green Salad", "side", 0), ("Masala Chaas (add-on)", "beverage", 15)],
    "dinner": [("Chapati (3)", "side", 0), ("Jeera Rice", "side", 0), ("Dal Fry", "side", 0),
               ("Gulab Jamun (add-on)", "dessert", 20)],
}
MEAL_PRICE = {"breakfast": 35.0, "lunch": 70.0, "dinner": 70.0}
PORTION_KG = {"breakfast": 0.25, "lunch": 0.40, "dinner": 0.38}


def main_dish_for(d: date, meal: str) -> str:
    dishes = DISHES[meal]
    idx = (d.weekday() + 2 * (d.isocalendar().week % 3)) % len(dishes)
    return dishes[idx][0]


def menu_for(d: date, meal: str) -> list[dict]:
    main = main_dish_for(d, meal)
    items = [{"name": main, "category": "main", "price": MEAL_PRICE[meal], "is_veg": True}]
    for name, cat, price in SIDES[meal]:
        items.append({"name": name, "category": cat, "price": float(price),
                      "is_veg": "Egg" not in name})
    return items


# --- Demand -------------------------------------------------------------------------------

BASE = {"breakfast": 205, "lunch": 418, "dinner": 262}
WEEKDAY = {
    "breakfast": [1.02, 1.00, 1.01, 0.99, 0.95, 0.80],
    "lunch":     [1.03, 1.00, 1.02, 0.99, 0.93, 0.68],
    "dinner":    [1.00, 1.01, 1.00, 0.99, 0.92, 0.85],
}
MONTH = {1: 0.97, 2: 1.00, 3: 1.00, 4: 1.02, 5: 1.00, 6: 1.00, 7: 0.92, 8: 1.00,
         9: 1.02, 10: 0.98, 11: 1.00, 12: 0.96}
MEAL_EVENT_SENSITIVITY = {"breakfast": 0.7, "lunch": 1.0, "dinner": 0.8}


def expected_attendance(d: date, meal: str, cal: dict, growth: float = 1.0) -> float:
    ev = cal.get(d)
    f = BASE[meal] * WEEKDAY[meal][d.weekday()] * MONTH[d.month] * DISH_FACTOR[main_dish_for(d, meal)] * growth
    if ev:
        if ev["closed"]:
            return 0.0
        # Vacations/holidays affect hostel meals (breakfast/dinner) less than lunch.
        sens = MEAL_EVENT_SENSITIVITY[meal] if ev["factor"] < 1 else 1.0
        f *= 1 - (1 - ev["factor"]) * sens
    return f


def generate_days(start: date, end: date, seed: int, era: str) -> list[dict]:
    """Generate per-service demand rows. era='legacy' (2025, before EcoByte) or 'ecobyte' (2026 demo).

    For era='ecobyte' the prepared/served/waste fields are left empty: the seeder fills them
    from the real prediction engine so that 'predicted vs actual' reflects the actual algorithm.
    """
    rng = random.Random(seed)
    cals = {y: academic_calendar(y) for y in range(start.year, end.year + 1)}
    rows = []
    history: dict[tuple, list[int]] = {}  # (meal, weekday) -> attendance list, for the legacy cook estimate
    for d in _span(start, end):
        if d.weekday() == 6:  # canteen closed on Sundays
            continue
        cal = cals[d.year]
        ev = cal.get(d)
        if ev and ev["closed"]:
            continue
        growth = 1.0 if era == "legacy" else 1.0 + 0.03 * (d.timetuple().tm_yday / 365)
        for meal in ("breakfast", "lunch", "dinner"):
            exp = expected_attendance(d, meal, cal, growth)
            att = max(0, round(exp * rng.gauss(1.0, 0.045)))
            dish = main_dish_for(d, meal)
            conf_ratio = rng.uniform(0.56, 0.70) if era == "legacy" else rng.uniform(0.70, 0.82)
            # Some confirmed students do not show; some unconfirmed students do.
            conf = max(0, round(att * conf_ratio * rng.gauss(1.0, 0.03)))
            row = {
                "date": d, "meal_type": meal, "main_dish": dish,
                "menu_items": ", ".join(i["name"] for i in menu_for(d, meal)),
                "is_holiday": bool(ev and ev["kind"] == "holiday"),
                "event": ev["name"] if ev else None,
                "advance_confirmations": conf,
                "slot_bookings": None if era == "legacy" else round(att * rng.uniform(0.55, 0.68)),
                "actual_attendance": att,
            }
            if era == "legacy":
                # Before EcoByte: the cook estimates from the last two same-weekday services + a generous margin.
                past = history.get((meal, d.weekday()), [])[-2:]
                guess = (sum(past) / len(past)) if past else BASE[meal] * WEEKDAY[meal][d.weekday()]
                prepared = round(guess * rng.uniform(1.07, 1.19))
                fill_service(row, prepared, rng, plate_rate=(0.065, 0.10), cost_per_kg=110.0)
                history.setdefault((meal, d.weekday()), []).append(att)
            rows.append(row)
    return rows


def fill_service(row: dict, prepared: int, rng: random.Random, plate_rate=(0.05, 0.08), cost_per_kg=120.0):
    meal = row["meal_type"]
    att = row["actual_attendance"]
    served = min(prepared, att)
    portion = PORTION_KG[meal]
    leftover = max(0.0, (prepared - served) * portion * rng.uniform(0.88, 1.02))
    dish_f = DISH_FACTOR.get(row["main_dish"], 1.0)
    # Less popular dishes leave more on the plate.
    pr = rng.uniform(*plate_rate) * (1.0 + (1.0 - dish_f) * 1.5)
    plate = served * portion * max(pr, 0.01)
    total = leftover + plate
    row.update({
        "meals_prepared": prepared, "meals_served": served,
        "prepared_kg": round(prepared * portion, 1), "served_kg": round(served * portion, 1),
        "leftover_kg": round(leftover, 1), "plate_waste_kg": round(plate, 1),
        "total_waste_kg": round(total, 1), "cost_per_kg": cost_per_kg,
        "waste_cost": round(round(total, 1) * cost_per_kg, 2),
    })
    return row
