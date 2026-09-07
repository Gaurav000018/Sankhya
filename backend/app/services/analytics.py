"""Workforce analytics for supervisor and administrator views.

These read the derived `competency_profile` and join it against each officer's
role requirements, so "at target" always means *against the role that officer
actually holds* — a Deputy Director at L3.5 and a Junior Statistical Officer at
L3.5 are not in the same position, and an average that ignores that says
nothing useful.

Aggregates run as SQL rather than per-officer Python. Calling `role_readiness`
once per officer is fine for one division and far too slow for a national view.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.orm import Session

from app.models import (
    Competency,
    CompetencyProfile,
    Division,
    EvidenceSource,
    FracRole,
    ProficiencyEvidence,
    RoleCompetencyRequirement,
    User,
    UserRole,
)
from app.services.competency import analyse_gaps, role_readiness


@dataclass
class OfficerSummary:
    user_id: int
    full_name: str
    email: str
    role_name: str | None
    service_years: float
    readiness: float
    widest_gap_competency: str | None
    widest_gap: float
    critical_gaps: int
    evidence_count: int
    fluency_scoring_enabled: bool


def team_roster(db: Session, supervisor: User) -> list[OfficerSummary]:
    """Officers a supervisor is responsible for.

    Scoped to their own division. Admins see everyone, which is why this takes
    the viewer rather than a division id.
    """
    stmt = select(User).where(User.is_active.is_(True))
    if supervisor.role != UserRole.ADMIN:
        if supervisor.division_id is None:
            return []
        stmt = stmt.where(User.division_id == supervisor.division_id)

    officers = db.scalars(stmt.limit(500)).all()
    evidence_counts = dict(
        db.execute(
            select(ProficiencyEvidence.user_id, func.count(ProficiencyEvidence.id))
            .group_by(ProficiencyEvidence.user_id)
        ).all()
    )

    summaries: list[OfficerSummary] = []
    for officer in officers:
        gaps = analyse_gaps(db, user=officer)
        open_gaps = [g for g in gaps if g.is_gap]
        widest = open_gaps[0] if open_gaps else None

        summaries.append(OfficerSummary(
            user_id=officer.id,
            full_name=officer.full_name,
            email=officer.email,
            role_name=officer.frac_role.name if officer.frac_role else None,
            service_years=officer.service_years,
            readiness=role_readiness(db, user=officer),
            widest_gap_competency=widest.competency_name if widest else None,
            widest_gap=widest.gap if widest else 0.0,
            critical_gaps=sum(1 for g in gaps if g.status == "critical"),
            evidence_count=evidence_counts.get(officer.id, 0),
            fluency_scoring_enabled=officer.fluency_scoring_enabled,
        ))

    # Lowest readiness first: this list exists to find who needs attention.
    summaries.sort(key=lambda s: (s.readiness, -s.critical_gaps))
    return summaries


def _at_target_expression():
    """1 where the officer meets their own role's requirement, else 0."""
    return cast(
        case(
            (CompetencyProfile.level >= RoleCompetencyRequirement.required_level, 1),
            else_=0,
        ),
        Float,
    )


def competency_heatmap(db: Session) -> dict:
    """Mean level and at-target share per division x competency."""
    rows = db.execute(
        select(
            Division.code,
            Division.name,
            Competency.code,
            Competency.name,
            func.avg(CompetencyProfile.level),
            func.avg(_at_target_expression()),
            func.count(CompetencyProfile.id),
        )
        .select_from(CompetencyProfile)
        .join(User, User.id == CompetencyProfile.user_id)
        .join(Division, Division.id == User.division_id)
        .join(Competency, Competency.id == CompetencyProfile.competency_id)
        .join(
            RoleCompetencyRequirement,
            (RoleCompetencyRequirement.frac_role_id == User.frac_role_id)
            & (RoleCompetencyRequirement.competency_id == CompetencyProfile.competency_id),
            isouter=True,
        )
        .group_by(Division.code, Division.name, Competency.code, Competency.name)
    ).all()

    divisions: dict[str, str] = {}
    competencies: dict[str, str] = {}
    cells: list[dict] = []

    for div_code, div_name, comp_code, comp_name, mean_level, at_target, count in rows:
        divisions[div_code] = div_name
        competencies[comp_code] = comp_name
        cells.append({
            "division": div_code,
            "competency": comp_code,
            "mean_level": round(float(mean_level or 0), 2),
            "at_target_pct": round(100 * float(at_target or 0), 1),
            "officers": int(count),
        })

    return {
        "divisions": [{"code": c, "name": n} for c, n in sorted(divisions.items())],
        "competencies": [{"code": c, "name": n} for c, n in sorted(competencies.items())],
        "cells": cells,
    }


def admin_overview(db: Session) -> dict:
    """National picture: headline counts, division standing, weakest competencies."""
    officer_count = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    evidence_count = db.scalar(select(func.count(ProficiencyEvidence.id))) or 0

    by_division = [
        {
            "code": code,
            "name": name,
            "state": state,
            "officers": int(officers),
            "mean_level": round(float(mean_level or 0), 2),
            "at_target_pct": round(100 * float(at_target or 0), 1),
        }
        for code, name, state, officers, mean_level, at_target in db.execute(
            select(
                Division.code, Division.name, Division.state,
                func.count(func.distinct(User.id)),
                func.avg(CompetencyProfile.level),
                func.avg(_at_target_expression()),
            )
            .select_from(Division)
            .join(User, User.division_id == Division.id)
            .join(CompetencyProfile, CompetencyProfile.user_id == User.id)
            .join(
                RoleCompetencyRequirement,
                (RoleCompetencyRequirement.frac_role_id == User.frac_role_id)
                & (RoleCompetencyRequirement.competency_id
                   == CompetencyProfile.competency_id),
                isouter=True,
            )
            .group_by(Division.code, Division.name, Division.state)
        ).all()
    ]
    by_division.sort(key=lambda d: d["at_target_pct"])

    by_competency = [
        {
            "code": code,
            "name": name,
            "domain": domain.value if hasattr(domain, "value") else str(domain),
            "mean_level": round(float(mean_level or 0), 2),
            "mean_required": round(float(required or 0), 2),
            "at_target_pct": round(100 * float(at_target or 0), 1),
            "officers_below_target": int(below or 0),
        }
        for code, name, domain, mean_level, required, at_target, below in db.execute(
            select(
                Competency.code, Competency.name, Competency.domain,
                func.avg(CompetencyProfile.level),
                func.avg(RoleCompetencyRequirement.required_level),
                func.avg(_at_target_expression()),
                func.sum(
                    case(
                        (CompetencyProfile.level
                         < RoleCompetencyRequirement.required_level, 1),
                        else_=0,
                    )
                ),
            )
            .select_from(CompetencyProfile)
            .join(Competency, Competency.id == CompetencyProfile.competency_id)
            .join(User, User.id == CompetencyProfile.user_id)
            .join(
                RoleCompetencyRequirement,
                (RoleCompetencyRequirement.frac_role_id == User.frac_role_id)
                & (RoleCompetencyRequirement.competency_id
                   == CompetencyProfile.competency_id),
                isouter=True,
            )
            .group_by(Competency.code, Competency.name, Competency.domain)
        ).all()
    ]
    by_competency.sort(key=lambda c: c["at_target_pct"])

    # Where the platform's knowledge actually comes from. A system leaning on
    # self-assessment is not measuring competency, and this makes that visible.
    evidence_mix = [
        {"source": src.value if hasattr(src, "value") else str(src), "count": int(count)}
        for src, count in db.execute(
            select(ProficiencyEvidence.source, func.count(ProficiencyEvidence.id))
            .group_by(ProficiencyEvidence.source)
        ).all()
    ]
    evidence_mix.sort(key=lambda e: e["count"], reverse=True)

    by_role = [
        {"code": code, "name": name, "officers": int(count)}
        for code, name, count in db.execute(
            select(FracRole.code, FracRole.name, func.count(User.id))
            .select_from(FracRole)
            .join(User, User.frac_role_id == FracRole.id, isouter=True)
            .group_by(FracRole.code, FracRole.name, FracRole.level_order)
            .order_by(FracRole.level_order)
        ).all()
    ]

    demonstrated = sum(
        e["count"] for e in evidence_mix
        if e["source"] in (EvidenceSource.SIMULATION.value, EvidenceSource.QUIZ.value,
                           EvidenceSource.DIAGNOSTIC.value, EvidenceSource.INTERVIEW.value)
    )

    return {
        "officers": officer_count,
        "evidence_records": evidence_count,
        "divisions": len(by_division),
        "demonstrated_evidence_pct": (
            round(100 * demonstrated / evidence_count, 1) if evidence_count else 0.0
        ),
        "by_division": by_division,
        "by_competency": by_competency,
        "by_role": by_role,
        "evidence_mix": evidence_mix,
    }
