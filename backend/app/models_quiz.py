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
    Text,
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

    # --- adaptive state ---------------------------------------------------- #
    # An adaptive attempt has no fixed item list: the next question depends on
    # every answer so far, so the ability estimate has to live on the attempt
    # between requests rather than being recomputed from scratch by the caller.
    #
    # `theta` is the posterior mean and `theta_se` its standard deviation, both
    # on the IRT scale. `theta_se` is not decoration — it decides when the test
    # stops and becomes the confidence on the evidence record, so an attempt
    # that lost it would produce evidence nobody could weigh.
    is_adaptive: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    theta: Mapped[float | None] = mapped_column(Float)
    theta_se: Mapped[float | None] = mapped_column(Float)
    # Why the test ended: "precision", "max_items" or "exhausted". Reported to
    # the officer, because a test that stops after six questions without saying
    # why reads as a malfunction.
    stop_reason: Mapped[str | None] = mapped_column(String(24))

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

    # --- the adaptive trace ------------------------------------------------ #
    # What the estimate was when this item was chosen, and what it became once
    # the answer was scored. Kept per response rather than derived afterwards
    # for two reasons: item parameters get recalibrated, so a replay months
    # later would not reproduce the path the officer actually walked; and the
    # officer's report shows the estimate narrowing item by item, which is the
    # clearest explanation of adaptive testing anybody gets.
    theta_before: Mapped[float | None] = mapped_column(Float)
    theta_after: Mapped[float | None] = mapped_column(Float)
    se_after: Mapped[float | None] = mapped_column(Float)
    # Fisher information this item carried at the estimate when it was picked —
    # how much the question was worth asking, recorded before we knew the answer.
    item_information: Mapped[float | None] = mapped_column(Float)
    # The difficulty in force when it was served. An item recalibrated later
    # must not silently rewrite the history of a test already taken.
    item_difficulty: Mapped[float | None] = mapped_column(Float)
    asked_because: Mapped[str | None] = mapped_column(Text)

    answered_at: Mapped[datetime | None] = mapped_column(TS)

    attempt: Mapped[QuizAttempt] = relationship(back_populates="responses")
    question: Mapped[GeneratedQuestion] = relationship()
