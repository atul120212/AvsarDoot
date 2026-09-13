from datetime import date
from typing import Any

EDU_RANK = {
    "10th": 1,
    "matric": 1,
    "12th": 2,
    "intermediate": 2,
    "diploma": 3,
    "graduate": 4,
    "any graduate": 4,
    "postgraduate": 5,
    "doctorate": 6,
}

DEGREE_LEVEL = {
    "b.tech": "graduate",
    "b.e.": "graduate",
    "b.e": "graduate",
    "b.sc": "graduate",
    "b.sc.": "graduate",
    "b.a.": "graduate",
    "b.a": "graduate",
    "b.com": "graduate",
    "b.com.": "graduate",
    "bba": "graduate",
    "llb": "graduate",
    "mbbs": "graduate",
    "m.tech": "postgraduate",
    "m.e.": "postgraduate",
    "m.sc": "postgraduate",
    "m.a.": "postgraduate",
    "mba": "postgraduate",
    "m.com": "postgraduate",
    "phd": "doctorate",
}


def calculate_age(dob: date, on_date: date | None) -> int:
    cutoff = on_date or date.today()
    years = cutoff.year - dob.year
    if (cutoff.month, cutoff.day) < (dob.month, dob.day):
        years -= 1
    return years


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _user_edu_rank(user) -> int:
    degree = _norm(user.degree_name)
    if degree in DEGREE_LEVEL:
        return EDU_RANK[DEGREE_LEVEL[degree]]
    return EDU_RANK.get(_norm(user.highest_education), 0)


def education_matches(user, required: list | None) -> tuple[bool, str]:
    if not required:
        return True, "Education: no specific requirement"
    tokens = {_norm(user.highest_education), _norm(user.degree_name), _norm(user.specialization)}
    tokens.discard("")
    user_rank = _user_edu_rank(user)
    for req in required:
        r = _norm(req)
        if r in tokens:
            return True, f"Education: {user.degree_name or user.highest_education} matches {req}"
        if r in EDU_RANK and user_rank >= EDU_RANK[r]:
            return True, f"Education: {user.highest_education} satisfies {req}"
        if "any graduate" in r and user_rank >= 4:
            return True, f"Education: {user.degree_name or user.highest_education} satisfies Any Graduate"
        if r in ("10th", "10th pass") and user_rank >= 1:
            return True, f"Education: {user.highest_education} satisfies 10th"
    return False, f"Education: {user.degree_name or user.highest_education} does not match {required}"


def stream_matches(user, required: list | None) -> bool:
    if not required:
        return True
    specs = {_norm(user.specialization), _norm(user.education_stream), _norm(user.degree_name)}
    return any(_norm(r) in specs or "any" in _norm(r) for r in required)


def _relax_years(rules: dict | None, category: str | None) -> int:
    if not rules or not category:
        return 0
    raw = rules.get(category)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def is_within_validity(cleared: dict[str, Any], year_validity: str | None) -> bool:
    if not year_validity or year_validity.lower() in ("same year", "same-year"):
        if cleared.get("year") and date.today().year != int(cleared["year"]):
            return False
        return True
    until = cleared.get("valid_until")
    if until is None:
        return True
    return date.today().year <= int(until)


def is_eligible(user, opp) -> tuple[bool, list[str]]:
    """Deterministic eligibility gate. Returns (eligible, reasons)."""
    reasons: list[str] = []
    ok = True

    edu_ok, edu_reason = education_matches(user, opp.education_required)
    if edu_ok:
        reasons.append(edu_reason)
    else:
        ok = False
        reasons.append(edu_reason)

    if opp.stream_required and not stream_matches(user, opp.stream_required):
        ok = False
        reasons.append(f"Stream: {user.specialization or user.education_stream} does not match {opp.stream_required}")
    elif opp.stream_required:
        reasons.append(f"Stream: {user.specialization or user.education_stream} matches")

    if opp.min_percentage is not None and user.percentage_or_cgpa is not None:
        try:
            pct = float(user.percentage_or_cgpa)
            if pct <= 10.0:
                pct = pct * 9.5  # Standard 10-point CGPA to percentage conversion
            if pct < float(opp.min_percentage):
                ok = False
                reasons.append(f"Percentage {pct:.1f}% below required {opp.min_percentage}%")
            else:
                reasons.append(f"Percentage {pct:.1f}% meets min {opp.min_percentage}%")
        except (TypeError, ValueError):
            pass

    if opp.age_min is not None or opp.age_max is not None:
        user_age = calculate_age(user.date_of_birth, opp.age_cutoff_date)
        effective_max = opp.age_max
        extra = _relax_years(opp.age_relaxation_rules, user.category)
        if effective_max is not None:
            effective_max = int(effective_max) + extra
        too_young = opp.age_min is not None and user_age < int(opp.age_min)
        too_old = effective_max is not None and user_age > effective_max
        if too_young or too_old:
            ok = False
            reasons.append(
                f"Age {user_age} outside {opp.age_min}-{effective_max} on cutoff {opp.age_cutoff_date or 'today'}"
            )
        else:
            reasons.append(
                f"Age {user_age} within {opp.age_min}-{effective_max}"
                + (f" ({user.category} +{extra} yrs relaxation)" if extra else "")
            )

    gender_req = opp.gender_restriction or "Any"
    if gender_req not in ("Any", None, "") and gender_req != user.gender:
        ok = False
        reasons.append(f"Gender restricted to {gender_req}")
    elif gender_req in ("Any", None, ""):
        reasons.append("Gender: open to all")

    domicile = opp.domicile_required
    if domicile not in (None, "", "Any") and domicile != user.domicile_state:
        ok = False
        reasons.append(f"Domicile required: {domicile}")
    elif domicile not in (None, "", "Any"):
        reasons.append(f"Domicile: {user.domicile_state} matches")

    if opp.certifications_required:
        have = {_norm(c) for c in (user.certifications or [])}
        missing = [c for c in opp.certifications_required if _norm(c) not in have]
        if missing:
            ok = False
            reasons.append(f"Missing certification(s): {missing}")
        else:
            reasons.append("Certifications: all required certificates present")

    if opp.prerequisite_exams:
        cleared = user.cleared_exams or []
        for req in opp.prerequisite_exams:
            exam_name = req.get("exam") if isinstance(req, dict) else None
            found = next((e for e in cleared if isinstance(e, dict) and e.get("exam") == exam_name), None)
            validity = req.get("year_validity") if isinstance(req, dict) else None
            if not found or not is_within_validity(found, validity):
                ok = False
                reasons.append(f"Requires prior clearance of: {exam_name}")
            else:
                reasons.append(f"Prerequisite cleared: {exam_name}")

    req_exp = opp.experience_required_years or 0
    if req_exp and (user.experience_years or 0) < req_exp:
        ok = False
        reasons.append(f"Experience: {user.experience_years or 0} yrs < required {req_exp}")
    elif req_exp:
        reasons.append(f"Experience: {user.experience_years} yrs meets {req_exp}")

    return ok, reasons
