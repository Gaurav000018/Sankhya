from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerify(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class TotpVerify(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    method: str


class OtpRequestResponse(BaseModel):
    # Identical whether or not the account exists, so the endpoint cannot be used
    # to discover which officers are registered.
    message: str
    cooldown_seconds: int
    # Populated only in dev mode, so a demo never waits on an email.
    dev_code: str | None = None


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    division_id: int | None
    frac_role_id: int | None
    service_years: float
    totp_enabled: bool
    fluency_scoring_enabled: bool


# --------------------------------------------------------------------------- #
# FRAC framework
# --------------------------------------------------------------------------- #

class FracRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    grade: str
    level_order: int
    min_service_years: float


class CompetencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    domain: str
    description: str | None


# --------------------------------------------------------------------------- #
# Skill Twin
# --------------------------------------------------------------------------- #

class CompetencyLevelOut(BaseModel):
    competency_id: int
    competency_code: str
    competency_name: str
    domain: str
    level: float
    evidence_count: int
    evidence_weight: float
    strongest_source: str | None
    last_evidence_at: datetime | None
    is_confident: bool


class SkillTwinOut(BaseModel):
    user: UserOut
    role_name: str | None
    role_readiness: float
    competencies: list[CompetencyLevelOut]


class GapOut(BaseModel):
    competency_id: int
    competency_code: str
    competency_name: str
    domain: str
    current_level: float
    required_level: float
    gap: float
    criticality: str
    status: str
    evidence_count: int
    strongest_source: str | None
    last_evidence_at: datetime | None


class DivergenceOut(BaseModel):
    competency_id: int
    competency_name: str
    self_rated_level: float
    assessed_level: float
    divergence: float


class EvidenceIn(BaseModel):
    user_id: int
    competency_id: int
    level_estimate: float = Field(ge=1, le=5)
    source: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    source_ref: str | None = None
    note: str | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    competency_id: int
    level_estimate: float
    confidence: float
    source: str
    source_ref: str | None
    note: str | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# AI interview
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# Learning
# --------------------------------------------------------------------------- #

class CourseOut(BaseModel):
    id: int
    external_id: str
    source: str
    title: str
    description: str
    provider: str | None
    competency_id: int | None
    level_from: float
    level_to: float
    duration_hours: float


class RecommendationOut(BaseModel):
    """A recommendation carries its own justification.

    `signals` exposes each contributing factor separately, so the officer can
    see *why* rather than being handed a single opaque ranking number.
    """

    id: int
    course: CourseOut
    competency_id: int
    competency_name: str
    current_level: float
    required_level: float
    gap: float
    score: float
    signals: dict
    reason: str


class PathItemOut(BaseModel):
    sequence: int
    status: str
    included_because: str | None
    course: CourseOut


class LearningPathOut(BaseModel):
    id: int
    competency_id: int
    competency_name: str
    current_level: float
    target_level: float
    reaches_level: float
    total_hours: float
    estimated_weeks: int
    reason: str
    items: list[PathItemOut]


class QuizStartIn(BaseModel):
    competency_id: int | None = None
    item_count: int = Field(default=8, ge=3, le=20)


class QuizAnswerIn(BaseModel):
    question_id: int
    selected_index: int = Field(ge=0, le=5)


class QuizSubmitIn(BaseModel):
    answers: list[QuizAnswerIn] = Field(default_factory=list)


class QuizItemOut(BaseModel):
    """The answer key fields are None while an attempt is open."""

    sequence: int
    question_id: int
    stem: str
    options: list
    bloom_level: str
    selected_index: int | None
    correct_index: int | None
    is_correct: bool | None
    explanation: str | None
    citation: dict | None


class QuizAttemptOut(BaseModel):
    id: int
    competency_id: int | None
    competency_name: str | None
    status: str
    item_count: int
    mean_difficulty: float | None
    items: list[QuizItemOut]


class QuizResultOut(BaseModel):
    attempt: QuizAttemptOut
    correct: int
    total: int
    accuracy: float
    derived_level: float
    confidence: float
    note: str


class InterviewStartIn(BaseModel):
    # Interview against a role you are aiming for, not only the one you hold.
    target_role_id: int | None = None


class TranscriptCorrectionIn(BaseModel):
    transcript: str = Field(min_length=1, max_length=20000)
    rejudge: bool = True


class UploadAcceptedOut(BaseModel):
    answer_id: int
    status: str
    worker_online: bool
    queue_depth: int
    message: str


class InterviewSummaryOut(BaseModel):
    id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    answers: int
    scored: int


class AxisOut(BaseModel):
    label: str
    score: float | None
    answers_scored: int


class MaterialOut(BaseModel):
    id: int
    title: str
    filename: str
    status: str
    competency_id: int | None
    page_count: int | None
    char_count: int
    chunk_count: int
    questions_generated: int
    created_at: datetime


class GenerateRequest(BaseModel):
    per_chunk: int = Field(default=2, ge=1, le=5)
    bloom_level: str = Field(default="apply")


class ReviewDecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class QuestionEditIn(BaseModel):
    """Editable fields only.

    The citation is absent by design: an edit must not be able to detach a
    question from the passage it was drawn from.
    """

    stem: str | None = Field(default=None, min_length=10, max_length=2000)
    options: list[str] | None = Field(default=None, min_length=3, max_length=6)
    correct_index: int | None = Field(default=None, ge=0, le=5)
    explanation: str | None = Field(default=None, max_length=4000)
    distractor_rationale: list[str] | None = None
    bloom_level: str | None = None


class QuestionOut(BaseModel):
    id: int
    material_id: int
    competency_id: int | None
    kind: str
    stem: str
    options: list
    # Stripped for learners — the person being assessed does not get the key.
    correct_index: int | None
    explanation: str | None
    distractor_rationale: list
    bloom_level: str
    citation: dict
    status: str
    quality_flags: list
    review_note: str | None
    generated_by_model: str | None
    times_attempted: int
    difficulty_p: float | None
    discrimination: float | None
    created_at: datetime


class InterviewOut(BaseModel):
    """The four-axis report.

    Note there is no overall score field. The four axes are reported separately
    and `disclosure` carries the reason, so any client rendering this payload
    carries the caveat with it.
    """

    interview_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    baseline: dict
    fluency_scoring_enabled: bool
    axes: dict[str, AxisOut]
    answers: list[dict]
    disclosure: dict
    questions: list[dict]
    worker_online: bool
    max_answer_seconds: int


class AttentionIn(BaseModel):
    """Camera engagement aggregates, computed in the officer's browser.

    Every field is a summary number. There is deliberately no field that could
    carry an image, a frame, or a face landmark — the schema is where "video
    never leaves the browser" is actually enforced, rather than being a promise
    the frontend makes.
    """

    screen_gaze_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    longest_look_away_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)
    look_away_count: int | None = Field(default=None, ge=0, le=10000)
    blink_rate_per_minute: float | None = Field(default=None, ge=0.0, le=300.0)
    head_stability: float | None = Field(default=None, ge=0.0, le=1.0)
    face_present_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    frames_analysed: int = Field(default=0, ge=0, le=1_000_000)
    consent_version: str | None = Field(default=None, max_length=32)


class QuestionSlotOut(BaseModel):
    answer_id: int
    sequence: int
    question: str | None = None
    is_baseline: bool = False
    status: str
    asked_because: str | None = None
    is_generated: bool = False
    competency_name: str | None = None


class NextQuestionOut(BaseModel):
    """The question the interview chose after the last answer."""

    done: bool
    answer_id: int | None = None
    sequence: int | None = None
    question: str | None = None
    competency_name: str | None = None
    # Why the interview asked this. Shown to the officer, not logged and hidden.
    asked_because: str | None = None
    # True when the model wrote this question during the session rather than it
    # coming from the SME-approved bank. Surfaced because an officer is entitled
    # to know which questions a person vetted.
    is_generated: bool = False
    asked: int = 0
    max_questions: int = 0
