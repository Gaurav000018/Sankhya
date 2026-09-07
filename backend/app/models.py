"""Database models for SANKHYA.

The spine of this schema is `ProficiencyEvidence`. It is append-only: nothing in
the application updates or deletes a row once written. Every competency level the
platform reports is *derived* from these rows (see services/competency.py), which
is what gives us trend over time, a full audit trail, and multi-signal blending
without building any of those as separate features.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #

class UserRole(str, enum.Enum):
    LEARNER = "learner"
    SUPERVISOR = "supervisor"
    SME = "sme"
    ADMIN = "admin"


class CompetencyDomain(str, enum.Enum):
    """The four domains named in the MoSPI problem statement."""

    STATISTICAL = "statistical"
    TECHNICAL = "technical"
    DIGITAL_GOVERNANCE = "digital_governance"
    BEHAVIOURAL = "behavioural"


class EvidenceSource(str, enum.Enum):
    """Where a piece of competency evidence came from.

    Ordering here is not significance — see SOURCE_WEIGHTS in
    services/competency.py, which is the single place reliability is expressed.
    """

    SIMULATION = "simulation"            # demonstrated on a real task
    QUIZ = "quiz"
    DIAGNOSTIC = "diagnostic"
    INTERVIEW = "interview"              # Knowledge axis ONLY
    LEARNING_ACTIVITY = "learning_activity"
    CERTIFICATION = "certification"
    SUPERVISOR = "supervisor"
    HISTORICAL = "historical"            # imported service record
    SELF = "self"


class Criticality(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def _enum(py_enum, name: str) -> Enum:
    """VARCHAR + CHECK rather than a native PG enum, so values can be added
    without a migration dance."""
    return Enum(py_enum, name=name, native_enum=False, validate_strings=True)


TS = DateTime(timezone=True)


# --------------------------------------------------------------------------- #
# Organisation & FRAC framework
# --------------------------------------------------------------------------- #

class Division(Base):
    __tablename__ = "divisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(80), default="Delhi")

    users: Mapped[list[User]] = relationship(back_populates="division")


class FracRole(Base):
    """A role in MoSPI's Framework of Roles, Activities and Competencies."""

    __tablename__ = "frac_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    grade: Mapped[str] = mapped_column(String(48))
    # Ascending seniority. The Promotion Readiness Engine walks this ordering.
    level_order: Mapped[int] = mapped_column(Integer, default=0)
    min_service_years: Mapped[float] = mapped_column(Float, default=0.0)

    requirements: Mapped[list[RoleCompetencyRequirement]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    domain: Mapped[CompetencyDomain] = mapped_column(
        _enum(CompetencyDomain, "competency_domain")
    )
    description: Mapped[str | None] = mapped_column(Text)


class RoleCompetencyRequirement(Base):
    """Proficiency a role requires, on the L1–L5 FRAC scale."""

    __tablename__ = "role_competency_requirements"
    __table_args__ = (
        UniqueConstraint("frac_role_id", "competency_id", name="uq_role_competency"),
        CheckConstraint("required_level >= 1 AND required_level <= 5",
                        name="ck_required_level_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    frac_role_id: Mapped[int] = mapped_column(ForeignKey("frac_roles.id", ondelete="CASCADE"))
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"))
    required_level: Mapped[float] = mapped_column(Float)
    criticality: Mapped[Criticality] = mapped_column(
        _enum(Criticality, "criticality"), default=Criticality.MEDIUM
    )

    role: Mapped[FracRole] = relationship(back_populates="requirements")
    competency: Mapped[Competency] = relationship()


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "user_role"), default=UserRole.LEARNER
    )

    password_hash: Mapped[str | None] = mapped_column(String(255))
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"))
    frac_role_id: Mapped[int | None] = mapped_column(ForeignKey("frac_roles.id"))
    service_years: Mapped[float] = mapped_column(Float, default=0.0)

    # Speech baseline from the read-aloud calibration task. Fluency is scored as a
    # deviation from these values, never against a population mean, so accent and
    # regional speech patterns are not penalised.
    baseline_wpm: Mapped[float | None] = mapped_column(Float)
    baseline_filler_rate: Mapped[float | None] = mapped_column(Float)
    # Officers with a speech disability can disable fluency scoring entirely; the
    # Knowledge axis is unaffected.
    fluency_scoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    division: Mapped[Division | None] = relationship(back_populates="users")
    frac_role: Mapped[FracRole | None] = relationship()

    @property
    def supervises(self) -> bool:
        return self.role in (UserRole.SUPERVISOR, UserRole.ADMIN)


# --------------------------------------------------------------------------- #
# The Digital Skill Twin
# --------------------------------------------------------------------------- #

class ProficiencyEvidence(Base):
    """One observation about one competency. APPEND-ONLY.

    Never UPDATE or DELETE a row here. A correction is a new row; a retraction is
    a new row with confidence 0 and a note. This is what makes every reported
    level traceable to the artifact that produced it.
    """

    __tablename__ = "proficiency_evidence"
    __table_args__ = (
        CheckConstraint("level_estimate >= 1 AND level_estimate <= 5",
                        name="ck_evidence_level_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1",
                        name="ck_evidence_confidence_range"),
        Index("ix_evidence_user_competency", "user_id", "competency_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"))

    level_estimate: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[EvidenceSource] = mapped_column(_enum(EvidenceSource, "evidence_source"))

    # Pointer back to the artifact: "interview_answer:412", "quiz_attempt:88".
    source_ref: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), index=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    competency: Mapped[Competency] = relationship()


class CompetencyProfile(Base):
    """Derived cache of the current level per (user, competency).

    Recomputed from evidence; never written to directly by feature code. Safe to
    truncate and rebuild at any time.
    """

    __tablename__ = "competency_profile"
    __table_args__ = (
        UniqueConstraint("user_id", "competency_id", name="uq_profile_user_competency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"))

    level: Mapped[float] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    # Sum of applied weights — low values mean "we do not know much about this yet".
    evidence_weight: Mapped[float] = mapped_column(Float, default=0.0)
    strongest_source: Mapped[EvidenceSource | None] = mapped_column(
        _enum(EvidenceSource, "evidence_source")
    )
    last_evidence_at: Mapped[datetime | None] = mapped_column(TS)
    computed_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    competency: Mapped[Competency] = relationship()


# --------------------------------------------------------------------------- #
# Governance
# --------------------------------------------------------------------------- #

class AuditLog(Base):
    """Append-only record of consequential actions, especially AI-produced ones."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    meta: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), index=True)
