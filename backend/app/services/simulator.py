"""Promotion simulator and readiness forecasting.

The readiness engine answers "how ready am I?". These answer the two questions
that follow, which are the ones an officer actually cares about:

* **What if I did X?** — pick courses, see the projected readiness.
* **When will I get there?** — at the rate evidence has actually been
  accumulating, how long until the target is met.

Both are projections and are labelled as such. A forecast presented as a
commitment is worse than no forecast, because someone plans a posting around it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competency, Criticality, FracRole, User
from app.models_learning import Course
from app.services.competency import GapItem, analyse_gaps
from app.services.lift import officer_lift

# A course does not deliver its full nominal gain. Completion is weak evidence
# and the model weights it at 0.40, so projecting the headline figure would
# systematically overpromise.
COURSE_YIELD = 0.5

# Below this monthly rate, projecting a date is arithmetic dressed up as insight.
MIN_MONTHLY_RATE = 0.02

CRITICALITY_WEIGHT = {
    Criticality.CRITICAL.value: 4.0,
    Criticality.HIGH.value: 3.0,
    Criticality.MEDIUM.value: 2.0,
    Criticality.LOW.value: 1.0,
}


def _weighted_readiness(gaps: list[GapItem], levels: dict[int, float]) -> float:
    achieved = demanded = 0.0
    for gap in gaps:
        weight = CRITICALITY_WEIGHT.get(gap.criticality, 2.0)
        current = levels.get(gap.competency_id, gap.current_level)
        achieved += weight * min(current, gap.required_level)
        demanded += weight * gap.required_level
    return round(100.0 * achieved / demanded, 1) if demanded else 0.0


@dataclass
class SimulatedStep:
    course_id: int
    title: str
    competency_name: str
    level_before: float
    level_after: float
    readiness_after: float
    readiness_gain: float
    duration_hours: float
    # Why a step is worth nothing, when it is worth nothing. A course that moves
    # the readiness figure by 0.0 is a course the officer should probably drop
    # from the plan, and silence there looks like a broken calculation rather
    # than a real answer.
    note: str | None = None


def simulate(
    db: Session, *, user: User, course_ids: list[int], target_role_id: int | None = None
) -> dict:
    """Project readiness if these courses were completed.

    Applied in the order given, because a course's contribution depends on where
    the officer already is — two courses covering the same band do not add up.
    """
    gaps = analyse_gaps(db, user=user, target_role_id=target_role_id)
    if not gaps:
        return {"error": "No role requirements to simulate against."}

    levels = {gap.competency_id: gap.current_level for gap in gaps}
    baseline = _weighted_readiness(gaps, levels)

    competencies = {c.id: c.name for c in db.scalars(select(Competency)).all()}
    steps: list[SimulatedStep] = []
    running = baseline

    # Courses the officer chose that this role does not ask for. Reported rather
    # than dropped: a plan that quietly returns three of the five courses you
    # picked looks like a bug, and the officer cannot tell which two vanished.
    excluded: list[dict] = []

    for course_id in course_ids:
        course = db.get(Course, course_id)
        if course is None:
            excluded.append({"course_id": course_id, "title": None,
                             "reason": "No such course."})
            continue
        if course.competency_id is None:
            excluded.append({"course_id": course.id, "title": course.title,
                             "reason": "This course is not mapped to a competency, "
                                       "so it cannot be scored against a role."})
            continue
        if course.competency_id not in levels:
            # Not required by this role: completing it is fine, but it moves
            # nothing here, and saying otherwise would be flattering.
            excluded.append({
                "course_id": course.id,
                "title": course.title,
                "reason": "Worth doing, but this role does not require that "
                          "competency, so it does not count toward this promotion.",
            })
            continue

        before = levels[course.competency_id]
        # Only the part of the course above where the officer already is counts.
        headroom = max(0.0, course.level_to - max(before, course.level_from))
        after = min(5.0, before + headroom * COURSE_YIELD)
        levels[course.competency_id] = after

        readiness = _weighted_readiness(gaps, levels)
        gain = round(readiness - running, 1)

        required = next(
            (g.required_level for g in gaps if g.competency_id == course.competency_id),
            None,
        )
        note = None
        if headroom <= 0:
            note = (
                f"This course covers up to level {course.level_to:g}, and the "
                f"officer is already at {before:.2f} — including it changes "
                "nothing. Courses are applied in order, so an earlier one in "
                "this plan may have overtaken it."
            )
        elif gain <= 0 and required is not None and before >= required:
            note = (
                f"The level rises, but {required:g} is all this role asks for and "
                f"the officer is already there. Worth doing for the skill; it "
                "does not move readiness for this promotion."
            )
        elif gain <= 0:
            note = "Too small a movement to change the readiness figure."

        steps.append(SimulatedStep(
            course_id=course.id,
            title=course.title,
            competency_name=competencies.get(course.competency_id, ""),
            level_before=round(before, 2),
            level_after=round(after, 2),
            readiness_after=readiness,
            readiness_gain=gain,
            duration_hours=course.duration_hours,
            note=note,
        ))
        running = readiness

    role = db.get(FracRole, target_role_id) if target_role_id else user.frac_role
    total_hours = sum(step.duration_hours for step in steps)

    return {
        "target_role": role.name if role else None,
        "readiness_now": baseline,
        "readiness_projected": running,
        "gain": round(running - baseline, 1),
        "total_hours": round(total_hours, 1),
        "estimated_weeks": max(1, round(total_hours / 3.0)) if total_hours else 0,
        "steps": [vars(step) for step in steps],
        "excluded": excluded,
        "assumptions": (
            f"A course is credited with {COURSE_YIELD:.0%} of the band it covers, "
            "and only the part above the officer's current level. Course "
            "completion is weak evidence in this model, so the projection is "
            "deliberately conservative — an assessment afterwards is what "
            "actually moves the profile."
        ),
        "caveat": (
            "A projection, not a commitment. Completing a course does not by "
            "itself raise a competency level here: it records a low-weight "
            "observation, and a quiz, interview or demonstrated task is what "
            "confirms it."
        ),
    }


def forecast(
    db: Session, *, user: User, target_role_id: int | None = None, window_days: int = 180
) -> dict:
    """When the officer reaches the target, at the rate they have been moving.

    The rate comes from measured lift over the window, not from a plan. If
    nothing has moved, this says so instead of projecting a date from noise.
    """
    gaps = analyse_gaps(db, user=user, target_role_id=target_role_id)
    open_gaps = [gap for gap in gaps if gap.is_gap]
    levels = {gap.competency_id: gap.current_level for gap in gaps}
    readiness_now = _weighted_readiness(gaps, levels)

    lifts = officer_lift(db, user=user, days=window_days)
    months = window_days / 30.0
    by_competency = {item.competency_id: item.change / months for item in lifts}

    overall_rate = (
        sum(by_competency.values()) / len(by_competency) if by_competency else 0.0
    )

    projections = []
    for gap in sorted(open_gaps, key=lambda g: g.gap, reverse=True):
        rate = by_competency.get(gap.competency_id, 0.0)
        if rate >= MIN_MONTHLY_RATE:
            months_needed = gap.gap / rate
            eta = datetime.now(timezone.utc) + timedelta(days=months_needed * 30)
            projections.append({
                "competency_name": gap.competency_name,
                "gap": gap.gap,
                "monthly_rate": round(rate, 3),
                "months_to_close": round(months_needed, 1),
                "projected_date": eta.strftime("%B %Y"),
            })
        else:
            projections.append({
                "competency_name": gap.competency_name,
                "gap": gap.gap,
                "monthly_rate": round(rate, 3),
                "months_to_close": None,
                "projected_date": None,
                "note": (
                    "Not moving. At the current rate this gap does not close, so "
                    "no date is projected."
                ),
            })

    movable = [p for p in projections if p["months_to_close"] is not None]
    role = db.get(FracRole, target_role_id) if target_role_id else user.frac_role

    return {
        "target_role": role.name if role else None,
        "window_days": window_days,
        "readiness_now": readiness_now,
        "monthly_rate": round(overall_rate, 3),
        "open_gaps": len(open_gaps),
        "gaps_on_track": len(movable),
        "gaps_stalled": len(open_gaps) - len(movable),
        "slowest": max(movable, key=lambda p: p["months_to_close"]) if movable else None,
        "projections": projections,
        "caveat": (
            "Projected from the rate evidence has accumulated over the last "
            f"{window_days} days, which reflects everything that happened in that "
            "period rather than a training plan. Evidence also decays, so a "
            "competency with no new evidence drifts downward and will never "
            "show a closing date."
        ),
    }
