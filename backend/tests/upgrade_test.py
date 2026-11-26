"""End-to-end test of the operations upgrade (Part 6 checklist), against a running server.

    python -m app.seed --reset && uvicorn app.main:app --port 8000   # fresh database
    python -m tests.upgrade_test
Writes data. Re-run `python -m app.seed --reset` afterwards.
"""
import threading
import uuid
from datetime import date, datetime, timedelta

from tests.client import check, counter, login, req

A = login("admin@ecobyte.app", "Admin@123", "admin")
today = date.today()


def next_open(d):
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


print("ADMIN: student management")
r = req("POST", "/api/admin/students", A, {"name": "Test Student", "email": "test.student@ecobyte.app", "student_code": "STU9001",
                                           "phone": "9876500000", "pass_type": "monthly"}).json()
new_id = r["student"]["id"]
check(r["temporary_password"] and r["student"]["pass"]["remaining_days"] == 30, "added student with a 30-day monthly pass")
lst = req("GET", "/api/admin/students", A, None, {"sort": "remaining_days"}).json()
check(lst["total"] == 6, "student list shows all 6 students")
exp = req("GET", "/api/admin/students", A, None, {"status": "expired"}).json()
check([x["name"] for x in exp["items"]] == ["Rohan Patil"], "filter: expired pass")
soon = req("GET", "/api/admin/students", A, None, {"status": "expiring_soon"}).json()
aarav = next(x for x in soon["items"] if x["student_code"] == "STU2025")
check(aarav["pass"]["remaining_days"] == 5 and aarav["pass"]["used_days"] == 25, "Aarav: 30-day pass, 25 used, 5 remaining, expiring soon")
key = str(uuid.uuid4())
body = {"days": 5, "reason": "student_leave", "note": "Going home for Diwali", "request_key": key}
e1 = req("POST", f"/api/admin/students/{aarav['id']}/extend", A, body).json()
e2 = req("POST", f"/api/admin/students/{aarav['id']}/extend", A, body).json()
check(e1["created"] and e2["duplicate"] and e1["new_expiry"] == e2["new_expiry"], "extend +5 days; repeating the same request does not double-extend")
prof = req("GET", f"/api/admin/students/{aarav['id']}", A).json()
check(prof["pass"]["remaining_days"] == 10 and len(prof["extensions"]) == 1 and prof["extensions"][0]["reason_label"] == "Student leave",
      "profile shows 10 days left and the extension history")
rohan = exp["items"][0]

print("STUDENT: pass & booking rules")
S = login("STU2025", "Student@123", "student")
check(isinstance(S, dict), "student signs in with student ID")
sub = req("GET", "/api/student/subscription", S).json()
check(sub["pass"]["remaining_days"] == 10 and sub["extensions"][0]["added_days"] == 5, "student sees updated validity and extension")
R = login("rohan@ecobyte.app", "Student@123", "student")
d1 = next_open(today + timedelta(days=1))
slots = req("GET", "/api/student/slots", S, None, {"date": str(d1)}).json()["slots"]
r = req("POST", "/api/student/bookings", R, {"slot_id": slots["lunch"][0]["id"], "date": str(d1)})
check(r.status_code == 403 and "does not cover" in r.json()["detail"], "expired pass cannot book")
booked = {}
for m in ("breakfast", "lunch", "dinner"):
    r = req("POST", "/api/student/bookings", S, {"slot_id": slots[m][1]["id"], "date": str(d1)})
    check(r.status_code == 200 and r.json()["state"] == "confirmed", f"booked {m} for {d1}")
    booked[m] = r.json()
r = req("POST", "/api/student/bookings", S, {"slot_id": slots["lunch"][2]["id"], "date": str(d1)})
check(r.status_code == 409, "duplicate lunch booking rejected")
r = req("POST", f"/api/student/bookings/{booked['lunch']['id']}/change", S, {"slot_id": slots["lunch"][3]["id"]})
check(r.status_code == 200 and r.json()["start"] == slots["lunch"][3]["start"], "changed lunch slot before the deadline")
r = req("POST", f"/api/student/bookings/{booked['dinner']['id']}/cancel", S)
check(r.status_code == 200 and r.json()["state"] == "cancelled", "cancelled dinner before the deadline")
ov = req("GET", "/api/admin/overview", A, None, {"date": str(d1)}).json()
lunch = next(m for m in ov["meals"] if m["meal_type"] == "lunch")
check(lunch["bookings"] == 1 and lunch["confirmed"] == 1, "admin sees the booking counted in lunch demand")

print("ADMIN: holidays -> student notifications")
hd = next_open(today + timedelta(days=3))
r = req("POST", "/api/admin/holidays", A, {"name": "Founders Day", "date": str(hd), "holiday_type": "college",
                                           "services": ["lunch", "dinner"], "message": "Campus celebration, canteen closed after breakfast.",
                                           "publish": True}).json()
check(r["published"]["students_notified"] == 6, "holiday published to all 6 students")
notes = req("GET", "/api/student/notifications", S).json()
check(any("Founders Day" in n["title"] for n in notes["items"]) and notes["unread"] >= 1, "student received the holiday notification")
hs = req("GET", "/api/student/slots", S, None, {"date": str(hd)}).json()
r = req("POST", "/api/student/bookings", S, {"slot_id": hs["slots"]["lunch"][0]["id"], "date": str(hd)})
check(r.status_code == 400 and "Founders Day" in r.json()["detail"], "cannot book lunch on the holiday")
r = req("POST", "/api/student/bookings", S, {"slot_id": hs["slots"]["breakfast"][0]["id"], "date": str(hd)})
check(r.status_code == 200, "breakfast on the holiday is still bookable (only lunch & dinner affected)")
r = req("POST", "/api/student/attendance", S, {"items": [{"date": str(hd), "meal_type": "dinner", "status": "coming"}]}).json()
check(r["saved"] == 0 and "unavailable" in r["errors"][0], "cannot confirm dinner on the holiday")

print("ADMIN: menu, attendance, tokens")
m = req("POST", "/api/admin/meals", A, {"date": str(today), "meal_type": "lunch", "name": "Paneer Tikka Thali", "items": "Roti\nRice",
                                        "price": 70, "published": True}).json()
menu = req("GET", "/api/student/dashboard", S).json()["today_meals"]
check(any(i["name"] == "Paneer Tikka Thali" for i in next(x for x in menu if x["meal_type"] == "lunch")["items"]), "menu update appears on student dashboard")
bal0 = req("GET", "/api/student/rewards", S).json()["balance"]
r = req("POST", "/api/admin/attendance/mark", A, {"user_ids": [aarav["id"]], "date": str(today), "meal_type": "breakfast", "present": True})
check(r.status_code == 200, "recorded actual attendance")
bal1 = req("GET", "/api/student/rewards", S).json()["balance"]
check(bal1 == bal0 + 10, "verified attendance earned 10 tokens")
req("POST", "/api/admin/attendance/mark", A, {"user_ids": [aarav["id"]], "date": str(today), "meal_type": "breakfast", "present": True})
check(req("GET", "/api/student/rewards", S).json()["balance"] == bal1, "marking twice never pays twice")
cal = req("GET", "/api/student/attendance/calendar", S, None, {"start": str(today - timedelta(days=7)), "end": str(today + timedelta(days=7))}).json()
st = {d["date"]: d["status"] for d in cal["days"]}
check(st[str(today)] == "present" and st[str(d1)] == "booked", "calendar: today present, upcoming booked day blue")
check(all(st[str(today - timedelta(days=i))] in ("absent", "closed") for i in range(1, 7)), "past days without records are absent/closed (never fake present)")

print("REWARDS: coupon redemption")
r = req("POST", "/api/student/rewards/redeem", S, {"reward_id": 1})
check(r.status_code == 400, "not enough tokens for tea (200)")
req("POST", "/api/admin/points/adjust", A, {"user_id": aarav["id"], "points": 240, "reason": "Food-waste awareness drive volunteer"})
bal = req("GET", "/api/student/rewards", S).json()["balance"]
res = [None, None]


def red(i):
    res[i] = req("POST", "/api/student/rewards/redeem", S, {"reward_id": 1}).status_code


ts = [threading.Thread(target=red, args=(i,)) for i in range(2)]
[t.start() for t in ts]
[t.join() for t in ts]
after = req("GET", "/api/student/rewards", S).json()
check(sorted(res) == [200, 400] and after["balance"] == bal - 200 and after["balance"] >= 0,
      f"two simultaneous tea redemptions with {bal} tokens: exactly one succeeds, balance {after['balance']}")
coupon = next(c for c in after["redemptions"] if c["status"] == "active")["code"]
look = req("POST", "/api/admin/coupons/lookup", A, {"code": coupon.lower()}).json()
check(look["status"] == "active" and look["reward"] == "Tea", "admin looks up the coupon")
check(req("POST", "/api/admin/coupons/redeem", A, {"code": coupon}).json()["status"] == "redeemed", "admin redeems the coupon")
r = req("POST", "/api/admin/coupons/redeem", A, {"code": coupon})
check(r.status_code == 409, "the same coupon cannot be redeemed twice")

print("STORE: order flow")
prods = req("GET", "/api/student/store/products", S).json()
tea = next(p for p in prods if p["name"] == "Tea")
samosa = next(p for p in prods if p["name"] == "Samosa")
o = req("POST", "/api/student/store/orders", S, {"items": [{"product_id": tea["id"], "quantity": 2}, {"product_id": samosa["id"], "quantity": 1}],
                                               "note": "Less sugar"}).json()
check(o["status"] == "placed" and o["total"] == 2 * tea["price"] + samosa["price"], f"order {o['code']} placed, total ₹{o['total']} computed on the server")
for stt in ("accepted", "preparing", "ready", "completed"):
    r = req("POST", f"/api/admin/orders/{o['id']}/status", A, {"status": stt})
    check(r.status_code == 200 and r.json()["status"] == stt, f"admin moves order to {stt}")
check(req("POST", f"/api/student/store/orders/{o['id']}/cancel", S).status_code == 400, "completed order cannot be cancelled")
np = req("POST", "/api/admin/products", A, {"name": "Masala Dosa", "category": "meal", "price": 45, "description": "Crispy dosa"}).json()
req("PUT", f"/api/admin/products/{np['id']}", A, {"name": "Masala Dosa", "category": "meal", "price": 45, "available": False})
r = req("POST", "/api/student/store/orders", S, {"items": [{"product_id": np["id"], "quantity": 1}]})
check(r.status_code == 409, "unavailable product cannot be ordered")

print("NGO: quick donate & assign")
now = datetime.now()
ngo = req("POST", "/api/admin/ngos", A, {"name": "Annapurna Trust", "phone": "9822000000", "contact_person": "Ravi"}).json()
d = req("POST", "/api/admin/donations", A, {"food_name": "Dal Khichdi", "category": "Cooked meal", "quantity": 40, "unit": "portions",
        "prepared_at": (now - timedelta(minutes=30)).isoformat(timespec="minutes"), "safe_until": (now + timedelta(hours=4)).isoformat(timespec="minutes"),
        "pickup_location": "College Canteen", "pickup_deadline": (now + timedelta(hours=2)).isoformat(timespec="minutes"), "food_safety_confirmed": True}).json()
r = req("POST", f"/api/admin/donations/{d['id']}/assign", A, {"ngo_id": ngo["id"], "quantity": 50})
check(r.status_code == 409, "cannot assign more than available")
r = req("POST", f"/api/admin/donations/{d['id']}/assign", A, {"ngo_id": ngo["id"], "quantity": 40}).json()
check(r["simple_status"] == "Assigned" and r["remaining"] == 0, "assigned all 40 portions to the NGO")
for a in r["allocations"]:
    req("POST", f"/api/admin/allocations/{a['id']}/status", A, {"status": "collected"})
r = req("POST", f"/api/admin/donations/{d['id']}/complete", A).json()
check(r["status"] == "completed", "donation collected and completed")

print("ADMIN: suspend & overview")
K = login("kabir@ecobyte.app", "Student@123", "student")
kab = next(x for x in req("GET", "/api/admin/students", A, None, {"q": "Kabir"}).json()["items"])
req("POST", f"/api/admin/students/{kab['id']}/suspend", A, {"suspended": True, "reason": "Pending dues"})
r = req("POST", "/api/student/bookings", K, {"slot_id": slots["lunch"][0]["id"], "date": str(d1)})
check(r.status_code == 403 and "suspended" in r.json()["detail"], "suspended student cannot book")
req("POST", f"/api/admin/students/{kab['id']}/suspend", A, {"suspended": False})
ops = req("GET", "/api/admin/overview", A).json()["operations"]
check(ops["passes"]["expired"] == 1 and ops["passes"]["expiring_soon"] >= 0 and ops["holidays"], "overview shows pass, holiday and order summaries")
r = req("POST", "/api/student/renewal-request", R, {"pass_type": "monthly"})
check(r.status_code == 200, "expired student requests renewal")
rq = req("GET", "/api/admin/renewals", A).json()
r = req("POST", f"/api/admin/renewals/{rq[0]['id']}", A, {"action": "approve"}).json()
check(r["status"] == "approved" and req("GET", "/api/student/subscription", R).json()["pass"]["status"] == "active",
      "admin approves renewal; Rohan's pass is active again")
check(req("GET", f"/api/admin/students/{rohan['id']}", S).status_code == 403, "students cannot open admin student records")

print(f"\nAll {counter['ok']} upgrade checks passed.")
