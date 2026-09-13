from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.matching import is_eligible
from app.models import Match, Opportunity, User, UserProfile
from app.notifications import match_email, send_email


OPEN_STATUSES = {"Upcoming", "ApplicationsOpen", "ClosingSoon", "AdmitCardOut"}


def _days_left(end: date | None) -> int | None:
    if not end:
        return None
    return (end - date.today()).days


def _interest_overlap(profile: UserProfile, opp: Opportunity) -> bool:
    sectors = profile.sector_interest or []
    domains = profile.domain_interest or []
    if sectors and opp.sector not in sectors:
        return False
    if not domains:
        return True
    if not opp.domain or opp.domain in ("Other", "General", None):
        return True
    if opp.domain in domains:
        return True
    # If candidate is interested in Govt/PSU and the opportunity is Govt/PSU,
    # allow recruitment domains (Railway, SSC, Banking, State-PSC, Police, UPSC, Defence) to match
    if opp.sector in ("Govt", "PSU") and any(s in ("Govt", "PSU") for s in sectors):
        return True
    return False


def upsert_match(
    db: Session,
    user: User,
    profile: UserProfile,
    opp: Opportunity,
    notify: bool,
    force_notify: bool = False,
) -> tuple[Match | None, dict]:
    ok, reasons = is_eligible(profile, opp)
    existing = (
        db.query(Match)
        .filter(Match.user_id == user.id, Match.opportunity_id == opp.id)
        .one_or_none()
    )
    if not ok:
        if existing and existing.user_action != "dismissed":
            db.delete(existing)
        return None, {"sent": False}
    if existing:
        existing.match_reasons = reasons
        match = existing
    else:
        match = Match(user_id=user.id, opportunity_id=opp.id, match_reasons=reasons)
        db.add(match)
        db.flush()

    channels = profile.notification_channels or ["email"]
    # Always include telegram if the user has linked their account
    if getattr(profile, "telegram_chat_id", None) and "telegram" not in channels:
        channels = list(channels) + ["telegram"]

    dispatched = {"sent": False, "telegram": False, "email": False}
    should_send = notify and (force_notify or not match.notified)
    if should_send:
        from app.notifications import dispatch_match_notifications

        tg_chat = getattr(profile, "telegram_chat_id", None)
        dispatch_match_notifications(
            user_email=user.email,
            user_phone=getattr(profile, "phone_number", None),
            user_telegram_chat_id=tg_chat,
            channels=channels,
            title=opp.canonical_title,
            reasons=reasons,
            apply_end=opp.apply_end_date,
            official_url=opp.primary_source_url,
            days_left=_days_left(opp.apply_end_date),
        )
        match.notified = True
        match.notified_at = datetime.now(timezone.utc)
        dispatched["sent"] = True
        dispatched["telegram"] = bool(tg_chat and "telegram" in channels)
        dispatched["email"] = bool(user.email and "email" in channels)
    return match, dispatched




def match_opportunity_to_users(db: Session, opp: Opportunity, force_notify: bool = False) -> dict:
    import logging
    log = logging.getLogger("avsardoot")

    if not opp.published or not opp.reviewed_by_human:
        return {"matched": 0, "notified_telegram": 0, "notified_email": 0, "recipients": []}

    recipients = []
    profiles = db.query(UserProfile).all()
    log.info("Matching '%s' against %d user profiles (force_notify=%s)", opp.canonical_title, len(profiles), force_notify)

    for profile in profiles:
        if not _interest_overlap(profile, opp):
            continue
        user = db.get(User, profile.user_id)
        if not user or not user.is_active:
            continue

        channels = profile.notification_channels or ["email"]
        if getattr(profile, "telegram_chat_id", None) and "telegram" not in channels:
            channels = list(channels) + ["telegram"]

        match, dispatched = upsert_match(db, user, profile, opp, notify=True, force_notify=force_notify)
        if match:
            has_telegram = bool(getattr(profile, "telegram_chat_id", None))
            recipients.append({
                "email": user.email,
                "telegram": has_telegram,
                "telegram_chat_id": getattr(profile, "telegram_chat_id", None),
                "channels": channels,
                "notified": match.notified,
                "reasons": match.match_reasons or [],
                "telegram_dispatched": dispatched["telegram"],
            })
            log.info("  ✅ Matched %s | telegram=%s | notified=%s | tg_dispatched=%s", user.email, has_telegram, match.notified, dispatched["telegram"])

    db.commit()
    notified_tg = sum(1 for r in recipients if r["telegram"] and (r["notified"] or r.get("telegram_dispatched")))
    notified_email = sum(1 for r in recipients if "email" in r["channels"] and r["notified"])
    log.info("Done: %d matched, %d telegram, %d email for '%s'", len(recipients), notified_tg, notified_email, opp.canonical_title)
    return {
        "matched": len(recipients),
        "notified_telegram": notified_tg,
        "notified_email": notified_email,
        "recipients": recipients,
    }





def match_profile_to_opportunities(db: Session, user: User, profile: UserProfile) -> int:
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.published.is_(True), Opportunity.reviewed_by_human.is_(True))
        .filter(Opportunity.status.in_(list(OPEN_STATUSES)))
        .all()
    )
    count = 0
    for opp in opps:
        m, _ = upsert_match(db, user, profile, opp, notify=True)
        if m:
            count += 1
    db.commit()
    return count


def refresh_closing_soon(db: Session) -> None:
    today = date.today()
    opps = db.query(Opportunity).filter(Opportunity.published.is_(True)).all()
    for opp in opps:
        if opp.status in ("Closed", "ResultDeclared"):
            continue
        if opp.apply_end_date and opp.apply_end_date < today:
            opp.status = "Closed"
        elif opp.apply_end_date and 0 <= (opp.apply_end_date - today).days <= 5:
            opp.status = "ClosingSoon"
        elif opp.apply_start_date and opp.apply_start_date <= today <= (opp.apply_end_date or today):
            if opp.status not in ("AdmitCardOut", "ResultDeclared"):
                opp.status = "ApplicationsOpen"
    db.commit()
