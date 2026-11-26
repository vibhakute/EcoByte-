# EcoByte

Smart canteen management, food-waste monitoring, demand prediction and NGO food donation for college canteens.

> "Prepare the right quantity of fresh food, at the right time, for the right number of students, and donate safe surplus food to people in need instead of wasting it."

The system is one connected flow:

> Student attendance → meal demand prediction → meal planning → food preparation → consumption tracking → waste monitoring → cost and savings analytics → NGO food donation

There are only **two logins**, Student and Canteen Admin. NGOs have no account or dashboard: they get a WhatsApp/SMS message with a secure link and accept or decline on a single page.

## Quick start

Requirements: Python 3.11+ and Node 18+.

```powershell
./start.ps1        # Windows
./start.sh         # macOS / Linux / Git Bash
```

Open http://localhost:8000.

| Portal  | URL            | Login |
|---------|----------------|-------|
| Admin   | `/admin/login` | `admin@ecobyte.app` / `Admin@123` |
| Student | `/login`       | `student@ecobyte.app`, `priya@ecobyte.app`, `rohan@ecobyte.app`, `sneha@ecobyte.app`, `kabir@ecobyte.app` — all `Student@123` |

New students can also self-register at `/register`. Change the demo passwords before real use.

### Everything starts at zero

`python -m app.seed --reset` creates the database below with every live number at zero. `python -m app.seed --reset --demo` also adds 25 more students (STU2030–STU2054, password `Student@123`) and three weeks of demo activity: attendance, bookings, tokens, coupons, store orders, waste entries, renewals and NGO donations (see `backend/app/demo_data.py`).

**Created by the seed:**
- the admin account and the 5 demo students
- the meal slots
- the reward catalogue and the college calendar
- a published sample menu for the next 7 days
- the 2025 historical dataset

**Not created:** no attendance, bookings, points, preparation, waste or donations. Every live number is 0 until students and the admin use the app. When a student ticks a meal, the admin's numbers update straight away.

> The 2025 history (`backend/data/EcoByte_2025_Synthetic_Canteen_Data.xlsx`) is **synthetic demonstration data**. It feeds Analytics and the "historical average" reference only. Replace it with real records via **Admin → Reports → Import**.

### Development mode

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev        # http://localhost:5173, proxies /api to :8000
```

## How meal demand is calculated

This is the default **Confirmations** mode. For each date and meal:

| Value | Formula |
|---|---|
| Confirmed **C** | Students who ticked "coming" (live) |
| Turnout **k** | Σ actual attendance ÷ Σ confirmations over the last 60 days of **real** recorded services. Needs at least 5 services; until then **k = 1.0**. Clipped to 0.5–2.0. |
| Predicted demand | round(C × k) — **0 until students confirm** |
| Buffer | ceil(predicted × 5%), configurable |
| Recommended | predicted + buffer |

Example: 4 students confirm lunch → predicted 4, buffer 1, prepare 5.

**How it learns.** The prediction is frozen when the admin clicks **Update preparation**. After the meal, the admin records actual attendance and meals served. That comparison learns the real turnout (walk-ins vs no-shows), so the forecast improves automatically.

Accuracy is shown only once at least 5 real services exist; no accuracy figure is ever invented.

**Historical average** is shown beside every meal as a reference: same weekday, same week last year, from the imported data.

**Hybrid mode** (Settings) blends live confirmations with a history model. The model multiplies the same-weekday level by trend, menu and calendar factors.
- It has a documented walk-forward backtest.
- An optional Random Forest can be trained and compared on held-out data (Analytics).
- On the synthetic data the simple model is more accurate than the Random Forest, and the app says so.

## Features

**Admin (12 sections)**

- **Overview:** today's date filter, and breakfast / lunch / dinner preparation columns. Each column shows expected, confirmed, historical average, predicted, buffer, recommended, prepared, served and remaining. Below them:
  - an attendance summary
  - computed quick insights
  - quick actions
  - waste today and active donations
- **Meal Planning:**
  - Add, edit and delete meals; schedule future dates; copy a day.
  - Each meal has items, a description, price, quantity, estimated cost and an optional image.
  - Publish and unpublish; published meals appear in the student menu instantly.
  - Predicted demand is shown beside each meal type, plus a 7-day forecast table.
- **Analytics:** 10 charts with presets for 7 days, 30 days, 3 months, 6 months, 1 year and 2025 history:
  - attendance trend and weekly comparison
  - meal comparison
  - predicted vs actual
  - prepared vs served
  - waste
  - weekday pattern
  - cost and savings trends
  - slot utilisation
  - plus a data table and the model card
- **Waste Monitoring:**
  - Per-food entries after each meal: prepared, served, leftover and plate waste in kg, with date and time.
  - Today and per-meal totals, week, month and waste %.
  - Highest-waste meals and days.
- **Waste Cost Tracker:** waste kg × cost per kg, with editable ingredient rates per meal. Daily, weekly, monthly and annual totals, plus the highest-cost foods and days.
- **Savings Tracker:**
  - Baseline vs actual, normalised per meal served so vacation months don't count as savings.
  - **Estimated** savings are kept separate from **verified** savings.
- **Student Attendance:**
  - A records table with search, date, meal and status filters and timestamps.
  - Mark arrivals; a no-shows list; Excel download.
- **Slot Booking:**
  - Confirmed, completed, cancelled and remaining seats per slot.
  - Editable times and capacity.
  - Overbooking is impossible.
- **Reward Management:**
  - Per-student earned, redeemed and balance, with history and adjustments.
  - Editable rules and catalogue; redemption codes.
- **NGO Food Donation:** see below.
- **Reports:** Excel exports (full report, attendance, waste, donations) and historical Excel import with column validation.
- **Settings:** canteen name, pickup location, public web address, forecast mode, buffer, deadline, rewards, ingredient costs, savings baseline and college calendar.

**Student**

- **Home:** greeting with student ID, today's meal card, weekly attendance dots, reward points, next-reward progress, upcoming booking, recent activity and quick actions.
- **Attendance:** per-meal weekly calendar showing Confirmed / Not attending / Pending / Closed for confirmation, with the deadline.
- **Menu:** meal cards with image, description, items, price, availability and timings.
- **Book Slots:** live seats per slot, with booking confirmation and cancellation.
- **Rewards:** balance, earned, redeemed, next reward, catalogue and history.
- **History:** attendance, bookings and points, with date filters.
- **Profile.**

## NGO food donation (no NGO login)

1. **Create the request.** Admin → NGO Food Donation → **Create donation request**. Enter food, category, veg/non-veg, quantity (portions or kg), prepared time, safe-until, pickup location and deadline, and an optional image.
   - The ID is generated automatically, e.g. `ECO-DON-2026-001`.
   - A food-safety confirmation is required.
   - Expired food is rejected, and the pickup deadline must fall before the safe-until time.
2. **Send it.** Click **Send to NGOs via WhatsApp**. Each registered NGO gets its own secret, single-use link and three ways to send it:
   - a WhatsApp button (`wa.me` with the message pre-filled)
   - an SMS link
   - copy link / copy message

   A generic shareable link is also available.
3. **The NGO responds.** The NGO opens the link (`/d/<token>`). It sees the **live remaining quantity**, then accepts a quantity or declines. No app or account is needed.
4. **No overlapping claims.** Acceptance is one atomic `UPDATE … WHERE allocated + qty <= quantity`, so two NGOs can never claim the same food. Example: 50 portions; NGO A takes 30; NGO B sees 20 remaining. When everything is allocated, acceptance closes.
5. **Tracking.** Status moves through Available → Request Sent → Partially / Fully Accepted → Pickup Confirmed → Collected, or Expired / Cancelled.
   - The admin sees each NGO, its quantity and status.
   - The admin can mark pickup or collection, or release an allocation back to the pool.
   - Admin notifications (the bell) report each accept or decline.

**Note on WhatsApp.** `wa.me` links open a pre-filled chat but cannot report replies back. Acceptance is therefore tracked through the secure link. Fully automatic WhatsApp notifications need the **WhatsApp Business Cloud API** (approved templates + webhook), which is not configured.

**Public address.** For NGOs to open links on their phones, EcoByte must be reachable from the internet (or the same network). Set **Settings → Public web address** accordingly.

## Automatic WhatsApp to NGOs

Donations → **WhatsApp setup** connects a real WhatsApp sender. Until a provider is saved, nothing is sent
automatically and "Send to NGOs via WhatsApp" opens a pre-filled chat (wa.me) as before.

| | Twilio sandbox (quickest test) | Meta WhatsApp Cloud API (official) |
|---|---|---|
| Account | twilio.com, free trial | developers.facebook.com app + WhatsApp product |
| Recipients while testing | each phone sends `join <sandbox-word>` to +1 415 523 8886 | up to 5 numbers added and verified under API Setup → To |
| First message to a number | allowed after joining | plain text only within 24 h of the NGO messaging you; use the `hello_world` test or an approved 6-variable template |
| Delivery status | fetched from Twilio automatically | via webhook `/api/public/whatsapp/webhook` (needs public HTTPS) |

- **Test:** WhatsApp setup → "Send a test message" (or **Test** next to an NGO). The message log shows
  Sending / Sent / Delivered / Read / Failed, and failures explain the fix (number not verified, sandbox not joined,
  24-hour window, expired token...).
- **Send a donation:** "Send to NGOs via WhatsApp" → **Send automatically**. With **Auto-send new donations** on,
  every new donation goes to all active NGOs as soon as it is created.
- **Links in the message** use Settings → Public web address. NGO phones cannot open `localhost`; for testing run a
  tunnel (`cloudflared tunnel --url http://localhost:8000`) and paste its https address there.
- **NGO contacts:** add, edit, deactivate or **Remove**. Removing revokes links the NGO has not answered; past
  donations keep its name and the message log keeps its history.
- Secrets (tokens) are stored in the local database and never returned by the API; webhooks check signatures
  (Meta app secret, Twilio auth token).
- `python -m tests.whatsapp_test` checks the whole flow against a fake provider (35 checks, no real messages).

## Architecture

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite, React Router, Recharts, lucide icons, custom CSS design system, inline SVG illustrations |
| Backend | FastAPI, SQLAlchemy 2, Pydantic |
| Database | SQLite by default; PostgreSQL via `DATABASE_URL=postgresql+psycopg://user:pass@host/ecobyte` (`pip install "psycopg[binary]"`) |
| Analytics | pandas, NumPy, scikit-learn |
| Auth | bcrypt hashing, JWT, server-side role checks on every admin/student route |

**Tables**
- users (students and admins)
- attendance
- meals (menus)
- meal_slots, slot_bookings
- rewards, reward_transactions, redemptions
- meal_records (historical attendance, preparation, consumption)
- waste_records (food waste and cost)
- savings_records
- ngo_contacts, donations, donation_invites, donation_allocations (allocations and pickup records)
- notifications
- calendar_events
- model_runs, import_logs, app_settings

## Operations upgrade (passes, holidays, store, coupons)

**Login.** A single login page has Student and Canteen Admin tabs. Students can sign in with their email **or** student ID (e.g. `STU2025`). "Remember me" keeps you signed in; unticked, the session ends when the tab closes. Forgot password: the admin issues a temporary password from **Student Management → Reset password**.

**Admin sidebar:**
1. Dashboard
2. Student Management
3. Meal & Menu
4. NGO & Food Donation
5. Holiday Management
6. Meal Slot Management
7. Attendance
8. Canteen Store
9. Rewards & Coupons
10. Reports & Analytics (Analytics, Waste, Cost, Savings, Exports)
11. Settings

**Mess passes.**
- Pass types: Monthly (30 days) or Six-Month (180 days).
- Validity is always computed from real dates: remaining = expiry − today + 1.
- Status: Active, then Expiring Soon (≤ 7 days left, configurable), then Expired; or Suspended.
- Admins can extend passes by +2, +5, +7 or a custom number of days, with a reason (student leave, medical leave, college holiday, special permission). Every extension is logged with previous expiry, new expiry, admin and date.
- Each extension dialog carries a unique key, so double-clicking never extends twice.
- Students can request a renewal; the admin approves it in Student Management.

**Holidays.**
- Create a holiday with name, date, type (national / festival / college / special), affected meals or full day, and a message.
- Publishing it:
  - notifies every student (bell and dashboard)
  - closes those meals for confirmation and booking
  - cancels existing bookings for them, with a notice to each student
- Passes are only extended for holidays if **Settings → Mess passes** says so.

**Bookings.**
- Booking requires an active pass and an open meal, and capacity is enforced on the server.
- Bookings can be made, changed or cancelled until N minutes before the slot (60 by default).
- Statuses: Confirmed, then Locked after the deadline, then Completed when served; or Cancelled.
- Confirmed bookings count towards expected demand.

**Attendance.**
- Actual attendance is recorded only at the counter (Admin → Attendance → Record attendance) or when a booking is marked served.
- Students see a calendar from their pass start date:
  - green = present
  - red = absent
  - grey = holiday or closed
  - blue = upcoming booked
- Future days are never marked present or absent.

**Canteen store.**
- Separate from the mess pass.
- Students add items to a cart and order. Prices are set by the server and payment is at the counter.
- Admins manage products and move orders: Placed, Accepted, Preparing, Ready for Pickup, Completed (or Cancelled).

**Reward tokens & coupons.**
- **Earning:** tokens for verified attendance (10 per meal), planning ahead (5 per day) and a full-week bonus. Admins can also award tokens.
- **Redeeming:** e.g. Tea 200 tokens. Tokens are deducted in the same transaction that creates a unique coupon code. A balance can never go negative.
- **Validating:** the admin looks the code up and redeems it once. Cancelling an active coupon refunds the tokens.
- All values are configurable.

**Tests:** `python -m tests.smoke_test` (43 checks) and `python -m tests.upgrade_test` (47 checks, the full Part 6 checklist), run against a freshly seeded server.

## Tests

```bash
cd backend
.venv/Scripts/python -m uvicorn app.main:app --port 8000   # terminal 1
.venv/Scripts/python -m tests.smoke_test                   # terminal 2
```

There are 43 end-to-end checks, covering:
- roles
- the zero start and live updates on tick
- publishing
- slot capacity
- waste cost
- **three NGOs accepting simultaneously, where exactly one wins**
- single-use links
- reports

The test writes data, so run `python -m app.seed --reset` afterwards.
