"""Create the schema and the starting data.

    python -m app.seed            # create tables and seed if the database is empty
    python -m app.seed --reset    # drop everything and start again from zero
    python -m app.seed --reset --demo   # ...plus three weeks of demo activity (see app/demo_data.py)

What is created
- Settings, one admin account and five demo student accounts (all with known passwords).
- Meal-time slots (15 minutes, 40 seats each), the reward catalogue and the college calendar.
- The 2025 historical dataset, imported through the normal Excel importer (it is SYNTHETIC
  demonstration data, flagged as such; it feeds analytics and the "historical average").
- A published sample menu for the next 7 days so students have something to see.

- Mess passes for the demo students (expiring soon / active / expired), canteen-store items.

Without --demo, nothing live is created (attendance, bookings, tokens, prepared/served counts, waste,
donations, orders): every live number starts at zero and changes only when people use the app.
With --demo, app/demo_data.py adds 25 more students and three weeks of realistic activity.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta

from .auth import hash_password
from .config import ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_ACCOUNTS, HISTORICAL_XLSX, MEAL_TYPES, MODEL_PATH
from .database import Base, SessionLocal, engine
from .models import AppSettings, CalendarEvent, Meal, MealSlot, MessSubscription, Product, Reward, User
from .services.mess import PASS_DAYS
from .services import prediction as P
from .services.importer import import_excel
from .services.synthetic import SIDES, academic_calendar, main_dish_for

DEMO_ADMIN = (ADMIN_EMAIL, ADMIN_PASSWORD)  # set ECOBYTE_ADMIN_EMAIL / _PASSWORD in production
DEMO_STUDENT_PASSWORD = "Student@123"
DEMO_STUDENTS = [
    ("student@ecobyte.app", "Aarav Kulkarni", "STU2025", "AI & Data Science", 3),
    ("priya@ecobyte.app", "Priya Deshmukh", "STU2026", "Computer Engineering", 2),
    ("rohan@ecobyte.app", "Rohan Patil", "STU2027", "Mechanical Engineering", 4),
    ("sneha@ecobyte.app", "Sneha Iyer", "STU2028", "Information Technology", 1),
    ("kabir@ecobyte.app", "Kabir Shah", "STU2029", "Electronics & Telecom", 3),
]
DESCRIPTIONS = {
    "breakfast": "Freshly made every morning, served with tea or coffee.",
    "lunch": "Complete thali with chapati, rice, dal and salad.",
    "dinner": "Light, home-style dinner with chapati, rice and dal.",
}
PRICE = {"breakfast": 35.0, "lunch": 70.0, "dinner": 70.0}


def log(msg: str):
    print(f"[seed {datetime.now():%H:%M:%S}] {msg}", flush=True)


def create_base(db):
    db.add(AppSettings())
    db.add(User(role="admin", email=DEMO_ADMIN[0], name="Canteen Admin", password_hash=hash_password(DEMO_ADMIN[1])))
    for email, name, code, dept, year in (DEMO_STUDENTS if DEMO_ACCOUNTS else []):
        db.add(User(role="student", email=email, name=name, password_hash=hash_password(DEMO_STUDENT_PASSWORD),
                    student_code=code, department=dept, year_of_study=year, is_demo=True))

    def add_slots(meal, start: time, n, minutes=15, cap=40):
        t = datetime.combine(date.today(), start)
        for _ in range(n):
            db.add(MealSlot(meal_type=meal, start_time=t.time(), end_time=(t + timedelta(minutes=minutes)).time(), capacity=cap))
            t += timedelta(minutes=minutes)
    add_slots("breakfast", time(7, 30), 6)
    add_slots("lunch", time(12, 0), 8)
    add_slots("dinner", time(19, 30), 6)

    db.add_all([  # token prices are configurable in Reward & Coupon Management
        Reward(name="Tea", description="One cup of masala tea at the counter.", points_cost=200, stock=1000),
        Reward(name="Coffee", description="One cup of filter coffee.", points_cost=300, stock=1000),
        Reward(name="Samosa", description="One hot samosa with chutney.", points_cost=350, stock=500),
        Reward(name="Sandwich", description="One veg grilled sandwich.", points_cost=500, stock=300),
        Reward(name="Free Meal Coupon", description="One complete lunch or dinner thali.", points_cost=800, stock=200),
        Reward(name="Food Hamper", description="Fruits, dry fruits and healthy snacks.", points_cost=2500, stock=30),
    ])
    db.add_all([
        Product(name="Tea", description="Masala chai, freshly brewed.", category="beverage", price=10),
        Product(name="Coffee", description="South Indian filter coffee.", category="beverage", price=15),
        Product(name="Cold Drink", description="Chilled 250 ml bottle.", category="beverage", price=30),
        Product(name="Sweet Lassi", description="Thick sweet lassi, 300 ml.", category="beverage", price=30),
        Product(name="Samosa", description="Crispy samosa with mint chutney.", category="snack", price=15),
        Product(name="Poha", description="Kanda poha with sev and lemon.", category="snack", price=25),
        Product(name="Veg Sandwich", description="Grilled sandwich with cheese and veggies.", category="snack", price=40),
        Product(name="Maggi", description="Masala Maggi noodles.", category="snack", price=35),
        Product(name="Gulab Jamun", description="Two pieces, served warm.", category="dessert", price=20),
    ])
    for y in (2025, 2026, 2027):
        for d, ev in academic_calendar(y).items():
            htype = None
            if ev["kind"] == "holiday":
                htype = "national" if ev["name"] in NATIONAL else "festival"
            db.add(CalendarEvent(date=d, kind=ev["kind"], name=ev["name"], canteen_closed=ev["closed"], holiday_type=htype,
                                 services="breakfast,lunch,dinner" if ev["closed"] else "", published=True,
                                 message=f"The canteen is closed for {ev['name']}." if ev["closed"] else "",
                                 published_at=datetime.combine(d - timedelta(days=14), time(10)) if ev["closed"] else None))
    db.commit()


NATIONAL = {"Republic Day", "Independence Day", "Gandhi Jayanti", "Maharashtra Day"}


def seed_passes(db, today: date):
    """Demo passes relative to today, so every status is visible: expiring soon, active, expired."""
    plan = {"student@ecobyte.app": ("monthly", -25), "priya@ecobyte.app": ("six_month", -40),
            "rohan@ecobyte.app": ("monthly", -35), "sneha@ecobyte.app": ("monthly", -10), "kabir@ecobyte.app": ("monthly", -2)}
    admin = db.query(User).filter_by(role="admin").first()
    for email, (ptype, offset) in plan.items():
        u = db.query(User).filter_by(email=email).first()
        if u is None:  # demo accounts turned off
            continue
        start = today + timedelta(days=offset)
        days = PASS_DAYS[ptype]
        db.add(MessSubscription(user_id=u.id, pass_type=ptype, purchase_date=start - timedelta(days=1), start_date=start,
                                base_days=days, expiry_date=start + timedelta(days=days - 1), price=3000 if ptype == "monthly" else 16000,
                                created_at=datetime.combine(start - timedelta(days=1), time(11)), created_by=admin.id))
    db.commit()


def import_history(db):
    if not HISTORICAL_XLSX.exists():
        from scripts.generate_dataset import build
        build(HISTORICAL_XLSX)
        log(f"Generated synthetic workbook {HISTORICAL_XLSX.name}")
    res = import_excel(db, HISTORICAL_XLSX.read_bytes(), HISTORICAL_XLSX.name)
    log(f"Imported {res['rows_imported']} historical rows from {res['filename']} (synthetic={res['is_synthetic']})")


def seed_menu(db, today: date):
    closed = {e.date for e in db.query(CalendarEvent).filter(CalendarEvent.canteen_closed.is_(True))}
    for i in range(7):
        d = today + timedelta(days=i)
        if d.weekday() == 6 or d in closed:
            continue
        for meal in MEAL_TYPES:
            items = [n.replace(" (add-on)", "") for n, _, price in SIDES[meal] if price == 0]
            db.add(Meal(date=d, meal_type=meal, name=main_dish_for(d, meal), items="\n".join(items),
                        description=DESCRIPTIONS[meal], price=PRICE[meal], is_veg=True, published=True))
    db.commit()


def run(reset: bool = False, demo: bool = False):
    if reset:
        Base.metadata.drop_all(engine)
        if MODEL_PATH.exists():
            MODEL_PATH.unlink()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            log("Database already seeded (use --reset to start again from zero).")
            return
        log("Creating accounts, slots, rewards and calendar...")
        create_base(db)
        import_history(db)
        seed_menu(db, date.today())
        seed_passes(db, date.today())
        if demo:
            from .demo_data import add_demo_activity
            log(f"Demo activity: {add_demo_activity(db)}")
        P.invalidate()
        if DEMO_ACCOUNTS:
            log(f"Done. Admin: {DEMO_ADMIN[0]} / {DEMO_ADMIN[1]}")
            log(f"Students ({DEMO_STUDENT_PASSWORD}): " + ", ".join(e for e, *_ in DEMO_STUDENTS))
        else:
            log(f"Done. Admin: {DEMO_ADMIN[0]} (password from ECOBYTE_ADMIN_PASSWORD). No demo student accounts.")
    finally:
        db.close()


if __name__ == "__main__":
    run(reset="--reset" in sys.argv, demo="--demo" in sys.argv)
