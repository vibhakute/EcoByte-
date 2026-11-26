"""Relational schema for EcoByte.

Students and admins share the `users` table and are separated by `role`;
every admin API checks the role server-side (see auth.require_admin).
NGOs have no accounts: they act only through single-use secret links (donation_invites).
"""
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(10), index=True)  # "admin" | "student"
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(100))
    student_code: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    department: Mapped[str | None] = mapped_column(String(80), nullable=True)
    year_of_study: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hostel_resident: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # account can sign in
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)  # mess privileges suspended by admin
    # Reward-token balance, kept in sync with the ledger and changed only by atomic UPDATEs
    # (UPDATE ... WHERE token_balance >= cost), so it can never go negative.
    token_balance: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AppSettings(Base):
    """Single-row table of admin-configurable parameters."""
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    canteen_name: Mapped[str] = mapped_column(String(120), default="College Canteen")
    buffer_pct: Mapped[float] = mapped_column(Float, default=5.0)
    # confirmations: predicted = confirmed x learned turnout ratio (starts at zero)
    # hybrid: history model (same-weekday, trend, menu, calendar) blended with confirmations
    forecast_mode: Mapped[str] = mapped_column(String(15), default="confirmations")
    attendance_deadline: Mapped[time] = mapped_column(Time, default=time(21, 0))  # day before
    attendance_window_days: Mapped[int] = mapped_column(Integer, default=13)
    points_per_confirmation: Mapped[int] = mapped_column(Integer, default=5)
    weekly_streak_bonus: Mapped[int] = mapped_column(Integer, default=10)
    cost_per_kg: Mapped[float] = mapped_column(Float, default=120.0)
    cost_breakfast: Mapped[float] = mapped_column(Float, default=100.0)
    cost_lunch: Mapped[float] = mapped_column(Float, default=125.0)
    cost_dinner: Mapped[float] = mapped_column(Float, default=120.0)
    booking_cancel_minutes: Mapped[int] = mapped_column(Integer, default=60)  # booking/cancel cut-off before service
    tokens_per_attended_meal: Mapped[int] = mapped_column(Integer, default=10)
    coupon_validity_days: Mapped[int] = mapped_column(Integer, default=30)
    holiday_extends_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    expiring_soon_days: Mapped[int] = mapped_column(Integer, default=7)
    price_monthly: Mapped[float] = mapped_column(Float, default=3000.0)
    price_six_month: Mapped[float] = mapped_column(Float, default=16000.0)
    baseline_mode: Mapped[str] = mapped_column(String(10), default="period")  # period | manual
    baseline_start: Mapped[date] = mapped_column(Date, default=date(2025, 1, 1))
    baseline_end: Mapped[date] = mapped_column(Date, default=date(2025, 12, 31))
    baseline_manual_daily: Mapped[float] = mapped_column(Float, default=0.0)
    active_model: Mapped[str] = mapped_column(String(20), default="baseline")  # baseline | random_forest
    public_base_url: Mapped[str] = mapped_column(String(200), default="")
    pickup_location: Mapped[str] = mapped_column(String(200), default="College Canteen, Main Building")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(20))  # holiday | vacation | exam | event
    name: Mapped[str] = mapped_column(String(120))
    canteen_closed: Mapped[bool] = mapped_column(Boolean, default=False)  # mirrors "published + full day"
    # Holiday Management fields. services = affected meals, comma separated (all three = full day).
    # A holiday blocks meals only once published.
    holiday_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # national | festival | college | special
    description: Mapped[str] = mapped_column(Text, default="")
    services: Mapped[str] = mapped_column(String(40), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("date", "name", name="uq_event_date_name"),)


class Meal(Base):
    """A planned meal (menu entry). Students only see published meals."""
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(120))
    items: Mapped[str] = mapped_column(Text, default="")  # one food item per line
    description: Mapped[str] = mapped_column(Text, default="")
    is_veg: Mapped[bool] = mapped_column(Boolean, default=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    quantity_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prep_cost: Mapped[float | None] = mapped_column(Float, nullable=True)  # estimated total cost (Rs)
    image: Mapped[str | None] = mapped_column(String(80), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (Index("ix_meal_date_type", "date", "meal_type"),)


class Attendance(Base):
    """A student's advance confirmation for one meal on one day."""
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10))  # coming | not_coming
    confirmed_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "date", "meal_type", name="uq_attendance_once"),)


class MealAttendance(Base):
    """ACTUAL attendance, recorded at the counter (or when a booking is marked served).
    Separate from Attendance (an advance plan) and SlotBooking (a reservation)."""
    __tablename__ = "meal_attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(10))
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(12), default="counter")  # counter | booking
    __table_args__ = (UniqueConstraint("user_id", "date", "meal_type", name="uq_meal_attendance"),)


class MessSubscription(Base):
    """A mess pass. Valid start_date .. expiry_date inclusive; expiry_date moves with extensions."""
    __tablename__ = "mess_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pass_type: Mapped[str] = mapped_column(String(12))  # monthly | six_month
    purchase_date: Mapped[date] = mapped_column(Date)
    start_date: Mapped[date] = mapped_column(Date)
    base_days: Mapped[int] = mapped_column(Integer)
    expiry_date: Mapped[date] = mapped_column(Date)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    extensions: Mapped[list["PassExtension"]] = relationship(back_populates="subscription", order_by="PassExtension.created_at")


class PassExtension(Base):
    __tablename__ = "pass_extensions"
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("mess_subscriptions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    previous_expiry: Mapped[date] = mapped_column(Date)
    added_days: Mapped[int] = mapped_column(Integer)
    new_expiry: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(30))  # student_leave | medical_leave | college_holiday | special_permission | other
    note: Mapped[str] = mapped_column(Text, default="")
    leave_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    request_key: Mapped[str] = mapped_column(String(80), unique=True)  # idempotency: a double click never extends twice
    created_at: Mapped[datetime] = mapped_column(DateTime)
    subscription: Mapped[MessSubscription] = relationship(back_populates="extensions")


class RenewalRequest(Base):
    __tablename__ = "renewal_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pass_type: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | rejected
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudentNotification(Base):
    __tablename__ = "student_notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # holiday | pass | order | reward
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ref_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Product(Base):
    """Canteen store item: extra purchases, kept separate from the mess pass."""
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="snack")  # beverage | snack | meal | dessert
    price: Mapped[float] = mapped_column(Float)
    image: Mapped[str | None] = mapped_column(String(80), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_veg: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StoreOrder(Base):
    __tablename__ = "store_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(14), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="placed")  # placed | accepted | preparing | ready | completed | cancelled
    total: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    items: Mapped[list["StoreOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class StoreOrderItem(Base):
    __tablename__ = "store_order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("store_orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(80))  # snapshot at order time
    unit_price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[float] = mapped_column(Float)
    order: Mapped[StoreOrder] = relationship(back_populates="items")


class MealSlot(Base):
    __tablename__ = "meal_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    meal_type: Mapped[str] = mapped_column(String(10), index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    capacity: Mapped[int] = mapped_column(Integer, default=40)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SlotBooking(Base):
    __tablename__ = "slot_bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("meal_slots.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), default="booked")  # booked | cancelled | served
    code: Mapped[str] = mapped_column(String(12), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    slot: Mapped[MealSlot] = relationship()
    __table_args__ = (Index("ix_booking_slot_date", "slot_id", "date", "status"),)


class Reward(Base):
    __tablename__ = "rewards"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    points_cost: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RewardTransaction(Base):
    """Append-only points ledger. `ref_key` is unique so the same event can never pay twice."""
    __tablename__ = "reward_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    points: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(12))  # earn | bonus | redeem | adjust
    description: Mapped[str] = mapped_column(String(200))
    ref_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Redemption(Base):
    __tablename__ = "redemptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reward_id: Mapped[int] = mapped_column(ForeignKey("rewards.id"))
    points: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | redeemed | expired | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reward: Mapped[Reward] = relationship()


class MealRecord(Base):
    """Demand side of one service (date x meal): confirmations, attendance, prediction, prepared, served."""
    __tablename__ = "meal_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(10))
    main_dish: Mapped[str | None] = mapped_column(String(120), nullable=True)
    menu_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    event: Mapped[str | None] = mapped_column(String(120), nullable=True)
    advance_confirmations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slot_bookings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_demand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meals_prepared: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meals_served: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="admin_entry")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("date", "meal_type", name="uq_meal_record"),)


class WasteRecord(Base):
    """One measured waste entry. Several entries per service are allowed (one per food item).
    waste_cost = total_waste_kg x cost_per_kg, stored for traceability."""
    __tablename__ = "waste_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(10))
    food_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prepared_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    served_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    leftover_kg: Mapped[float] = mapped_column(Float, default=0.0)   # cooked, never served
    plate_waste_kg: Mapped[float] = mapped_column(Float, default=0.0)  # served, not eaten
    total_waste_kg: Mapped[float] = mapped_column(Float)
    cost_per_kg: Mapped[float] = mapped_column(Float)
    waste_cost: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="admin_entry")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (Index("ix_waste_date_meal", "date", "meal_type"),)


class SavingsRecord(Base):
    """Monthly savings ledger (months never overlap). verified_amount only from real financial evidence."""
    __tablename__ = "savings_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(7), unique=True)  # YYYY-MM
    operating_days: Mapped[int] = mapped_column(Integer)
    baseline_cost: Mapped[float] = mapped_column(Float)
    actual_cost: Mapped[float] = mapped_column(Float)
    estimated_saving: Mapped[float] = mapped_column(Float)
    verified_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(20))
    trained_at: Mapped[datetime] = mapped_column(DateTime)
    train_rows: Mapped[int] = mapped_column(Integer)
    test_rows: Mapped[int] = mapped_column(Integer)
    test_start: Mapped[date] = mapped_column(Date)
    test_end: Mapped[date] = mapped_column(Date)
    mae: Mapped[float] = mapped_column(Float)
    mape: Mapped[float] = mapped_column(Float)
    baseline_mae: Mapped[float] = mapped_column(Float)
    baseline_mape: Mapped[float] = mapped_column(Float)
    features: Mapped[str] = mapped_column(Text)


class ImportLog(Base):
    __tablename__ = "import_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200))
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    rows_read: Mapped[int] = mapped_column(Integer)
    rows_imported: Mapped[int] = mapped_column(Integer)
    rows_skipped: Mapped[int] = mapped_column(Integer)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    messages: Mapped[str] = mapped_column(Text, default="")


# --- NGO food donation (no NGO accounts) -----------------------------------------------------

class NgoContact(Base):
    __tablename__ = "ngo_contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str] = mapped_column(String(20))  # digits incl. country code, e.g. 919876543210
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Donation(Base):
    __tablename__ = "donations"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)  # ECO-DON-2026-001
    food_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    is_veg: Mapped[bool] = mapped_column(Boolean, default=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))  # portions | kg
    allocated_qty: Mapped[float] = mapped_column(Float, default=0.0)  # updated atomically
    collected_qty: Mapped[float] = mapped_column(Float, default=0.0)
    prepared_at: Mapped[datetime] = mapped_column(DateTime)
    safe_until: Mapped[datetime] = mapped_column(DateTime)
    pickup_location: Mapped[str] = mapped_column(String(200))
    pickup_deadline: Mapped[datetime] = mapped_column(DateTime)
    instructions: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str | None] = mapped_column(String(80), nullable=True)
    meal_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    invites: Mapped[list["DonationInvite"]] = relationship(back_populates="donation", cascade="all, delete-orphan")
    allocations: Mapped[list["DonationAllocation"]] = relationship(back_populates="donation", cascade="all, delete-orphan")


class DonationInvite(Base):
    """A secret link sent to one NGO (or a generic shareable link when ngo_id is null)."""
    __tablename__ = "donation_invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id", ondelete="CASCADE"), index=True)
    ngo_id: Mapped[int | None] = mapped_column(ForeignKey("ngo_contacts.id"), nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response: Mapped[str | None] = mapped_column(String(10), nullable=True)  # accepted | declined
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    donation: Mapped[Donation] = relationship(back_populates="invites")
    ngo: Mapped[NgoContact | None] = relationship()


class DonationAllocation(Base):
    __tablename__ = "donation_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    donation_id: Mapped[int] = mapped_column(ForeignKey("donations.id", ondelete="CASCADE"), index=True)
    invite_id: Mapped[int | None] = mapped_column(ForeignKey("donation_invites.id"), nullable=True)  # null = assigned by admin
    ngo_id: Mapped[int | None] = mapped_column(ForeignKey("ngo_contacts.id"), nullable=True)
    organisation: Mapped[str] = mapped_column(String(120))
    contact_name: Mapped[str] = mapped_column(String(120))
    contact_phone: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(Float)
    pickup_eta: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="accepted")  # accepted | pickup_confirmed | collected | cancelled
    collected_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    donation: Mapped[Donation] = relationship(back_populates="allocations")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(120), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class WhatsAppConfig(Base):
    """Single row: how EcoByte sends WhatsApp messages automatically. Secrets are never returned by the API."""
    __tablename__ = "whatsapp_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(10), default="off")  # off | meta | twilio
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False)  # send new donations to every active NGO
    meta_phone_number_id: Mapped[str] = mapped_column(String(40), default="")
    meta_token: Mapped[str] = mapped_column(Text, default="")
    meta_app_secret: Mapped[str] = mapped_column(String(80), default="")
    meta_verify_token: Mapped[str] = mapped_column(String(80), default="")
    meta_template: Mapped[str] = mapped_column(String(80), default="")  # empty = send plain text
    meta_template_lang: Mapped[str] = mapped_column(String(12), default="en_US")
    twilio_sid: Mapped[str] = mapped_column(String(40), default="")
    twilio_token: Mapped[str] = mapped_column(String(80), default="")
    twilio_from: Mapped[str] = mapped_column(String(20), default="")  # e.g. 14155238886 (sandbox)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WhatsAppMessage(Base):
    """Every WhatsApp message EcoByte sent (or received on the webhook), with its delivery status."""
    __tablename__ = "whatsapp_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(String(3), default="out")  # out | in
    provider: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(12), default="donation")  # donation | test | reply
    phone: Mapped[str] = mapped_column(String(20), index=True)
    ngo_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # plain id: removing an NGO keeps the log
    ngo_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    donation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(14), default="pending")  # pending | sent | delivered | read | failed | received
    provider_id: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
