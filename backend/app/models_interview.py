"""AI interview models.

Two structural decisions are enforced here rather than left to convention:

1. `AnswerScore` has four independent columns and **no composite column**. There
   is nowhere to store a blended score, so no downstream feature can start
   depending on one.
2. Only the Knowledge axis becomes competency evidence. Fluency, Communication
   and Confidence describe delivery and expression, and are reported to the
   officer as coaching feedback. See
   `services/competency.record_interview_evidence`.
3. `AttentionMetrics` holds camera-derived engagement figures and is a separate
   table, not columns on `AnswerMetrics`. It is optional, it is governed by its
   own consent, and an officer withdrawing that consent must be able to delete
   it without taking their speech measurements with it.
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
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models import TS, Competency, FracRole, User, _enum


class InterviewStatus(str, enum.Enum):
    CALIBRATING = "calibrating"      # read-aloud baseline task
    IN_PROGRESS = "in_progress"
    ANALYSING = "analysing"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class AnswerStatus(str, enum.Enum):
    RECORDED = "recorded"            # audio received
    TRANSCRIBED = "transcribed"      # ASR done, awaiting officer's correction
    ANALYSING = "analysing"
    SCORED = "scored"
    FAILED = "failed"


class InterviewQuestion(Base):
    """Pre-generated, role-grounded question bank.

    Generated offline and reviewed, not produced live: it removes a model call
    from the demo path and lets questions be checked before an officer sees them.
    """

    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    competency_id: Mapped[int | None] = mapped_column(ForeignKey("competencies.id"))
    frac_role_id: Mapped[int | None] = mapped_column(ForeignKey("frac_roles.id"))

    prompt: Mapped[str] = mapped_column(Text)
    # Concepts a complete answer should touch. The judge scores coverage against
    # these rather than against its own free-form idea of a good answer.
    expected_points: Mapped[list | None] = mapped_column(JSONB)
    bloom_level: Mapped[str] = mapped_column(String(24), default="apply")
    difficulty: Mapped[float] = mapped_column(Float, default=3.0)
    language: Mapped[str] = mapped_column(String(8), default="en")

    # Read-aloud calibration prompts carry no competency and are never scored
    # for knowledge — they exist only to measure the officer's own baseline.
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Written by the model during a live interview rather than drawn from the
    # SME-approved bank. Kept, not discarded, for two reasons: the officer's
    # report has to show what they were actually asked, and an SME reviewing the
    # session needs to see the probe that produced the evidence. Evidence from a
    # generated question is written at reduced confidence — see
    # `adaptive.GENERATED_CONFIDENCE_FACTOR`.
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    # The answer that prompted it, so a follow-up can be traced to its trigger.
    #
    # `use_alter` because this closes a cycle: an answer points at its question,
    # and a generated question points back at the answer that provoked it.
    # Without it the two tables cannot be created in any order, and the
    # constraint is emitted as a separate ALTER once both exist.
    generated_from_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "interview_answers.id", ondelete="SET NULL",
            use_alter=True, name="fk_question_generated_from_answer",
        )
    )

    competency: Mapped[Competency | None] = relationship()
    role: Mapped[FracRole | None] = relationship()


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_role_id: Mapped[int | None] = mapped_column(ForeignKey("frac_roles.id"))

    status: Mapped[InterviewStatus] = mapped_column(
        _enum(InterviewStatus, "interview_status"), default=InterviewStatus.CALIBRATING
    )

    # Baseline captured at the start of THIS session. Stored per interview rather
    # than read from the user record so a session is reproducible after the fact
    # and a cold or hoarse day does not silently follow someone forever.
    baseline_wpm: Mapped[float | None] = mapped_column(Float)
    baseline_filler_rate: Mapped[float | None] = mapped_column(Float)

    # Snapshot of the officer's accommodation setting when the session ran.
    fluency_scoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(8), default="en")

    # Adaptive sessions lay out one question at a time, each chosen from the
    # previous answer. Fixed sessions lay them all out at the start and are kept
    # because they are reproducible: the same officer gets the same questions,
    # which is what a regression test needs.
    is_adaptive: Mapped[bool] = mapped_column(Boolean, default=True)
    max_questions: Mapped[int] = mapped_column(Integer, default=6)

    started_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(TS)

    user: Mapped[User] = relationship()
    answers: Mapped[list[InterviewAnswer]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id"))
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[AnswerStatus] = mapped_column(
        _enum(AnswerStatus, "answer_status"), default=AnswerStatus.RECORDED
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    # What ASR produced, and what the officer confirmed. Whisper's error rate is
    # higher on Indian English and on Hindi-English code-switching, so the
    # officer corrects the transcript before it reaches the judge. The original
    # is kept: the difference between the two is itself a measurement of how
    # well ASR served this speaker.
    transcript_raw: Mapped[str | None] = mapped_column(Text)
    transcript_confirmed: Mapped[str | None] = mapped_column(Text)

    failure_reason: Mapped[str | None] = mapped_column(String(255))

    # Why the interview asked this, in a sentence the officer can read. An
    # adaptive interview that cannot say why it changed direction is a black box
    # the officer has no way to argue with.
    asked_because: Mapped[str | None] = mapped_column(String(400))

    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    interview: Mapped[Interview] = relationship(back_populates="answers")
    # Two foreign keys now link these tables — an answer points at its question,
    # and a generated question points back at the answer that provoked it — so
    # the join has to be named explicitly.
    question: Mapped[InterviewQuestion] = relationship(
        foreign_keys="InterviewAnswer.question_id"
    )
    metrics: Mapped[AnswerMetrics | None] = relationship(
        back_populates="answer", uselist=False, cascade="all, delete-orphan"
    )
    attention: Mapped[AttentionMetrics | None] = relationship(
        back_populates="answer", uselist=False, cascade="all, delete-orphan"
    )
    score: Mapped[AnswerScore | None] = relationship(
        back_populates="answer", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def transcript(self) -> str | None:
        """What the judge reads: the officer's correction where one exists."""
        return self.transcript_confirmed or self.transcript_raw


class AnswerMetrics(Base):
    """Measured speech signal. Facts, not judgements.

    No audio is retained — these derived numbers are all that survives an answer.
    """

    __tablename__ = "answer_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("interview_answers.id", ondelete="CASCADE"), unique=True
    )

    words: Mapped[int] = mapped_column(Integer, default=0)
    wpm: Mapped[float | None] = mapped_column(Float)
    articulation_rate: Mapped[float | None] = mapped_column(Float)

    # Counted by Vosk, not Whisper: Whisper is trained to clean speech up and
    # deletes "um" / "uh" outright, which would make every officer look fluent.
    filler_count: Mapped[int] = mapped_column(Integer, default=0)
    filler_rate: Mapped[float | None] = mapped_column(Float)   # per 100 words
    fillers: Mapped[list | None] = mapped_column(JSONB)         # [{word, t}]

    pause_count: Mapped[int] = mapped_column(Integer, default=0)
    long_pause_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_pause_seconds: Mapped[float | None] = mapped_column(Float)
    latency_to_first_word: Mapped[float | None] = mapped_column(Float)
    # [{start, end}] — the actual gaps, so the report can draw where the
    # hesitation happened rather than only how much of it there was.
    pause_spans: Mapped[list | None] = mapped_column(JSONB)

    pitch_mean: Mapped[float | None] = mapped_column(Float)
    pitch_sd: Mapped[float | None] = mapped_column(Float)
    intensity_mean: Mapped[float | None] = mapped_column(Float)
    jitter: Mapped[float | None] = mapped_column(Float)

    hedge_count: Mapped[int] = mapped_column(Integer, default=0)

    answer: Mapped[InterviewAnswer] = relationship(back_populates="metrics")


class AnswerScore(Base):
    """Five independent axes. Deliberately no composite column.

    Knowledge, Structure and Communication come from the rubric judge. Fluency
    and Confidence are computed from measured signal relative to the officer's
    own baseline. Fluency is NULL when the officer has fluency scoring switched
    off, and the other four axes are unaffected by that.

    Communication is judged from the transcript — whether terms are defined and
    ideas are ordered for a listener — and never from how the answer sounded.
    Accent, pace and hesitation belong to Fluency, which is measured against the
    officer's own baseline; folding them into Communication would rebuild the
    thing this separation exists to prevent.
    """

    __tablename__ = "answer_scores"
    __table_args__ = (
        CheckConstraint("knowledge >= 1 AND knowledge <= 5", name="ck_knowledge_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("interview_answers.id", ondelete="CASCADE"), unique=True
    )

    knowledge: Mapped[float] = mapped_column(Float)
    knowledge_confidence: Mapped[float] = mapped_column(Float, default=0.7)
    structure: Mapped[float | None] = mapped_column(Float)
    communication: Mapped[float | None] = mapped_column(Float)
    fluency: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    # Which expected points the answer covered and which it missed, plus the
    # judge's short reasons. Shown to the officer verbatim.
    covered_points: Mapped[list | None] = mapped_column(JSONB)
    missed_points: Mapped[list | None] = mapped_column(JSONB)
    rationale: Mapped[dict | None] = mapped_column(JSONB)

    model_name: Mapped[str | None] = mapped_column(String(80))
    judged_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    answer: Mapped[InterviewAnswer] = relationship(back_populates="score")


class AttentionMetrics(Base):
    """Camera-derived engagement, computed in the officer's browser.

    **No video, image or face landmark ever reaches this server.** MediaPipe Face
    Mesh runs on the officer's machine against the live preview; what arrives
    here are the summary numbers below. That is not a storage optimisation — it
    is what keeps facial geometry, which is biometric personal data under the
    DPDP Act 2023, out of a government database entirely.

    **Nothing here is competency evidence, and nothing here reaches a
    supervisor.** These figures are shown to the officer, about the officer, so
    they can watch their own recording and see what a listener would see. They
    are excluded from every axis, from promotion readiness, and from the team
    and division views.

    The reason is that gaze is not a competence signal. Eye-contact norms are
    cultural — in Indian official settings sustained direct eye contact with a
    senior can read as disrespect rather than engagement. Autistic officers, and
    officers with visual impairment, nystagmus or strabismus, produce entirely
    different gaze patterns at identical competence. Face detection accuracy
    itself varies with skin tone, spectacles and lighting. Any one of those
    would make a scored gaze axis indefensible in a promotion file; together
    they make it obviously so.

    `quality` records how much of the answer the camera actually tracked. A
    figure derived from 20% of the frames is reported as unreliable rather than
    presented next to one derived from 95%.
    """

    __tablename__ = "attention_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("interview_answers.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Share of tracked time the officer was looking at the screen, 0-1.
    screen_gaze_ratio: Mapped[float | None] = mapped_column(Float)
    # Longest continuous stretch looking away, in seconds. More useful to an
    # officer than the ratio: "you lost the camera for 11 seconds" is actionable.
    longest_look_away_seconds: Mapped[float | None] = mapped_column(Float)
    look_away_count: Mapped[int | None] = mapped_column(Integer)

    # Blinks per minute. Reported for completeness, interpreted for nothing —
    # blink rate varies with contact lenses, air conditioning and screen glare.
    blink_rate_per_minute: Mapped[float | None] = mapped_column(Float)

    # How steady the head was. High values mean the officer moved around a lot,
    # which is worth knowing when reviewing your own recording.
    head_stability: Mapped[float | None] = mapped_column(Float)

    # Fraction of frames in which a face was found at all, 0-1. Everything above
    # is conditioned on this.
    face_present_ratio: Mapped[float | None] = mapped_column(Float)
    frames_analysed: Mapped[int] = mapped_column(Integer, default=0)

    # "good" | "partial" | "unusable" — set from face_present_ratio so the
    # interface never has to re-derive the rule.
    quality: Mapped[str] = mapped_column(String(16), default="unusable")

    # What the officer was told before the camera turned on, and what they
    # agreed to. Stored because consent that cannot be produced later is not
    # consent.
    consent_version: Mapped[str | None] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    answer: Mapped[InterviewAnswer] = relationship(back_populates="attention")
