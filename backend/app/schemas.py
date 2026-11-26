from datetime import date, datetime, time
from datetime import date as DateType
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Meal = Literal["breakfast", "lunch", "dinner"]


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)
    portal: Literal["admin", "student"]


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    student_code: str = Field(min_length=3, max_length=30)
    department: str | None = Field(default=None, max_length=80)
    year_of_study: int | None = Field(default=None, ge=1, le=6)


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\-\s]{0,20}$")
    department: str | None = Field(default=None, max_length=80)
    year_of_study: int | None = Field(default=None, ge=1, le=6)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AttendanceItem(BaseModel):
    date: date
    meal_type: Meal
    status: Literal["coming", "not_coming"]


class AttendanceIn(BaseModel):
    items: list[AttendanceItem] = Field(min_length=1, max_length=60)


class BookingIn(BaseModel):
    slot_id: int
    date: date


class RedeemIn(BaseModel):
    reward_id: int


class MealIn(BaseModel):
    date: date
    meal_type: Meal
    name: str = Field(min_length=2, max_length=120)
    items: str = Field(default="", max_length=1000)
    description: str = Field(default="", max_length=1000)
    is_veg: bool = True
    price: float = Field(default=0, ge=0, le=10000)
    quantity_available: int | None = Field(default=None, ge=0, le=100000)
    prep_cost: float | None = Field(default=None, ge=0, le=10_000_000)
    available: bool = True
    published: bool = False


class MealPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    items: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=1000)
    is_veg: bool | None = None
    price: float | None = Field(default=None, ge=0, le=10000)
    quantity_available: int | None = Field(default=None, ge=0, le=100000)
    prep_cost: float | None = Field(default=None, ge=0, le=10_000_000)
    available: bool | None = None
    published: bool | None = None
    date: DateType | None = None
    meal_type: Meal | None = None


class CopyMenuIn(BaseModel):
    from_date: date
    to_date: date


class PreparationIn(BaseModel):
    date: date
    meal_type: Meal
    meals_prepared: int = Field(ge=0, le=100000)


class PublishIn(BaseModel):
    date: date
    published: bool = True


class SlotIn(BaseModel):
    meal_type: Meal
    start_time: time
    end_time: time
    capacity: int = Field(ge=1, le=2000)
    active: bool = True

    @field_validator("end_time")
    @classmethod
    def _order(cls, v, info):
        st = info.data.get("start_time")
        if st and v <= st:
            raise ValueError("end time must be after start time")
        return v


class SlotPatch(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=2000)
    active: bool | None = None
    start_time: time | None = None
    end_time: time | None = None


class RewardIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    points_cost: int = Field(ge=1, le=100000)
    stock: int = Field(ge=0, le=100000)
    active: bool = True


class AdjustPointsIn(BaseModel):
    user_id: int
    points: int = Field(ge=-10000, le=10000)
    reason: str = Field(min_length=3, max_length=200)


class SettingsIn(BaseModel):
    canteen_name: str | None = Field(default=None, min_length=2, max_length=120)
    buffer_pct: float | None = Field(default=None, ge=0, le=50)
    forecast_mode: Literal["confirmations", "hybrid"] | None = None
    attendance_deadline: time | None = None
    attendance_window_days: int | None = Field(default=None, ge=1, le=31)
    points_per_confirmation: int | None = Field(default=None, ge=0, le=1000)
    weekly_streak_bonus: int | None = Field(default=None, ge=0, le=1000)
    cost_per_kg: float | None = Field(default=None, gt=0, le=100000)
    cost_breakfast: float | None = Field(default=None, gt=0, le=100000)
    cost_lunch: float | None = Field(default=None, gt=0, le=100000)
    cost_dinner: float | None = Field(default=None, gt=0, le=100000)
    booking_cancel_minutes: int | None = Field(default=None, ge=0, le=1440)
    baseline_mode: Literal["period", "manual"] | None = None
    baseline_start: date | None = None
    baseline_end: date | None = None
    baseline_manual_daily: float | None = Field(default=None, ge=0)
    active_model: Literal["baseline", "random_forest"] | None = None
    public_base_url: str | None = Field(default=None, max_length=200, pattern=r"^(https?://[^\s]+)?$")
    tokens_per_attended_meal: int | None = Field(default=None, ge=0, le=1000)
    coupon_validity_days: int | None = Field(default=None, ge=1, le=365)
    holiday_extends_pass: bool | None = None
    expiring_soon_days: int | None = Field(default=None, ge=1, le=30)
    price_monthly: float | None = Field(default=None, ge=0, le=1_000_000)
    price_six_month: float | None = Field(default=None, ge=0, le=1_000_000)
    pickup_location: str | None = Field(default=None, min_length=3, max_length=200)


class ActualsIn(BaseModel):
    date: date
    meal_type: Meal
    actual_attendance: int = Field(ge=0, le=100000)
    meals_prepared: int = Field(ge=0, le=100000)
    meals_served: int = Field(ge=0, le=100000)

    @field_validator("meals_served")
    @classmethod
    def _served(cls, v, info):
        p = info.data.get("meals_prepared")
        if p is not None and v > p:
            raise ValueError("meals served cannot exceed meals prepared")
        return v


class WasteIn(BaseModel):
    date: date
    meal_type: Meal
    food_name: str = Field(min_length=2, max_length=120)
    recorded_at: time | None = None
    prepared_kg: float = Field(ge=0, le=100000)
    served_kg: float = Field(ge=0, le=100000)
    leftover_kg: float = Field(ge=0, le=100000)
    plate_waste_kg: float = Field(default=0, ge=0, le=100000)
    cost_per_kg: float | None = Field(default=None, gt=0, le=100000)
    notes: str | None = Field(default=None, max_length=500)


class EventIn(BaseModel):
    date: date
    kind: Literal["holiday", "vacation", "exam", "event"]
    name: str = Field(min_length=2, max_length=120)
    canteen_closed: bool = False


class VerifySavingIn(BaseModel):
    verified_amount: float | None = Field(default=None, ge=-10_000_000, le=10_000_000)
    verified_note: str | None = Field(default=None, max_length=500)


class ArrivalIn(BaseModel):
    user_id: int
    date: date
    meal_type: Meal
    arrived: bool


class NgoIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str = Field(min_length=8, max_length=20)
    email: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=200)
    active: bool = True


class DonationIn(BaseModel):
    food_name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    is_veg: bool = True
    quantity: float = Field(gt=0, le=100000)
    unit: Literal["portions", "kg"] = "portions"
    prepared_at: datetime
    safe_until: datetime
    pickup_location: str = Field(min_length=3, max_length=200)
    pickup_deadline: datetime
    instructions: str = Field(default="", max_length=1000)
    meal_type: Meal | None = None
    food_safety_confirmed: bool


class InviteIn(BaseModel):
    ngo_ids: list[int] = Field(default_factory=list, max_length=200)
    generic: bool = False
    base_url: str = Field(min_length=8, max_length=200, pattern=r"^https?://[^\s]+$")


class AllocationStatusIn(BaseModel):
    status: Literal["pickup_confirmed", "collected", "cancelled"]
    collected_qty: float | None = Field(default=None, ge=0, le=100000)


class AcceptIn(BaseModel):
    quantity: float = Field(gt=0, le=100000)
    organisation: str = Field(default="", max_length=120)
    contact_name: str = Field(min_length=2, max_length=120)
    contact_phone: str = Field(min_length=8, max_length=20)
    pickup_eta: str | None = Field(default=None, max_length=40)


class DeclineIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


# --- Student management & passes ------------------------------------------------------------------

PassType = Literal["monthly", "six_month"]
ExtendReason = Literal["student_leave", "medical_leave", "college_holiday", "special_permission", "other"]


class StudentCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    student_code: str = Field(min_length=3, max_length=30)
    phone: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\-\s]{0,20}$")
    department: str | None = Field(default=None, max_length=80)
    year_of_study: int | None = Field(default=None, ge=1, le=6)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    pass_type: PassType | None = None
    start_date: DateType | None = None


class StudentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+\-\s]{0,20}$")
    department: str | None = Field(default=None, max_length=80)
    year_of_study: int | None = Field(default=None, ge=1, le=6)


class ExtendIn(BaseModel):
    days: int = Field(ge=1, le=90)
    reason: ExtendReason
    note: str = Field(default="", max_length=300)
    request_key: str = Field(min_length=8, max_length=80)
    leave_from: DateType | None = None
    leave_to: DateType | None = None


class RenewIn(BaseModel):
    pass_type: PassType
    start_date: DateType | None = None


class SuspendIn(BaseModel):
    suspended: bool
    reason: str = Field(default="", max_length=300)


class RenewalActionIn(BaseModel):
    action: Literal["approve", "reject"]
    start_date: DateType | None = None
    note: str = Field(default="", max_length=300)


class RenewalRequestIn(BaseModel):
    pass_type: PassType
    note: str = Field(default="", max_length=300)


# --- Holidays --------------------------------------------------------------------------------------

class HolidayIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    date: DateType
    holiday_type: Literal["national", "festival", "college", "special"]
    description: str = Field(default="", max_length=500)
    services: list[Literal["breakfast", "lunch", "dinner"]] = Field(min_length=1, max_length=3)
    message: str = Field(default="", max_length=500)
    publish: bool = False


# --- Attendance recording --------------------------------------------------------------------------

class MarkAttendanceIn(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=2000)
    date: DateType
    meal_type: Meal
    present: bool


# --- Store -----------------------------------------------------------------------------------------

class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    category: Literal["beverage", "snack", "meal", "dessert"] = "snack"
    price: float = Field(gt=0, le=10000)
    available: bool = True
    is_veg: bool = True


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=20)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=30)
    note: str = Field(default="", max_length=300)


class OrderStatusIn(BaseModel):
    status: Literal["accepted", "preparing", "ready", "completed", "cancelled"]


# --- Coupons, bookings, donations ------------------------------------------------------------------

class CouponCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class ChangeSlotIn(BaseModel):
    slot_id: int


class AssignIn(BaseModel):
    ngo_id: int
    quantity: float = Field(gt=0, le=100000)
    pickup_eta: str | None = Field(default=None, max_length=40)
