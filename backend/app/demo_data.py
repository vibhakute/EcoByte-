"""Demo activity: three weeks of realistic canteen usage so every screen has something to show.

    python -m app.seed --reset --demo     # fresh database + demo activity (what the demo uses)
    python -m app.seed --reset            # fresh database, every live number starts at zero

What is added (all relative to today, deterministic, flagged with source="demo_seed" where the
table has a source column):
- 25 more students (STU2030-STU2054) with passes: active, six-month, expiring soon, expired, suspended.
- 21 days of meal plans, slot bookings and recorded attendance; tokens earned from them.
- Daily meal records (confirmed / predicted / prepared / served) and food-waste entries.
- Today's plans and bookings, tomorrow's plans, coupons, store orders, renewal requests,
  a pass extension, NGO contacts, donations (completed, assigned, available) and one
  upcoming published holiday (dinner only) with the student notifications it produces.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, time, timedelta

from .auth import hash_password
from .config import MEAL_TYPES
from .models import (Attendance, CalendarEvent, Donation, DonationAllocation, MealAttendance, MealRecord, MealSlot,
                     MessSubscription, NgoContact, Notification, Product, Redemption, RenewalRequest, Reward,
                     RewardTransaction, SlotBooking, StoreOrder, StoreOrderItem, StudentNotification, User, WasteRecord)
from .services import mess
from .services.donations import refresh_status
from .services.forecast import cost_for_meal, get_settings
from .services.student_ops import new_code
from .services.synthetic import main_dish_for

DAYS_BACK = 21
PASSWORD = "Student@123"
SERVICE_END = {"breakfast": time(9, 0), "lunch": time(14, 0), "dinner": time(21, 0)}
PORTION_KG = {"breakfast": 0.22, "lunch": 0.45, "dinner": 0.40}
P_COMING = {"breakfast": 0.62, "lunch": 0.9, "dinner": 0.78}
DEPTS = ["Computer Engineering", "AI & Data Science", "Information Technology", "Mechanical Engineering",
         "Electronics & Telecom", "Civil Engineering", "Electrical Engineering"]
NAMES = ["Ananya Joshi", "Vihaan Mehta", "Ishita Rao", "Arjun Nair", "Diya Kapoor", "Reyansh Gupta", "Meera Pillai",
         "Aditya Kulkarni", "Saanvi Bhosale", "Kunal Jadhav", "Riya Sharma", "Omkar Pawar", "Tanvi Gokhale",
         "Yash Thakur", "Nidhi Verma", "Harsh Agarwal", "Pooja Shinde", "Siddharth Menon", "Aditi Chavan",
         "Rahul Deshpande", "Kavya Reddy", "Nikhil More", "Shruti Naik", "Varun Bansal", "Anjali Kale"]


class Demo:
    def __init__(self, db, today: date | None = None, now: datetime | None = None):
        self.db = db
        self.now = now or datetime.now()
        self.today = today or self.now.date()
        self.rng = random.Random(2025)
        self.s = get_settings(db)
        self.admin = db.query(User).filter_by(role="admin").first()
        self.refs: set[str] = set()
        self.slots = {m: db.query(MealSlot).filter_by(meal_type=m, active=True).order_by(MealSlot.start_time).all() for m in MEAL_TYPES}

    # --- helpers ---------------------------------------------------------------------------------
    def at(self, d: date, h: int, m: int = 0) -> datetime:
        return datetime.combine(d, time(h, m))

    def tok(self, u: User, pts: int, kind: str, desc: str, ref: str, when: datetime):
        if ref in self.refs:
            return
        self.refs.add(ref)
        self.db.add(RewardTransaction(user_id=u.id, points=pts, kind=kind, description=desc[:200], ref_key=ref, created_at=when))
        u.token_balance = (u.token_balance or 0) + pts

    def note(self, u: User, kind: str, title: str, body: str, link: str, when: datetime, read: bool = True):
        self.db.add(StudentNotification(user_id=u.id, kind=kind, title=title, body=body, link=link, read=read, created_at=when))

    def admin_note(self, kind: str, title: str, body: str, link: str, when: datetime, read: bool = False):
        self.db.add(Notification(kind=kind, title=title, body=body, link=link, read=read, created_at=when))

    def covers(self, u: User, d: date) -> bool:
        if u.suspended and d >= self.today - timedelta(days=3):
            return False
        return any(s.start_date <= d <= s.expiry_date for s in self.passes.get(u.id, []))

    # --- students & passes -------------------------------------------------------------------------
    def students(self):
        db, t = self.db, self.today
        pw = hash_password(PASSWORD)
        for i, name in enumerate(NAMES):
            first = name.split()[0].lower()
            u = User(role="student", email=f"{first}{i + 30}@ecobyte.app", name=name, password_hash=pw,
                     student_code=f"STU20{30 + i}", department=DEPTS[i % len(DEPTS)], year_of_study=1 + i % 4,
                     phone=f"98{self.rng.randint(10000000, 99999999)}", hostel_resident=i % 3 != 0, is_demo=True)
            db.add(u)
            db.flush()
            if i % 5 == 0:
                plan = [("six_month", -self.rng.randint(30, 150))]
            elif i == 3:
                plan = [("monthly", -57), ("monthly", -27)]  # 4 days left
            elif i == 7:
                plan = [("monthly", -59), ("monthly", -29)]  # 2 days left
            elif i == 11:
                plan = [("monthly", -40)]  # expired 11 days ago
            else:
                start = -self.rng.randint(1, 27)
                plan = [("monthly", start - 30), ("monthly", start)]
            for ptype, off in plan:
                start = t + timedelta(days=off)
                days = mess.PASS_DAYS[ptype]
                db.add(MessSubscription(user_id=u.id, pass_type=ptype, purchase_date=start - timedelta(days=1), start_date=start,
                                        base_days=days, expiry_date=start + timedelta(days=days - 1),
                                        price=self.s.price_monthly if ptype == "monthly" else self.s.price_six_month,
                                        created_at=self.at(start - timedelta(days=1), 11, 15), created_by=self.admin.id))
            if i == 15:
                u.suspended = True
        db.flush()
        self.users = db.query(User).filter_by(role="student").order_by(User.id).all()
        self.by_email = {u.email: u for u in self.users}
        self.passes = {}
        for sub in db.query(MessSubscription).filter(MessSubscription.cancelled.is_(False)):
            self.passes.setdefault(sub.user_id, []).append(sub)
        self.habit = {u.id: self.rng.uniform(0.72, 0.98) for u in self.users}
        for u in self.users:  # pass activation notices
            for sub in self.passes.get(u.id, []):
                self.note(u, "pass", f"{mess.PASS_LABEL[sub.pass_type]} mess pass activated",
                          f"Valid {sub.start_date:%d %b %Y} – {sub.expiry_date:%d %b %Y}.", "/student", sub.created_at)

    # --- three weeks of meals ----------------------------------------------------------------------
    def history(self):
        db, rng, t = self.db, self.rng, self.today
        start = t - timedelta(days=DAYS_BACK)
        self.cl = mess.closures(db, start, t + timedelta(days=14))
        ratio_hist = {m: [] for m in MEAL_TYPES}
        planned_days: dict[int, set[date]] = {}
        for n in range(DAYS_BACK, 0, -1):
            d = t - timedelta(days=n)
            planners = {}
            for u in self.users:
                if self.covers(u, d) and rng.random() < 0.82:
                    planners[u.id] = self.at(d - timedelta(days=1), rng.randint(17, 20), rng.randint(0, 59))
            for meal in MEAL_TYPES:
                if mess.meal_closed(self.cl, d, meal):
                    continue
                coming, attended, booked = set(), set(), set()
                for u in self.users:
                    if not self.covers(u, d):
                        continue
                    h = self.habit[u.id]
                    if u.id in planners:
                        status = "coming" if rng.random() < P_COMING[meal] * (0.6 + 0.4 * h) else "not_coming"
                        db.add(Attendance(user_id=u.id, date=d, meal_type=meal, status=status,
                                          confirmed_at=planners[u.id], updated_at=planners[u.id]))
                        planned_days.setdefault(u.id, set()).add(d)
                        p = 0.94 if status == "coming" else 0.03
                        if status == "coming":
                            coming.add(u.id)
                    else:
                        p = 0.35 * h
                    if rng.random() >= p:
                        continue
                    attended.add(u.id)
                    slot = rng.choice(self.slots[meal])
                    seen = self.at(d, slot.start_time.hour, slot.start_time.minute) + timedelta(minutes=rng.randint(0, 12))
                    src = "counter"
                    if u.id in coming and rng.random() < 0.6:
                        booked.add(u.id)
                        src = "booking"
                        db.add(SlotBooking(user_id=u.id, slot_id=slot.id, date=d, meal_type=meal, status="served",
                                           code=new_code("EB-"), created_at=planners[u.id] + timedelta(minutes=3)))
                    db.add(MealAttendance(user_id=u.id, date=d, meal_type=meal, recorded_at=seen, recorded_by=self.admin.id, source=src))
                    self.tok(u, self.s.tokens_per_attended_meal, "earn", f"Attended {meal} on {d:%a %d %b}",
                             f"attend:{u.id}:{d.isoformat()}:{meal}", seen)
                # what the admin recorded at the end of the service
                confirmed = len(coming | booked)
                hist = ratio_hist[meal]
                k = sum(a for a, _ in hist) / sum(c for _, c in hist) if len(hist) >= 5 else 1.0
                predicted = round(confirmed * k)
                prepared = max(predicted + math.ceil(predicted * self.s.buffer_pct / 100), len(attended))
                served = len(attended)
                hist.append((served, confirmed))
                dish = main_dish_for(d, meal)
                db.add(MealRecord(date=d, meal_type=meal, main_dish=dish, advance_confirmations=confirmed, slot_bookings=len(booked),
                                  actual_attendance=served, predicted_demand=predicted, meals_prepared=prepared,
                                  meals_served=served, source="demo_seed", is_synthetic=False))
                pk = PORTION_KG[meal]
                prep_kg = round(prepared * pk * rng.uniform(1.02, 1.1), 1)
                served_kg = round(served * pk, 1)
                leftover = round(max(0.2, prep_kg - served_kg), 2)
                plate = round(served_kg * rng.uniform(0.04, 0.09), 2)
                total = round(leftover + plate, 2)
                cpk = cost_for_meal(self.s, meal)
                db.add(WasteRecord(date=d, meal_type=meal, food_name=dish, recorded_at=self.at(d, SERVICE_END[meal].hour, 20),
                                   prepared_kg=prep_kg, served_kg=served_kg, leftover_kg=leftover, plate_waste_kg=plate,
                                   total_waste_kg=total, cost_per_kg=cpk, waste_cost=round(total * cpk, 2),
                                   source="demo_seed", is_synthetic=False))
            for u in self.users:
                if u.id in planners:
                    self.tok(u, self.s.points_per_confirmation, "earn", f"Planned meals in advance for {d:%a %d %b}",
                             f"confirm:{u.id}:{d.isoformat()}", planners[u.id])
        # full-week planning bonus for complete past weeks
        for u in self.users:
            days = planned_days.get(u.id, set())
            mondays = {x - timedelta(days=x.weekday()) for x in days}
            for mon in sorted(mondays):
                week = [mon + timedelta(days=i) for i in range(7)]
                open_days = [x for x in week if x < t and not mess.day_closed(self.cl, x) and self.covers(u, x)]
                if week[-1] < t and open_days and all(x in days for x in open_days) and len(open_days) >= 4:
                    iso = mon.isocalendar()
                    self.tok(u, self.s.weekly_streak_bonus, "bonus", f"Full-week planning bonus (week of {mon:%d %b})",
                             f"streak:{u.id}:{iso.year}-{iso.week}", self.at(week[-1], 21))
        db.flush()

    # --- today and the next few days ----------------------------------------------------------------
    def live(self):
        db, rng, t, now = self.db, self.rng, self.today, self.now
        aarav = self.by_email["student@ecobyte.app"]
        for n in range(0, 4):
            d = t + timedelta(days=n)
            share = [0.85, 0.7, 0.45, 0.3][n]
            for u in self.users:
                if not self.covers(u, d) or (u is not aarav and rng.random() > share):
                    continue
                when = self.at(t - timedelta(days=1), rng.randint(17, 20), rng.randint(0, 59)) if n == 0 \
                    else now - timedelta(minutes=rng.randint(20, 600))
                if when > now:
                    when = now - timedelta(minutes=5)
                for meal in MEAL_TYPES:
                    if mess.meal_closed(self.cl, d, meal):
                        continue
                    coming = u is aarav or rng.random() < P_COMING[meal]
                    db.add(Attendance(user_id=u.id, date=d, meal_type=meal, status="coming" if coming else "not_coming",
                                      confirmed_at=when, updated_at=when))
                    if not coming or n > 1:
                        continue
                    ended = n == 0 and now.time() >= SERVICE_END[meal]
                    if (u is aarav and meal != "breakfast") or rng.random() < 0.5:
                        slots = self.slots[meal]
                        slot = slots[(u.id + n) % len(slots)]
                        db.add(SlotBooking(user_id=u.id, slot_id=slot.id, date=d, meal_type=meal,
                                           status="served" if ended else "booked", code=new_code("EB-"),
                                           created_at=when + timedelta(minutes=2)))
                    if ended and rng.random() < 0.93:
                        seen = self.at(d, SERVICE_END[meal].hour - 1, rng.randint(0, 50))
                        db.add(MealAttendance(user_id=u.id, date=d, meal_type=meal, recorded_at=seen, recorded_by=self.admin.id))
                        self.tok(u, self.s.tokens_per_attended_meal, "earn", f"Attended {meal} on {d:%a %d %b}",
                                 f"attend:{u.id}:{d.isoformat()}:{meal}", seen)
                self.tok(u, self.s.points_per_confirmation, "earn", f"Planned meals in advance for {d:%a %d %b}",
                         f"confirm:{u.id}:{d.isoformat()}", when)
        db.flush()

    # --- coupons -------------------------------------------------------------------------------------
    def coupons(self):
        db, rng, now = self.db, self.rng, self.now
        rewards = {r.name: r for r in db.query(Reward)}
        plan = [("student@ecobyte.app", "Tea", "active"), ("priya@ecobyte.app", "Coffee", "redeemed"),
                ("priya@ecobyte.app", "Tea", "active"), ("sneha@ecobyte.app", "Tea", "redeemed")]
        rich = sorted((u for u in self.users if u.email not in {p[0] for p in plan}), key=lambda u: -u.token_balance)
        plan += [(u.email, name, st) for u, (name, st) in zip(rich, [("Samosa", "redeemed"), ("Tea", "active"), ("Coffee", "active"),
                                                                     ("Tea", "redeemed"), ("Tea", "cancelled"), ("Sandwich", "active")])]
        for email, name, status in plan:
            u, r = self.by_email[email], rewards[name]
            if u.token_balance < r.points_cost:
                continue
            made = now - timedelta(days=rng.randint(1, 5), hours=rng.randint(0, 8))
            code = new_code("RW-")
            red = Redemption(user_id=u.id, reward_id=r.id, points=r.points_cost, code=code, status=status, created_at=made,
                             expires_at=made + timedelta(days=self.s.coupon_validity_days))
            db.add(red)
            r.stock -= 1
            self.tok(u, -r.points_cost, "redeem", f"Coupon {code}: {r.name}", f"redeem:{code}", made)
            if status == "redeemed":
                red.redeemed_at, red.redeemed_by = made + timedelta(hours=rng.randint(2, 30)), self.admin.id
                self.note(u, "reward", f"Coupon {code} used", f"{r.name} served at the counter.", "/student/rewards", red.redeemed_at)
            elif status == "cancelled":
                red.cancelled_at = made + timedelta(hours=3)
                r.stock += 1
                self.tok(u, r.points_cost, "refund", f"Refund for cancelled coupon {code}", f"refund:{code}", red.cancelled_at)
            else:
                self.note(u, "reward", f"{r.name} coupon ready: {code}", f"Show the code at the counter. Valid {self.s.coupon_validity_days} days.",
                          "/student/rewards", made, read=False)
        db.flush()

    # --- canteen store -------------------------------------------------------------------------------
    def store(self):
        db, rng, now, t = self.db, self.rng, self.now, self.today
        products = db.query(Product).filter_by(available=True).all()
        active = [u for u in self.users if not u.suspended]
        plan = [(-6, "completed"), (-6, "completed"), (-5, "completed"), (-4, "completed"), (-4, "cancelled"), (-3, "completed"),
                (-2, "completed"), (-2, "completed"), (-1, "completed"), (-1, "completed"), (0, "completed"),
                (0, "ready"), (0, "preparing"), (0, "accepted"), (0, "placed"), (0, "placed")]
        for i, (off, status) in enumerate(plan):
            u = self.by_email["student@ecobyte.app"] if status == "ready" else rng.choice(active)
            if off == 0:
                made = now - timedelta(minutes=10 + 35 * (len(plan) - i))
            else:
                made = self.at(t + timedelta(days=off), rng.choice([10, 11, 13, 16, 17]), rng.randint(0, 59))
            o = StoreOrder(code=new_code("OR-"), user_id=u.id, status=status, total=0, created_at=made,
                           updated_at=made + timedelta(minutes=rng.randint(5, 25)) if status != "placed" else made)
            total = 0.0
            for p in rng.sample(products, rng.randint(1, 3)):
                q = rng.randint(1, 2)
                total += p.price * q
                o.items.append(StoreOrderItem(product_id=p.id, name=p.name, unit_price=p.price, quantity=q, line_total=p.price * q))
            o.total = round(total, 2)
            db.add(o)
            db.flush()
            if off == 0:
                self.admin_note("order", f"New store order {o.code}",
                                f"{u.name}: " + ", ".join(f"{x.quantity}× {x.name}" for x in o.items) + f" · ₹{o.total:g}",
                                "/admin/store", made, read=status != "placed")
            if status in ("ready", "completed"):
                msg = "ready for pickup at the counter" if status == "ready" else "completed. Enjoy!"
                self.note(u, "order", f"Order {o.code} is {msg}", f"Total ₹{o.total:g}", "/student/store", o.updated_at,
                          read=status == "completed")

    # --- renewals, extensions ------------------------------------------------------------------------
    def passes_admin(self):
        db, now = self.db, self.now
        rohan = self.by_email["rohan@ecobyte.app"]
        soon = [u for u in self.users if u.student_code in ("STU2033", "STU2037")]
        for u, ptype, note, hrs in [(rohan, "monthly", "Will pay at the office tomorrow morning.", 3),
                                    (soon[0], "six_month", "Switching to the six-month pass.", 26)]:
            made = now - timedelta(hours=hrs)
            db.add(RenewalRequest(user_id=u.id, pass_type=ptype, note=note, created_at=made))
            self.admin_note("pass", f"Pass renewal request: {u.name}", f"{mess.PASS_LABEL[ptype]} pass · {u.student_code}",
                            "/admin/students", made)
        for u in soon:
            sub = max(self.passes[u.id], key=lambda s: s.expiry_date)
            left = (sub.expiry_date - self.today).days + 1
            self.note(u, "pass", f"Your mess pass expires in {left} days", "Renew at the canteen office to keep booking meals.",
                      "/student", now - timedelta(hours=8), read=False)
        priya = self.by_email["priya@ecobyte.app"]
        lf = self.today - timedelta(days=18)
        ext, _ = mess.extend_pass(db, priya, 5, "medical_leave", "Viral fever – medical certificate submitted.", self.admin.id,
                                  "demo:ext:priya", lf, lf + timedelta(days=4))
        ext.created_at = self.at(self.today - timedelta(days=12), 12, 10)
        other = next(u for u in self.users if u.student_code == "STU2034")
        ext2, _ = mess.extend_pass(db, other, 2, "student_leave", "Home visit for a family function.", self.admin.id, "demo:ext:stu2034")
        ext2.created_at = self.at(self.today - timedelta(days=4), 16, 40)
        db.flush()

    # --- NGO donations -------------------------------------------------------------------------------
    def donations(self):
        db, now, t = self.db, self.now, self.today
        ngos = [NgoContact(name="Green Plate Foundation", contact_person="Mr. Sameer Joshi", phone="919000000101",
                           email="pickup@greenplate.example", address="Kothrud, Pune"),
                NgoContact(name="Hope Kitchen Trust", contact_person="Ms. Leena Fernandes", phone="919000000102",
                           address="Shivajinagar, Pune"),
                NgoContact(name="Little Hands Children's Home", contact_person="Mrs. Asha Patil", phone="919000000103",
                           address="Hadapsar, Pune")]
        db.add_all(ngos)
        db.flush()
        loc = self.s.pickup_location
        past = [(-6, "Veg Pulao", "Rice & grains", 28, "portions", 0, "completed"),
                (-4, "Dal Tadka & Rice", "Curry / dal", 9.5, "kg", 1, "completed"),
                (-2, "Chapati & Mix Veg", "Cooked meal", 35, "portions", 2, "completed"),
                (-1, "Rajma Chawal", "Cooked meal", 22, "portions", 0, "collected")]
        n = 0
        for off, food, cat, qty, unit, ngo_i, status in past:
            d = t + timedelta(days=off)
            n += 1
            don = Donation(code=f"ECO-DON-{d.year}-{n:03d}", food_name=food, category=cat, is_veg=True, quantity=qty, unit=unit,
                           allocated_qty=qty, collected_qty=qty, prepared_at=self.at(d, 19, 45), safe_until=self.at(d, 23, 59),
                           pickup_location=loc, pickup_deadline=self.at(d, 22, 30), instructions="Bring your own containers.",
                           meal_type="dinner", status=status, created_at=self.at(d, 21, 10))
            ngo = ngos[ngo_i]
            don.allocations.append(DonationAllocation(ngo_id=ngo.id, organisation=ngo.name, contact_name=ngo.contact_person,
                                                      contact_phone=ngo.phone, quantity=qty, pickup_eta="22:00", status="collected",
                                                      collected_qty=qty, created_at=self.at(d, 21, 25), collected_at=self.at(d, 22, 5)))
            db.add(don)
            self.admin_note("donation", f"{ngo.name} accepted {qty:g} {unit}", f"{don.code} · {food}", "/admin/donations",
                            self.at(d, 21, 25), read=True)
        # today: one assigned, one still available
        for food, cat, qty, unit, ngo_i in [("Paneer Butter Masala & Rice", "Cooked meal", 18, "portions", 1),
                                            ("Veg Biryani", "Rice & grains", 6.5, "kg", None)]:
            n += 1
            made = now - timedelta(minutes=40 if ngo_i is None else 95)
            don = Donation(code=f"ECO-DON-{t.year}-{n:03d}", food_name=food, category=cat, is_veg=True, quantity=qty, unit=unit,
                           prepared_at=made - timedelta(minutes=30), safe_until=now + timedelta(hours=6), pickup_location=loc,
                           pickup_deadline=now + timedelta(hours=4), instructions="Packed in steel containers at the back gate.",
                           meal_type="lunch", status="available", created_at=made)
            db.add(don)
            db.flush()
            if ngo_i is not None:
                ngo = ngos[ngo_i]
                don.allocated_qty = qty
                don.allocations.append(DonationAllocation(ngo_id=ngo.id, organisation=ngo.name, contact_name=ngo.contact_person,
                                                          contact_phone=ngo.phone, quantity=qty, pickup_eta="Within 1 hour",
                                                          status="accepted", created_at=made + timedelta(minutes=20)))
                db.flush()
                refresh_status(db, don, now)
                self.admin_note("donation", f"Assigned to {ngo.name}", f"{don.code} · {qty:g} {unit} of {food}", "/admin/donations",
                                made + timedelta(minutes=20))

    # --- an upcoming holiday ---------------------------------------------------------------------------
    def holiday(self):
        db = self.db
        d = self.today + timedelta(days=9)
        taken = {e.date for e in db.query(CalendarEvent).filter(CalendarEvent.date >= d, CalendarEvent.date <= d + timedelta(days=14))}
        while d.weekday() == 6 or d in taken:
            d += timedelta(days=1)
        ev = CalendarEvent(date=d, kind="holiday", name="Annual Sports Day", holiday_type="college",
                           description="Closing ceremony at the main ground runs late.", services="dinner",
                           message="Dinner will not be served on Sports Day. Breakfast and lunch run as usual.",
                           published=False, created_at=self.now - timedelta(days=1))
        db.add(ev)
        db.flush()
        mess.publish_holiday(db, ev, self.admin.id)

    def run(self):
        self.students()
        self.history()
        self.live()
        self.coupons()
        self.store()
        self.passes_admin()
        self.donations()
        self.holiday()
        self.db.commit()
        return {
            "students": len(self.users),
            "attendance": self.db.query(MealAttendance).count(),
            "bookings": self.db.query(SlotBooking).count(),
            "meal_records": self.db.query(MealRecord).filter_by(source="demo_seed").count(),
            "waste_records": self.db.query(WasteRecord).filter_by(source="demo_seed").count(),
            "orders": self.db.query(StoreOrder).count(),
            "coupons": self.db.query(Redemption).count(),
            "donations": self.db.query(Donation).count(),
        }


def add_demo_activity(db) -> dict:
    if db.query(User).filter(User.student_code == "STU2030").first():
        return {"skipped": "demo activity already present"}
    return Demo(db).run()


if __name__ == "__main__":
    from .database import SessionLocal
    s = SessionLocal()
    try:
        print(add_demo_activity(s))
    finally:
        s.close()
