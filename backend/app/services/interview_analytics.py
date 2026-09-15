"""Aggregate interview statistics for workforce planning.

Two rules shape everything here.

**No camera data, ever.** This module does not import `AttentionMetrics` and
has no query that could reach it. Officers are told their camera feedback is
theirs alone; an analytics screen that quietly aggregated it would make that
false, and "we only show averages" is not a defence when a division has four
people in it.

**Small cohorts are suppressed, not rounded.** A mean over three officers is a
short step from naming them, and in a division of four the person who scored
lowest can work out that it was them. Anything below `MIN_COHORT` reports the
count and withholds the figure, which is a more honest screen than one that
silently drops small divisions and lets the reader assume they had no gaps.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Competency, Division, User
from app.models_interview import (
    AnswerScore,
    AnswerStatus,
    Interview,
    InterviewAnswer,
    InterviewQuestion,
    InterviewStatus,
)

# Below this, a figure is withheld rather than published. Five is a common floor
# for statistical disclosure control and is what MoSPI's own dissemination
# practice would expect of a table like this.
MIN_COHORT = 5

# Axes reported in aggregate. Deliberately enumerated rather than read from the
# model, so a new column cannot appear on an admin screen by being added to the
# table — and `fluency` is absent on purpose: it is NULL for officers using the
# accommodation, so an average over it would quietly compare two populations.
REPORTED_AXES = ("knowledge", "structure", "communication", "confidence")

WEAK_LEVEL = 2.5


@dataclass
class Suppressed:
    """A figure withheld because the cohort was too small to publish."""

    officers: int
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "value": None,
            "officers": self.officers,
            "suppressed": True,
            "reason": self.reason or (
                f"Fewer than {MIN_COHORT} officers. Publishing a mean over this "
                "few identifies them."
            ),
        }


def _published(value: float | None, officers: int, digits: int = 2) -> dict:
    if officers < MIN_COHORT:
        return Suppressed(officers=officers).as_dict()
    return {
        "value": None if value is None else round(float(value), digits),
        "officers": officers,
        "suppressed": False,
    }


def _scored_answers_query(division_id: int | None):
    """Answers that were actually scored, excluding the calibration read-aloud."""
    stmt = (
        select(AnswerScore, InterviewQuestion, User)
        .select_from(AnswerScore)
        .join(InterviewAnswer, InterviewAnswer.id == AnswerScore.answer_id)
        .join(InterviewQuestion, InterviewQuestion.id == InterviewAnswer.question_id)
        .join(Interview, Interview.id == InterviewAnswer.interview_id)
        .join(User, User.id == Interview.user_id)
        .where(
            InterviewQuestion.is_baseline.is_(False),
            InterviewAnswer.status == AnswerStatus.SCORED,
            # A degraded verdict carries confidence 0 and a placeholder score.
            # Averaging those in would move a division's figure because a model
            # call failed, which is not a fact about anybody's competence.
            AnswerScore.knowledge_confidence > 0,
        )
    )
    if division_id is not None:
        stmt = stmt.where(User.division_id == division_id)
    return stmt


def interview_overview(db: Session, *, division_id: int | None = None) -> dict:
    """Aggregate interview results, suppressed where the cohort is too small."""
    rows = db.execute(_scored_answers_query(division_id)).all()

    officers = {user.id for _, _, user in rows}
    officer_count = len(officers)

    axis_values: dict[str, list[float]] = {axis: [] for axis in REPORTED_AXES}
    per_competency: dict[int, list[float]] = {}
    missed_points: dict[str, int] = {}
    generated_used = 0

    for score, question, _user in rows:
        for axis in REPORTED_AXES:
            value = getattr(score, axis, None)
            if value is not None:
                axis_values[axis].append(float(value))
        if question.competency_id is not None and score.knowledge is not None:
            per_competency.setdefault(question.competency_id, []).append(
                float(score.knowledge)
            )
        for point in score.missed_points or []:
            missed_points[str(point)] = missed_points.get(str(point), 0) + 1
        if question.is_generated:
            generated_used += 1

    competency_names = {
        c.id: c.name for c in db.scalars(select(Competency)).all()
    }

    # Competencies where officers actually struggled. Suppressed per competency,
    # because a competency only two people were asked about is as identifying as
    # a small division.
    weak: list[dict] = []
    for competency_id, values in per_competency.items():
        mean = sum(values) / len(values)
        published = _published(mean, len(values))
        weak.append({
            "competency_id": competency_id,
            "competency_name": competency_names.get(competency_id, ""),
            "answers": len(values),
            "mean_knowledge": published,
            # None, not False, when the mean is withheld. A boolean derived from
            # a suppressed number leaks most of what suppressing it protected:
            # "withheld, and below 2.5" over a single answer describes one
            # officer as precisely as printing the figure would.
            "is_weak": None if published["suppressed"] else mean < WEAK_LEVEL,
        })
    weak.sort(key=lambda row: (
        row["mean_knowledge"]["value"] if row["mean_knowledge"]["value"] is not None else 99
    ))

    sessions = db.scalar(
        select(func.count(Interview.id)).where(
            Interview.status == InterviewStatus.COMPLETED,
            *([Interview.user_id.in_(
                select(User.id).where(User.division_id == division_id)
            )] if division_id is not None else []),
        )
    ) or 0

    return {
        "cohort": {
            "officers_interviewed": officer_count,
            "sessions_completed": int(sessions),
            "answers_scored": len(rows),
            "below_disclosure_threshold": officer_count < MIN_COHORT,
        },
        "axes": {
            axis: _published(
                sum(values) / len(values) if values else None, officer_count
            )
            for axis, values in axis_values.items()
        },
        "weakest_competencies": weak[:10],
        "most_missed_points": [
            {"point": point, "times": times}
            for point, times in sorted(missed_points.items(), key=lambda kv: -kv[1])[:10]
        ] if officer_count >= MIN_COHORT else [],
        "adaptive": {
            "generated_questions_answered": generated_used,
            "note": (
                "Questions the model wrote during a session. Their evidence is "
                "discounted because no subject-matter expert reviewed them; a "
                "high number here means the bank needs more questions, not that "
                "officers did anything differently."
            ),
        },
        "disclosure": {
            "min_cohort": MIN_COHORT,
            "note": (
                f"Figures over fewer than {MIN_COHORT} officers are withheld "
                "rather than shown, because a mean over a handful of people "
                "identifies them. Camera engagement is not aggregated here or "
                "anywhere else — it is shown to the officer who recorded it and "
                "to nobody else."
            ),
        },
    }


def division_interview_trends(db: Session) -> dict:
    """Per-division interview participation and Knowledge, for the admin view."""
    rows = db.execute(
        select(
            Division.id, Division.code, Division.name,
            func.count(func.distinct(Interview.user_id)),
            func.avg(AnswerScore.knowledge),
        )
        .select_from(AnswerScore)
        .join(InterviewAnswer, InterviewAnswer.id == AnswerScore.answer_id)
        .join(InterviewQuestion, InterviewQuestion.id == InterviewAnswer.question_id)
        .join(Interview, Interview.id == InterviewAnswer.interview_id)
        .join(User, User.id == Interview.user_id)
        .join(Division, Division.id == User.division_id)
        .where(
            InterviewQuestion.is_baseline.is_(False),
            InterviewAnswer.status == AnswerStatus.SCORED,
            AnswerScore.knowledge_confidence > 0,
        )
        .group_by(Division.id, Division.code, Division.name)
        .order_by(Division.code)
    ).all()

    return {
        "divisions": [
            {
                "division_id": division_id,
                "code": code,
                "name": name,
                "officers_interviewed": int(officers),
                "mean_knowledge": _published(mean, int(officers)),
            }
            for division_id, code, name, officers, mean in rows
        ],
        "note": (
            "Participation is voluntary, so a division with few interviews has "
            "told you about its uptake, not about its competence. Read this "
            "alongside the evidence heatmap rather than instead of it."
        ),
    }
