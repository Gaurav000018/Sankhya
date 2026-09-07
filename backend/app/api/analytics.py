"""Supervisor and administrator analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db import get_db
from app.models import User, UserRole
from app.services import acbp, analytics, efficacy, lift

router = APIRouter(tags=["analytics"])


@router.get("/team/officers")
def team_officers(
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
):
    """Officers this supervisor is responsible for, lowest readiness first.

    Scoped to their own division; admins see everyone.
    """
    roster = analytics.team_roster(db, viewer)
    return {
        "scope": "all divisions" if viewer.role == UserRole.ADMIN else "own division",
        "officers": [vars(o) for o in roster],
        "summary": {
            "officers": len(roster),
            "with_critical_gaps": sum(1 for o in roster if o.critical_gaps > 0),
            "mean_readiness": (
                round(sum(o.readiness for o in roster) / len(roster), 1)
                if roster else 0.0
            ),
        },
    }


@router.get("/analytics/overview")
def overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """National picture across divisions, competencies and evidence sources."""
    return analytics.admin_overview(db)


@router.get("/analytics/heatmap")
def heatmap(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
):
    """Division x competency readiness.

    Cells carry the numeric level as well as the at-target share, so colour is
    never the only channel carrying meaning.
    """
    return analytics.competency_heatmap(db)


@router.get("/analytics/course-efficacy")
def course_efficacy(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Which courses actually move competency.

    No LMS measures this. Because every assessment writes dated evidence, the
    before/after comparison is already available — see `services/efficacy` for
    what the figure does and does not claim.
    """
    return efficacy.catalogue_efficacy(db)


@router.get("/analytics/acbp")
def acbp_draft(
    financial_year: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Draft Annual Capacity Building Plan, computed from the evidence base.

    Mission Karmayogi requires each ministry to publish an ACBP; this produces a
    draft for a human to edit rather than a finished plan.
    """
    return acbp.build_draft(db, financial_year=financial_year)


@router.get("/analytics/lift")
def workforce_lift(
    days: int = 180,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
):
    """Aggregate competency movement — the figure a capacity building plan is
    judged against a year later."""
    return lift.workforce_lift(db, days=max(30, min(days, 730)))
