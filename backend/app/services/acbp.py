"""Annual Capacity Building Plan draft.

Mission Karmayogi requires every ministry to publish an ACBP. It is currently
assembled by hand from whatever information is available. Here it is computed
from the evidence base: which competencies are short, who is short on them, what
in the catalogue closes the gap, and roughly what that costs in officer-hours.

This produces a **draft for a human to edit**, not a plan. It says so in the
output, and it records the counts it was derived from so a reviewer can check
the arithmetic rather than trust it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.orm import Session

from app.models import (
    Competency,
    CompetencyProfile,
    Criticality,
    Division,
    FracRole,
    RoleCompetencyRequirement,
    User,
)
from app.models_learning import Course

# Officers short by less than this are within measurement noise.
MATERIAL_GAP = 0.25

PRIORITY_BANDS = [
    (0.60, "Priority 1"),
    (0.40, "Priority 2"),
    (0.00, "Priority 3"),
]


@dataclass
class PriorityArea:
    competency_id: int
    competency_code: str
    competency_name: str
    domain: str
    priority: str
    officers_short: int
    officers_assessed: int
    share_short: float
    mean_gap: float
    critical_for_roles: list[str]
    top_divisions: list[dict] = field(default_factory=list)
    recommended_courses: list[dict] = field(default_factory=list)
    estimated_officer_hours: float = 0.0


def _priority_for(share: float, criticality_weight: float) -> str:
    weighted = share * (0.7 + 0.3 * criticality_weight)
    for threshold, label in PRIORITY_BANDS:
        if weighted >= threshold:
            return label
    return "Priority 3"


def build_draft(db: Session, financial_year: str | None = None) -> dict:
    """Compute the draft from the current evidence base."""
    now = datetime.now(timezone.utc)
    if financial_year is None:
        # Indian financial year runs April to March.
        start = now.year if now.month >= 4 else now.year - 1
        financial_year = f"{start}-{str(start + 1)[-2:]}"

    short_expr = cast(
        case(
            (CompetencyProfile.level
             < RoleCompetencyRequirement.required_level - MATERIAL_GAP, 1),
            else_=0,
        ),
        Float,
    )
    gap_expr = case(
        (CompetencyProfile.level < RoleCompetencyRequirement.required_level,
         RoleCompetencyRequirement.required_level - CompetencyProfile.level),
        else_=0.0,
    )

    rows = db.execute(
        select(
            Competency.id, Competency.code, Competency.name, Competency.domain,
            func.count(CompetencyProfile.id),
            func.sum(short_expr),
            func.avg(gap_expr),
        )
        .select_from(CompetencyProfile)
        .join(Competency, Competency.id == CompetencyProfile.competency_id)
        .join(User, User.id == CompetencyProfile.user_id)
        .join(
            RoleCompetencyRequirement,
            (RoleCompetencyRequirement.frac_role_id == User.frac_role_id)
            & (RoleCompetencyRequirement.competency_id == CompetencyProfile.competency_id),
        )
        .where(User.is_active.is_(True))
        .group_by(Competency.id, Competency.code, Competency.name, Competency.domain)
    ).all()

    areas: list[PriorityArea] = []
    for comp_id, code, name, domain, assessed, short, mean_gap in rows:
        assessed = int(assessed or 0)
        short = int(short or 0)
        if assessed == 0 or short == 0:
            continue
        share = short / assessed

        critical_roles = [
            role_code for (role_code,) in db.execute(
                select(FracRole.code)
                .join(RoleCompetencyRequirement,
                      RoleCompetencyRequirement.frac_role_id == FracRole.id)
                .where(
                    RoleCompetencyRequirement.competency_id == comp_id,
                    RoleCompetencyRequirement.criticality == Criticality.CRITICAL,
                )
                .order_by(FracRole.level_order)
            ).all()
        ]

        divisions = [
            {"code": div_code, "name": div_name, "officers_short": int(count)}
            for div_code, div_name, count in db.execute(
                select(Division.code, Division.name, func.sum(short_expr))
                .select_from(CompetencyProfile)
                .join(User, User.id == CompetencyProfile.user_id)
                .join(Division, Division.id == User.division_id)
                .join(
                    RoleCompetencyRequirement,
                    (RoleCompetencyRequirement.frac_role_id == User.frac_role_id)
                    & (RoleCompetencyRequirement.competency_id
                       == CompetencyProfile.competency_id),
                )
                .where(CompetencyProfile.competency_id == comp_id)
                .group_by(Division.code, Division.name)
                .order_by(func.sum(short_expr).desc())
                .limit(3)
            ).all()
            if count and int(count) > 0
        ]

        courses = db.scalars(
            select(Course)
            .where(Course.competency_id == comp_id, Course.is_active.is_(True))
            .order_by(Course.level_from)
        ).all()

        # One representative course per officer who is short, costed at its
        # published duration. Deliberately conservative: officers with a wide gap
        # will need more than one course, and the note says so.
        per_officer_hours = min((c.duration_hours for c in courses), default=0.0)

        areas.append(PriorityArea(
            competency_id=comp_id,
            competency_code=code,
            competency_name=name,
            domain=domain.value if hasattr(domain, "value") else str(domain),
            priority=_priority_for(share, 1.0 if critical_roles else 0.4),
            officers_short=short,
            officers_assessed=assessed,
            share_short=round(100 * share, 1),
            mean_gap=round(float(mean_gap or 0), 2),
            critical_for_roles=critical_roles,
            top_divisions=divisions,
            recommended_courses=[
                {"id": c.id, "title": c.title, "provider": c.provider,
                 "level_from": c.level_from, "level_to": c.level_to,
                 "duration_hours": c.duration_hours}
                for c in courses[:3]
            ],
            estimated_officer_hours=round(short * per_officer_hours, 1),
        ))

    areas.sort(key=lambda a: (a.priority, -a.share_short))

    total_hours = sum(a.estimated_officer_hours for a in areas)
    officers = db.scalar(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ) or 0

    return {
        "financial_year": financial_year,
        "generated_at": now,
        "status": "draft",
        "ministry": "Ministry of Statistics and Programme Implementation",
        "officers_covered": officers,
        "priority_areas": [vars(a) for a in areas],
        "totals": {
            "priority_areas": len(areas),
            "priority_1": sum(1 for a in areas if a.priority == "Priority 1"),
            "estimated_officer_hours": round(total_hours, 1),
            "estimated_officer_days": round(total_hours / 6, 1),
        },
        "basis": (
            "Derived from the derived competency profile of every active officer, "
            "compared against the requirements of the role each one actually holds. "
            f"An officer is counted short when they are more than {MATERIAL_GAP} of a "
            "level below requirement."
        ),
        "caveat": (
            "This is a computed draft for review, not an approved plan. Officer-hour "
            "estimates assume one representative course per officer and will "
            "understate the cost where gaps are wide. Budget, trainer availability "
            "and posting cycles are not modelled."
        ),
    }
