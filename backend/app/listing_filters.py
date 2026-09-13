"""Reject aggregator hub/nav pages so we only ingest single-notification posts."""

from __future__ import annotations

from urllib.parse import urlparse

LISTING_PATHS = {
    "/",
    "/latestjob",
    "/latestjob.php",
    "/latestjob/",
    "/admitcard",
    "/admitcard/",
    "/result",
    "/result/",
    "/results",
    "/results/",
    "/admission",
    "/admission/",
    "/syllabus",
    "/syllabus/",
    "/answer-key",
    "/answerkey",
    "/answerkey/",
    "/documents",
    "/contactus",
    "/about-us",
    "/about-us/",
    "/terms-and-conditions",
    "/terms-and-conditions/",
    "/government-jobs",
    "/government-jobs/",
    "/latest-notifications",
    "/latest-notifications/",
    "/bank-jobs",
    "/bank-jobs/",
    "/railway-jobs",
    "/railway-jobs/",
    "/state-government-jobs",
    "/state-government-jobs/",
    "/sarkari-naukri",
    "/sarkarijob",
    "/upscholarship",
    "/upscholarship/",
    "/scholarship",
    "/scholarship/",
    "/certificate-verification",
    "/certificate-verification/",
}

LISTING_TITLES = {
    "admit card",
    "admit cards",
    "latest job",
    "latest jobs",
    "results",
    "result",
    "admission",
    "admissions",
    "syllabus",
    "answer key",
    "answer keys",
    "up scholarship",
    "scholarship",
    "scholarships",
    "government jobs",
    "certificate verification",
}

NAV_PREFIXES = (
    "/wp-json",
    "/wp-content",
    "/xmlrpc",
    "/feed",
    "/category/",
    "/tag/",
    "/author/",
    "/page/",
    "/search",
)


def normalize_url(url: str) -> str:
    return (url or "").strip().split("#")[0].split("?")[0].rstrip("/").lower()


def is_listing_title(title: str | None) -> bool:
    if not title:
        return True
    t = title.strip().lower()
    t = t.replace("®", "").replace("™", "").strip()
    # Strip common suffixes
    for suffix in (" - sarkari result", "| freejobalert.com", " - sarkariresult.com", " : sarkari result"):
        if suffix in t:
            t = t.replace(suffix, "").strip()
    if t in LISTING_TITLES:
        return True
    # Strip leading/trailing punctuation
    t_clean = "".join(c for c in t if c.isalnum() or c.isspace()).strip()
    if t_clean in LISTING_TITLES:
        return True
    if len(t_clean) < 16 and any(t_clean == k for k in ("jobs", "home", "more", "get details", "admit card", "latest job", "results", "admission", "up scholarship")):
        return True
    return False


def is_listing_url(url: str | None) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    path = parsed.path or "/"
    low = path.rstrip("/").lower() or "/"
    if low in LISTING_PATHS or (low + "/") in LISTING_PATHS:
        return True
    if any(low.startswith(p) for p in NAV_PREFIXES):
        return True
    
    host = (parsed.netloc or "").lower()
    segments = [s for s in path.split("/") if s]
    
    if "sarkariresult.com" in host:
        if len(segments) <= 1:
            return True
        if segments[0] in {
            "latestjob",
            "admitcard",
            "result",
            "results",
            "admission",
            "syllabus",
            "answerkey",
            "documents",
            "upscholarship",
            "scholarship",
        }:
            # Hub index pages or category sub-indexes
            return True
        # Single post URLs on SarkariResult generally have year (/2026/...) or multi-segment board paths
        # If segments == 2 and first segment is not a year (like 2024-2027), check if it's a known hub
        if len(segments) == 2 and segments[0] in {"category", "tag", "page", "author"}:
            return True

    if "freejobalert.com" in host:
        if not segments:
            return True
        if segments[0] != "articles":
            return True
        if len(segments) < 2:
            return True
            
    return False


def is_hub_content(text: str) -> bool:
    """Detect if scraped text is from an aggregator hub/index page rather than a single job."""
    if not text:
        return False
    t = text.lower()
    hub_signatures = [
        "section of sarkariresult.com, powered by sarkari result",
        "section of sarkariresult.com",
        "skip to content sarkari result",
        "has become a trusted platform providing the latest admit cards",
        "has become a trusted platform providing the latest",
        "all admit card",
        "all latest job",
        "all results",
    ]
    for sig in hub_signatures:
        if sig in t:
            return True
    # If text contains nav bar dump with multiple job titles but no eligibility or dates
    if "menu home latest job admit card results admission" in t:
        return True
    return False


def is_job_post_url(url: str | None) -> bool:
    return not is_listing_url(url) and not is_listing_title(url)


def looks_like_notification_title(title: str | None) -> bool:
    t = (title or "").lower()
    if is_listing_title(title):
        return False
    if len((title or "").strip()) < 18:
        return False
    hints = (
        "recruitment",
        "notification",
        "online form",
        "vacancy",
        "apply",
        "posts",
        "exam",
        "trainee",
        "officer",
        "constable",
        "engineer",
        "clerk",
        "apprentice",
    )
    return any(h in t for h in hints)

