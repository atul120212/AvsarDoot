"""Source adapters: fetch only single-notification pages, extract into QA (never auto-publish)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx


try:
    from rapidfuzz import fuzz
except ImportError:
    class FuzzFallback:
        @staticmethod
        def token_sort_ratio(s1: str, s2: str) -> float:
            import difflib
            w1 = " ".join(sorted((s1 or "").lower().split()))
            w2 = " ".join(sorted((s2 or "").lower().split()))
            return difflib.SequenceMatcher(None, w1, w2).ratio() * 100
    fuzz = FuzzFallback()

from sqlalchemy.orm import Session

from app.config import settings
from app.extraction import extract_fields
from app.listing_filters import is_hub_content, is_listing_title, is_listing_url, looks_like_notification_title
from app.models import Opportunity

log = logging.getLogger("avsardoot")

UA = {"User-Agent": "AvsarDootBot/1.1 (eligibility-matching; +https://avsardoot.local)"}
AGGREGATOR_HOSTS = ("sarkariresult.com", "freejobalert.com", "sarkarinaukri.com", "rojgarresult.com")


def strip_html(html: str) -> str:
    if not html:
        return ""
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def parse_date_str(val: Any) -> date | None:
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            d = datetime.strptime(val, fmt).date()
            if d.year < 100:
                d = d.replace(year=2000 + d.year)
            return d
        except ValueError:
            pass
    return None


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def pick_official_url(html: str, page_url: str, extracted_url: str | None) -> tuple[str, list[dict[str, str]]]:
    """Prefer recruiting-body URL; keep aggregator URL as alt source."""
    found: list[str] = []
    if extracted_url:
        found.append(extracted_url)

    # First check links specifically with informative anchor labels like "Official Website", "Apply Online"
    labeled_matches = re.findall(r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>([^<]+)</a>', html, re.I)
    for href, label in labeled_matches:
        host = urlparse(href).netloc.lower()
        if any(a in host for a in AGGREGATOR_HOSTS) or any(bad in host for bad in ("facebook.com", "twitter.com", "t.me", "whatsapp.com", "youtube.com", "instagram.com")):
            continue
        l_text = label.lower()
        if any(k in l_text for k in ("official website", "apply online", "official site", "click here to apply", "registration")):
            if href not in found:
                found.insert(0, href)

    for href in re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.I):
        host = urlparse(href).netloc.lower()
        if any(a in host for a in AGGREGATOR_HOSTS):
            continue
        if any(bad in host for bad in ("facebook.com", "twitter.com", "t.me", "whatsapp.com", "youtube.com", "instagram.com")):
            continue
        if href not in found:
            found.append(href)

    official = None
    for href in found:
        host = urlparse(href).netloc.lower()
        if host.endswith(".gov.in") or host.endswith(".nic.in") or ".gov.in" in host or ".nic.in" in host:
            official = href
            break
    if not official:
        for href in found:
            host = urlparse(href).netloc.lower()
            if any(k in host for k in ("ssc.gov", "upsc.gov", "ibps.in", "sbi.co.in", "rbi.org", "indianrailways", "nta.ac.in", "pgimer.edu.in", "aiims")):
                official = href
                break
    if not official and found:
        official = found[0]
    primary = official or page_url
    alts = [{"source": urlparse(page_url).netloc, "url": page_url}]
    return primary, alts


def extract_main_html(html: str) -> str:
    for pat in (
        r'(?is)<article[^>]*>(.*)</article>',
        r'(?is)<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*)</div>',
        r'(?is)<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*)</div>',
    ):
        m = re.search(pat, html)
        if m and len(strip_html(m.group(1))) > 400:
            return m.group(1)
    return html


@dataclass
class RawPage:
    url: str
    html: str
    fetched_at: datetime
    title: str = ""


@dataclass
class RawRecord:
    source: str
    source_url: str
    title: str
    raw_text: str
    html: str = ""
    pdf_url: str | None = None
    posted_date: str | None = None


class BaseAdapter(ABC):
    source_name: str

    @abstractmethod
    def fetch(self, limit: int = 8) -> list[RawPage]:
        ...

    def parse(self, page: RawPage) -> RawRecord:
        main = extract_main_html(page.html)
        raw_text = strip_html(main)
        pdf_url = None
        pdf_match = re.search(r'href="(https?://[^"]+\.pdf)"', page.html, re.I)
        if pdf_match:
            pdf_url = pdf_match.group(1)
        title = page.title
        if not title:
            t_match = re.search(r"<title>(.*?)</title>", page.html, re.I)
            title = strip_html(t_match.group(1)) if t_match else "Notification"
        title = re.sub(r"\s*[|\-–]\s*SARKARI RESULT.*", "", title, flags=re.I).strip()
        title = re.sub(r"\s*[|\-–]\s*FreeJobAlert.*", "", title, flags=re.I).strip()
        return RawRecord(
            source=self.source_name,
            source_url=page.url,
            title=title,
            raw_text=raw_text,
            html=page.html,
            pdf_url=pdf_url,
        )


def _get(url: str, timeout: float = 20) -> httpx.Response:
    return httpx.get(url, headers=UA, timeout=timeout, follow_redirects=True)


class SarkariResultAdapter(BaseAdapter):
    source_name = "sarkariresult"

    def fetch(self, limit: int = 8) -> list[RawPage]:
        pages: list[RawPage] = []
        now = datetime.now(timezone.utc)
        candidates: list[tuple[str, str]] = []

        try:
            api_url = "https://www.sarkariresult.com/wp-json/wp/v2/posts?per_page=20"
            resp = _get(api_url)
            if resp.status_code == 200:
                for p in resp.json():
                    url = p.get("link") or ""
                    title = strip_html(p.get("title", {}).get("rendered", ""))
                    if is_listing_url(url) or is_listing_title(title):
                        continue
                    if not looks_like_notification_title(title) and not re.search(r"/20\d{2}/", url):
                        continue
                    candidates.append((url, title))
        except Exception as ex:
            log.warning("SarkariResult WP API fetch failed: %s", ex)

        if len(candidates) < limit:
            try:
                resp = _get("https://www.sarkariresult.com/latestjob/")
                if resp.status_code == 200:
                    # Only match URLs with a year path segment (/2025/, /2026/) or
                    # known sub-categories like /railway/, /bank/, etc.
                    VALID_PATH = re.compile(
                        r'sarkariresult\.com/(?:20\d{2}|railway|bank|police|defence|teaching|psu|state)/',
                        re.I,
                    )
                    matches = re.findall(
                        r'href="(https?://www\.sarkariresult\.com/[^"]+)"[^>]*>([^<]{12,160})</a>',
                        resp.text,
                    )
                    for link_url, link_text in matches:
                        if not VALID_PATH.search(link_url):
                            continue
                        title = strip_html(link_text)
                        if is_listing_url(link_url) or is_listing_title(title):
                            continue
                        candidates.append((link_url, title))
            except Exception as ex:
                log.warning("SarkariResult HTML listing failed: %s", ex)


        seen = set()
        for url, title in candidates:
            key = url.rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                time.sleep(0.6)
                detail = _get(url)
                if detail.status_code != 200:
                    continue
                if is_listing_url(str(detail.url)) or is_listing_title(title):
                    continue
                if is_hub_content(detail.text):
                    log.info("Skipping hub page content for %s", detail.url)
                    continue
                pages.append(RawPage(url=str(detail.url), html=detail.text, fetched_at=now, title=title))
            except Exception as ex:
                log.warning("Failed to fetch detail %s: %s", url, ex)
            if len(pages) >= limit:
                break
        return pages


class FreeJobAlertAdapter(BaseAdapter):
    source_name = "freejobalert"

    def fetch(self, limit: int = 8) -> list[RawPage]:
        pages: list[RawPage] = []
        now = datetime.now(timezone.utc)
        listing_url = "https://www.freejobalert.com/government-jobs/"
        try:
            resp = _get(listing_url)
            if resp.status_code != 200:
                return pages
            arts = re.findall(r'href="(https://www\.freejobalert\.com/articles/[^"]+)"', resp.text)
            unique_urls = []
            for art_url in arts:
                if is_listing_url(art_url):
                    continue
                if art_url not in unique_urls:
                    unique_urls.append(art_url)
            for art_url in unique_urls:
                try:
                    time.sleep(1.05)  # robots.txt crawl-delay: 1
                    detail = _get(art_url)
                    if detail.status_code != 200:
                        continue
                    t_match = re.search(r"<title>(.*?)</title>", detail.text, re.I)
                    title = strip_html(t_match.group(1)) if t_match else ""
                    if is_listing_title(title) or not looks_like_notification_title(title):
                        if "recruitment" not in (title or "").lower() and "notification" not in (title or "").lower():
                            continue
                    if is_hub_content(detail.text):
                        continue
                    pages.append(RawPage(url=str(detail.url), html=detail.text, fetched_at=now, title=title))
                except Exception as ex:
                    log.warning("FreeJobAlert detail fetch failed %s: %s", art_url, ex)
                if len(pages) >= limit:
                    break
        except Exception as ex:
            log.warning("FreeJobAlert listing fetch failed: %s", ex)
        return pages


ADAPTERS = {
    "sarkariresult": SarkariResultAdapter,
    "freejobalert": FreeJobAlertAdapter,
}


def _find_duplicate(db: Session, title: str, org: str | None, source_url: str) -> Opportunity | None:
    by_url = db.query(Opportunity).filter(Opportunity.primary_source_url == source_url).first()
    if by_url:
        return by_url
    # aggregator URL stored as alt
    all_opps = db.query(Opportunity).all()
    for opp in all_opps:
        alts = opp.alt_sources or []
        if any(isinstance(a, dict) and a.get("url") == source_url for a in alts):
            return opp
        score = fuzz.token_sort_ratio((title or "").lower(), (opp.canonical_title or "").lower())
        if score >= 92 and (not org or not opp.org_name or org.lower()[:12] in (opp.org_name or "").lower()):
            return opp
    return None


def purge_listing_junk(db: Session) -> int:
    """Drop unreviewed hub/category pages that were ingested by older scrapers."""
    removed = 0
    pending = db.query(Opportunity).filter(Opportunity.reviewed_by_human.is_(False), Opportunity.published.is_(False)).all()
    for opp in pending:
        title_low = (opp.canonical_title or "").strip().lower()
        url = (opp.primary_source_url or "").lower()
        is_junk = (
            is_listing_url(opp.primary_source_url)
            or is_listing_title(opp.canonical_title)
            or is_hub_content(opp.raw_notification_text or "")
            or title_low in {
                "admit card",
                "admit cards",
                "latest job",
                "latest jobs",
                "results",
                "result",
                "admission",
                "admissions",
                "up scholarship",
                "scholarship",
                "syllabus",
                "answer key",
                "answer keys",
            }
            or any(h in url for h in ("/admitcard", "/latestjob", "/result", "/admission", "/upscholarship", "/scholarship"))
        )
        if is_junk:
            db.delete(opp)
            removed += 1
    if removed:
        db.commit()
    return removed


def ingest_scraped_records(db: Session, source: str = "all", limit: int = 8) -> dict[str, Any]:
    selected = ADAPTERS if source == "all" else {k: v for k, v in ADAPTERS.items() if k == source}
    scraped_count = 0
    ingested_count = 0
    skipped_count = 0
    skipped_listing = 0
    purged = purge_listing_junk(db)

    per_source = max(3, limit // max(len(selected), 1))

    for source_name, adapter_cls in selected.items():
        adapter = adapter_cls()
        try:
            pages = adapter.fetch(limit=per_source)
        except Exception as ex:
            log.error("Scraper %s fetch failed: %s", source_name, ex)
            continue

        for page in pages:
            scraped_count += 1
            if is_listing_url(page.url) or is_listing_title(page.title):
                skipped_listing += 1
                continue
            try:
                raw_rec = adapter.parse(page)
            except Exception as ex:
                log.error("Parse failed for page %s: %s", page.url, ex)
                continue
            if len(raw_rec.raw_text) < 250:
                skipped_listing += 1
                continue

            extracted, confidence, _, evidence = extract_fields(raw_rec.raw_text)
            if extracted.get("is_single_notification") is False:
                skipped_listing += 1
                continue

            official, alts = pick_official_url(
                raw_rec.html, raw_rec.source_url, extracted.get("official_apply_url")
            )
            title = extracted.get("canonical_title") or raw_rec.title
            org = extracted.get("org_name") or None
            if not org:
                org = "Unknown (needs QA)"

            existing = _find_duplicate(db, title, org, raw_rec.source_url) or _find_duplicate(db, title, org, official)
            if existing:
                skipped_count += 1
                alts_exist = existing.alt_sources or []
                if not any(isinstance(a, dict) and a.get("url") == raw_rec.source_url for a in alts_exist):
                    existing.alt_sources = alts_exist + [{"source": source_name, "url": raw_rec.source_url}]
                existing.last_scraped_at = datetime.now(timezone.utc)
                continue

            opp = Opportunity(
                canonical_title=title,
                org_name=org,
                sector=extracted.get("sector") if extracted.get("sector") in ("Govt", "Private", "PSU") else "Govt",
                opportunity_type=extracted.get("opportunity_type")
                if extracted.get("opportunity_type") in ("Job", "Admission", "Result", "AdmitCard", "AnswerKey")
                else "Job",
                domain=extracted.get("domain") or "Other",
                education_required=extracted.get("education_required"),
                stream_required=extracted.get("stream_required"),
                min_percentage=extracted.get("min_percentage"),
                age_min=extracted.get("age_min"),
                age_max=extracted.get("age_max"),
                age_relaxation_rules=extracted.get("age_relaxation_rules"),
                age_cutoff_date=parse_date_str(extracted.get("age_cutoff_date")),
                gender_restriction=extracted.get("gender_restriction") or "Any",
                domicile_required=extracted.get("domicile_required") or "Any",
                certifications_required=extracted.get("certifications_required"),
                prerequisite_exams=extracted.get("prerequisite_exams"),
                experience_required_years=extracted.get("experience_required_years"),
                category_vacancies=extracted.get("category_vacancies"),
                apply_start_date=parse_date_str(extracted.get("apply_start_date")),
                apply_end_date=parse_date_str(extracted.get("apply_end_date")),
                exam_date=parse_date_str(extracted.get("exam_date")),
                fee_structure=extracted.get("fee_structure"),
                primary_source_url=official,
                alt_sources=alts,
                raw_notification_text=raw_rec.raw_text[:20000],
                pdf_url=raw_rec.pdf_url,
                extraction_confidence=confidence,
                extraction_evidence=evidence,
                reviewed_by_human=False,
                published=False,
                last_scraped_at=datetime.now(timezone.utc),
            )
            db.add(opp)
            ingested_count += 1

    if ingested_count > 0 or skipped_count > 0:
        db.commit()

    return {
        "scraped": scraped_count,
        "ingested": ingested_count,
        "skipped": skipped_count,
        "skipped_listing": skipped_listing,
        "purged_listing": purged,
        "extractor": (
            "gemini" if settings.gemini_api_key else "anthropic" if settings.anthropic_api_key else "heuristic"
        ),
    }
