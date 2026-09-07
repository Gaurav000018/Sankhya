"""Quiz attempts and item responses.

Two jobs, and the second is the one that makes this worth building:

1. An officer answers approved questions, and the result becomes competency
   evidence like anything else.
2. Those responses are what item psychometrics are computed from. Without
   attempts, `difficulty_p` and `discrimination` are columns that can never be
   filled, and "our instruments self-correct" is a claim with nothing behind it.

Responses are immutable once submitted — an attempt is a measurement, and a
measurement you can edit afterwards is not one.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models import TS, Competency, User, _enum
from app.models_content import GeneratedQuestion


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    ABANDONED = "abandoned"


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_attempt_user_competency", "user_id", "competency_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    competency_id: Mapped[int | None] = mapped_column(ForeignKey("competencies.id"))

    status: Mapped[AttemptStatus] = mapped_column(
        _enum(AttemptStatus, "attempt_status"), default=AttemptStatus.IN_PROGRESS
    )
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    # Mean difficulty of the items actually asked. An 80% on a hard paper is not
    # the same result as 80% on an easy one, and the derived level says so.
    mean_difficulty: Mapped[float | None] = mapped_column(Float)
    derived_level: Mapped[float | None] = mapped_column(Float)

    started_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(TS)

    user: Mapped[User] = relationship()
    competency: Mapped[Competency | None] = relationship()
    responses: Mapped[list[ItemResponse]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan",
        order_by="ItemResponse.sequence",
    )

    @property
    def accuracy(self) -> float:
        return self.correct_count / self.item_count if self.item_count else 0.0


class ItemResponse(Base):
    __tablename__ = "item_responses"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_response_per_item"),
        CheckConstraint("selected_index >= 0", name="ck_selected_index"),
        Index("ix_response_question", "question_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("generated_questions.id"))
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    selected_index: Mapped[int | None] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    seconds_taken: Mapped[float | None] = mapped_column(Float)
    # The order options were shown in, so a re-render matches what was answered.
    option_order: Mapped[str | None] = mapped_column(String(40))

    answered_at: Mapped[datetime | None] = mapped_column(TS)

    attempt: Mapped[QuizAttempt] = relationship(back_populates="responses")
    question: Mapped[GeneratedQuestion] = relationship()
