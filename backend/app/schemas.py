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


class GoogleSignInRequest(BaseModel):
    """The ID token Google Identity Services hands the browser."""

    credential: str = Field(min_length=32, max_length=8192)


class AuthConfigResponse(BaseModel):
    """What sign-in methods this deployment actually offers.

    The frontend asks rather than assuming, so a build does not have to be
    rebuilt to turn Google sign-in on, and the button is never shown for a
    server that would reject it.
    """

    google_client_id: str | None
    registration_open: bool
    allowed_email_domains: list[str]


class RegisterRequest(BaseModel):
    """Self-registration.

    Division and FRAC role are deliberately absent: an officer does not get to
    declare which division they belong to or what grade they hold, because the
    whole platform rests on those being authoritative. An administrator assigns
    them after the address is verified.
    """

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    service_years: float = Field(default=0, ge=0, le=60)


class RegisterResponse(BaseModel):
    # Deliberately says nothing about whether the address was already in use.
    message: str
    email_sent: bool
    # Dev mode only, so a demo never waits on an email arriving.
    dev_verify_url: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class MessageResponse(BaseModel):
    message: str
    # Dev mode only. Never populated when EMAIL_ENABLED is true.
    dev_url: str | None = None


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
    """Opening an adaptive attempt.

    There is deliberately no `item_count`. The test decides its own length from
    how fast the estimate converges, which is the point of it — a caller that
    could ask for three items could ask for a measurement too thin to record.
    """

    competency_id: int | None = None


class WrittenAnswerIn(BaseModel):
    """A typed interview answer, for deployments with no speech pipeline."""

    # Long enough that a one-word reply cannot be scored as an answer, short
    # enough to stay within the judge's context.
    answer: str = Field(min_length=20, max_length=6000)


# --------------------------------------------------------------------------- #
# The adaptive assessment
# --------------------------------------------------------------------------- #


class AbilityOut(BaseModel):
    """The ability estimate and how wide it is.

    `level` without `level_low`/`level_high` would be a point estimate presented
    as a fact. Twelve multiple-choice items do not support that, so the interval
    travels with the number everywhere it is shown.
    """

    theta: float
    se: float
    level: float
    level_low: float
    level_high: float
    reliability: float


class AdaptiveItemOut(BaseModel):
    """One question, as served. No answer key — that is the point."""

    sequence: int
    question_id: int
    stem: str
    options: list
    bloom_level: str
    # Difficulty on the L1-L5 axis, and whether it is measured or authored.
    difficulty_level: float
    is_calibrated: bool
    # Fisher information at the estimate when this was chosen: how much the
    # question was worth asking, before anybody knew the answer.
    information: float
    asked_because: str | None


class GradedItemOut(BaseModel):
    """The item just answered, with the key now released."""

    question_id: int
    stem: str
    options: list
    selected_index: int | None
    correct_index: int
    is_correct: bool
    skipped: bool
    difficulty_level: float
    explanation: str | None
    distractor_rationale: list | None
    citation: dict | None


class AdaptiveAttemptOut(BaseModel):
    id: int
    competency_id: int | None
    competency_name: str | None
    status: str
    asked: int
    correct: int
    min_items: int
    max_items: int
    target_se: float
    ability: AbilityOut
    current_item: AdaptiveItemOut | None
    finished: bool
    stop_reason: str | None = None
    stop_explanation: str | None = None


class AdaptiveAnswerIn(BaseModel):
    question_id: int
    # None is a deliberate skip, scored as incorrect but recorded as a skip so a
    # report can tell "did not know" from "did not answer".
    selected_index: int | None = Field(default=None, ge=0, le=5)
    seconds_taken: float | None = Field(default=None, ge=0, le=3600)


class AdaptiveAnswerOut(BaseModel):
    graded: GradedItemOut
    ability: AbilityOut
    next_item: AdaptiveItemOut | None
    attempt: AdaptiveAttemptOut
    result: "AdaptiveResultOut | None" = None


class AdaptiveResultOut(BaseModel):
    """What the finished attempt concluded, and how it got there."""

    attempt_id: int
    competency_id: int | None
    competency_name: str | None
    asked: int
    correct: int
    accuracy: float
    ability: AbilityOut
    derived_level: float
    confidence: float
    stop_reason: str | None
    stop_explanation: str | None
    mean_item_level: float | None
    # The path the estimate took, item by item.
    trace: list[dict]
    review: list[GradedItemOut]
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
    # Strengths, weaknesses and next steps, derived from the numbers above.
    # Declared explicitly: `build_report` has always produced it, but a response
    # model drops any field it does not name, so the report reached the browser
    # without its feedback and nothing anywhere raised an error.
    coaching: dict | None = None
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
    hands_visible_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    hand_movement: float | None = Field(default=None, ge=0.0, le=1.0)
    face_touch_count: int | None = Field(default=None, ge=0, le=10_000)
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
