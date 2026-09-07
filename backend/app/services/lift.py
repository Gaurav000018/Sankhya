"""Competency lift over time.

Distinct from course efficacy, which asks whether a *course* works. This asks
whether an *officer* — or a division, or the whole workforce — has actually
moved, which is what "training effectiveness" means to someone signing off a
capacity building budget.

Because every level is derived from dated evidence, the historical level is not
stored or approximated: it is recomputed from the evidence that existed at the
time, with recency decay measured from that date. A figure reconstructed any
other way would drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Competency,
    Division,
    EvidenceSource,
    ProficiencyEvidence,
    User,
)
from app.services.competency import DEFAULT_LEVEL, derive_level

DEFAULT_WINDOW_DAYS = 180

# Below this, a change is measurement noise rather than learning.
MATERIAL_CHANGE = 0.15


@dataclass
class CompetencyLift:
    competency_id: int
    competency_code: str
    competency_name: str
    level_then: float
    level_now: float
    change: float
    evidence_then: int
    evidence_added: int
    direction: str

    @property
    def is_material(self) -> bool:
        return abs(self.change) >= MATERIAL_CHANGE


def _direction(change: float) -> str:
    if change >= MATERIAL_CHANGE:
        return "improved"
    if change <= -MATERIAL_CHANGE:
        return "declined"
    return "steady"


def officer_lift(
    db: Session, *, user: User, days: int = DEFAULT_WINDOW_DAYS
) -> list[CompetencyLift]:
    """How each of this officer's competencies has moved over the window."""
    as_of = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.scalars(
        select(ProficiencyEvidence).where(ProficiencyEvidence.user_id == user.id)
    ).all()

    by_competency: dict[int, list[ProficiencyEvidence]] = {}
    for row in rows:
        by_competency.setdefault(row.competency_id, []).append(row)

    competencies = {c.id: c for c in db.scalars(select(Competency)).all()}
    results: list[CompetencyLift] = []

    for comp_id, evidence in by_competency.items():
        competency = competencies.get(comp_id)
        if competency is None:
            continue

        then = derive_level(evidence, as_of=as_of)
        now = derive_level(evidence)
        change = round(now.level - then.level, 2)

        results.append(CompetencyLift(
            competency_id=comp_id,
            competency_code=competency.code,
            competency_name=competency.name,
            level_then=then.level,
            level_now=now.level,
            change=change,
            evidence_then=then.evidence_count,
            evidence_added=now.evidence_count - then.evidence_count,
            direction=_direction(change),
        ))

    results.sort(key=lambda r: r.change, reverse=True)
    return results


def officer_summary(
    db: Session, *, user: User, days: int = DEFAULT_WINDOW_DAYS
) -> dict:
    lifts = officer_lift(db, user=user, days=days)
    improved = [item for item in lifts if item.direction == "improved"]
    declined = [item for item in lifts if item.direction == "declined"]

    mean_change = (
        round(sum(item.change for item in lifts) / len(lifts), 3) if lifts else 0.0
    )

    return {
        "window_days": days,
        "competencies": [vars(item) for item in lifts],
        "summary": {
            "measured": len(lifts),
            "improved": len(improved),
            "declined": len(declined),
            "steady": len(lifts) - len(improved) - len(declined),
            "mean_change": mean_change,
            "evidence_added": sum(item.evidence_added for item in lifts),
        },
        "note": (
            "Levels are recomputed from the evidence that existed at each date, "
            "with recency decay measured from that date. A decline usually means "
            "older evidence has aged rather than that anyone got worse — skills "
            "decay in this model unless evidence is refreshed."
        ),
    }


def workforce_lift(db: Session, *, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Aggregate movement, by competency and by division.

    This is the figure a capacity building plan is judged against a year later.
    """
    as_of = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.scalars(select(ProficiencyEvidence)).all()
    by_user_competency: dict[tuple[int, int], list[ProficiencyEvidence]] = {}
    for row in rows:
        by_user_competency.setdefault((row.user_id, row.competency_id), []).append(row)

    competencies = {c.id: c for c in db.scalars(select(Competency)).all()}
    users = {u.id: u for u in db.scalars(select(User)).all()}
    divisions = {d.id: d for d in db.scalars(select(Division)).all()}

    per_competency: dict[int, list[float]] = {}
    per_division: dict[int, list[float]] = {}
    total_then: list[float] = []
    total_now: list[float] = []

    for (user_id, comp_id), evidence in by_user_competency.items():
        user = users.get(user_id)
        if user is None or not user.is_active:
            continue

        then = derive_level(evidence, as_of=as_of).level
        now = derive_level(evidence).level
        change = now - then

        per_competency.setdefault(comp_id, []).append(change)
        if user.division_id is not None:
            per_division.setdefault(user.division_id, []).append(change)
        total_then.append(then)
        total_now.append(now)

    def summarise(changes: list[float]) -> dict:
        return {
            "mean_change": round(sum(changes) / len(changes), 3) if changes else 0.0,
            "improved": sum(1 for c in changes if c >= MATERIAL_CHANGE),
            "declined": sum(1 for c in changes if c <= -MATERIAL_CHANGE),
            "measured": len(changes),
        }

    by_competency = [
        {
            "code": competencies[cid].code,
            "name": competencies[cid].name,
            **summarise(changes),
        }
        for cid, changes in per_competency.items()
        if cid in competencies
    ]
    by_competency.sort(key=lambda item: item["mean_change"], reverse=True)

    by_division = [
        {
            "code": divisions[did].code,
            "name": divisions[did].name,
            **summarise(changes),
        }
        for did, changes in per_division.items()
        if did in divisions
    ]
    by_division.sort(key=lambda item: item["mean_change"], reverse=True)

    # Which sources drove the change: a workforce improving only on
    # self-assessment has not improved.
    recent_sources = [
        {"source": source.value if hasattr(source, "value") else str(source),
         "count": int(count)}
        for source, count in db.execute(
            select(ProficiencyEvidence.source, func.count(ProficiencyEvidence.id))
            .where(ProficiencyEvidence.created_at >= as_of)
            .group_by(ProficiencyEvidence.source)
        ).all()
    ]
    recent_sources.sort(key=lambda item: item["count"], reverse=True)

    demonstrated = {
        EvidenceSource.SIMULATION.value, EvidenceSource.QUIZ.value,
        EvidenceSource.DIAGNOSTIC.value, EvidenceSource.INTERVIEW.value,
    }
    total_recent = sum(item["count"] for item in recent_sources) or 1

    return {
        "window_days": days,
        "overall": {
            "mean_level_then": round(sum(total_then) / len(total_then), 3) if total_then else DEFAULT_LEVEL,
            "mean_level_now": round(sum(total_now) / len(total_now), 3) if total_now else DEFAULT_LEVEL,
            "mean_change": round(
                (sum(total_now) - sum(total_then)) / len(total_now), 3
            ) if total_now else 0.0,
            "profiles_measured": len(total_now),
        },
        "by_competency": by_competency,
        "by_division": by_division,
        "evidence_in_window": {
            "total": total_recent,
            "by_source": recent_sources,
            "demonstrated_pct": round(
                100 * sum(item["count"] for item in recent_sources
                          if item["source"] in demonstrated) / total_recent, 1
            ),
        },
        "caveat": (
            "Movement here is not attributable to training on its own. It reflects "
            "everything that happened in the window, including evidence ageing. "
            "Read it alongside course efficacy rather than instead of it."
        ),
    }
