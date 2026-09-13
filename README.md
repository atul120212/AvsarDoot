# AvsarDoot

Subscription-style **opportunity matching** for jobs and admissions in India. Users fill an eligibility profile once; the system surfaces only opportunities they qualify for, always linking to the **official** notification.

This product does **not** host applications and is **not** a recruiting authority.

Phase 1 (this repo): schema, matching engine, onboarding, feed, detail pages, email-ready notifications, admin QA + manual curation, sample Banking / SSC / State-PSC data.

Phase 2 stubs: scraper adapters and LLM extraction endpoint (`POST /admin/extract`).

## Quick start (local, SQLite)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

- Admin: `admin@avsardoot.local` / `admin123`
- Register a user, complete onboarding, then open **Feed**

## Docker

```bash
docker compose up --build
```

Set `DATABASE_URL` in `backend/.env` to the Postgres URL from `docker-compose.yml`, then run seed against that database.

## What is implemented

| Spec section | Status |
|---|---|
| 3 Data model (`opportunities`, `user_profiles`, `matches`) | Done |
| 5 Matching engine (education, stream, age+relaxation, gender, domicile, certs, prerequisites, experience) | Done |
| 6 Email notifications + T-5 / T-1 reminders (SMTP optional; logs if unset) | Done |
| 7 Feed, detail (fixed 8 sections), badges, multi-step onboarding | Done |
| 4.6 Admin QA (side-by-side raw text vs fields, approve/reject) | Done |
| 4 Scrapers | Adapter stubs only |
| 9 Disclaimer + official CTA | Done |

## API

- `POST /auth/register` `POST /auth/login`
- `GET/PUT /profile` — saving a profile re-runs matching
- `GET /feed` `GET /opportunities/{id}`
- `GET/POST/PUT /admin/opportunities` `POST /admin/opportunities/{id}/approve|reject`
- `POST /admin/extract`

## Privacy

Date of birth and category are stored for matching only. Enable disk encryption / managed Postgres at rest in production. Do not commit real `.env` secrets. Configure `SECRET_KEY` before any real users.
