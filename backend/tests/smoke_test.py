"""End-to-end API smoke test against a running server (standard library only).

    uvicorn app.main:app --port 8000      # terminal 1 (fresh database: python -m app.seed --reset)
    python -m tests.smoke_test            # terminal 2 (ECOBYTE_URL overrides the address)

Writes data (attendance, bookings, a donation...). Re-run `python -m app.seed --reset` afterwards.
"""
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = os.getenv("ECOBYTE_URL", "http://127.0.0.1:8000")


class Resp:
    def __init__(self, status, body):
        self.status_code, self.content = status, body

    def json(self):
        return json.loads(self.content)


def req(method, path, headers=None, body=None, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as x:
            return Resp(x.status, x.read())
    except urllib.error.HTTPError as e:
        return Resp(e.code, e.read())


ok = 0


def check(cond, msg):
    global ok
    if not cond:
        raise AssertionError(msg)
    ok += 1
    print("  ok -", msg)


def login(email, pw, portal):
    r = req("POST", "/api/auth/login", body={"email": email, "password": pw, "portal": portal})
    return {"Authorization": f"Bearer {r.json()['token']}"} if r.status_code == 200 else r


def next_open(d):
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


print("auth & roles")
A = login("admin@ecobyte.app", "Admin@123", "admin"); check(isinstance(A, dict), "admin login")
S1 = login("student@ecobyte.app", "Student@123", "student"); check(isinstance(S1, dict), "student 1 login")
S2 = login("priya@ecobyte.app", "Student@123", "student"); check(isinstance(S2, dict), "student 2 login")
check(login("student@ecobyte.app", "Student@123", "admin").status_code == 403, "student cannot use admin portal")
check(req("GET", "/api/admin/overview").status_code == 401, "admin API needs auth")
for p in ["/api/admin/overview", "/api/admin/forecast", "/api/admin/donations", "/api/admin/costs", "/api/admin/attendance/records"]:
    check(req("GET", p, S1).status_code == 403, f"student blocked from {p}")

print("starts at zero, updates on tick")
target = next_open(date.today() + timedelta(days=2))
o = req("GET", "/api/admin/overview", A, params={"date": str(target)}).json()
check(all(m["confirmed"] == 0 and m["predicted"] == 0 and m["recommended"] == 0 for m in o["meals"]), "all meals start at 0")
check(o["attendance"]["confirmed_students"] == 0 and o["attendance"]["registered"] == 5, "0 of 5 students confirmed")
r = req("POST", "/api/student/attendance", S1, {"items": [{"date": str(target), "meal_type": "lunch", "status": "coming"},
                                                            {"date": str(target), "meal_type": "breakfast", "status": "not_coming"}]}).json()
check(r["saved"] == 2 and r["points_awarded"] >= 5, "student 1 ticked lunch, earned points")
lunch = lambda: next(m for m in req("GET", "/api/admin/overview", A, params={"date": str(target)}).json()["meals"] if m["meal_type"] == "lunch")
l1 = lunch()
check(l1["confirmed"] == 1 and l1["predicted"] == 1 and l1["recommended"] == 2, f"lunch: confirmed 1 -> predicted 1, prepare {l1['recommended']}")
req("POST", "/api/student/attendance", S2, {"items": [{"date": str(target), "meal_type": "lunch", "status": "coming"}]})
check(lunch()["confirmed"] == 2, "second student tick -> confirmed 2")
r = req("POST", "/api/student/attendance", S1, {"items": [{"date": str(target), "meal_type": "lunch", "status": "not_coming"}]}).json()
check(r["points_awarded"] == 0 and lunch()["confirmed"] == 1, "change of mind updates count, no extra points")

print("meal planning")
m = req("POST", "/api/admin/meals", A, {"date": str(target), "meal_type": "dinner", "name": "Paneer Bhurji", "items": "Roti\nVegetable Rice",
                                         "description": "Test", "price": 70, "prep_cost": 3000, "quantity_available": 120}).json()
names = lambda: [x["name"] for x in req("GET", "/api/student/menu", S1, params={"date": str(target)}).json()["meals"]["dinner"]]
check("Paneer Bhurji" not in names(), "unpublished meal hidden from students")
req("PATCH", f"/api/admin/meals/{m['id']}", A, {"published": True})
check("Paneer Bhurji" in names(), "published meal visible to students")
r = req("POST", "/api/admin/preparation", A, {"date": str(target), "meal_type": "lunch", "meals_prepared": 3})
check(r.status_code == 200 and r.json()["predicted"] == 1, "preparation saved with frozen prediction")

print("slots")
slots = req("GET", "/api/admin/slots", A, params={"date": str(target)}).json()["slots"]
sl = next(s for s in slots if s["meal_type"] == "dinner")
req("PATCH", f"/api/admin/slots/{sl['id']}", A, {"capacity": 1})
check(req("POST", "/api/student/bookings", S1, {"slot_id": sl["id"], "date": str(target)}).status_code == 200, "student 1 booked last seat")
r = req("POST", "/api/student/bookings", S2, {"slot_id": sl["id"], "date": str(target)})
check(r.status_code == 409 and "full" in r.json()["detail"], "full slot rejects student 2")
req("PATCH", f"/api/admin/slots/{sl['id']}", A, {"capacity": 40})

print("waste & cost")
r = req("POST", "/api/admin/waste", A, {"date": str(date.today()), "meal_type": "lunch", "food_name": "Dal Rice", "prepared_kg": 40,
                                         "served_kg": 36, "leftover_kg": 4, "plate_waste_kg": 1.2})
check(r.status_code == 200 and r.json()["waste_cost"] == round(5.2 * 125, 2), "waste cost = 5.2 kg x Rs 125 (lunch rate)")
o = req("GET", "/api/admin/overview", A).json()
check(o["waste"]["by_meal"]["lunch"]["kg"] == 5.2, "overview shows today's lunch waste")

print("NGO donation: atomic allocation")
now = datetime.now()
ngos = [req("POST", "/api/admin/ngos", A, {"name": f"Test NGO {i}", "phone": f"98765432{i}0"}).json() for i in range(3)]
d = req("POST", "/api/admin/donations", A, {"food_name": "Vegetable Rice", "category": "Cooked meal", "quantity": 50, "unit": "portions",
        "prepared_at": (now - timedelta(hours=1)).isoformat(timespec="minutes"), "safe_until": (now + timedelta(hours=5)).isoformat(timespec="minutes"),
        "pickup_location": "College Canteen", "pickup_deadline": (now + timedelta(hours=3)).isoformat(timespec="minutes"),
        "food_safety_confirmed": True}).json()
check(d["code"].startswith(f"ECO-DON-{now.year}-") and d["status"] == "available", f"donation {d['code']} created")
bad = req("POST", "/api/admin/donations", A, {"food_name": "Old Rice", "category": "Cooked meal", "quantity": 5, "unit": "portions",
          "prepared_at": (now - timedelta(hours=9)).isoformat(), "safe_until": (now - timedelta(hours=1)).isoformat(),
          "pickup_location": "Canteen", "pickup_deadline": (now - timedelta(hours=2)).isoformat(), "food_safety_confirmed": True})
check(bad.status_code == 400, "expired food cannot be listed")
inv = req("POST", f"/api/admin/donations/{d['id']}/invites", A, {"ngo_ids": [n["id"] for n in ngos], "base_url": BASE}).json()
check(len(inv["links"]) == 3 and inv["links"][0]["whatsapp_url"].startswith("https://wa.me/91"), "3 WhatsApp links generated")
check(inv["donation"]["status"] == "request_sent", "status request_sent")
tokens = [l["link"].rsplit("/", 1)[1] for l in inv["links"]]
check(req("GET", f"/api/public/donations/{tokens[0]}").json()["donation"]["remaining"] == 50, "public link works without login")
results = [None] * 3


def accept(i):
    results[i] = req("POST", f"/api/public/donations/{tokens[i]}/accept", body={
        "quantity": 30, "contact_name": f"Volunteer {i}", "contact_phone": "9123456789"}).status_code


threads = [threading.Thread(target=accept, args=(i,)) for i in range(3)]
[t.start() for t in threads]
[t.join() for t in threads]
check(sorted(results) == [200, 409, 409], f"3 NGOs accept 30 of 50 at once -> exactly one wins {results}")
loser = results.index(409)
r = req("GET", f"/api/public/donations/{tokens[loser]}").json()
check(r["donation"]["remaining"] == 20, "other NGOs now see 20 remaining")
check(req("POST", f"/api/public/donations/{tokens[results.index(200)]}/accept", body={"quantity": 5, "contact_name": "X Y",
          "contact_phone": "9123456789"}).status_code == 409, "a link cannot be used twice")
r = req("POST", f"/api/public/donations/{tokens[loser]}/accept", body={"quantity": 20, "contact_name": "Volunteer", "contact_phone": "9123456789"})
check(r.status_code == 200 and r.json()["donation"]["status"] == "fully_accepted", "remaining 20 accepted -> fully accepted")
other = [i for i in range(3) if i != loser and results[i] != 200][0]
check(req("POST", f"/api/public/donations/{tokens[other]}/accept", body={"quantity": 1, "contact_name": "Late NGO",
          "contact_phone": "9123456789"}).status_code == 409, "no acceptance after full allocation")
det = req("GET", f"/api/admin/donations/{d['id']}", A).json()
check(sum(a["quantity"] for a in det["allocations"]) == 50, "allocations total exactly 50")
for a in det["allocations"]:
    req("POST", f"/api/admin/allocations/{a['id']}/status", A, {"status": "collected"})
check(req("GET", f"/api/admin/donations/{d['id']}", A).json()["status"] == "collected", "all collected -> donation collected")
check(req("GET", "/api/admin/notifications", A).json()["unread"] >= 2, "admin notified of NGO acceptances")

print("history, reports, analytics")
h = req("GET", "/api/student/history", S1).json()
check(h["participation"]["meals_confirmed"] >= 0 and len(h["attendance"]) >= 2, "student history")
for p in ["/api/admin/reports/export", "/api/admin/reports/attendance", "/api/admin/reports/waste", "/api/admin/reports/donations"]:
    r = req("GET", p, A)
    check(r.status_code == 200 and r.content[:2] == b"PK", f"excel {p.rsplit('/', 1)[1]}")
an = req("GET", "/api/admin/analytics", A, params={"start": "2025-01-01"}).json()
check(len(an["series"]) > 10, "analytics over imported history")
f = req("GET", "/api/admin/forecast", A).json()
check(not f["accuracy"]["available"], "no fake accuracy before real records")
print(f"\nAll {ok} checks passed.")
