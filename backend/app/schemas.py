from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    subscription_tier: str = "free"
    onboarding_complete: bool


class UserCreate(BaseModel):
    email: str = Field(min_length=5)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class ClearedExam(BaseModel):
    exam: str
    year: int | None = None
    valid_until: int | None = None


class ProfileIn(BaseModel):
    phone_number: str | None = None
    telegram_chat_id: str | None = None
    date_of_birth: date
    gender: str | None = None
    category: str | None = None
    domicile_state: str | None = None
    highest_education: str | None = None
    education_stream: str | None = None
    degree_name: str | None = None
    specialization: str | None = None
    percentage_or_cgpa: float | None = None
    certifications: list[str] | None = None
    cleared_exams: list[dict[str, Any]] | None = None
    experience_years: int | None = 0
    experience_domain: str | None = None
    sector_interest: list[str] | None = None
    domain_interest: list[str] | None = None
    notification_channels: list[str] | None = None


class ProfileOut(ProfileIn):
    id: UUID
    user_id: UUID

    model_config = {"from_attributes": True}


class OpportunityIn(BaseModel):
    canonical_title: str
    org_name: str
    sector: str
    opportunity_type: str
    domain: str | None = None
    education_required: list[str] | None = None
    stream_required: list[str] | None = None
    min_percentage: float | None = None
    age_min: int | None = None
    age_max: int | None = None
    age_relaxation_rules: dict[str, Any] | None = None
    age_cutoff_date: date | None = None
    gender_restriction: str | None = "Any"
    domicile_required: str | None = "Any"
    certifications_required: list[str] | None = None
    prerequisite_exams: list[dict[str, Any]] | None = None
    experience_required_years: int | None = None
    category_vacancies: dict[str, Any] | None = None
    physical_standards: dict[str, Any] | None = None
    notified_at: date | None = None
    apply_start_date: date | None = None
    apply_end_date: date | None = None
    exam_date: date | None = None
    result_date: date | None = None
    exam_stage: str | None = None
    status: str = "Upcoming"
    fee_structure: dict[str, Any] | None = None
    primary_source_url: str
    alt_sources: list[dict[str, Any]] | None = None
    raw_notification_text: str | None = None
    pdf_url: str | None = None
    extraction_confidence: float | None = None
    extraction_evidence: dict[str, Any] | None = None
    reviewed_by_human: bool = False
    published: bool = False


class OpportunityOut(OpportunityIn):
    id: UUID
    last_scraped_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    match_reasons: list[str] | None = None
    is_match: bool | None = None

    model_config = {"from_attributes": True}


class MatchAction(BaseModel):
    action: str


class ExtractRequest(BaseModel):
    raw_text: str
    query: str | None = None
