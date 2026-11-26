"""Canteen store: extra food purchases, separate from the mess pass.

Prices are always taken from the database at order time (never from the client) and copied
into the order lines, so later price changes don't alter past orders. Payment is at the counter.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Notification, Product, StoreOrder, StoreOrderItem, User
from . import mess
from .student_ops import new_code

FLOW = {"placed": ("accepted", "cancelled"), "accepted": ("preparing", "cancelled"),
        "preparing": ("ready", "cancelled"), "ready": ("completed", "cancelled"), "completed": (), "cancelled": ()}
LABEL = {"placed": "Placed", "accepted": "Accepted", "preparing": "Preparing", "ready": "Ready for Pickup",
         "completed": "Completed", "cancelled": "Cancelled"}


def product_out(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "category": p.category, "price": p.price,
            "image": f"/api/uploads/{p.image}" if p.image else None, "available": p.available, "is_veg": p.is_veg}


def order_out(o: StoreOrder, student: User | None = None) -> dict:
    out = {"id": o.id, "code": o.code, "status": o.status, "status_label": LABEL[o.status], "total": o.total, "note": o.note,
           "created_at": o.created_at.isoformat(timespec="minutes"), "updated_at": o.updated_at.isoformat(timespec="minutes"),
           "next": list(FLOW[o.status]),
           "items": [{"name": i.name, "quantity": i.quantity, "unit_price": i.unit_price, "line_total": i.line_total} for i in o.items]}
    if student:
        out["student"] = {"name": student.name, "student_code": student.student_code}
    return out


def place_order(db: Session, user: User, items: list, note: str = "") -> StoreOrder:
    if not items:
        raise HTTPException(400, "Your cart is empty")
    qty: dict[int, int] = {}
    for it in items:
        qty[it.product_id] = qty.get(it.product_id, 0) + it.quantity
    if len(qty) > 15 or any(q < 1 or q > 20 for q in qty.values()):
        raise HTTPException(400, "Order between 1 and 20 of each item (max 15 different items)")
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(qty)).all()}
    missing = [pid for pid in qty if pid not in products or not products[pid].available]
    if missing:
        names = ", ".join(products[p].name for p in missing if p in products) or "Some items"
        raise HTTPException(409, f"{names} {'is' if len(missing) == 1 else 'are'} no longer available. Please update your cart.")
    now = datetime.now()
    o = StoreOrder(code=new_code("OR-"), user_id=user.id, status="placed", total=0, note=(note or "")[:300],
                   created_at=now, updated_at=now)
    total = 0.0
    for pid, q in qty.items():
        p = products[pid]
        line = round(p.price * q, 2)
        total += line
        o.items.append(StoreOrderItem(product_id=pid, name=p.name, unit_price=p.price, quantity=q, line_total=line))
    o.total = round(total, 2)
    db.add(o)
    db.add(Notification(kind="order", title=f"New store order {o.code}",
                        body=f"{user.name}: " + ", ".join(f"{i.quantity}× {i.name}" for i in o.items) + f" · ₹{o.total:g}",
                        link="/admin/store", created_at=now))
    db.commit()
    db.refresh(o)
    return o


def set_status(db: Session, o: StoreOrder, status: str, by_student: bool = False) -> StoreOrder:
    if by_student and not (o.status == "placed" and status == "cancelled"):
        raise HTTPException(400, "You can cancel an order only before the canteen accepts it.")
    if status not in FLOW[o.status]:
        raise HTTPException(400, f"An order that is {LABEL[o.status].lower()} cannot become {LABEL.get(status, status).lower()}.")
    o.status, o.updated_at = status, datetime.now()
    if not by_student:
        msg = {"accepted": "accepted by the canteen", "preparing": "being prepared", "ready": "ready for pickup at the counter",
               "completed": "completed. Enjoy!", "cancelled": "cancelled by the canteen"}[status]
        mess.notify_student(db, o.user_id, "order", f"Order {o.code} is {msg}", f"Total ₹{o.total:g}", "/student/store",
                            f"order:{o.id}:{status}")
    db.commit()
    db.refresh(o)
    return o
