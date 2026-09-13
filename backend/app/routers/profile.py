from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.matching_service import match_profile_to_opportunities
from app.models import User, UserProfile
from app.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "onboarding_complete": user.profile is not None,
    }


@router.get("", response_model=ProfileOut | None)
def get_profile(user: User = Depends(get_current_user)):
    return user.profile


@router.put("", response_model=ProfileOut)
def upsert_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = user.profile
    data = body.model_dump()
    if profile:
        for k, v in data.items():
            setattr(profile, k, v)
    else:
        profile = UserProfile(user_id=user.id, **data)
        db.add(profile)
    db.commit()
    db.refresh(profile)
    match_profile_to_opportunities(db, user, profile)
    return profile
