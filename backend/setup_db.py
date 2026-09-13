"""
AvsarDoot — Supabase Database Setup Script
==========================================
Run this once to:
  1. Test the database connection
  2. Create all tables (users, user_profiles, opportunities, matches)
  3. Seed sample Banking / SSC / PSC / Railway / PSU opportunities
  4. Create the default admin user

Usage:
    cd d:\\AvsarDoot\\backend
    .venv\\Scripts\\activate
    python setup_db.py
"""

import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date

print("\n" + "=" * 60)
print("  AvsarDoot — Supabase Database Setup")
print("=" * 60)

# ─── Step 1: Load config & check DATABASE_URL ─────────────────
print("\n[1/5] Loading configuration...")
try:
    from app.config import settings
    db_url = settings.database_url
    if "supabase" in db_url or "postgresql" in db_url:
        # Mask password for display
        parts = db_url.split("@")
        safe_url = parts[0].split(":")[0] + ":***@" + parts[1] if "@" in db_url else db_url
        print(f"      DATABASE_URL : {safe_url}")
        print(f"      Driver       : PostgreSQL / psycopg v3")
    elif "sqlite" in db_url:
        print(f"      DATABASE_URL : {db_url}")
        print("      ⚠️  Still using SQLite — update DATABASE_URL in .env to Supabase first!")
        sys.exit(1)
    else:
        print(f"      DATABASE_URL : {db_url}")
    print("      ✓ Config loaded")
except Exception as e:
    print(f"      ✗ Config error: {e}")
    sys.exit(1)

# ─── Step 2: Test connection ───────────────────────────────────
print("\n[2/5] Testing database connection...")
try:
    from sqlalchemy import text
    from app.db import engine

    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        short_version = version.split(",")[0]  # e.g. "PostgreSQL 15.1"
        print(f"      ✓ Connected! Server: {short_version}")
except Exception as e:
    print(f"      ✗ Connection FAILED: {e}")
    print("\n  Common fixes:")
    print("  - Make sure your Supabase project is not paused")
    print("  - Verify DATABASE_URL in .env uses postgresql+psycopg://")
    print("  - Check your internet connection (run: ping db.xxx.supabase.co)")
    sys.exit(1)

# ─── Step 3: Create all tables ────────────────────────────────
print("\n[3/5] Creating database schema (tables)...")
try:
    from app.db import Base, engine
    # Import all models to register them with Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # List tables that now exist
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]

    print(f"      ✓ Schema created. Tables in database:")
    for t in tables:
        print(f"        • {t}")
except Exception as e:
    print(f"      ✗ Schema creation failed: {e}")
    sys.exit(1)

# ─── Step 4: Create admin user ────────────────────────────────
print("\n[4/5] Creating admin user...")
try:
    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_password

    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.email == settings.admin_email.lower()).first()
        if existing_admin:
            print(f"      ⚠️  Admin already exists: {settings.admin_email}")
        else:
            admin = User(
                email=settings.admin_email.lower(),
                hashed_password=hash_password(settings.admin_password),
                role="admin",
                subscription_tier="premium",
            )
            db.add(admin)
            db.commit()
            print(f"      ✓ Admin created: {settings.admin_email} / {settings.admin_password}")
    finally:
        db.close()
except Exception as e:
    print(f"      ✗ Admin creation failed: {e}")
    sys.exit(1)

# ─── Step 5: Seed sample opportunities ───────────────────────
print("\n[5/5] Seeding sample opportunities...")
try:
    from app.models import Opportunity

    SEED = [
        {
            "canonical_title": "IBPS CRP PO/MT-XVI 2026",
            "org_name": "Institute of Banking Personnel Selection",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "Banking",
            "education_required": ["Any Graduate", "Graduate"],
            "stream_required": None,
            "min_percentage": None,
            "age_min": 20,
            "age_max": 30,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5, "PwD": 10},
            "age_cutoff_date": date(2026, 8, 1),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "category_vacancies": {"General": 1400, "OBC": 900, "SC": 500, "ST": 250, "EWS": 350},
            "notified_at": date(2026, 7, 1),
            "apply_start_date": date(2026, 8, 1),
            "apply_end_date": date(2026, 9, 21),
            "exam_date": date(2026, 10, 18),
            "exam_stage": "Prelims",
            "status": "ApplicationsOpen",
            "fee_structure": {"General": 850, "OBC": 850, "SC": 175, "ST": 175},
            "primary_source_url": "https://www.ibps.in/",
            "raw_notification_text": "IBPS invites online applications for CRP PO/MT-XVI. Graduation in any discipline. Age 20-30 as on 01.08.2026.",
            "extraction_confidence": 1.0,
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "SBI Clerk (Junior Associate) 2026",
            "org_name": "State Bank of India",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "Banking",
            "education_required": ["Any Graduate", "Graduate"],
            "age_min": 20,
            "age_max": 28,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5, "PwD": 10},
            "age_cutoff_date": date(2026, 4, 1),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "category_vacancies": {"General": 2000, "OBC": 1200, "SC": 700, "ST": 350, "EWS": 500},
            "apply_start_date": date(2026, 4, 1),
            "apply_end_date": date(2026, 9, 10),
            "exam_date": date(2026, 11, 2),
            "exam_stage": "Prelims",
            "status": "ClosingSoon",
            "fee_structure": {"General": 750, "OBC": 750, "SC": 125, "ST": 125},
            "primary_source_url": "https://sbi.co.in/web/careers",
            "raw_notification_text": "SBI Junior Associate recruitment. Graduation required. Age 20-28.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "SSC Combined Graduate Level (CGL) 2026",
            "org_name": "Staff Selection Commission",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "SSC",
            "education_required": ["Any Graduate", "Graduate", "B.A.", "B.Sc", "B.Com"],
            "age_min": 18,
            "age_max": 32,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5, "PwD": 10},
            "age_cutoff_date": date(2026, 8, 1),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "category_vacancies": {"General": 4000, "OBC": 2500, "SC": 1400, "ST": 700, "EWS": 900},
            "apply_start_date": date(2026, 6, 24),
            "apply_end_date": date(2026, 9, 25),
            "exam_date": date(2026, 12, 5),
            "exam_stage": "Prelims",
            "status": "ApplicationsOpen",
            "fee_structure": {"General": 100, "OBC": 100, "SC": 0, "ST": 0},
            "primary_source_url": "https://ssc.gov.in/",
            "raw_notification_text": "SSC CGL 2026. Bachelor's degree from a recognised university. Age 18-32.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "RRB NTPC Graduate 2026",
            "org_name": "Railway Recruitment Board",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "Railway",
            "education_required": ["Any Graduate", "Graduate"],
            "age_min": 18,
            "age_max": 33,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5},
            "age_cutoff_date": date(2026, 7, 1),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "category_vacancies": {"General": 3500, "OBC": 2200, "SC": 1200, "ST": 600, "EWS": 800},
            "apply_start_date": date(2026, 7, 15),
            "apply_end_date": date(2026, 10, 14),
            "exam_stage": "CBT-1",
            "status": "ApplicationsOpen",
            "fee_structure": {"General": 500, "OBC": 500, "SC": 250, "ST": 250},
            "primary_source_url": "https://indianrailways.gov.in/",
            "raw_notification_text": "RRB NTPC graduate posts. Age 18-33.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "UPPSC Combined State / Upper Subordinate Services 2026",
            "org_name": "Uttar Pradesh Public Service Commission",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "State-PSC",
            "education_required": ["Any Graduate", "Graduate"],
            "age_min": 21,
            "age_max": 40,
            "age_relaxation_rules": {"OBC": 5, "SC": 5, "ST": 5, "PwD": 15},
            "age_cutoff_date": date(2026, 7, 1),
            "gender_restriction": "Any",
            "domicile_required": "Uttar Pradesh",
            "category_vacancies": {"General": 80, "OBC": 50, "SC": 35, "ST": 8, "EWS": 20},
            "apply_start_date": date(2026, 6, 1),
            "apply_end_date": date(2026, 9, 18),
            "exam_date": date(2026, 12, 20),
            "exam_stage": "Prelims",
            "status": "ApplicationsOpen",
            "fee_structure": {"General": 125, "OBC": 125, "SC": 65, "ST": 65},
            "primary_source_url": "https://uppsc.up.nic.in/",
            "raw_notification_text": "UPPSC PCS 2026. Graduation. Domicile of Uttar Pradesh required. Age 21-40.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "UPSC Civil Services (Prelims) 2027",
            "org_name": "Union Public Service Commission",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "UPSC-CSE",
            "education_required": ["Any Graduate", "Graduate"],
            "age_min": 21,
            "age_max": 32,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5, "PwD": 10},
            "age_cutoff_date": date(2027, 8, 1),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "apply_start_date": date(2027, 2, 1),
            "apply_end_date": date(2027, 3, 21),
            "exam_date": date(2027, 5, 24),
            "exam_stage": "Prelims",
            "status": "Upcoming",
            "fee_structure": {"General": 100, "OBC": 100, "SC": 0, "ST": 0},
            "primary_source_url": "https://upsc.gov.in/",
            "raw_notification_text": "UPSC CSE Prelims 2027. Degree from a recognised university.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "RBI Grade B Officers 2026",
            "org_name": "Reserve Bank of India",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "Banking",
            "education_required": ["Graduate", "Postgraduate", "Any Graduate"],
            "min_percentage": 60,
            "age_min": 21,
            "age_max": 30,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5},
            "age_cutoff_date": date(2026, 5, 1),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "apply_start_date": date(2026, 5, 1),
            "apply_end_date": date(2026, 9, 12),
            "exam_stage": "Phase-I",
            "status": "ClosingSoon",
            "fee_structure": {"General": 850, "OBC": 850, "SC": 100, "ST": 100},
            "primary_source_url": "https://opportunities.rbi.org.in/",
            "raw_notification_text": "RBI Grade B. Minimum 60% in graduation. Age 21-30.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "IOCL Graduate Engineer Trainee 2026",
            "org_name": "Indian Oil Corporation Limited",
            "sector": "PSU",
            "opportunity_type": "Job",
            "domain": "Engineering",
            "education_required": ["B.Tech", "B.E."],
            "stream_required": ["Computer Science", "IT", "Electrical", "Mechanical", "Chemical"],
            "min_percentage": 65,
            "age_min": 18,
            "age_max": 26,
            "age_relaxation_rules": {"OBC": 3, "SC": 5, "ST": 5},
            "age_cutoff_date": date(2026, 6, 30),
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "apply_start_date": date(2026, 8, 1),
            "apply_end_date": date(2026, 9, 22),
            "exam_stage": "GATE",
            "status": "ApplicationsOpen",
            "fee_structure": {"General": 0, "OBC": 0, "SC": 0, "ST": 0},
            "primary_source_url": "https://iocl.com/latest-job-opening",
            "raw_notification_text": "IOCL GET through GATE. B.E./B.Tech in specified branches. 65% marks.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "NTA UGC-NET December 2026",
            "org_name": "National Testing Agency",
            "sector": "Govt",
            "opportunity_type": "Admission",
            "domain": "Teaching",
            "education_required": ["Postgraduate", "M.A.", "M.Sc", "M.Com", "M.Tech"],
            "min_percentage": 55,
            "age_min": None,
            "age_max": None,
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "apply_start_date": date(2026, 9, 1),
            "apply_end_date": date(2026, 10, 10),
            "exam_date": date(2026, 12, 15),
            "exam_stage": "Single-Stage",
            "status": "Upcoming",
            "fee_structure": {"General": 1150, "OBC": 600, "SC": 325, "ST": 325},
            "primary_source_url": "https://ugcnet.nta.ac.in/",
            "raw_notification_text": "UGC NET. Master's degree with 55%.",
            "reviewed_by_human": True,
            "published": True,
        },
        {
            "canonical_title": "Delhi Police Constable 2026 (draft — awaiting QA)",
            "org_name": "Staff Selection Commission",
            "sector": "Govt",
            "opportunity_type": "Job",
            "domain": "Police",
            "education_required": None,
            "age_min": 18,
            "age_max": None,
            "gender_restriction": "Any",
            "domicile_required": "Any",
            "physical_standards": {"height_male_cm": 170, "height_female_cm": 157},
            "apply_end_date": date(2026, 10, 5),
            "status": "Upcoming",
            "primary_source_url": "https://ssc.gov.in/",
            "raw_notification_text": "Draft extraction missing age_max and education — must stay in QA queue.",
            "extraction_confidence": 0.3,
            "reviewed_by_human": False,
            "published": False,
        },
    ]

    db = SessionLocal()
    try:
        existing_count = db.query(Opportunity).count()
        if existing_count > 0:
            print(f"      ⚠️  {existing_count} opportunities already exist — skipping seed to avoid duplicates.")
        else:
            for row in SEED:
                db.add(Opportunity(**row))
            db.commit()
            print(f"      ✓ Seeded {len(SEED)} sample opportunities")
    finally:
        db.close()

except Exception as e:
    print(f"      ✗ Seeding failed: {e}")
    sys.exit(1)

# ─── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  ✅  Database Setup Complete!")
print("=" * 60)
print("""
  Tables created  : users, user_profiles, opportunities, matches
  Admin account   : admin@avsardoot.local / admin123
  Sample data     : 10 opportunities seeded

  Next steps:
  ─────────────────────────────────────────────
  1. Start backend:
       uvicorn app.main:app --reload --port 8000

  2. Start frontend (in another terminal):
       cd ../frontend && npm run dev

  3. Open app:    http://localhost:3000
     API docs:    http://localhost:8000/docs
     Admin panel: http://localhost:3000/admin
""")
