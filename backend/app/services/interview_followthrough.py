"""Turn what an interview found into things the officer can actually do next.

The interview is only worth sitting if something follows from it. This assembles
that: courses against the competencies that came up weakest, a learning path
where the catalogue can build one, and — the part no course covers — practice
the officer can do without booking anything.

It reuses the recommender rather than ranking courses a second way. An officer
who sees one set of recommendations on their development plan and a different
set after an interview has no way to know which to believe, and the honest
answer is that there is one ranking and the interview only changed its input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Competency, User
from app.models_interview import Interview
from app.services.competency import analyse_gaps
from app.services.recommender import score_courses

# One interview is a handful of observations. Offering ten courses off the back
# of three questions implies a confidence the evidence does not carry.
MAX_COMPETENCIES = 3
COURSES_PER_COMPETENCY = 2


@dataclass
class FollowThrough:
    competencies: list[dict] = field(default_factory=list)
    practice: list[dict] = field(default_factory=list)
    caveat: str = ""


def _practice_activities(
    competency_names: list[str], missed_points: list[str], weak_axes: list[str]
) -> list[dict]:
    """Things to do that are not a course.

    Most of what an interview exposes is not a knowledge gap a course fills —
    it is that the officer knows the material and cannot yet explain it under
    time pressure. Sending them on a three-day course for that wastes three
    days.
    """
    activities: list[dict] = []

    if missed_points:
        activities.append({
            "kind": "recall",
            "title": "Write out the points you missed, from memory",
            "detail": (
                "Before reading anything: "
                + "; ".join(missed_points[:3])
                + ". Then check what you wrote against the source. Retrieving it "
                "cold is what fixes it in memory; re-reading it feels like "
                "learning and is not."
            ),
        })

    for name in competency_names[:2]:
        activities.append({
            "kind": "explain",
            "title": f"Explain {name} to someone outside your division",
            "detail": (
                "Five minutes, no notes, to a colleague who does not do this "
                "work. The questions they ask are the parts you have not "
                "actually understood yet."
            ),
        })

    if "structure" in weak_axes:
        activities.append({
            "kind": "drill",
            "title": "Answer three questions in the same shape",
            "detail": (
                "Direct answer, then why, then one concrete example. Record "
                "yourself and listen back once. Structure is a habit rather "
                "than knowledge, and it changes in a week."
            ),
        })

    if "communication" in weak_axes:
        activities.append({
            "kind": "drill",
            "title": "Define your terms out loud before you use them",
            "detail": (
                "Take a briefing note you have written and read it aloud, "
                "defining each technical term the first time it appears. The "
                "ones you cannot define quickly are the ones your audience "
                "loses you on."
            ),
        })

    if "confidence" in weak_axes:
        activities.append({
            "kind": "drill",
            "title": "Say what you would check, rather than hedging",
            "detail": (
                "Where you are unsure, 'I would check the sampling frame "
                "documentation for that' reads as judgement. 'I think maybe it "
                "is something like that' reads as a guess, and it is the same "
                "amount of knowledge either way."
            ),
        })

    activities.append({
        "kind": "mock",
        "title": "Sit this interview again in a fortnight",
        "detail": (
            "Against the same target role, so the two are comparable. Leave "
            "enough time to have actually done something in between — a "
            "re-attempt the next day measures your memory of the questions."
        ),
    })

    return activities


def build_follow_through(
    db: Session, *, user: User, interview: Interview, report: dict
) -> FollowThrough:
    """Courses, paths and practice, from this interview's own findings."""
    coaching = report.get("coaching") or {}
    focus_ids = list(coaching.get("focus_competency_ids") or [])[:MAX_COMPETENCIES]

    # Weak axes, read back off the report so the advice cannot disagree with the
    # numbers the officer is looking at.
    weak_axes = [
        axis for axis, block in (report.get("axes") or {}).items()
        if (block or {}).get("score") is not None and block["score"] <= 2.5
    ]

    missed: list[str] = []
    for answer in report.get("answers") or []:
        for point in answer.get("missed_points") or []:
            if point not in missed:
                missed.append(str(point))

    gaps = {
        gap.competency_id: gap
        for gap in analyse_gaps(db, user=user, target_role_id=interview.target_role_id)
    }

    competencies: list[dict] = []
    names: list[str] = []

    for competency_id in focus_ids:
        competency = db.get(Competency, competency_id)
        gap = gaps.get(competency_id)
        if competency is None:
            continue
        names.append(competency.name)

        courses: list[dict] = []
        if gap is not None:
            for scored in score_courses(
                db, user=user, gap=gap, limit=COURSES_PER_COMPETENCY
            ):
                courses.append({
                    "course_id": scored.course.id,
                    "title": scored.course.title,
                    "provider": scored.course.provider,
                    "level_from": scored.course.level_from,
                    "level_to": scored.course.level_to,
                    "duration_hours": scored.course.duration_hours,
                    "score": scored.score,
                    "reason": scored.reason,
                })

        competencies.append({
            "competency_id": competency_id,
            "competency_name": competency.name,
            "current_level": gap.current_level if gap else None,
            "required_level": gap.required_level if gap else None,
            "courses": courses,
            # Said plainly, because an empty course list otherwise reads as a
            # system failure rather than a fact about the catalogue.
            "note": None if courses else (
                "No course in the catalogue covers the band you need here. The "
                "practice activities below are what is available, and this is "
                "worth raising with your training coordinator."
            ),
            "can_build_path": bool(courses),
        })

    return FollowThrough(
        competencies=competencies,
        practice=_practice_activities(names, missed, weak_axes),
        caveat=(
            "Drawn from one interview, which is a handful of observations rather "
            "than a verdict. Completing a course does not by itself raise a "
            "competency level in this system — it records a low-weight "
            "observation, and an assessment afterwards is what confirms it."
        ),
    )
