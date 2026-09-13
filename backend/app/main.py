import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine, migrate_schema
from app.models import Match, Opportunity, User  # registers all tables with Base.metadata
from app.notifications import send_email
from app.routers import admin, auth, opportunities, profile, subscription, telegram
from app.security import hash_password

log = logging.getLogger("avsardoot")
logging.basicConfig(level=logging.INFO)
scheduler = BackgroundScheduler()

# Run schema migration now that all models are registered
try:
    migrate_schema()
except Exception as _me:
    log.warning("migrate_schema failed: %s", _me)


def ensure_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.admin_email.lower()).first()
        if not existing:
            db.add(
                User(
                    email=settings.admin_email.lower(),
                    hashed_password=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            db.commit()
            log.info("Created admin user %s", settings.admin_email)
    finally:
        db.close()


def deadline_job():
    db: Session = SessionLocal()
    try:
        today = date.today()
        opps = db.query(Opportunity).filter(Opportunity.published.is_(True)).all()
        for opp in opps:
            if opp.apply_end_date and opp.apply_end_date < today and opp.status not in ("Closed", "ResultDeclared"):
                opp.status = "Closed"
            elif (
                opp.apply_end_date
                and 0 <= (opp.apply_end_date - today).days <= 5
                and opp.status not in ("Closed", "ResultDeclared")
            ):
                opp.status = "ClosingSoon"
        matches = db.query(Match).filter(Match.user_action != "dismissed").all()
        for m in matches:
            opp = db.get(Opportunity, m.opportunity_id)
            user = db.get(User, m.user_id)
            if not opp or not user or not opp.apply_end_date:
                continue
            days = (opp.apply_end_date - today).days
            if days == 5 and not m.reminder_t5_sent:
                send_email(
                    user.email,
                    f"Reminder: {opp.canonical_title} closes in 5 days",
                    f"Apply by {opp.apply_end_date}. Official: {opp.primary_source_url}",
                )
                m.reminder_t5_sent = True
            if days == 1 and not m.reminder_t1_sent:
                send_email(
                    user.email,
                    f"Last day tomorrow: {opp.canonical_title}",
                    f"Apply by {opp.apply_end_date}. Official: {opp.primary_source_url}",
                )
                m.reminder_t1_sent = True
        db.commit()
    except Exception:
        log.exception("deadline_job failed")
        db.rollback()
    finally:
        db.close()


def scraper_job():
    db: Session = SessionLocal()
    try:
        from app.scrapers import ingest_scraped_records

        res = ingest_scraped_records(db, source="all")
        log.info("Periodic scraper_job finished: %s", res)
    except Exception:
        log.exception("scraper_job failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    ensure_admin()
    scheduler.add_job(deadline_job, "interval", hours=6, id="deadlines", replace_existing=True)
    scheduler.add_job(scraper_job, "interval", hours=12, id="scrapers", replace_existing=True)
    # Telegram polling — runs every 6 seconds to process bot messages locally
    if settings.telegram_bot_token:
        from app.routers.telegram import telegram_poll_job
        scheduler.add_job(
            telegram_poll_job,
            "interval",
            seconds=6,
            id="telegram_poll",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        log.info("Telegram polling started for bot @%s", settings.telegram_bot_username)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)



app = FastAPI(
    title="AvsarDoot API",
    description="Opportunity matching platform — filtering and alerts only, not a recruiting authority.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(opportunities.router)
app.include_router(admin.router)
app.include_router(subscription.router)
app.include_router(telegram.router)


@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}
