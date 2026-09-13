from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/subscription", tags=["subscription"])


class UpgradeRequest(BaseModel):
    tier: str  # "premium" or "free"


@router.get("/tier")
def get_subscription_status(user: User = Depends(get_current_user)):
    tier = getattr(user, "subscription_tier", "free")
    is_premium = tier == "premium"
    return {
        "user_id": str(user.id),
        "email": user.email,
        "subscription_tier": tier,
        "is_premium": is_premium,
        "features": {
            "basic_matching_feed": True,
            "email_alerts": True,
            "whatsapp_instant_alerts": is_premium,
            "t5_t1_sms_reminders": is_premium,
            "application_tracker_analytics": is_premium,
            "mains_stage_prerequisite_tracking": is_premium,
        },
    }


@router.post("/upgrade")
def upgrade_tier(body: UpgradeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.tier not in ("free", "premium"):
        raise HTTPException(400, "Invalid tier selection. Choose 'free' or 'premium'.")

    user.subscription_tier = body.tier
    db.commit()
    db.refresh(user)

    return {
        "ok": True,
        "subscription_tier": user.subscription_tier,
        "message": f"Successfully updated subscription plan to {user.subscription_tier.upper()}.",
    }
