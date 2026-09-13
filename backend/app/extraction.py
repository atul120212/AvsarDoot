"""Extract structured eligibility fields from notification text.

Order: Gemini (if GEMINI_API_KEY) → Anthropic → regex heuristic.
Every LLM field is returned with a short quote so QA can verify it in the source.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings

log = logging.getLogger("avsardoot.extraction")

EXTRACTION_SYSTEM_PROMPT = """
You extract structured fields from ONE government/private job or admission notification.

Rules:
- Use ONLY the provided text. Do not invent dates, ages, fees, or URLs.
- If a field is not clearly present, set value to null.
- For every non-null value, copy a short verbatim quote (max 180 chars) from the text that supports it.
- official_apply_url must be a URL that actually appears in the text, preferably nic.in / gov.in / the recruiting body's site. Never use aggregator homepages (sarkariresult, freejobalert) as official_apply_url.
- If the text is a listing/hub page of many unrelated jobs (Admit Card index, Latest Job index, Results index), set is_single_notification=false.

Return a single JSON object:
{
  "is_single_notification": true,
  "reject_reason": null,
  "canonical_title": {"value": string|null, "quote": string|null},
  "org_name": {"value": string|null, "quote": string|null},
  "opportunity_type": {"value": "Job"|"Admission"|"Result"|"AdmitCard"|"AnswerKey"|null, "quote": string|null},
  "domain": {"value": "Banking"|"Railway"|"Defense"|"Teaching"|"Engineering"|"Medical"|"Police"|"Judiciary"|"Clerical"|"UPSC-CSE"|"State-PSC"|"SSC"|"PSU"|"Other"|null, "quote": string|null},
  "sector": {"value": "Govt"|"Private"|"PSU"|null, "quote": string|null},
  "education_required": {"value": [string]|null, "quote": string|null},
  "stream_required": {"value": [string]|null, "quote": string|null},
  "min_percentage": {"value": number|null, "quote": string|null},
  "age_min": {"value": number|null, "quote": string|null},
  "age_max": {"value": number|null, "quote": string|null},
  "age_relaxation_rules": {"value": object|null, "quote": string|null},
  "age_cutoff_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
  "gender_restriction": {"value": "Any"|"Male"|"Female"|null, "quote": string|null},
  "domicile_required": {"value": string|null, "quote": string|null},
  "certifications_required": {"value": [string]|null, "quote": string|null},
  "prerequisite_exams": {"value": [{"exam": string, "year_validity": string}]|null, "quote": string|null},
  "experience_required_years": {"value": number|null, "quote": string|null},
  "category_vacancies": {"value": object|null, "quote": string|null},
  "notified_at": {"value": "YYYY-MM-DD"|null, "quote": string|null},
  "apply_start_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
  "apply_end_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
  "exam_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
  "fee_structure": {"value": object|null, "quote": string|null},
  "official_apply_url": {"value": string|null, "quote": string|null}
}
""".strip()

SEARCH_PROMPT = """
You are searching a job/admission notification for a specific question.
Answer ONLY from the text. Return JSON:
{"answer": string|null, "quotes": [string], "not_found": boolean}
quotes must be verbatim snippets from the text (max 3).
Question: {question}
"""

FIELD_KEYS = [
    "canonical_title",
    "org_name",
    "opportunity_type",
    "domain",
    "sector",
    "education_required",
    "stream_required",
    "min_percentage",
    "age_min",
    "age_max",
    "age_relaxation_rules",
    "age_cutoff_date",
    "gender_restriction",
    "domicile_required",
    "certifications_required",
    "prerequisite_exams",
    "experience_required_years",
    "category_vacancies",
    "notified_at",
    "apply_start_date",
    "apply_end_date",
    "exam_date",
    "fee_structure",
    "official_apply_url",
]


def _parse_json_blob(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def flatten_extraction(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence: dict[str, Any] = {}
    flat: dict[str, Any] = {
        "is_single_notification": payload.get("is_single_notification", True),
        "reject_reason": payload.get("reject_reason"),
    }
    for key in FIELD_KEYS:
        raw = payload.get(key)
        if isinstance(raw, dict) and "value" in raw:
            flat[key] = raw.get("value")
            if raw.get("quote"):
                evidence[key] = raw.get("quote")
        else:
            flat[key] = raw
    if payload.get("is_single_notification") is False:
        evidence["_listing"] = payload.get("reject_reason") or "Model classified this as a listing/hub page"
    return flat, evidence


def _confidence(flat: dict[str, Any], provider: str) -> float:
    critical = [flat.get("org_name"), flat.get("education_required"), flat.get("age_max"), flat.get("apply_end_date")]
    filled = sum(1 for v in critical if v)
    if provider == "heuristic":
        return 0.2 + 0.1 * filled
    base = 0.45 + 0.12 * filled
    if not flat.get("is_single_notification", True):
        return 0.15
    return min(base, 0.92)


VERIFICATION_PROMPT = """
You are an expert Indian Recruitment & Examination QA Auditor for AvsarDoot.
Your task is to analyze the notification text, verify existing structured fields, and extract any missing details.

Rules:
1. Base your answers ONLY on the provided text.
2. If the text is a category or hub index page (e.g. Admit Card list, Results index, navigation menu, multiple unrelated jobs), set is_single_notification=false and state why in reject_reason.
3. For each field:
   - Provide "value" (extracted or validated). If not present in the text, set value to null.
   - Provide "quote": a short verbatim snippet (max 180 chars) from the text that supports the value.
4. Compare against current_fields if provided:
   - List any field that was null or empty in current_fields but you extracted in missing_fields_filled.
   - List any discrepancies where current_fields had an incorrect value compared to the text.
5. Pay special attention to:
   - canonical_title: Official clean title (e.g. "SSC CHSL (10+2) Recruitment 2026", "PGIMER Nursing Officer Recruitment 2026")
   - org_name: Exact recruiting body (e.g. "Staff Selection Commission (SSC)", "PGIMER Chandigarh", "Railway Recruitment Board (RRB)")
   - education_required: List of required qualifications, e.g. ["10+2 Intermediate", "Bachelor Degree in Any Stream", "B.Sc Nursing", "Diploma"]
   - age_min: Minimum age limit integer (e.g. 18, 20, 21)
   - age_max: Maximum age limit integer (e.g. 27, 30, 32, 35)
   - age_cutoff_date: Cutoff date in YYYY-MM-DD
   - apply_start_date: Application begin date in YYYY-MM-DD
   - apply_end_date: Last date to apply in YYYY-MM-DD
   - exam_date: Exam date in YYYY-MM-DD
   - fee_structure: e.g. {"General": 100, "SC": 0, "ST": 0}
   - official_apply_url: Official government or organization application URL (e.g. ssc.gov.in, pgimer.edu.in)

Return a single JSON object:
{
  "is_single_notification": true,
  "reject_reason": null,
  "fields": {
    "canonical_title": {"value": string|null, "quote": string|null},
    "org_name": {"value": string|null, "quote": string|null},
    "opportunity_type": {"value": "Job"|"Admission"|"Result"|"AdmitCard"|"AnswerKey"|null, "quote": string|null},
    "domain": {"value": "Banking"|"Railway"|"Defense"|"Teaching"|"Engineering"|"Medical"|"Police"|"Judiciary"|"Clerical"|"UPSC-CSE"|"State-PSC"|"SSC"|"PSU"|"Other"|null, "quote": string|null},
    "sector": {"value": "Govt"|"Private"|"PSU"|null, "quote": string|null},
    "education_required": {"value": [string]|null, "quote": string|null},
    "stream_required": {"value": [string]|null, "quote": string|null},
    "age_min": {"value": number|null, "quote": string|null},
    "age_max": {"value": number|null, "quote": string|null},
    "age_cutoff_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
    "gender_restriction": {"value": "Any"|"Male"|"Female"|null, "quote": string|null},
    "domicile_required": {"value": string|null, "quote": string|null},
    "apply_start_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
    "apply_end_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
    "exam_date": {"value": "YYYY-MM-DD"|null, "quote": string|null},
    "fee_structure": {"value": object|null, "quote": string|null},
    "official_apply_url": {"value": string|null, "quote": string|null}
  },
  "missing_fields_filled": [string],
  "discrepancies": [{"field": string, "existing": any, "verified": any, "explanation": string}]
}
""".strip()


def heuristic_extract(raw_text: str) -> dict[str, Any]:
    from app.listing_filters import is_hub_content
    text = raw_text or ""
    
    if is_hub_content(text):
        return {
            "is_single_notification": False,
            "reject_reason": "Aggregator hub / category navigation page detected",
            "org_name": None,
            "education_required": None,
            "age_min": None,
            "age_max": None,
        }

    # 1. Organization & Domain Recognition
    org = None
    domain = "Other"
    top_chunk = text[:1500]

    org_domain_map = [
        (r"\b(?:SSC|Staff Selection Commission)\b", "Staff Selection Commission (SSC)", "SSC"),
        (r"\b(?:UPSC|Union Public Service Commission)\b", "Union Public Service Commission (UPSC)", "UPSC-CSE"),
        (r"\b(?:RRB|Railway Recruitment Board|RRC|Indian Railways)\b", "Railway Recruitment Board (RRB)", "Railway"),
        (r"\b(?:IBPS|Institute of Banking Personnel Selection)\b", "Institute of Banking Personnel Selection (IBPS)", "Banking"),
        (r"\b(?:SBI|State Bank of India)\b", "State Bank of India (SBI)", "Banking"),
        (r"\b(?:RBI|Reserve Bank of India)\b", "Reserve Bank of India (RBI)", "Banking"),
        (r"\b(?:PGIMER|Postgraduate Institute of Medical)\b", "PGIMER Chandigarh", "Medical"),
        (r"\b(?:AIIMS|All India Institute of Medical Sciences)\b", "AIIMS", "Medical"),
        (r"\b(?:UPPSC|Uttar Pradesh Public Service Commission)\b", "Uttar Pradesh Public Service Commission (UPPSC)", "State-PSC"),
        (r"\b(?:UPSSSC)\b", "Uttar Pradesh Subordinate Services Selection Commission (UPSSSC)", "Clerical"),
        (r"\b(?:BPSC|Bihar Public Service Commission)\b", "Bihar Public Service Commission (BPSC)", "State-PSC"),
        (r"\b(?:RPSC|Rajasthan Public Service Commission)\b", "Rajasthan Public Service Commission (RPSC)", "State-PSC"),
        (r"\b(?:MPESB|MPPEB|Vyapam)\b", "Madhya Pradesh Employees Selection Board (MPESB)", "State-PSC"),
        (r"\b(?:NTA|National Testing Agency)\b", "National Testing Agency (NTA)", "Teaching"),
        (r"\b(?:DRDO)\b", "Defense Research and Development Organisation (DRDO)", "Defense"),
        (r"\b(?:ISRO)\b", "Indian Space Research Organisation (ISRO)", "Engineering"),
        (r"\b(?:IOCL|Indian Oil)\b", "Indian Oil Corporation Limited (IOCL)", "PSU"),
        (r"\b(?:ONGC)\b", "Oil and Natural Gas Corporation (ONGC)", "PSU"),
        (r"\b(?:Delhi Police|UP Police|Police Constable|Sub Inspector|SI CAPF|CPO)\b", None, "Police"),
    ]

    for pattern, mapped_org, mapped_domain in org_domain_map:
        if re.search(pattern, top_chunk, re.I):
            if mapped_org and not org:
                org = mapped_org
            if mapped_domain and domain == "Other":
                domain = mapped_domain

    if not org:
        for pat in (
            r"(?:Organization|Organisation|Department|Recruitment Board|Commission|Board Name)\s*[:\-–]\s*([A-Za-z0-9 .,&()]{3,80})",
            r"(UPSC|SSC|IBPS|RRB|SBI|RBI|NTA|UPPSC|BPSC|MPSC|IB|DRDO|ISRO|IOCL|ONGC)",
        ):
            m = re.search(pat, text, re.I)
            if m:
                org = m.group(1).strip()
                break

    # 2. Age Limits (handles SarkariResult Minimum Age / Maximum Age tables)
    age_min = None
    age_max = None

    # Minimum Age
    m_min = re.search(r"Minimum Age\s*[:\-–]?\s*(\d{1,2})\s*(?:Years?)?", text, re.I)
    if m_min:
        age_min = int(m_min.group(1))
    else:
        m_min2 = re.search(r"(?:Min|Minimum)\s*Age[^0-9]{0,20}(\d{1,2})", text, re.I)
        if m_min2:
            age_min = int(m_min2.group(1))

    # Maximum Age
    m_max = re.search(r"Maximum Age\s*[:\-–]?\s*(\d{1,2})\s*(?:Years?)?", text, re.I)
    if m_max:
        age_max = int(m_max.group(1))
    else:
        m_max2 = re.search(r"(?:Max|Maximum)\s*Age[^0-9]{0,20}(\d{1,2})", text, re.I)
        if m_max2:
            age_max = int(m_max2.group(1))

    # Range fallback: 18-32 or 18 to 32 Years
    if not age_min or not age_max:
        m_range = re.search(r"Age(?:\s*Limit)?\s*[:\-–]?\s*(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})\s*(?:Years?)?", text, re.I)
        if m_range:
            age_min = age_min or int(m_range.group(1))
            age_max = age_max or int(m_range.group(2))

    # Age cutoff date
    age_cutoff = None
    m_cutoff = re.search(r"Age Limit as on\s*[:\-–]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text, re.I)
    if m_cutoff:
        age_cutoff = m_cutoff.group(1)

    # 3. Education / Qualifications
    education = []
    if re.search(r"\b(?:10\+2|Intermediate|12th Pass|Senior Secondary)\b", text, re.I):
        education.append("12th / 10+2 Intermediate")
    if re.search(r"\b(?:Bachelor(?:\s*Degree)?|Graduation|Graduate|Degree in Any (?:Stream|Discipline))\b", text, re.I):
        education.append("Any Graduate")
    if re.search(r"\b(?:B\.Tech|B\.E\.|Engineering Degree)\b", text, re.I):
        education.append("B.Tech / B.E.")
    if re.search(r"\b(?:Diploma in|Polytechnic)\b", text, re.I):
        education.append("Diploma")
    if re.search(r"\b(?:B\.Sc Nursing|GNM|Nursing)\b", text, re.I):
        education.append("B.Sc Nursing / GNM")
    if re.search(r"\b(?:10th Pass|Matric|High School)\b", text, re.I):
        education.append("10th / High School")
    if re.search(r"\b(?:Post\s*Graduate|Master(?:\s*Degree)?|M\.Tech|M\.Sc|M\.Com|M\.A\.)\b", text, re.I):
        education.append("Postgraduate")
    if re.search(r"\b(?:ITI)\b", text, re.I):
        education.append("ITI")

    m_edu = re.search(
        r"(?:Eligibility(?:\s*Details)?|Educational Qualification|Qualification)\s*[:\-–]\s*([^\n.]{4,180})",
        text,
        re.I,
    )
    if m_edu and not education:
        clean_edu = m_edu.group(1).strip()
        education = [p.strip() for p in re.split(r"[/,;]| or ", clean_edu) if p.strip()][:6]

    # 4. Dates
    def find_date(*labels: str) -> str | None:
        for label in labels:
            m = re.search(
                rf"{label}\s*[:\-–]?\s*(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})",
                text,
                re.I,
            )
            if m:
                return m.group(1)
        return None

    start = find_date(
        "Application Begin", "Apply Start", "Starting Date", "Start Date", "Online Apply Start"
    )
    last = find_date(
        "Last Date for Apply Online", "Last Date to Apply", "Last Date for Apply", "Apply End", "Closing Date", "Application Ends", "Last Date"
    )
    exam = find_date(
        "Exam Date CBT", "Exam Date", "Date of Exam", "CBT Exam Date", "Tier I Exam Date"
    )

    # 5. Fee structure
    fee_structure = None
    gen_fee = re.search(r"(?:General|Gen|OBC|EWS)\s*[:\-–]?\s*(?:Rs\.?|INR)?\s*(\d{1,4})", text, re.I)
    sc_fee = re.search(r"(?:SC\s*/\s*ST|SC|ST)\s*[:\-–]?\s*(?:Rs\.?|INR)?\s*(\d{1,4})", text, re.I)
    if gen_fee or sc_fee:
        fee_structure = {}
        if gen_fee:
            fee_structure["General / OBC"] = int(gen_fee.group(1))
        if sc_fee:
            fee_structure["SC / ST"] = int(sc_fee.group(1))

    return {
        "is_single_notification": True,
        "org_name": org,
        "domain": domain,
        "education_required": education if education else None,
        "age_min": age_min,
        "age_max": age_max,
        "age_cutoff_date": age_cutoff,
        "gender_restriction": "Any",
        "apply_start_date": start,
        "apply_end_date": last,
        "exam_date": exam,
        "fee_structure": fee_structure,
        "_note": "regex_heuristic; run LLM verification to cross-check against source",
    }


def _gemini_generate(user_text: str, system: str) -> dict[str, Any]:
    import httpx

    models = [settings.gemini_model, "gemini-2.0-flash"]
    last_error: Exception | None = None
    for model in dict.fromkeys(models):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user_text[:55000]}"}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "maxOutputTokens": 4096,
            },
        }
        try:
            resp = httpx.post(url, params={"key": settings.gemini_api_key}, json=payload, timeout=90)
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_json_blob(text)
        except Exception as ex:
            last_error = ex
            log.warning("Gemini model %s failed: %s", model, ex)
    raise last_error or RuntimeError("Gemini extraction failed")


def _anthropic_generate(user_text: str) -> dict[str, Any]:
    import httpx

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2500,
            "system": EXTRACTION_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_text[:80000]}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return _parse_json_blob(resp.json()["content"][0]["text"])


def extract_fields(raw_text: str) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
    """Returns (flat_fields, confidence, needs_human_review, evidence)."""
    evidence: dict[str, Any] = {}
    provider = "heuristic"

    if settings.gemini_api_key:
        try:
            payload = _gemini_generate(raw_text, EXTRACTION_SYSTEM_PROMPT)
            flat, evidence = flatten_extraction(payload)
            provider = "gemini"
            evidence["_provider"] = provider
            return flat, _confidence(flat, provider), True, evidence
        except Exception:
            log.exception("Gemini extraction failed; trying fallback")

    if settings.anthropic_api_key:
        try:
            payload = _anthropic_generate(raw_text)
            flat, evidence = flatten_extraction(payload)
            provider = "anthropic"
            evidence["_provider"] = provider
            return flat, _confidence(flat, provider), True, evidence
        except Exception:
            log.exception("Anthropic extraction failed; using heuristic")

    data = heuristic_extract(raw_text)
    evidence = {"_provider": "heuristic", "_note": data.get("_note")}
    return data, _confidence(data, "heuristic"), True, evidence


def search_notification(raw_text: str, question: str) -> dict[str, Any]:
    """Keyword hits plus optional Gemini answer with quotes."""
    text = raw_text or ""
    q = (question or "").strip()
    snippets: list[dict[str, Any]] = []
    if q:
        pattern = re.compile(re.escape(q), re.I)
        for m in pattern.finditer(text):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            snippets.append({"start": m.start(), "end": m.end(), "snippet": text[start:end]})
            if len(snippets) >= 8:
                break
        if not snippets:
            tokens = [t for t in re.split(r"\s+", q) if len(t) > 2]
            for token in tokens[:4]:
                m = re.search(re.escape(token), text, re.I)
                if m:
                    start = max(0, m.start() - 80)
                    end = min(len(text), m.end() + 80)
                    snippets.append({"start": m.start(), "end": m.end(), "snippet": text[start:end]})

    llm: dict[str, Any] | None = None
    if settings.gemini_api_key and q:
        try:
            llm = _gemini_generate(
                f"NOTIFICATION TEXT:\n{text[:50000]}\n\nQUESTION: {q}",
                SEARCH_PROMPT.format(question=q),
            )
        except Exception:
            log.exception("Gemini search failed")
    elif not settings.gemini_api_key:
        llm = {"note": "Set GEMINI_API_KEY to ask the model; keyword hits are shown below."}

    return {"query": q, "keyword_hits": snippets, "llm": llm, "hit_count": len(snippets)}


def verify_and_fill_with_llm(
    raw_text: str, current_fields: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Verify existing extracted details and find missing fields using LLM (Gemini/Anthropic) with fallback."""
    current = current_fields or {}
    text = raw_text or ""
    provider = "heuristic"
    user_prompt = f"CURRENT EXTRACTED FIELDS:\n{json.dumps(current, indent=2, default=str)}\n\nNOTIFICATION TEXT:\n{text[:55000]}"

    if settings.gemini_api_key:
        try:
            payload = _gemini_generate(user_prompt, VERIFICATION_PROMPT)
            flat, evidence = flatten_extraction(payload.get("fields") or payload)
            missing = payload.get("missing_fields_filled") or []
            discrepancies = payload.get("discrepancies") or []
            is_single = payload.get("is_single_notification", True)
            reject_reason = payload.get("reject_reason")
            provider = "gemini"
            conf = _confidence(flat, provider)
            return {
                "is_single_notification": is_single,
                "reject_reason": reject_reason,
                "verified_fields": flat,
                "evidence": evidence,
                "missing_fields_filled": missing,
                "discrepancies": discrepancies,
                "confidence": conf,
                "provider": provider,
            }
        except Exception:
            log.exception("Gemini verification failed; trying fallback")

    if settings.anthropic_api_key:
        try:
            payload = _anthropic_generate(f"{VERIFICATION_PROMPT}\n\n{user_prompt}")
            flat, evidence = flatten_extraction(payload.get("fields") or payload)
            missing = payload.get("missing_fields_filled") or []
            discrepancies = payload.get("discrepancies") or []
            is_single = payload.get("is_single_notification", True)
            reject_reason = payload.get("reject_reason")
            provider = "anthropic"
            conf = _confidence(flat, provider)
            return {
                "is_single_notification": is_single,
                "reject_reason": reject_reason,
                "verified_fields": flat,
                "evidence": evidence,
                "missing_fields_filled": missing,
                "discrepancies": discrepancies,
                "confidence": conf,
                "provider": provider,
            }
        except Exception:
            log.exception("Anthropic verification failed; using heuristic")

    # Heuristic fallback
    data = heuristic_extract(text)
    missing_filled = []
    for k in (
        "org_name",
        "education_required",
        "age_min",
        "age_max",
        "age_cutoff_date",
        "apply_start_date",
        "apply_end_date",
        "exam_date",
        "domain",
        "fee_structure",
    ):
        if not current.get(k) and data.get(k):
            missing_filled.append(k)

    conf = _confidence(data, "heuristic")
    evidence = {
        "_provider": "heuristic",
        "_note": "Generated using enhanced Indian recruitment regex; configure GEMINI_API_KEY for full AI verification.",
    }
    return {
        "is_single_notification": data.get("is_single_notification", True),
        "reject_reason": data.get("reject_reason"),
        "verified_fields": data,
        "evidence": evidence,
        "missing_fields_filled": missing_filled,
        "discrepancies": [],
        "confidence": conf,
        "provider": "heuristic",
    }

