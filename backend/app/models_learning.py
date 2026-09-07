"""Courses, recommendations and learning paths.

Two things are modelled deliberately rather than implied:

* **Why a course was recommended** is stored, not recomputed at render time.
  A recommendation an officer cannot interrogate is a search result with extra
  steps, and the reason has to survive the catalogue changing underneath it.
* **Prerequisites are edges, not a text field.** A learning path is a
  topological order over that graph, so "do this first" is derived rather than
  hand-maintained.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
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
from app.models import TS, Competency, FracRole, User, _enum
from app.models_content import EMBEDDING_DIM


class CourseSource(str, enum.Enum):
    IGOT = "igot"
    NSSTA = "nssta"          # the ministry's own training academy
    EXTERNAL = "external"
    INTERNAL = "internal"


class PathItemStatus(str, enum.Enum):
    LOCKED = "locked"        # a prerequisite is still outstanding
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_course_source_external"),
        Index("ix_course_competency", "competency_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[CourseSource] = mapped_column(
        _enum(CourseSource, "course_source"), default=CourseSource.IGOT
    )
    # The identifier in the upstream catalogue, so a re-sync updates rather than
    # duplicates.
    external_id: Mapped[str] = mapped_column(String(120))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str | None] = mapped_column(String(160))
    url: Mapped[str | None] = mapped_column(String(500))

    competency_id: Mapped[int | None] = mapped_column(ForeignKey("competencies.id"))
    # The band this course actually moves someone through. A foundation course
    # cannot take an officer from L3 to L4, and recommending it for that is how
    # a recommender loses trust.
    level_from: Mapped[float] = mapped_column(Float, default=1.0)
    level_to: Mapped[float] = mapped_column(Float, default=3.0)

    duration_hours: Mapped[float] = mapped_column(Float, default=4.0)
    language: Mapped[str] = mapped_column(String(8), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    synced_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    competency: Mapped[Competency | None] = relationship()
    prerequisites: Mapped[list[CoursePrerequisite]] = relationship(
        back_populates="course",
        foreign_keys="CoursePrerequisite.course_id",
        cascade="all, delete-orphan",
    )

    @property
    def level_gain(self) -> float:
        return max(0.0, self.level_to - self.level_from)


class CoursePrerequisite(Base):
    """Edge in the prerequisite graph: `course` requires `requires`."""

    __tablename__ = "course_prerequisites"
    __table_args__ = (
        UniqueConstraint("course_id", "requires_id", name="uq_prerequisite"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    requires_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))

    course: Mapped[Course] = relationship(
        back_populates="prerequisites", foreign_keys=[course_id]
    )
    requires: Mapped[Course] = relationship(foreign_keys=[requires_id])


class CourseCompletion(Base):
    """An officer finished a course.

    Kept separate from `proficiency_evidence` on purpose: completing a course is
    an event, not a competency claim. It produces a low-weight LEARNING_ACTIVITY
    observation, and it is also the anchor for measuring whether the course
    actually moved anyone — the before/after that course efficacy needs.
    """

    __tablename__ = "course_completions"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_completion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)

    completed_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    # Derived level at completion time, so lift can be measured later without
    # reconstructing history.
    level_at_completion: Mapped[float | None] = mapped_column(Float)

    user: Mapped[User] = relationship()
    course: Mapped[Course] = relationship()


class Recommendation(Base):
    """A recommendation, with the reasoning kept alongside it."""

    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendation_user_competency", "user_id", "competency_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id"))
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("frac_roles.id"))

    # The gap as it stood when this was produced. Stored rather than looked up,
    # so the explanation still makes sense after the officer's level moves.
    current_level: Mapped[float] = mapped_column(Float)
    required_level: Mapped[float] = mapped_column(Float)

    score: Mapped[float] = mapped_column(Float)
    # Each contributing signal, kept separately so the explanation can name them
    # instead of asserting a single opaque number.
    signals: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    course: Mapped[Course] = relationship()
    competency: Mapped[Competency] = relationship()
    target_role: Mapped[FracRole | None] = relationship()


class LearningPath(Base):
    """An ordered sequence closing one competency gap."""

    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id"))
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("frac_roles.id"))

    current_level: Mapped[float] = mapped_column(Float)
    target_level: Mapped[float] = mapped_column(Float)
    # How far the sequence actually gets. Below target_level when the catalogue
    # has nothing that finishes the job — which the path says plainly rather
    # than implying the gap is closed.
    reaches_level: Mapped[float] = mapped_column(Float, default=0.0)
    total_hours: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_weeks: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    competency: Mapped[Competency] = relationship()
    items: Mapped[list[PathItem]] = relationship(
        back_populates="path", cascade="all, delete-orphan", order_by="PathItem.sequence"
    )


class PathItem(Base):
    __tablename__ = "path_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[PathItemStatus] = mapped_column(
        _enum(PathItemStatus, "path_item_status"), default=PathItemStatus.LOCKED
    )
    # Present when this course is here only because something later needs it.
    included_because: Mapped[str | None] = mapped_column(String(255))

    path: Mapped[LearningPath] = relationship(back_populates="items")
    course: Mapped[Course] = relationship()
