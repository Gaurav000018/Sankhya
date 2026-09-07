"""AI interview orchestration.

The session shape is: calibrate, then answer role-grounded questions chosen from
the previous answer, then a five-axis report. `services/adaptive.py` decides what
comes next; this module runs the session and scores what comes back.

The rule this module exists to enforce is in `_write_evidence`: only Knowledge
reaches the Digital Skill Twin. Communication, Fluency and Confidence are
computed, stored and shown to the officer as coaching feedback, and stop there.
Camera-derived attention does not even reach this module — see
`models_interview.AttentionMetrics`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Competency, User
from app.models_interview import (
    AnswerMetrics,
    AnswerScore,
    AnswerStatus,
    Interview,
    InterviewAnswer,
    InterviewQuestion,
    InterviewStatus,
)
from app.services.adaptive import decide_next, evidence_confidence
from app.services.coaching import build_coaching
from app.services.competency import analyse_gaps, record_interview_evidence
from app.services.interview_scoring import (
    Baseline,
    SpeechSignal,
    compute_baseline,
    score_delivery,
)

log = logging.getLogger("sankhya.interview")

DEFAULT_QUESTION_COUNT = 5
MAX_ANSWER_SECONDS = 90


class InterviewError(Exception):
    """Something the caller did wrong, surfaced as a 4xx."""


# --------------------------------------------------------------------------- #
# Starting a session
# --------------------------------------------------------------------------- #

def select_questions(
    db: Session, *, user: User, target_role_id: int | None = None,
    count: int = DEFAULT_QUESTION_COUNT,
) -> list[InterviewQuestion]:
    """Pick questions weighted toward the officer's widest gaps.

    An interview that samples competencies uniformly spends most of its time
    confirming what the Skill Twin already knows. Asking where the evidence is
    weakest is what makes the session worth the officer's time.
    """
    gaps = analyse_gaps(db, user=user, target_role_id=target_role_id)
    ranked = [g.competency_id for g in gaps if g.is_gap] or [g.competency_id for g in gaps]

    questions: list[InterviewQuestion] = []
    seen: set[int] = set()

    for competency_id in ranked:
        if len(questions) >= count:
            break
        found = db.scalars(
            select(InterviewQuestion).where(
                InterviewQuestion.competency_id == competency_id,
                InterviewQuestion.is_active.is_(True),
                InterviewQuestion.is_baseline.is_(False),
            ).limit(2)
        ).all()
        for q in found:
            if q.id not in seen and len(questions) < count:
                questions.append(q)
                seen.add(q.id)

    # Top up from anywhere if the bank is thin for this officer's gaps.
    if len(questions) < count:
        for q in db.scalars(
            select(InterviewQuestion).where(
                InterviewQuestion.is_active.is_(True),
                InterviewQuestion.is_baseline.is_(False),
            ).limit(count * 3)
        ).all():
            if q.id not in seen and len(questions) < count:
                questions.append(q)
                seen.add(q.id)

    return questions


def _opening_reason(
    db: Session, user: User, target_role_id: int | None, question: InterviewQuestion
) -> str:
    """Why the interview opens where it does, in the officer's own report."""
    for gap in analyse_gaps(db, user=user, target_role_id=target_role_id):
        if gap.competency_id == question.competency_id:
            return (
                f"{gap.competency_name} is where your evidence is thinnest against "
                f"this role — assessed at L{gap.current_level:.1f} against a "
                f"requirement of L{gap.required_level:.1f}."
            )
    return "Opening question for this role."


def get_baseline_question(db: Session) -> InterviewQuestion | None:
    return db.scalar(
        select(InterviewQuestion).where(
            InterviewQuestion.is_baseline.is_(True),
            InterviewQuestion.is_active.is_(True),
        ).limit(1)
    )


def start_interview(
    db: Session, *, user: User, target_role_id: int | None = None,
    adaptive: bool = True, max_questions: int = DEFAULT_QUESTION_COUNT,
) -> Interview:
    """Open a session, calibration first.

    An adaptive session lays out only the opening question; each one after it is
    chosen from the answer before by `services/adaptive.decide_next`. A fixed
    session lays them all out now, which is what the regression tests use — the
    same officer gets the same questions every run.
    """
    interview = Interview(
        user_id=user.id,
        target_role_id=target_role_id,
        status=InterviewStatus.CALIBRATING,
        # Snapshot the accommodation setting so a later change to the officer's
        # profile cannot retroactively alter how a past session was scored.
        fluency_scoring_enabled=user.fluency_scoring_enabled,
        is_adaptive=adaptive,
        max_questions=max_questions,
    )
    db.add(interview)
    db.flush()

    sequence = 0
    baseline = get_baseline_question(db)
    if baseline:
        db.add(InterviewAnswer(
            interview_id=interview.id, question_id=baseline.id, sequence=sequence
        ))
        sequence += 1

    questions = select_questions(
        db, user=user, target_role_id=target_role_id,
        count=1 if adaptive else max_questions,
    )
    if not questions:
        raise InterviewError(
            "No interview questions are available yet. Seed the question bank first."
        )

    for index, q in enumerate(questions):
        db.add(InterviewAnswer(
            interview_id=interview.id, question_id=q.id, sequence=sequence,
            asked_because=(
                _opening_reason(db, user, target_role_id, q)
                if adaptive and index == 0 else None
            ),
        ))
        sequence += 1

    db.add(AuditLog(
        actor_user_id=user.id,
        action="interview.started",
        entity_type="interview",
        entity_id=str(interview.id),
        meta={
            "target_role_id": target_role_id,
            "questions": len(questions),
            "adaptive": adaptive,
            "fluency_scoring_enabled": interview.fluency_scoring_enabled,
        },
    ))
    db.flush()
    return interview


# --------------------------------------------------------------------------- #
# Analysing one answer
# --------------------------------------------------------------------------- #

@dataclass
class AnalysisInput:
    """What the worker hands back after running the speech pipeline.

    Kept as a plain structure so the service can be tested without any audio,
    models or GPU.
    """

    transcript: str
    signal: SpeechSignal
    fillers: list[dict]
    pauses: dict
    prosody: dict
    duration: float
    warnings: list[str]


def _store_metrics(db: Session, answer: InterviewAnswer, data: AnalysisInput) -> AnswerMetrics:
    # Assign through the relationship, not by setting answer_id on a detached
    # row. Setting only the foreign key leaves `answer.metrics` stale for the
    # rest of the session, so anything that reads it back — `build_report`, most
    # obviously — sees None and silently reports nothing.
    metrics = answer.metrics
    if metrics is None:
        metrics = AnswerMetrics()
        answer.metrics = metrics

    metrics.words = data.signal.words
    metrics.wpm = data.signal.wpm
    metrics.filler_count = data.signal.filler_count
    metrics.filler_rate = data.signal.filler_rate
    metrics.fillers = data.fillers
    metrics.pause_count = data.pauses.get("pause_count", 0)
    metrics.long_pause_count = data.pauses.get("long_pause_count", 0)
    metrics.mean_pause_seconds = data.pauses.get("mean_pause_seconds")
    metrics.latency_to_first_word = data.pauses.get("latency_to_first_word")
    metrics.pause_spans = data.pauses.get("pause_spans")
    metrics.pitch_mean = data.prosody.get("pitch_mean")
    metrics.pitch_sd = data.prosody.get("pitch_sd")
    metrics.intensity_mean = data.prosody.get("intensity_mean")
    metrics.jitter = data.prosody.get("jitter")
    metrics.hedge_count = data.signal.hedge_count
    db.flush()
    return metrics


def apply_calibration(db: Session, answer: InterviewAnswer, data: AnalysisInput) -> Interview:
    """Record the read-aloud baseline. Never scored for knowledge.

    Reading neutral text carries no knowledge load, so what it measures is how
    this officer speaks when they are not searching for an answer.
    """
    interview = answer.interview
    _store_metrics(db, answer, data)

    baseline = compute_baseline(data.signal)
    interview.baseline_wpm = baseline.wpm
    interview.baseline_filler_rate = baseline.filler_rate
    interview.status = InterviewStatus.IN_PROGRESS

    answer.transcript_raw = data.transcript
    answer.status = AnswerStatus.SCORED   # nothing further to do with it
    db.flush()
    return interview


def _write_evidence(db: Session, answer: InterviewAnswer, knowledge: float,
                    knowledge_confidence: float) -> None:
    """Knowledge only.

    Delivery axes are not routed here, and there is no code path that would let
    them be: `record_interview_evidence` takes a knowledge level and nothing else.
    """
    question = answer.question
    if question is None or question.competency_id is None:
        return
    record_interview_evidence(
        db,
        user_id=answer.interview.user_id,
        competency_id=question.competency_id,
        knowledge_level=knowledge,
        # A question the model wrote mid-interview is discounted here: no SME has
        # agreed that it measures the competency it is filed under, so it should
        # not move a level as hard as a reviewed question does.
        knowledge_confidence=evidence_confidence(question, knowledge_confidence),
        interview_answer_ref=f"interview_answer:{answer.id}",
    )


def score_answer(db: Session, answer: InterviewAnswer, data: AnalysisInput, verdict) -> AnswerScore:
    """Assemble the five axes and write Knowledge through to the Skill Twin."""
    interview = answer.interview
    _store_metrics(db, answer, data)

    if not answer.transcript_raw:
        answer.transcript_raw = data.transcript

    delivery = score_delivery(
        data.signal,
        Baseline(wpm=interview.baseline_wpm, filler_rate=interview.baseline_filler_rate),
        fluency_enabled=interview.fluency_scoring_enabled,
    )

    score = answer.score
    if score is None:
        score = AnswerScore()
        answer.score = score

    score.knowledge = verdict.knowledge
    score.knowledge_confidence = verdict.knowledge_confidence
    score.structure = verdict.structure
    score.communication = verdict.communication
    score.fluency = delivery.fluency
    score.confidence = delivery.confidence
    score.covered_points = verdict.covered_points
    score.missed_points = verdict.missed_points
    score.rationale = {
        **(verdict.reasons or {}),
        "delivery_notes": delivery.notes,
        "pipeline_warnings": data.warnings,
        "degraded": verdict.degraded,
    }
    score.model_name = verdict.model_name
    score.judged_at = datetime.now(timezone.utc)

    answer.status = AnswerStatus.SCORED
    db.flush()

    # A degraded verdict carries confidence 0, so this writes an observation with
    # no weight: the answer is kept and shown, but unparseable model output never
    # moves anyone's competency level.
    _write_evidence(db, answer, verdict.knowledge, verdict.knowledge_confidence)

    db.add(AuditLog(
        actor_user_id=interview.user_id,
        action="interview.answer_scored",
        entity_type="interview_answer",
        entity_id=str(answer.id),
        meta={
            "knowledge": score.knowledge,
            "structure": score.structure,
            "fluency": score.fluency,
            "confidence": score.confidence,
            "model": score.model_name,
            "degraded": verdict.degraded,
        },
    ))
    db.flush()
    return score


def complete_interview(db: Session, interview: Interview) -> Interview:
    interview.status = InterviewStatus.COMPLETED
    interview.completed_at = datetime.now(timezone.utc)
    db.flush()
    return interview


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #

AXIS_LABELS = {
    "knowledge": "Knowledge",
    "structure": "Structure",
    # Judged from the transcript: was it explained so a colleague could follow?
    "communication": "Communication",
    # Measured from the audio against the officer's own baseline. Renamed from
    # "Communication delivery" when the Communication axis arrived — two things
    # sharing a name is how an accent judgement ends up read as a competency one.
    "fluency": "Delivery",
    # Speaking consistency and hesitation patterns. Distinct from
    # `knowledge_confidence`, which is the judge's certainty about its own
    # Knowledge score and is never shown as an axis.
    "confidence": "Confidence",
}


def apply_officer_only_redaction(
    items: list[dict], *, viewer_id: int | None, officer_id: int
) -> None:
    """Remove camera engagement from a report unless the officer is the reader.

    A supervisor can legitimately open a subordinate's interview — that is what
    `can_view_officer` allows — so this cannot be left to the caller. It is a
    named function rather than three lines inside `build_report` because it is
    the enforcement point for a promise made to officers in the consent text,
    and a promise enforced somewhere findable is one that survives editing.

    Fails closed: a caller that does not say who is asking gets the redacted
    report, not the officer's data.
    """
    if viewer_id is not None and viewer_id == officer_id:
        return
    for item in items:
        item.pop("attention", None)


def build_report(
    db: Session, interview: Interview, *, viewer_id: int | None = None
) -> dict:
    """The five-axis report, with the fumble timeline the UI draws.

    Axis averages are reported separately and there is deliberately no overall
    figure. If a caller wants one it has to invent it, visibly.
    """
    answers = sorted(interview.answers, key=lambda a: a.sequence)
    competencies = {c.id: c for c in db.scalars(select(Competency)).all()}

    items = []
    sums: dict[str, list[float]] = {k: [] for k in AXIS_LABELS}

    for answer in answers:
        question = answer.question
        if question is None or question.is_baseline:
            continue

        score, metrics = answer.score, answer.metrics
        attention = answer.attention
        competency = competencies.get(question.competency_id)

        if score:
            for axis in AXIS_LABELS:
                value = getattr(score, axis, None)
                if value is not None:
                    sums[axis].append(value)

        items.append({
            "answer_id": answer.id,
            "sequence": answer.sequence,
            "status": answer.status.value,
            "question": question.prompt,
            "competency": competency.name if competency else None,
            "competency_id": question.competency_id,
            "transcript": answer.transcript,
            "transcript_was_corrected": bool(
                answer.transcript_confirmed
                and answer.transcript_confirmed != answer.transcript_raw
            ),
            "duration_seconds": answer.duration_seconds,
            "video_recorded": attention is not None,
            "scores": {
                "knowledge": score.knowledge if score else None,
                "structure": score.structure if score else None,
                "communication": score.communication if score else None,
                "fluency": score.fluency if score else None,
                "confidence": score.confidence if score else None,
            } if score else None,
            "covered_points": score.covered_points if score else [],
            "missed_points": score.missed_points if score else [],
            "rationale": score.rationale if score else None,
            # Everything the fumble timeline needs: where the hesitation was,
            # not merely how much of it there was.
            "timeline": {
                "duration": answer.duration_seconds or 0,
                "fillers": (metrics.fillers or []) if metrics else [],
                "pauses": (metrics.pause_spans or []) if metrics else [],
                "latency_to_first_word": metrics.latency_to_first_word if metrics else None,
            },
            "metrics": {
                "words": metrics.words,
                "wpm": metrics.wpm,
                "filler_count": metrics.filler_count,
                "filler_rate": metrics.filler_rate,
                "long_pause_count": metrics.long_pause_count,
                "hedge_count": metrics.hedge_count,
                "pitch_mean": metrics.pitch_mean,
                "pitch_sd": metrics.pitch_sd,
                "jitter": metrics.jitter,
            } if metrics else None,
            # Coaching only, and only in the officer's own report. This block
            # is removed below for any viewer who is not the officer, so a
            # supervisor opening this interview never receives it.
            "attention": {
                "screen_gaze_ratio": attention.screen_gaze_ratio,
                "longest_look_away_seconds": attention.longest_look_away_seconds,
                "look_away_count": attention.look_away_count,
                "blink_rate_per_minute": attention.blink_rate_per_minute,
                "head_stability": attention.head_stability,
                "face_present_ratio": attention.face_present_ratio,
                "frames_analysed": attention.frames_analysed,
                "quality": attention.quality,
                "for_officer": True,
                "scored": False,
            } if attention else None,
        })

    apply_officer_only_redaction(items, viewer_id=viewer_id, officer_id=interview.user_id)

    axes = {
        axis: {
            "label": label,
            "score": round(sum(values) / len(values), 2) if values else None,
            "answers_scored": len(values),
        }
        for axis, label in AXIS_LABELS.items()
        for values in [sums[axis]]
    }

    report = {
        "interview_id": interview.id,
        "status": interview.status.value,
        "started_at": interview.started_at,
        "completed_at": interview.completed_at,
        "baseline": {
            "wpm": interview.baseline_wpm,
            "filler_rate": interview.baseline_filler_rate,
            "captured": interview.baseline_wpm is not None,
        },
        "fluency_scoring_enabled": interview.fluency_scoring_enabled,
        "axes": axes,
        "answers": items,
        # Stated in the payload, not only in the UI, so any client that renders
        # this report carries the caveat with it.
        "disclosure": {
            "composite_score": None,
            "note": (
                "Reported as five independent axes. No overall score is produced. "
                "Knowledge is the only axis recorded as competency evidence; "
                "Communication, Delivery and Confidence are coaching feedback. "
                "Communication is judged from the transcript, never from how the "
                "answer sounded. Delivery is measured against this officer's own "
                "calibration baseline, not a population average. Camera "
                "engagement, where a camera was used, is shown to the officer "
                "alone and is not an axis."
            ),
        },
    }

    # Derived from the numbers immediately above, so the advice and the figures
    # printed next to it cannot disagree. Nothing here comes from a model — see
    # `services/coaching.py` for why.
    coaching = build_coaching(report)
    report["coaching"] = {
        "strengths": coaching.strengths,
        "weaknesses": coaching.weaknesses,
        "suggestions": coaching.suggestions,
        "practice": coaching.practice,
        "focus_competency_ids": coaching.focus_competency_ids,
        "note": (
            "Worked out from the measurements in this report, not written by a "
            "model. Every line traces to a number you can see above."
        ),
    }
    return report


# --------------------------------------------------------------------------- #
# Adaptive continuation
# --------------------------------------------------------------------------- #

def advance(db: Session, interview: Interview) -> InterviewAnswer | None:
    """Append the next question, chosen from the answer before it.

    Returns None when the session has run its course — the question budget is
    spent, or the bank has nothing left to ask. That is a normal ending, and the
    caller completes the interview rather than treating it as a failure.

    Repeated calls are safe: if a question is already waiting unanswered, that
    one is returned instead of a second being queued. The frontend polls this
    after each answer is scored, and a double submission must not produce two
    questions the officer then has to answer.
    """
    if not interview.is_adaptive:
        return None

    # A question is outstanding until it reaches a terminal state. Note that a
    # planned-but-unanswered row carries AnswerStatus.RECORDED — that is the
    # column default — so "waiting" cannot be tested by status equality, only by
    # the absence of a finished one. This also stops a second question being
    # queued while the first is still being analysed.
    waiting = next(
        (
            a for a in sorted(interview.answers, key=lambda x: x.sequence)
            if a.status not in (AnswerStatus.SCORED, AnswerStatus.FAILED)
        ),
        None,
    )
    if waiting is not None:
        return waiting

    decision = decide_next(db, interview=interview, max_questions=interview.max_questions)
    if decision is None:
        return None

    answer = InterviewAnswer(
        question_id=decision.question.id,
        sequence=max((a.sequence for a in interview.answers), default=-1) + 1,
        asked_because=decision.asked_because,
    )
    # Appended through the relationship, not by setting interview_id. Setting
    # only the foreign key leaves `interview.answers` stale for the rest of the
    # session, so the next call to advance() cannot see the question this one
    # just added and queues a second — the same failure that once left
    # `answer.score` stale and made every axis read as None.
    interview.answers.append(answer)
    db.flush()

    db.add(AuditLog(
        actor_user_id=interview.user_id,
        action="interview.question_added",
        entity_type="interview_answer",
        entity_id=str(answer.id),
        meta={
            "intent": decision.intent,
            "generated": decision.is_generated,
            "competency_id": decision.question.competency_id,
        },
    ))
    db.flush()
    return answer
