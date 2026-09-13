from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.matching import is_eligible
from app.models import Match, Opportunity, User
from app.schemas import MatchAction, OpportunityOut

router = APIRouter(tags=["opportunities"])


def _public_filter(q):
    return q.filter(Opportunity.published.is_(True), Opportunity.reviewed_by_human.is_(True))


def _serialize(opp: Opportunity, reasons=None, is_match=None) -> dict:
    data = OpportunityOut.model_validate(opp).model_dump(mode="json")
    data["match_reasons"] = reasons
    data["is_match"] = is_match
    return data


@router.get("/feed")
def feed(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str | None = None,
    sector: str | None = None,
    domain: str | None = None,
    only_matches: bool = Query(default=True),
):
    q = _public_filter(db.query(Opportunity))
    if status:
        q = q.filter(Opportunity.status == status)
    if sector:
        q = q.filter(Opportunity.sector == sector)
    if domain:
        q = q.filter(Opportunity.domain == domain)
    opps = q.order_by(Opportunity.apply_end_date.is_(None), Opportunity.apply_end_date.asc(), Opportunity.created_at.desc()).all()

    profile = user.profile
    matches = {
        m.opportunity_id: m
        for m in db.query(Match).filter(Match.user_id == user.id).all()
    }
    items = []
    for opp in opps:
        reasons = None
        matched = False
        if profile:
            ok, reasons = is_eligible(profile, opp)
            matched = ok
        stored = matches.get(opp.id)
        if stored and stored.match_reasons:
            reasons = stored.match_reasons
            matched = True
        if stored and stored.user_action == "dismissed":
            continue
        if only_matches and profile and not matched:
            continue
        row = _serialize(opp, reasons, matched)
        items.append(row)
    return {"items": items, "onboarding_complete": profile is not None}


@router.get("/opportunities/{opp_id}")
def detail(opp_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp or not opp.published or not opp.reviewed_by_human:
        raise HTTPException(404, "Opportunity not found")
    reasons = None
    matched = False
    if user.profile:
        matched, reasons = is_eligible(user.profile, opp)
    m = db.query(Match).filter(Match.user_id == user.id, Match.opportunity_id == opp.id).one_or_none()
    if m:
        reasons = m.match_reasons
        if not m.user_action:
            m.user_action = "viewed"
            db.commit()
    related = (
        _public_filter(db.query(Opportunity))
        .filter(Opportunity.id != opp.id, Opportunity.domain == opp.domain)
        .limit(5)
        .all()
    )
    return {
        "opportunity": _serialize(opp, reasons, matched),
        "related": [_serialize(r) for r in related],
        "disclaimer": (
            "Please verify all eligibility details from the official notification before applying. "
            "This platform provides alerts and filtering only."
        ),
    }


ALLOWED_ACTIONS = {"viewed", "clicked_official_link", "dismissed", "saved", "applied", "shortlisted"}


@router.post("/opportunities/{opp_id}/action")
def action(opp_id: UUID, body: MatchAction, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.action not in ALLOWED_ACTIONS:
        raise HTTPException(400, f"Invalid action. Allowed: {ALLOWED_ACTIONS}")
    m = db.query(Match).filter(Match.user_id == user.id, Match.opportunity_id == opp_id).one_or_none()
    if not m:
        m = Match(user_id=user.id, opportunity_id=opp_id, match_reasons=[], user_action=body.action)
        db.add(m)
    else:
        m.user_action = body.action
    db.commit()
    return {"ok": True, "action": body.action}


@router.get("/tracker")
def tracker(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = db.query(Match).filter(Match.user_id == user.id, Match.user_action.isnot(None)).all()
    grouped: dict[str, list[dict]] = {
        "applied": [],
        "shortlisted": [],
        "saved": [],
        "dismissed": [],
        "other": [],
    }
    for m in matches:
        opp = db.get(Opportunity, m.opportunity_id)
        if not opp:
            continue
        item = _serialize(opp, reasons=m.match_reasons, is_match=True)
        item["user_action"] = m.user_action
        item["matched_at"] = m.matched_at.isoformat() if m.matched_at else None
        target_group = m.user_action if m.user_action in grouped else "other"
        grouped[target_group].append(item)

    return {"tracker": grouped}



@router.get("/meta")
def meta():
    return {
        "sectors": ["Govt", "Private", "PSU"],
        "domains": [
            "Banking",
            "Railway",
            "Defense",
            "Teaching",
            "Engineering",
            "Medical",
            "Police",
            "Judiciary",
            "Clerical",
            "UPSC-CSE",
            "State-PSC",
            "SSC",
            "PSU",
            "Other",
        ],
        "education_levels": ["10th", "12th", "Diploma", "Graduate", "Postgraduate", "Doctorate"],
        "categories": ["General", "OBC", "SC", "ST", "EWS", "PwD"],
        "indian_states": [
            "Andhra Pradesh",
            "Arunachal Pradesh",
            "Assam",
            "Bihar",
            "Chhattisgarh",
            "Delhi",
            "Goa",
            "Gujarat",
            "Haryana",
            "Himachal Pradesh",
            "Jharkhand",
            "Karnataka",
            "Kerala",
            "Madhya Pradesh",
            "Maharashtra",
            "Manipur",
            "Meghalaya",
            "Mizoram",
            "Nagaland",
            "Odisha",
            "Punjab",
            "Rajasthan",
            "Sikkim",
            "Tamil Nadu",
            "Telangana",
            "Tripura",
            "Uttar Pradesh",
            "Uttarakhand",
            "West Bengal",
            "Jammu and Kashmir",
            "Ladakh",
        ],
        "today": date.today().isoformat(),
    }
