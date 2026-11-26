from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import create_token, current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import LoginIn, RegisterIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "role": u.role, "name": u.name, "email": u.email, "student_code": u.student_code,
            "department": u.department, "year_of_study": u.year_of_study, "phone": u.phone,
            "suspended": bool(u.suspended)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    ident = body.email.strip()
    # Students may sign in with their email or their student ID.
    u = db.query(User).filter(or_(User.email == ident.lower(), func.upper(User.student_code) == ident.upper())).first()
    # Same message for unknown account and bad password: don't reveal which accounts exist.
    if u is None or not verify_password(body.password, u.password_hash) or not u.is_active:
        raise HTTPException(401, "Incorrect email / student ID or password")
    if u.role != body.portal:
        portal = "Admin" if u.role == "admin" else "Student"
        raise HTTPException(403, f"This account belongs to the {portal} portal. Please sign in there.")
    return {"token": create_token(u), "user": user_out(u)}


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")
    if db.query(User).filter(User.student_code == body.student_code.strip().upper()).first():
        raise HTTPException(409, "This student ID is already registered")
    u = User(role="student", email=email, name=body.name.strip(), password_hash=hash_password(body.password),
             student_code=body.student_code.strip().upper(), department=body.department,
             year_of_study=body.year_of_study)
    db.add(u)
    db.commit()
    return {"token": create_token(u), "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
