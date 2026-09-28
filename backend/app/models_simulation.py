"""Role-based competency simulation: a situation, a decision, and a defence of it.

Every other source on the platform measures what an officer *knows*. This one
measures what they would *do* — a real situation from their own work, with the
constraint that makes it hard, and no single right answer. That is why
`SOURCE_WEIGHTS` trusts it above everything else: it is the closest the platform
gets to watching someone do the job.

Scored on five axes rather than the interview's three. Reasoning,
prioritisation and decision-making are the whole point here and are absent from
a knowledge question, so folding them into one "knowledge" number would throw
away exactly what the exercise was built to see.

Only the competency axes become evidence. The rest are shown to the officer as
feedback and stop there, on the same principle as the interview's delivery
scores.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models import Competency, User

TS = DateTime(timezone=True)


class SimulationStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    SCORED = "scored"
    ABANDONED = "abandoned"


class Scenario(Base):
    """One situation an officer might actually face.

    Authored rather than generated. A situational exercise is only fair if the
    rubric is defensible, and a model inventing both the crisis and the marking
    scheme gives an officer nothing to appeal against.
    """

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id"), index=True)

    # The situation as the officer reads it.
    situation: Mapped[str] = mapped_column(Text)
    # What they are being asked to produce.
    task: Mapped[str] = mapped_column(Text)
    # The constraint that makes it a judgement rather than a recall question.
    constraint: Mapped[str | None] = mapped_column(Text)

    # What a strong answer covers. Shown to the officer only after they submit,
    # so it cannot be reverse-engineered into the answer.
    expected_points: Mapped[list] = mapped_column(JSONB, default=list)
    # Things that look right and are not. Named so the judge can spot them and
    # so the feedback can say why, rather than only what was missed.
    common_traps: Mapped[list] = mapped_column(JSONB, default=list)

    # Roughly the FRAC level this situation sits at, used to pick a scenario
    # near the officer's own level rather than far above it.
    target_level: Mapped[float] = mapped_column(Float, default=3.0)
    minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    competency: Mapped[Competency] = relationship()


class SimulationAttempt(Base):
    __tablename__ = "simulation_attempts"
    __table_args__ = (
        Index("ix_simulation_user_scenario", "user_id", "scenario_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"), index=True)
    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, name="simulation_status"),
        default=SimulationStatus.IN_PROGRESS,
    )

    response: Mapped[str | None] = mapped_column(Text)

    # --- the five axes ------------------------------------------------------ #
    # Knowledge and reasoning are what become competency evidence. The other
    # three describe how the decision was made and communicated, and are
    # feedback only — the same line the interview draws around delivery.
    knowledge: Mapped[float | None] = mapped_column(Float)
    reasoning: Mapped[float | None] = mapped_column(Float)
    prioritisation: Mapped[float | None] = mapped_column(Float)
    communication: Mapped[float | None] = mapped_column(Float)
    decision_making: Mapped[float | None] = mapped_column(Float)

    # Level written to the evidence record, and how sure the judge was.
    derived_level: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    covered_points: Mapped[list] = mapped_column(JSONB, default=list)
    missed_points: Mapped[list] = mapped_column(JSONB, default=list)
    traps_hit: Mapped[list] = mapped_column(JSONB, default=list)
    feedback: Mapped[str | None] = mapped_column(Text)

    # Which model scored it, so a stub-scored attempt is never mistaken for a
    # judged one after the fact.
    model_name: Mapped[str | None] = mapped_column(String(80))
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(TS)

    user: Mapped[User] = relationship()
    scenario: Mapped[Scenario] = relationship()
