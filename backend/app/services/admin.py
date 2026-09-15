"""The administrator's view of individual officers.

Everything else an administrator can see is an aggregate: division readiness,
competency priorities, the ACBP draft. This is the one place the platform shows
a named person's record, which makes it the one place where two things have to
be got right.

**It has to scale.** `analytics.team_roster` calls `analyse_gaps` and
`role_readiness` once per officer, which is fine for one division and quadratic
in irritation for a national roster of several thousand. The listing here is a
single grouped query with the per-officer work pushed into SQL, so adding
officers costs rows rather than round trips. The per-officer *detail* still uses
the shared services, because there it runs once and correctness matters more
than speed.

**It has to be accountable.** Reading a named officer's assessment history is a
privileged act, and one of the platform's own principles is that competency data
must not be usable against the person who supplied it. So every drill-down is
written to the audit log with the subject's id, and the detail view carries the
same evidence trail the officer sees themselves — an administrator and an
officer looking at the same competency see the same number derived the same way,
or the Skill Twin is not one record but two.

What is deliberately *not* here: any write path. Nothing on this screen can
change an officer's level, because every level in the platform is derived from
evidence and the only way to affect one is to append evidence with a source and
a confidence. An administrator who could edit a number directly would break the
audit trail the whole design rests on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Float, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.ml import irt
from app.models import (
    Competency,
    Criticality,
    CompetencyProfile,
    Division,
    EvidenceSource,
    FracRole,
    ProficiencyEvidence,
    RoleCompetencyRequirement,
    User,
    UserRole,
)
from app.models_interview import Interview, InterviewStatus
from app.models_learning import Course, CourseCompletion
from app.models_quiz import AttemptStatus, QuizAttempt
from app.services import adaptive_quiz
from app.services.competency import (
    DEFAULT_LEVEL,
    GAP_CRITICAL,
    analyse_gaps,
    detect_divergence,
    role_readiness,
)

# A roster page. Large enough that a division fits on one screen, small enough
# that the response stays well under a megabyte on a national query.
PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass
class LearnerRow:
    """One officer, as the roster lists them."""

    user_id: int
    full_name: str
    email: str
    account_role: str
    division: str | None
    frac_role: str | None
    service_years: float
    is_active: bool

    readiness: float
    competencies_required: int
    competencies_measured: int
    competencies_at_target: int
    critical_gaps: int
    widest_gap_competency: str | None
    widest_gap: float

    evidence_count: int
    demonstrated_count: int
    assessments: int
    interviews: int
    courses_completed: int
    last_activity: datetime | None


@dataclass
class LearnerDetail:
    """Everything the platform holds about one officer, assembled."""

    profile: dict
    competencies: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)
    divergence: list[dict] = field(default_factory=list)
    assessments: list[dict] = field(default_factory=list)
    interviews: list[dict] = field(default_factory=list)
    learning: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# The roster
# --------------------------------------------------------------------------- #

# Sources that show somebody doing the work, rather than attending or claiming.
# The same set the admin overview uses, and the distinction the whole platform
# turns on — so it is defined once and imported, not retyped per screen.
DEMONSTRATED_SOURCES = (
    EvidenceSource.SIMULATION,
    EvidenceSource.QUIZ,
    EvidenceSource.DIAGNOSTIC,
    EvidenceSource.INTERVIEW,
)

# 1 + the rank `competency._CRITICALITY_RANK` assigns, because a SQL CASE cannot
# read a Python dict and the roster needs this arithmetic inside the query.
# `test_competency` asserts the two agree, so reweighting criticality in one
# place cannot silently make the roster disagree with the officer's own
# dashboard — which would look like a bug in whichever screen you checked second.
SQL_CRITICALITY_WEIGHT: dict[Criticality, float] = {
    Criticality.CRITICAL: 4.0,
    Criticality.HIGH: 3.0,
    Criticality.MEDIUM: 2.0,
    Criticality.LOW: 1.0,
}


def _counts_by_user(db: Session, column, model, *conditions) -> dict[int, int]:
    """A `{user_id: count}` map, as one grouped query.

    Six of these beat six hundred correlated subqueries, and each is small
    enough to read on its own line at the call site.
    """
    stmt = select(column, func.count()).group_by(column)
    if conditions:
        stmt = stmt.where(*conditions)
    return dict(db.execute(stmt).all())


def _readiness_subquery():
    """Role readiness per officer, computed in SQL.

    This deliberately reproduces `competency.role_readiness` rather than
    inventing a cheaper approximation, and the reason is worth stating: the
    first version of this roster used the share of competencies fully at target,
    which is a perfectly reasonable measure and gave 10% for an officer the
    detail page reported at 76%. Both numbers were right. Having two of them
    under one word was the bug — a supervisor comparing the roster against the
    officer's own dashboard would have concluded one of the screens was broken.

    So: achieved level over demanded level, weighted by criticality, counted
    across every competency the officer's role *requires* rather than every one
    they happen to have been measured on. An unmeasured requirement counts as
    `DEFAULT_LEVEL`, exactly as `analyse_gaps` treats it — otherwise an officer
    with one measured competency would score higher than one measured on all
    twelve.
    """
    weight = case(
        *(
            (RoleCompetencyRequirement.criticality == level, value)
            for level, value in SQL_CRITICALITY_WEIGHT.items()
        ),
        else_=1.0,
    )
    current = func.coalesce(CompetencyProfile.level, DEFAULT_LEVEL)

    return (
        select(
            User.id.label("user_id"),
            func.sum(
                weight * func.least(current, RoleCompetencyRequirement.required_level)
            ).label("achieved"),
            func.sum(weight * RoleCompetencyRequirement.required_level).label("demanded"),
            func.count().label("required_count"),
            func.sum(
                case((current >= RoleCompetencyRequirement.required_level, 1), else_=0)
            ).label("at_target"),
            func.sum(
                case(
                    (
                        RoleCompetencyRequirement.required_level - current
                        >= GAP_CRITICAL,
                        1,
                    ),
                    else_=0,
                )
            ).label("critical_gaps"),
            func.sum(case((CompetencyProfile.id.is_not(None), 1), else_=0)).label(
                "measured"
            ),
        )
        .join(
            RoleCompetencyRequirement,
            RoleCompetencyRequirement.frac_role_id == User.frac_role_id,
        )
        .outerjoin(
            CompetencyProfile,
            and_(
                CompetencyProfile.user_id == User.id,
                CompetencyProfile.competency_id
                == RoleCompetencyRequirement.competency_id,
            ),
        )
        .group_by(User.id)
        .subquery()
    )


def list_learners(
    db: Session,
    *,
    viewer: User,
    search: str | None = None,
    division_id: int | None = None,
    frac_role_id: int | None = None,
    only_with_critical_gaps: bool = False,
    include_inactive: bool = False,
    sort: str = "readiness",
    page: int = 1,
    page_size: int = PAGE_SIZE,
) -> dict:
    """The officer roster, filtered and paged.

    A supervisor sees their own division whatever they ask for; the scope is
    applied here rather than trusted to the caller, because a filter parameter
    is a request and a role boundary is not negotiable.
    """
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    page = max(1, page)

    requirements = _readiness_subquery()

    # The same formula as `competency.role_readiness`, as an expression so it
    # can be sorted on without materialising every officer.
    readiness_expr = case(
        (
            requirements.c.demanded > 0,
            100.0
            * cast(requirements.c.achieved, Float)
            / cast(requirements.c.demanded, Float),
        ),
        else_=0.0,
    )

    stmt = (
        select(
            User,
            Division.name.label("division_name"),
            FracRole.name.label("frac_role_name"),
            readiness_expr.label("readiness"),
            func.coalesce(requirements.c.required_count, 0).label("required_count"),
            func.coalesce(requirements.c.at_target, 0).label("at_target"),
            func.coalesce(requirements.c.measured, 0).label("measured"),
            func.coalesce(requirements.c.critical_gaps, 0).label("critical_gaps"),
        )
        .outerjoin(Division, Division.id == User.division_id)
        .outerjoin(FracRole, FracRole.id == User.frac_role_id)
        .outerjoin(requirements, requirements.c.user_id == User.id)
    )

    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))

    # Scope. An administrator sees everyone; a supervisor sees their division
    # and nothing else, regardless of what they filtered for.
    if viewer.role != UserRole.ADMIN:
        if viewer.division_id is None:
            return {
                "learners": [], "total": 0, "page": 1, "page_size": page_size,
                "pages": 0, "scope": "no division assigned",
                "note": "A supervisor with no division assigned has no roster.",
            }
        stmt = stmt.where(User.division_id == viewer.division_id)
    elif division_id is not None:
        stmt = stmt.where(User.division_id == division_id)

    if frac_role_id is not None:
        stmt = stmt.where(User.frac_role_id == frac_role_id)

    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
            )
        )

    total = db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0

    order = {
        "readiness": readiness_expr.asc(),
        "readiness_desc": readiness_expr.desc(),
        "name": User.full_name.asc(),
        "recent": User.created_at.desc(),
    }.get(sort, readiness_expr.asc())
    stmt = stmt.order_by(order, User.id.asc())

    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    user_ids = [row[0].id for row in rows]
    if not user_ids:
        return {
            "learners": [], "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "scope": "all divisions" if viewer.role == UserRole.ADMIN else "own division",
        }

    scoped = ProficiencyEvidence.user_id.in_(user_ids)
    evidence_counts = _counts_by_user(
        db, ProficiencyEvidence.user_id, ProficiencyEvidence, scoped
    )
    demonstrated_counts = _counts_by_user(
        db, ProficiencyEvidence.user_id, ProficiencyEvidence,
        scoped, ProficiencyEvidence.source.in_(DEMONSTRATED_SOURCES),
    )
    assessment_counts = _counts_by_user(
        db, QuizAttempt.user_id, QuizAttempt,
        QuizAttempt.user_id.in_(user_ids),
        QuizAttempt.status == AttemptStatus.SUBMITTED,
    )
    interview_counts = _counts_by_user(
        db, Interview.user_id, Interview, Interview.user_id.in_(user_ids)
    )
    course_counts = _counts_by_user(
        db, CourseCompletion.user_id, CourseCompletion,
        CourseCompletion.user_id.in_(user_ids),
    )
    last_activity = dict(
        db.execute(
            select(ProficiencyEvidence.user_id, func.max(ProficiencyEvidence.created_at))
            .where(scoped)
            .group_by(ProficiencyEvidence.user_id)
        ).all()
    )

    # The two gap figures need the requirement comparison per competency, which
    # does not collapse into the grouped query above without losing which
    # competency is widest. One more grouped query rather than N calls to
    # `analyse_gaps`.
    gap_rows = db.execute(
        select(
            CompetencyProfile.user_id,
            Competency.name,
            (RoleCompetencyRequirement.required_level - CompetencyProfile.level).label("gap"),
        )
        .join(User, User.id == CompetencyProfile.user_id)
        .join(Competency, Competency.id == CompetencyProfile.competency_id)
        .join(
            RoleCompetencyRequirement,
            and_(
                RoleCompetencyRequirement.frac_role_id == User.frac_role_id,
                RoleCompetencyRequirement.competency_id == CompetencyProfile.competency_id,
            ),
        )
        .where(CompetencyProfile.user_id.in_(user_ids))
    ).all()

    widest: dict[int, tuple[str, float]] = {}
    for user_id, name, gap in gap_rows:
        if gap is None:
            continue
        if gap > 0.1 and (user_id not in widest or gap > widest[user_id][1]):
            widest[user_id] = (name, float(gap))

    learners = []
    for (
        user, division_name, role_name, readiness,
        required_count, at_target, measured, critical_gaps,
    ) in rows:
        gap = widest.get(user.id)
        learners.append(LearnerRow(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            account_role=user.role.value,
            division=division_name,
            frac_role=role_name,
            service_years=round(user.service_years, 1),
            is_active=user.is_active,
            readiness=round(float(readiness or 0.0), 1),
            competencies_required=int(required_count or 0),
            competencies_measured=int(measured or 0),
            competencies_at_target=int(at_target or 0),
            critical_gaps=int(critical_gaps or 0),
            widest_gap_competency=gap[0] if gap else None,
            widest_gap=round(gap[1], 2) if gap else 0.0,
            evidence_count=evidence_counts.get(user.id, 0),
            demonstrated_count=demonstrated_counts.get(user.id, 0),
            assessments=assessment_counts.get(user.id, 0),
            interviews=interview_counts.get(user.id, 0),
            courses_completed=course_counts.get(user.id, 0),
            last_activity=last_activity.get(user.id),
        ))

    if only_with_critical_gaps:
        learners = [row for row in learners if row.critical_gaps > 0]

    return {
        "learners": [vars(row) for row in learners],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "scope": "all divisions" if viewer.role == UserRole.ADMIN else "own division",
        "note": (
            "Readiness is the criticality-weighted share of the role's "
            "requirement an officer currently meets — the same figure their own "
            "dashboard shows, computed the same way. `competencies_measured` "
            "says how much of that rests on evidence: a requirement with no "
            "evidence counts at the floor, so a high readiness on two measured "
            "competencies out of twelve is a statement about the assessment "
            "coverage, not about the officer."
        ),
    }


def filter_options(db: Session, *, viewer: User) -> dict:
    """Divisions and roles the viewer may filter by.

    A supervisor is offered their own division only, so the filter cannot be
    used to discover that other divisions exist or how many officers they hold.
    """
    divisions = db.execute(
        select(Division.id, Division.name).order_by(Division.name)
    ).all()
    if viewer.role != UserRole.ADMIN:
        divisions = [d for d in divisions if d[0] == viewer.division_id]

    roles = db.execute(
        select(FracRole.id, FracRole.name).order_by(FracRole.level_order)
    ).all()
    return {
        "divisions": [{"id": i, "name": n} for i, n in divisions],
        "frac_roles": [{"id": i, "name": n} for i, n in roles],
    }


# --------------------------------------------------------------------------- #
# One officer's record
# --------------------------------------------------------------------------- #


def _assessment_rows(db: Session, user: User) -> list[dict]:
    """Every submitted assessment, with its adaptive trace.

    The trace is what makes an administrator's view of a result meaningful: a
    bare "L2.1" invites the reading that the officer is weak, where the path
    shows whether the estimate was well determined or whether the bank simply
    ran out of items near them.
    """
    attempts = db.scalars(
        select(QuizAttempt)
        .where(
            QuizAttempt.user_id == user.id,
            QuizAttempt.status == AttemptStatus.SUBMITTED,
        )
        .order_by(QuizAttempt.submitted_at.desc())
        .limit(40)
    ).all()

    rows = []
    for attempt in attempts:
        ability = adaptive_quiz.ability_of(attempt)
        rows.append({
            "id": attempt.id,
            "competency_id": attempt.competency_id,
            "competency_name": attempt.competency.name if attempt.competency else None,
            "adaptive": attempt.is_adaptive,
            "items": attempt.item_count,
            "correct": attempt.correct_count,
            "accuracy": round(100 * attempt.accuracy, 1),
            "derived_level": attempt.derived_level,
            "theta": attempt.theta,
            "theta_se": attempt.theta_se,
            "level_low": round(ability.level_low, 2) if attempt.theta is not None else None,
            "level_high": round(ability.level_high, 2) if attempt.theta is not None else None,
            "reliability": round(ability.reliability, 3) if attempt.theta is not None else None,
            "stop_reason": attempt.stop_reason,
            "mean_item_level": attempt.mean_difficulty,
            "submitted_at": attempt.submitted_at,
            "trace": adaptive_quiz.trace(attempt) if attempt.is_adaptive else [],
        })
    return rows


def _interview_rows(db: Session, user: User) -> list[dict]:
    interviews = db.scalars(
        select(Interview)
        .where(Interview.user_id == user.id)
        .order_by(Interview.started_at.desc())
        .limit(20)
    ).all()

    rows = []
    for interview in interviews:
        answered = [a for a in interview.answers if a.score is not None]
        # Reported per axis and never combined. A single interview number would
        # let fluency stand in for knowledge, which is the specific thing this
        # platform refuses to do.
        axes: dict[str, list[float]] = {}
        for answer in answered:
            score = answer.score
            for axis in ("knowledge", "structure", "communication"):
                value = getattr(score, axis, None)
                if value is not None:
                    axes.setdefault(axis, []).append(value)

        rows.append({
            "id": interview.id,
            "status": interview.status.value,
            "completed": interview.status == InterviewStatus.COMPLETED,
            "questions": len(interview.answers),
            "scored": len(answered),
            "language": interview.language,
            "fluency_scoring_enabled": interview.fluency_scoring_enabled,
            "axes": {
                axis: round(sum(values) / len(values), 2)
                for axis, values in axes.items()
            },
            "started_at": interview.started_at,
            "completed_at": interview.completed_at,
        })
    return rows


def _learning_rows(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(CourseCompletion, Course)
        .join(Course, Course.id == CourseCompletion.course_id)
        .where(CourseCompletion.user_id == user.id)
        .order_by(CourseCompletion.completed_at.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": completion.id,
            "course_title": course.title,
            "provider": getattr(course, "provider", None),
            "competency_id": course.competency_id,
            "completed_at": completion.completed_at,
            "level_at_completion": completion.level_at_completion,
        }
        for completion, course in rows
    ]


def _evidence_rows(db: Session, user: User, limit: int = 120) -> list[dict]:
    rows = db.scalars(
        select(ProficiencyEvidence)
        .where(ProficiencyEvidence.user_id == user.id)
        .order_by(ProficiencyEvidence.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": ev.id,
            "competency_id": ev.competency_id,
            "competency_name": ev.competency.name if ev.competency else None,
            "level_estimate": ev.level_estimate,
            "confidence": ev.confidence,
            "source": ev.source.value,
            "source_ref": ev.source_ref,
            "note": ev.note,
            "created_at": ev.created_at,
        }
        for ev in rows
    ]


def learner_detail(db: Session, *, user: User) -> LearnerDetail:
    """One officer's complete record, assembled from the same services the
    officer's own screens use.

    Deliberately not a separate query path. If an administrator's view of a
    competency were computed differently from the officer's, the Skill Twin
    would be two records that happen to agree most of the time, and the first
    time they disagreed nobody would be able to say which was right.
    """
    gaps = analyse_gaps(db, user=user)
    profiles = db.scalars(
        select(CompetencyProfile).where(CompetencyProfile.user_id == user.id)
    ).all()
    levels = {p.competency_id: p for p in profiles}

    assessments = _assessment_rows(db, user)
    interviews = _interview_rows(db, user)
    learning = _learning_rows(db, user)
    evidence = _evidence_rows(db, user)

    demonstrated = sum(
        1 for e in evidence if e["source"] in {s.value for s in DEMONSTRATED_SOURCES}
    )

    return LearnerDetail(
        profile={
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "account_role": user.role.value,
            "division": user.division.name if user.division else None,
            "frac_role": user.frac_role.name if user.frac_role else None,
            "frac_role_id": user.frac_role_id,
            "service_years": round(user.service_years, 1),
            "is_active": user.is_active,
            "created_at": user.created_at,
            "fluency_scoring_enabled": user.fluency_scoring_enabled,
        },
        competencies=[
            {
                "competency_id": gap.competency_id,
                "competency_name": gap.competency_name,
                "current_level": gap.current_level,
                "required_level": gap.required_level,
                "gap": gap.gap,
                "status": gap.status,
                "criticality": getattr(gap, "criticality", None),
                "evidence_count": (
                    levels[gap.competency_id].evidence_count
                    if gap.competency_id in levels else 0
                ),
                "evidence_weight": (
                    levels[gap.competency_id].evidence_weight
                    if gap.competency_id in levels else 0.0
                ),
                "strongest_source": (
                    levels[gap.competency_id].strongest_source.value
                    if gap.competency_id in levels
                    and levels[gap.competency_id].strongest_source
                    else None
                ),
            }
            for gap in gaps
        ],
        gaps=[
            {
                "competency_id": g.competency_id,
                "competency_name": g.competency_name,
                "gap": g.gap,
                "status": g.status,
            }
            for g in gaps if g.is_gap
        ],
        divergence=[
            {
                "competency_id": d.competency_id,
                "competency_name": d.competency_name,
                "self_rated_level": d.self_rated_level,
                "assessed_level": d.assessed_level,
                "divergence": d.divergence,
            }
            for d in detect_divergence(db, user_id=user.id)
        ],
        assessments=assessments,
        interviews=interviews,
        learning=learning,
        evidence=evidence,
        summary={
            "readiness": role_readiness(db, user=user),
            "competencies_measured": len(levels),
            "open_gaps": sum(1 for g in gaps if g.is_gap),
            "critical_gaps": sum(1 for g in gaps if g.status == "critical"),
            "evidence_records": len(evidence),
            "demonstrated_records": demonstrated,
            "assessments": len(assessments),
            "interviews": len(interviews),
            "courses_completed": len(learning),
            "last_activity": evidence[0]["created_at"] if evidence else None,
            # Adaptive assessments carry an interval; this is the mean width,
            # which says how firmly this officer has actually been measured
            # rather than how well they scored.
            "mean_assessment_interval": (
                round(
                    sum(
                        (a["level_high"] - a["level_low"])
                        for a in assessments
                        if a["level_high"] is not None and a["level_low"] is not None
                    )
                    / max(
                        1,
                        sum(
                            1 for a in assessments
                            if a["level_high"] is not None and a["level_low"] is not None
                        ),
                    ),
                    2,
                )
                if assessments else None
            ),
        },
    )


def workforce_assessment_summary(db: Session) -> dict:
    """How much of the workforce has actually been measured, and how well.

    Coverage rather than performance. An administrator reading a readiness
    figure needs to know whether it rests on assessments or on self-ratings,
    and this is the number that says so.
    """
    officers = db.scalar(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ) or 0
    assessed = db.scalar(
        select(func.count(func.distinct(QuizAttempt.user_id)))
        .where(QuizAttempt.status == AttemptStatus.SUBMITTED)
    ) or 0
    interviewed = db.scalar(
        select(func.count(func.distinct(Interview.user_id)))
    ) or 0
    adaptive = db.scalar(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.status == AttemptStatus.SUBMITTED,
            QuizAttempt.is_adaptive.is_(True),
        )
    ) or 0
    mean_se = db.scalar(
        select(func.avg(QuizAttempt.theta_se)).where(
            QuizAttempt.status == AttemptStatus.SUBMITTED,
            QuizAttempt.theta_se.is_not(None),
        )
    )

    by_stop = dict(
        db.execute(
            select(QuizAttempt.stop_reason, func.count())
            .where(QuizAttempt.stop_reason.is_not(None))
            .group_by(QuizAttempt.stop_reason)
        ).all()
    )

    return {
        "officers": officers,
        "assessed": assessed,
        "interviewed": interviewed,
        "assessed_pct": round(100 * assessed / officers, 1) if officers else 0.0,
        "adaptive_attempts": adaptive,
        "mean_interval_width": (
            round(2 * 1.96 * float(mean_se) * irt.LEVELS_PER_THETA, 2)
            if mean_se else None
        ),
        "stop_reasons": by_stop,
        "note": (
            "`mean_interval_width` is the average width of the 95% interval on "
            "an adaptive result, in FRAC levels. A wide average means the "
            "assessment is not resolving officers sharply — usually a thin item "
            "bank rather than an unusual cohort, which "
            "`/item-bank/health` will confirm."
        ),
    }
