"""Course efficacy: does a course actually move competency?

No LMS measures this. iGOT records that an officer completed a course; nothing
records whether they were any better afterwards. Because every assessment in
this platform writes dated evidence, the before/after is already available.

**What this measures, honestly.** Lift is the change in an officer's assessed
level on the course's competency, comparing evidence in a window before
completion against evidence in a window after. That is a real measurement and it
is *correlational, not causal*: other learning happened in the same period, and
officers who choose a course are not a random sample. It is reported as
"observed lift", never as "this course caused". The confound is stated in the
API response rather than left for a reader to discover.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvidenceSource, ProficiencyEvidence, User
from app.models_learning import Course, CourseCompletion

# Evidence within this many days either side of completion counts.
WINDOW_DAYS = 120

# Below this, a lift figure is noise. Reported, but flagged as provisional.
MIN_SAMPLE = 5

# Course completion itself writes evidence. Including it would let a course
# prove its own worth, so it is excluded from both windows.
EXCLUDED_SOURCES = {EvidenceSource.LEARNING_ACTIVITY, EvidenceSource.SELF}


@dataclass
class CourseEfficacy:
    course_id: int
    title: str
    provider: str | None
    competency_name: str | None
    completions: int
    measured: int
    median_lift: float | None
    mean_lift: float | None
    improved: int
    unchanged_or_worse: int
    verdict: str
    note: str

    @property
    def is_provisional(self) -> bool:
        return self.measured < MIN_SAMPLE


def _mean_level(rows: list[ProficiencyEvidence]) -> float | None:
    usable = [r for r in rows if r.source not in EXCLUDED_SOURCES]
    if not usable:
        return None
    return sum(r.level_estimate for r in usable) / len(usable)


def measure_course(db: Session, course: Course) -> CourseEfficacy:
    completions = db.scalars(
        select(CourseCompletion).where(CourseCompletion.course_id == course.id)
    ).all()

    lifts: list[float] = []
    for completion in completions:
        if course.competency_id is None:
            break
        at = completion.completed_at
        window = timedelta(days=WINDOW_DAYS)

        before = db.scalars(
            select(ProficiencyEvidence).where(
                ProficiencyEvidence.user_id == completion.user_id,
                ProficiencyEvidence.competency_id == course.competency_id,
                ProficiencyEvidence.created_at < at,
                ProficiencyEvidence.created_at >= at - window,
            )
        ).all()
        after = db.scalars(
            select(ProficiencyEvidence).where(
                ProficiencyEvidence.user_id == completion.user_id,
                ProficiencyEvidence.competency_id == course.competency_id,
                ProficiencyEvidence.created_at > at,
                ProficiencyEvidence.created_at <= at + window,
            )
        ).all()

        before_level, after_level = _mean_level(before), _mean_level(after)
        if before_level is None or after_level is None:
            # Without evidence on both sides there is nothing to compare. Saying
            # "no lift" here would punish a course for thin assessment coverage.
            continue
        lifts.append(after_level - before_level)

    competency_name = course.competency.name if course.competency else None

    if not lifts:
        return CourseEfficacy(
            course_id=course.id, title=course.title, provider=course.provider,
            competency_name=competency_name, completions=len(completions),
            measured=0, median_lift=None, mean_lift=None, improved=0,
            unchanged_or_worse=0, verdict="not_measurable",
            note="No officer has assessment evidence both before and after completing this.",
        )

    med = round(median(lifts), 3)
    improved = sum(1 for lift in lifts if lift > 0.1)

    if len(lifts) < MIN_SAMPLE:
        verdict, note = "provisional", (
            f"Only {len(lifts)} officers have evidence on both sides. Treat as indicative."
        )
    elif med >= 0.35:
        verdict, note = "effective", "Officers measurably improve after this course."
    elif med >= 0.1:
        verdict, note = "modest", "A small observed improvement."
    else:
        verdict, note = "review", (
            "No measurable improvement. Worth reviewing the content, the level band, "
            "or whether the right officers are taking it."
        )

    return CourseEfficacy(
        course_id=course.id, title=course.title, provider=course.provider,
        competency_name=competency_name, completions=len(completions),
        measured=len(lifts), median_lift=med,
        mean_lift=round(sum(lifts) / len(lifts), 3), improved=improved,
        unchanged_or_worse=len(lifts) - improved, verdict=verdict, note=note,
    )


def catalogue_efficacy(db: Session) -> dict:
    """Every course, ranked by observed lift."""
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    results = [measure_course(db, c) for c in courses]

    measurable = [r for r in results if r.median_lift is not None]
    measurable.sort(key=lambda r: r.median_lift or 0, reverse=True)
    unmeasured = [r for r in results if r.median_lift is None]

    officers = db.scalar(
        select(ProficiencyEvidence.user_id).limit(1)
    )  # cheap existence probe, keeps the response honest when the db is empty

    return {
        "window_days": WINDOW_DAYS,
        "courses": [vars(r) for r in measurable] + [vars(r) for r in unmeasured],
        "summary": {
            "total": len(results),
            "measurable": len(measurable),
            "effective": sum(1 for r in measurable if r.verdict == "effective"),
            "needs_review": sum(1 for r in measurable if r.verdict == "review"),
            "has_evidence": officers is not None,
        },
        "method": (
            f"Mean assessed level in the {WINDOW_DAYS} days after completion minus the "
            f"mean in the {WINDOW_DAYS} days before, per officer. Course-completion "
            f"and self-assessment records are excluded so a course cannot supply its "
            f"own evidence of working."
        ),
        "caveat": (
            "Observed lift is correlational, not causal. Officers who take a course "
            "are not a random sample, and other learning happens in the same window. "
            "Use it to find courses worth investigating, not to prove one works."
        ),
    }
