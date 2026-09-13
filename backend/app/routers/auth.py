from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, Token, UserCreate
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(400, "Email already registered")
    user = User(email=body.email.lower(), hashed_password=hash_password(body.password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(str(user.id), user.role), role=user.role, onboarding_complete=False)


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    return Token(
        access_token=create_access_token(str(user.id), user.role),
        role=user.role,
        onboarding_complete=user.profile is not None,
    )
