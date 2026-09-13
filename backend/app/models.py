import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator, Uuid

from app.db import Base


class JSONType(TypeDecorator):
    """JSONB on Postgres, JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class GUID(TypeDecorator):
    impl = Uuid(as_uuid=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(Uuid(as_uuid=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), unique=True)
    phone_number: Mapped[str | None] = mapped_column(String(30))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50))
    telegram_link_token: Mapped[str | None] = mapped_column(String(64))  # temp token for /start linking
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(20))
    domicile_state: Mapped[str | None] = mapped_column(String(80))

    highest_education: Mapped[str | None] = mapped_column(String(40))
    education_stream: Mapped[str | None] = mapped_column(String(80))
    degree_name: Mapped[str | None] = mapped_column(String(80))
    specialization: Mapped[str | None] = mapped_column(String(120))
    percentage_or_cgpa: Mapped[float | None] = mapped_column(Numeric)

    certifications: Mapped[list | None] = mapped_column(JSONType)
    cleared_exams: Mapped[list | None] = mapped_column(JSONType)
    experience_years: Mapped[int | None] = mapped_column(Integer)
    experience_domain: Mapped[str | None] = mapped_column(String(120))

    sector_interest: Mapped[list | None] = mapped_column(JSONType)
    domain_interest: Mapped[list | None] = mapped_column(JSONType)
    notification_channels: Mapped[list | None] = mapped_column(JSONType)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint("sector IN ('Govt','Private','PSU')", name="ck_opp_sector"),
        CheckConstraint(
            "opportunity_type IN ('Job','Admission','Result','AdmitCard','AnswerKey')",
            name="ck_opp_type",
        ),
        CheckConstraint(
            "status IN ('Upcoming','ApplicationsOpen','ClosingSoon','Closed','ResultDeclared','AdmitCardOut')",
            name="ck_opp_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    canonical_title: Mapped[str] = mapped_column(Text, nullable=False)
    org_name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str] = mapped_column(String(20), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(80))

    education_required: Mapped[list | None] = mapped_column(JSONType)
    stream_required: Mapped[list | None] = mapped_column(JSONType)
    min_percentage: Mapped[float | None] = mapped_column(Numeric)
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    age_relaxation_rules: Mapped[dict | None] = mapped_column(JSONType)
    age_cutoff_date: Mapped[date | None] = mapped_column(Date)
    gender_restriction: Mapped[str | None] = mapped_column(String(20), default="Any")
    domicile_required: Mapped[str | None] = mapped_column(String(80))
    certifications_required: Mapped[list | None] = mapped_column(JSONType)
    prerequisite_exams: Mapped[list | None] = mapped_column(JSONType)
    experience_required_years: Mapped[int | None] = mapped_column(Integer)
    category_vacancies: Mapped[dict | None] = mapped_column(JSONType)
    physical_standards: Mapped[dict | None] = mapped_column(JSONType)

    notified_at: Mapped[date | None] = mapped_column(Date)
    apply_start_date: Mapped[date | None] = mapped_column(Date)
    apply_end_date: Mapped[date | None] = mapped_column(Date)
    exam_date: Mapped[date | None] = mapped_column(Date)
    result_date: Mapped[date | None] = mapped_column(Date)
    exam_stage: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="Upcoming")

    fee_structure: Mapped[dict | None] = mapped_column(JSONType)

    primary_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_sources: Mapped[list | None] = mapped_column(JSONType)
    raw_notification_text: Mapped[str | None] = mapped_column(Text)
    pdf_url: Mapped[str | None] = mapped_column(Text)

    extraction_confidence: Mapped[float | None] = mapped_column(Numeric)
    extraction_evidence: Mapped[dict | None] = mapped_column(JSONType)
    reviewed_by_human: Mapped[bool] = mapped_column(Boolean, default=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    opportunity_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("opportunities.id"))
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    match_reasons: Mapped[list | None] = mapped_column(JSONType)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_action: Mapped[str | None] = mapped_column(String(40))
    reminder_t5_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_t1_sent: Mapped[bool] = mapped_column(Boolean, default=False)
