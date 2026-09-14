"""The guided journey: what an officer did, what it showed, and what to do next.

This composes rather than computes. Every number here already exists — the
Skill Twin derives levels from evidence, `analyse_gaps` ranks them against the
role, `forecast` projects movement, `recommend` ranks courses. What was missing
is the join: a single account of *this officer's* assessment and interview
together, and a roadmap ordered by what actually stands between them and the
next role.

Two rules it keeps:

**It never introduces a number that is not already evidence.** Where the
assessment and the interview disagree, that disagreement is reported rather than
averaged — an officer scoring L4 on a quiz and L2 in an interview on the same
competency has learned something the mean would erase.

**It says when it does not know.** A competency with no assessment and no
interview gets "not measured", not a zero. Absence of evidence is the one thing
this platform must never render as evidence of absence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Competency,
    EvidenceSource,
    FracRole,
    ProficiencyEvidence,
    User,
)
from app.models_interview import Interview, InterviewStatus
from app.models_quiz import AttemptStatus, QuizAttempt
from app.services.competency import analyse_gaps
from app.services.recommender import recommend
from app.services.simulator import forecast

# How far back a journey looks. Long enough to include a session an officer
# started last week, short enough that it describes them now.
WINDOW_DAYS = 90

log = logging.getLogger("sankhya.journey")


@dataclass
class Signal:
    """One competency, as seen by one method."""

    competency_id: int
    competency_code: str
    competency_name: str
    level: float | None
    records: int


@dataclass
class Divergence:
    competency_name: str
    assessment_level: float
    interview_level: float
    gap: float
    reading: str


@dataclass
class RoadmapStep:
    order: int
    competency_name: str
    current_level: float
    required_level: float
    gap: float
    criticality: str
    why: str
    action: str
    course_title: str | None
    course_provider: str | None
    course_hours: float | None
    course_reason: str | None


@dataclass
class Journey:
    assessment: list[Signal] = field(default_factory=list)
    interview: list[Signal] = field(default_factory=list)
    divergences: list[Divergence] = field(default_factory=list)
    roadmap: list[RoadmapStep] = field(default_factory=list)
    narrative: list[str] = field(default_factory=list)
    target_role: str | None = None
    readiness_now: float = 0.0
    months_to_target: float | None = None
    projected_date: str | None = None
    unmeasured: list[str] = field(default_factory=list)
    caveat: str = ""


def _levels_by_source(
    db: Session, user: User, sources: list[EvidenceSource], since: datetime
) -> dict[int, tuple[float, int]]:
    """Mean level and record count per competency, for the given sources.

    The mean is over this window only. A quiz taken today and one taken a year
    ago are not the same statement about someone, and the Skill Twin already
    handles long-run blending with recency decay — this is deliberately the
    short view, so the journey describes the session the officer just completed.
    """
    rows = db.scalars(
        select(ProficiencyEvidence).where(
            ProficiencyEvidence.user_id == user.id,
            ProficiencyEvidence.source.in_(sources),
            ProficiencyEvidence.created_at >= since,
        )
    ).all()

    buckets: dict[int, list[float]] = {}
    for row in rows:
        buckets.setdefault(row.competency_id, []).append(row.level_estimate)

    return {
        cid: (round(sum(vals) / len(vals), 2), len(vals)) for cid, vals in buckets.items()
    }


def _signals(
    db: Session, levels: dict[int, tuple[float, int]], competencies: dict[int, Competency]
) -> list[Signal]:
    out = [
        Signal(
            competency_id=cid,
            competency_code=competencies[cid].code,
            competency_name=competencies[cid].name,
            level=level,
            records=count,
        )
        for cid, (level, count) in levels.items()
        if cid in competencies
    ]
    return sorted(out, key=lambda s: s.level or 0)


def _read_divergence(assessment: float, interview: float) -> str:
    """Name what a gap between the two methods usually means.

    Deliberately hedged. These are two small samples of the same person, and the
    honest reading is a prompt for a conversation, not a diagnosis.
    """
    delta = assessment - interview
    if delta >= 1.0:
        return (
            "Recognises the right answer but explains it less convincingly out loud. "
            "Often means the knowledge is there and the articulation is not yet — "
            "which matters most in exactly the senior roles that involve defending a "
            "number to someone else."
        )
    return (
        "Explains it better than the multiple-choice score suggests. Either the "
        "items happened to probe an unfamiliar corner, or the understanding is "
        "real but not yet reliable under a forced choice."
    )


def build_journey(
    db: Session, *, user: User, target_role_id: int | None = None
) -> Journey:
    """Compose the analysis and roadmap for one officer."""
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    competencies = {c.id: c for c in db.scalars(select(Competency))}

    assessment_levels = _levels_by_source(
        db, user, [EvidenceSource.QUIZ, EvidenceSource.DIAGNOSTIC], since
    )
    interview_levels = _levels_by_source(db, user, [EvidenceSource.INTERVIEW], since)

    journey = Journey()
    journey.assessment = _signals(db, assessment_levels, competencies)
    journey.interview = _signals(db, interview_levels, competencies)

    # --- where the two methods disagree ------------------------------------ #
    for cid, (a_level, _) in assessment_levels.items():
        if cid not in interview_levels or cid not in competencies:
            continue
        i_level = interview_levels[cid][0]
        if abs(a_level - i_level) < 0.75:
            continue
        journey.divergences.append(
            Divergence(
                competency_name=competencies[cid].name,
                assessment_level=a_level,
                interview_level=i_level,
                gap=round(abs(a_level - i_level), 2),
                reading=_read_divergence(a_level, i_level),
            )
        )
    journey.divergences.sort(key=lambda d: d.gap, reverse=True)

    # --- the roadmap, ordered by what actually blocks the next role --------- #
    target = db.get(FracRole, target_role_id) if target_role_id else None
    if target is None and user.frac_role_id:
        current = db.get(FracRole, user.frac_role_id)
        if current is not None:
            target = db.scalar(
                select(FracRole).where(FracRole.level_order == current.level_order + 1)
            )
    journey.target_role = target.name if target else None

    gaps = analyse_gaps(db, user=user, target_role_id=target.id if target else None)
    open_gaps = [g for g in gaps if g.is_gap]
    open_gaps.sort(key=lambda g: (g.criticality != "critical", -g.gap))

    measured = set(assessment_levels) | set(interview_levels)
    journey.unmeasured = [
        competencies[g.competency_id].name
        for g in open_gaps
        if g.competency_id not in measured and g.competency_id in competencies
    ][:5]

    # Keyed on the first recommendation per competency: `recommend` returns
    # several ranked options for each gap, and the roadmap wants the top one.
    # `setdefault` keeps the best; a plain dict comprehension would keep the
    # worst.
    recommendations: dict[int, object] = {}
    try:
        for rec in recommend(db, user=user, target_role_id=target.id if target else None):
            recommendations.setdefault(rec.competency_id, rec)
    except SQLAlchemyError as exc:
        # A roadmap without courses is still a roadmap: losing the catalogue
        # should not lose the ordering of what to work on. Narrow on purpose —
        # a bare `except Exception` here previously swallowed a TypeError from a
        # wrong keyword argument, and every step silently lost its course with
        # nothing logged.
        log.error("Catalogue unavailable for roadmap (%s)", type(exc).__name__)

    for index, gap in enumerate(open_gaps[:6], start=1):
        rec = recommendations.get(gap.competency_id)
        seen_in = []
        if gap.competency_id in assessment_levels:
            seen_in.append("the assessment")
        if gap.competency_id in interview_levels:
            seen_in.append("the interview")

        if seen_in:
            why = (
                f"Measured at L{gap.current_level} in {' and '.join(seen_in)}, against "
                f"L{gap.required_level} required."
            )
        else:
            why = (
                f"Required at L{gap.required_level} for this role, and not yet "
                "measured — take an assessment on it so the gap is real rather "
                "than assumed."
            )

        journey.roadmap.append(
            RoadmapStep(
                order=index,
                competency_name=gap.competency_name,
                current_level=gap.current_level,
                required_level=gap.required_level,
                gap=round(gap.gap, 2),
                criticality=gap.criticality,
                why=why,
                action=(
                    "Close this before the others — it is marked critical for the role."
                    if gap.criticality == "critical"
                    else "Work on this once the critical gaps are closing."
                ),
                course_title=rec.course.title if rec else None,
                course_provider=rec.course.provider if rec else None,
                course_hours=rec.course.duration_hours if rec else None,
                course_reason=rec.reason if rec else None,
            )
        )

    # --- projection ---------------------------------------------------------- #
    if target is not None:
        # `forecast` returns a plain dict, which is also what the promotion
        # endpoint serialises directly.
        projection = forecast(db, user=user, target_role_id=target.id)
        journey.readiness_now = projection.get("readiness_now", 0.0)
        slowest = projection.get("slowest") or {}
        journey.months_to_target = slowest.get("months_to_close")
        journey.projected_date = slowest.get("projected_date")
        journey.caveat = projection.get("caveat", "")

    journey.narrative = _narrative(db, user, journey, len(open_gaps))
    return journey


def _narrative(db: Session, user: User, journey: Journey, open_gap_count: int) -> list[str]:
    """Plain sentences an officer can read without knowing the model.

    Assembled from what was actually measured. Nothing here is generated by a
    language model: a paragraph describing someone's competence has to be
    reproducible and defensible, and a sentence that changes between two runs of
    the same data is neither.
    """
    lines: list[str] = []

    attempts = db.scalars(
        select(QuizAttempt).where(
            QuizAttempt.user_id == user.id, QuizAttempt.status == AttemptStatus.SUBMITTED
        )
    ).all()
    interviews = db.scalars(
        select(Interview).where(
            Interview.user_id == user.id, Interview.status == InterviewStatus.COMPLETED
        )
    ).all()

    lines.append(
        f"You have completed {len(attempts)} assessment"
        f"{'' if len(attempts) == 1 else 's'} and {len(interviews)} interview"
        f"{'' if len(interviews) == 1 else 's'}. "
        f"Everything below is derived from the {len(journey.assessment) + len(journey.interview)} "
        "competency readings those produced — no part of it is self-reported."
    )

    if journey.assessment:
        weakest = journey.assessment[0]
        strongest = journey.assessment[-1]
        if weakest.competency_id != strongest.competency_id:
            lines.append(
                f"The assessment put you strongest on {strongest.competency_name} "
                f"(L{strongest.level}) and weakest on {weakest.competency_name} "
                f"(L{weakest.level})."
            )

    if journey.interview:
        weakest = journey.interview[0]
        lines.append(
            f"The interview scored {weakest.competency_name} lowest at L{weakest.level}. "
            "Interview evidence carries the Knowledge axis only — how an answer was "
            "delivered never becomes a competency level."
        )

    if journey.divergences:
        first = journey.divergences[0]
        lines.append(
            f"The two methods disagree most on {first.competency_name}: "
            f"L{first.assessment_level} written against L{first.interview_level} spoken. "
            f"{first.reading}"
        )

    if journey.target_role:
        lines.append(
            f"Against {journey.target_role} you are {journey.readiness_now}% ready, with "
            f"{open_gap_count} competenc{'y' if open_gap_count == 1 else 'ies'} still short."
        )
        if journey.projected_date:
            lines.append(
                f"At your current rate of movement the binding gap closes around "
                f"{journey.projected_date}. That is an extrapolation of your own "
                "history, not a promise."
            )
        elif journey.months_to_target is None:
            lines.append(
                "No completion date is projected: the widest gaps are not currently "
                "moving, so there is no rate to extrapolate from."
            )

    if journey.unmeasured:
        lines.append(
            "Not yet measured: "
            + ", ".join(journey.unmeasured)
            + ". These are required for the role but have no assessment or interview "
            "evidence, so their gap is assumed from the role requirement rather than "
            "observed."
        )

    return lines
