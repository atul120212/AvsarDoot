from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_admin
from app.extraction import extract_fields, search_notification
from app.matching_service import match_opportunity_to_users
from app.models import Opportunity, User
from app.schemas import ExtractRequest, OpportunityIn, OpportunityOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _needs_qa_block(body: OpportunityIn) -> bool:
    return not body.age_max or not body.education_required


@router.get("/opportunities", dependencies=[Depends(get_admin)])
def list_opps(db: Session = Depends(get_db), queue: str | None = None):
    q = db.query(Opportunity).order_by(Opportunity.created_at.desc())
    if queue == "qa":
        q = q.filter(Opportunity.reviewed_by_human.is_(False))
    elif queue == "live":
        q = q.filter(Opportunity.published.is_(True), Opportunity.reviewed_by_human.is_(True))
    return {"items": [OpportunityOut.model_validate(o).model_dump(mode="json") for o in q.all()]}


@router.post("/opportunities", dependencies=[Depends(get_admin)])
def create_opp(body: OpportunityIn, db: Session = Depends(get_db)):
    if body.published and (not body.reviewed_by_human or _needs_qa_block(body)):
        raise HTTPException(
            400,
            "Cannot publish without human review and both age_max and education_required.",
        )
    opp = Opportunity(**body.model_dump())
    db.add(opp)
    db.commit()
    db.refresh(opp)
    if opp.published and opp.reviewed_by_human:
        match_opportunity_to_users(db, opp)
    return OpportunityOut.model_validate(opp)


@router.get("/opportunities/{opp_id}", dependencies=[Depends(get_admin)])
def get_opp(opp_id: UUID, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    return OpportunityOut.model_validate(opp)


@router.put("/opportunities/{opp_id}", dependencies=[Depends(get_admin)])
def update_opp(opp_id: UUID, body: OpportunityIn, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    if body.published and (not body.reviewed_by_human or _needs_qa_block(body)):
        raise HTTPException(
            400,
            "Cannot publish without human review and both age_max and education_required.",
        )
    for k, v in body.model_dump().items():
        setattr(opp, k, v)
    db.commit()
    db.refresh(opp)
    if opp.published and opp.reviewed_by_human:
        match_opportunity_to_users(db, opp)
    return OpportunityOut.model_validate(opp)


@router.post("/opportunities/{opp_id}/approve", dependencies=[Depends(get_admin)])
def approve(opp_id: UUID, db: Session = Depends(get_db), admin: User = Depends(get_admin)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    if not opp.age_max or not opp.education_required:
        raise HTTPException(400, "age_max and education_required are required before approve")
    opp.reviewed_by_human = True
    opp.published = True
    if opp.status == "Upcoming" and opp.apply_start_date:
        from datetime import date

        if opp.apply_start_date <= date.today() <= (opp.apply_end_date or date.today()):
            opp.status = "ApplicationsOpen"
    db.commit()
    match_result = match_opportunity_to_users(db, opp, force_notify=True)
    return {
        "ok": True,
        "id": str(opp.id),
        "matched": match_result["matched"],
        "notified_telegram": match_result["notified_telegram"],
        "notified_email": match_result["notified_email"],
        "recipients": match_result["recipients"],
    }


@router.post("/opportunities/{opp_id}/reject", dependencies=[Depends(get_admin)])
def reject(opp_id: UUID, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    opp.published = False
    opp.reviewed_by_human = False
    db.commit()
    return {"ok": True}


@router.delete("/opportunities/{opp_id}", dependencies=[Depends(get_admin)])
def delete_opportunity(opp_id: UUID, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    db.delete(opp)
    db.commit()
    return {"ok": True, "deleted_id": str(opp_id)}


@router.post("/opportunities/{opp_id}/verify-llm", dependencies=[Depends(get_admin)])
def verify_opportunity_llm(opp_id: UUID, db: Session = Depends(get_db)):
    from app.extraction import verify_and_fill_with_llm

    opp = db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Not found")
    current_data = {
        "canonical_title": opp.canonical_title,
        "org_name": opp.org_name,
        "education_required": opp.education_required,
        "stream_required": opp.stream_required,
        "age_min": opp.age_min,
        "age_max": opp.age_max,
        "age_cutoff_date": str(opp.age_cutoff_date) if opp.age_cutoff_date else None,
        "apply_start_date": str(opp.apply_start_date) if opp.apply_start_date else None,
        "apply_end_date": str(opp.apply_end_date) if opp.apply_end_date else None,
        "exam_date": str(opp.exam_date) if opp.exam_date else None,
        "fee_structure": opp.fee_structure,
        "domain": opp.domain,
        "sector": opp.sector,
    }
    result = verify_and_fill_with_llm(opp.raw_notification_text or "", current_data)
    return result


@router.post("/extract", dependencies=[Depends(get_admin)])
def extract(body: ExtractRequest):
    data, confidence, needs_review, evidence = extract_fields(body.raw_text)
    return {
        "extracted": data,
        "extraction_confidence": confidence,
        "needs_human_review": needs_review,
        "evidence": evidence,
        "provider": (evidence or {}).get("_provider"),
    }


@router.post("/extract/verify", dependencies=[Depends(get_admin)])
def extract_verify(body: dict):
    from app.extraction import verify_and_fill_with_llm

    raw_text = body.get("raw_text", "")
    current_fields = body.get("current_fields", {})
    return verify_and_fill_with_llm(raw_text, current_fields)


@router.get("/llm-status", dependencies=[Depends(get_admin)])
def llm_status():
    from app.config import settings

    has_gemini = bool(settings.gemini_api_key)
    has_anthropic = bool(settings.anthropic_api_key)
    active_provider = "gemini" if has_gemini else "anthropic" if has_anthropic else "heuristic"
    return {
        "active_provider": active_provider,
        "has_gemini": has_gemini,
        "has_anthropic": has_anthropic,
        "gemini_model": settings.gemini_model,
    }


@router.post("/purge-junk", dependencies=[Depends(get_admin)])
def purge_junk(db: Session = Depends(get_db)):
    from app.scrapers import purge_listing_junk

    removed = purge_listing_junk(db)
    return {"ok": True, "purged_count": removed}


@router.post("/extract/search", dependencies=[Depends(get_admin)])
def extract_search(body: ExtractRequest):
    return search_notification(body.raw_text, body.query)


@router.post("/scrape", dependencies=[Depends(get_admin)])
def trigger_scrape(source: str = "all", limit: int = 8, db: Session = Depends(get_db)):
    from app.scrapers import ingest_scraped_records

    stats = ingest_scraped_records(db, source=source, limit=limit)
    return {"ok": True, "stats": stats}


