"""Diagnostic self-assessment, and officer settings.

A brand-new officer has no evidence, so every competency sits at the default
level and the dashboard has nothing to say. The diagnostic fixes that — but it
is deliberately **self-assessment, not measurement**.

Writing it as SELF evidence (weight 0.20, the lowest in the model) means the
profile is populated and usable immediately, while any real assessment
afterwards overwhelms it. It also gives the confidence-competence divergence
check something to compare against, which is the whole reason self-assessment is
kept in the model rather than excluded.

The response says all of this to the officer rather than presenting a
self-rating as though it were a result.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, write_audit
from app.db import get_db
from app.models import (
    Competency,
    EvidenceSource,
    ProficiencyEvidence,
    RoleCompetencyRequirement,
    User,
)
from app.schemas import UserOut
from app.services.competency import analyse_gaps, record_evidence

router = APIRouter(tags=["onboarding"])

# Plain-language anchors. "Rate yourself 1 to 5" invites everyone to pick 4;
# describing what each level looks like in the work makes the answer mean
# something.
LEVEL_DESCRIPTIONS = {
    1: "I have not worked with this",
    2: "I can follow a documented procedure with support",
    3: "I work independently on routine cases",
    4: "I handle non-routine cases and review others' work",
    5: "I set the approach and others come to me on it",
}


class SelfRating(BaseModel):
    competency_id: int
    level: float = Field(ge=1, le=5)


class DiagnosticSubmission(BaseModel):
    ratings: list[SelfRating] = Field(min_length=1)


class SettingsUpdate(BaseModel):
    """Only what an officer may change about themselves."""

    fluency_scoring_enabled: bool | None = None


@router.get("/diagnostic")
def get_diagnostic(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """The competencies this officer's role requires, with anchors.

    Reports whether they have already done this, so the UI can offer it as
    onboarding rather than pushing it at someone who is already measured.
    """
    if user.frac_role_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No FRAC role is assigned to your account, so there is nothing to "
            "assess against. Ask your division administrator.",
        )

    requirements = db.scalars(
        select(RoleCompetencyRequirement).where(
            RoleCompetencyRequirement.frac_role_id == user.frac_role_id
        )
    ).all()
    competencies = {
        c.id: c
        for c in db.scalars(
            select(Competency).where(
                Competency.id.in_([r.competency_id for r in requirements])
            )
        ).all()
    }

    already_rated = {
        row[0]
        for row in db.execute(
            select(ProficiencyEvidence.competency_id).where(
                ProficiencyEvidence.user_id == user.id,
                ProficiencyEvidence.source == EvidenceSource.SELF,
            )
        ).all()
    }
    evidence_count = db.scalar(
        select(ProficiencyEvidence.id)
        .where(ProficiencyEvidence.user_id == user.id)
        .limit(1)
    )

    return {
        "role": user.frac_role.name if user.frac_role else None,
        "completed": len(already_rated) > 0,
        "has_any_evidence": evidence_count is not None,
        "level_descriptions": LEVEL_DESCRIPTIONS,
        "competencies": [
            {
                "id": competencies[r.competency_id].id,
                "code": competencies[r.competency_id].code,
                "name": competencies[r.competency_id].name,
                "domain": competencies[r.competency_id].domain.value,
                "required_level": r.required_level,
                "criticality": r.criticality.value,
                "already_rated": r.competency_id in already_rated,
            }
            for r in requirements
            if r.competency_id in competencies
        ],
        "disclosure": (
            "This is a self-assessment, not a measurement. It carries the lowest "
            "weight of any evidence in the system, so a quiz, an interview or a "
            "piece of demonstrated work will outweigh it immediately. It exists "
            "so your profile is not empty while you are being assessed properly."
        ),
    }


@router.post("/diagnostic", status_code=status.HTTP_201_CREATED)
def submit_diagnostic(
    payload: DiagnosticSubmission,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record self-ratings as SELF evidence and hand back the resulting gaps."""
    valid = {
        row[0]
        for row in db.execute(
            select(RoleCompetencyRequirement.competency_id).where(
                RoleCompetencyRequirement.frac_role_id == user.frac_role_id
            )
        ).all()
    }

    unknown = [r.competency_id for r in payload.ratings if r.competency_id not in valid]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Your role does not require competency {unknown[0]}, so a rating for "
            f"it would not mean anything.",
        )

    for rating in payload.ratings:
        record_evidence(
            db,
            user_id=user.id,
            competency_id=rating.competency_id,
            level_estimate=rating.level,
            source=EvidenceSource.SELF,
            # Not a confidence in the officer — a statement that self-report is
            # a weak instrument. The source weight does the rest.
            confidence=0.8,
            source_ref="diagnostic",
            note="Diagnostic self-assessment",
        )

    write_audit(
        db, action="diagnostic.submitted", actor_user_id=user.id,
        entity_type="user", entity_id=str(user.id),
        meta={"ratings": len(payload.ratings)}, request=request,
    )
    db.commit()

    gaps = analyse_gaps(db, user=user)
    return {
        "recorded": len(payload.ratings),
        "gaps": [
            {
                "competency_id": g.competency_id,
                "competency_name": g.competency_name,
                "current_level": g.current_level,
                "required_level": g.required_level,
                "status": g.status,
            }
            for g in gaps
            if g.is_gap
        ],
        "next_step": (
            "Take a quiz or an AI interview on your widest gap. Those produce "
            "measured evidence, which will replace these estimates in your profile."
        ),
    }


@router.patch("/me/settings", response_model=UserOut)
def update_settings(
    payload: SettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change your own settings.

    `fluency_scoring_enabled` is the accommodation switch: turning it off stops
    the AI interview scoring delivery, and leaves the Knowledge axis untouched.
    An officer sets this for themselves — requiring a supervisor's approval to
    switch off a scoring axis would defeat the point.
    """
    changed: dict[str, object] = {}
    if payload.fluency_scoring_enabled is not None:
        user.fluency_scoring_enabled = payload.fluency_scoring_enabled
        changed["fluency_scoring_enabled"] = payload.fluency_scoring_enabled

    if changed:
        write_audit(
            db, action="user.settings_changed", actor_user_id=user.id,
            entity_type="user", entity_id=str(user.id), meta=changed,
            request=request,
        )
    db.commit()
    db.refresh(user)
    return user
