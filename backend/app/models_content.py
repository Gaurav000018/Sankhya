"""Learning material, and the questions generated from it.

The integrity chain runs: Material -> MaterialChunk -> GeneratedQuestion, where
every question carries a `citation_chunk_id` and a `citation_quote` that must
appear verbatim in that chunk. A question whose citation does not verify is
never published — see `services/quizgen.verify_citation`.

`GeneratedQuestion.status` is the SME review queue and psychometric retirement in
one column: draft -> approved -> retired, or draft -> rejected.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
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
from app.models import TS, Competency, User, _enum

# nomic-embed-text via Ollama. Changing model means changing this and reseeding.
EMBEDDING_DIM = 768


class MaterialStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"


class QuestionStatus(str, enum.Enum):
    DRAFT = "draft"            # generated, not yet seen by a human
    APPROVED = "approved"      # an SME cleared it; only these reach officers
    REJECTED = "rejected"
    RETIRED = "retired"        # withdrawn on psychometric grounds


class QuestionKind(str, enum.Enum):
    MCQ = "mcq"
    NUMERICAL = "numerical"
    SCENARIO = "scenario"


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(120))
    competency_id: Mapped[int | None] = mapped_column(ForeignKey("competencies.id"))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    status: Mapped[MaterialStatus] = mapped_column(
        _enum(MaterialStatus, "material_status"), default=MaterialStatus.UPLOADED
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    competency: Mapped[Competency | None] = relationship()
    uploaded_by: Mapped[User | None] = relationship()
    chunks: Mapped[list[MaterialChunk]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )


class MaterialChunk(Base):
    """A passage of source text. The unit a citation points at."""

    __tablename__ = "material_chunks"
    __table_args__ = (
        Index("ix_chunk_material_ordinal", "material_id", "ordinal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    material: Mapped[Material] = relationship(back_populates="chunks")


class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"
    __table_args__ = (
        CheckConstraint(
            "correct_index >= 0 AND correct_index <= 5", name="ck_correct_index_range"
        ),
        Index("ix_question_status_competency", "status", "competency_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    competency_id: Mapped[int | None] = mapped_column(ForeignKey("competencies.id"))

    kind: Mapped[QuestionKind] = mapped_column(
        _enum(QuestionKind, "question_kind"), default=QuestionKind.MCQ
    )
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)
    # Why each wrong option is wrong. Distractors built from misconceptions teach
    # something; distractors built from noise do not.
    distractor_rationale: Mapped[list | None] = mapped_column(JSONB)

    bloom_level: Mapped[str] = mapped_column(String(24), default="apply")

    # The citation. Verified before the question is ever stored as reviewable:
    # the quote must appear in the referenced chunk.
    citation_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_chunks.id", ondelete="SET NULL")
    )
    citation_quote: Mapped[str | None] = mapped_column(Text)
    citation_page: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[QuestionStatus] = mapped_column(
        _enum(QuestionStatus, "question_status"), default=QuestionStatus.DRAFT
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(TS)

    # Flags raised by the automated ambiguity check, before an SME reads it.
    # Cuts reviewer workload by putting the suspect ones first.
    quality_flags: Mapped[list | None] = mapped_column(JSONB)

    generated_by_model: Mapped[str | None] = mapped_column(String(80))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    # Psychometrics, filled in once the item has been attempted enough times.
    times_attempted: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    difficulty_p: Mapped[float | None] = mapped_column(Float)
    discrimination: Mapped[float | None] = mapped_column(Float)

    # --- IRT parameters ---------------------------------------------------- #
    # The classical pair above describe how a *sample* behaved. These describe
    # the *item*, on the same scale as a person's ability, which is what lets
    # the assessment choose the next question rather than pick a fixed set.
    #
    # They are not nullable, because an item with no difficulty cannot be
    # selected for and would silently never be served. Every item starts with
    # the author's intent and moves from there only when responses justify it.
    irt_a: Mapped[float] = mapped_column(Float, default=1.3, server_default="1.3")
    irt_b: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    # What the author said the difficulty was, kept beside what the data says.
    # Calibration shrinks towards this rather than replacing it outright, and
    # the distance between the two is the single most useful review signal in
    # the bank: an item two theta harder than intended is usually miskeyed.
    irt_b_authored: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    # The guessing floor: 1/options. Stored per item rather than assumed, so a
    # five-option or true/false item is modelled at its own floor instead of
    # everything being treated as a four-way choice.
    irt_c: Mapped[float] = mapped_column(Float, default=0.25, server_default="0.25")
    irt_sample_size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    irt_calibrated_at: Mapped[datetime | None] = mapped_column(TS)

    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    material: Mapped[Material] = relationship()
    competency: Mapped[Competency | None] = relationship()
    citation_chunk: Mapped[MaterialChunk | None] = relationship()
    reviewed_by: Mapped[User | None] = relationship()

    @property
    def is_publishable(self) -> bool:
        """Only approved questions reach an officer. Draft is not 'probably fine'."""
        return self.status == QuestionStatus.APPROVED

    @property
    def is_calibrated(self) -> bool:
        """Is `irt_b` a measurement, or still the author's estimate?

        Shown wherever a difficulty is displayed. An officer told a question is
        "L4.2" deserves to know whether that came from four hundred people or
        from one author's judgement.
        """
        return self.irt_calibrated_at is not None
