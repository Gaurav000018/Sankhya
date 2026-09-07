"""Digital Skill Twin, gap analysis, and evidence intake."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import (
    can_view_officer,
    get_current_user,
    require_roles,
    write_audit,
)
from app.db import get_db
from app.models import (
    Competency,
    CompetencyProfile,
    EvidenceSource,
    FracRole,
    ProficiencyEvidence,
    User,
    UserRole,
)
from app.schemas import (
    CompetencyLevelOut,
    CompetencyOut,
    DivergenceOut,
    EvidenceIn,
    EvidenceOut,
    FracRoleOut,
    GapOut,
    SkillTwinOut,
)
from app.services import lift as lift_service
from app.services import report as report_service
from app.services.competency import (
    DEFAULT_LEVEL,
    MIN_WEIGHT_FOR_CONFIDENT_LEVEL,
    analyse_gaps,
    detect_divergence,
    record_evidence,
    role_readiness,
)

router = APIRouter(tags=["skill-twin"])


def _require_role_exists(db: Session, target_role_id: int | None) -> None:
    """An unknown target role must fail loudly.

    Returning an empty gap list would read as 'no gaps' — the worst possible
    answer to give someone asking whether they are ready for a promotion.
    """
    if target_role_id is None:
        return
    if db.get(FracRole, target_role_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That target role does not exist")


@router.get("/frac/roles", response_model=list[FracRoleOut])
def list_roles(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The FRAC role ladder, ascending. Drives the Promotion Simulator's picker."""
    return list(db.scalars(select(FracRole).order_by(FracRole.level_order)).all())


@router.get("/frac/competencies", response_model=list[CompetencyOut])
def list_competencies(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Competency).order_by(Competency.code)).all())


def _resolve_target(db: Session, viewer: User, user_id: int | None) -> User:
    if user_id is None or user_id == viewer.id:
        return viewer
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Officer not found")
    if not can_view_officer(viewer, target):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only view officers in your own division"
        )
    return target


def _build_skill_twin(db: Session, user: User) -> SkillTwinOut:
    """Every competency in the framework, measured or not.

    A competency with no evidence is reported at the default level with
    `is_confident: False` and a zero evidence count, rather than being omitted.
    Silence is not the same as a low score, and a radar chart that quietly drops
    axes is a chart that lies about coverage.
    """
    profiles = {
        p.competency_id: p
        for p in db.scalars(
            select(CompetencyProfile).where(CompetencyProfile.user_id == user.id)
        ).all()
    }

    levels = []
    for comp in db.scalars(select(Competency)).all():
        p = profiles.get(comp.id)
        levels.append(
            CompetencyLevelOut(
                competency_id=comp.id,
                competency_code=comp.code,
                competency_name=comp.name,
                domain=comp.domain.value,
                level=p.level if p else DEFAULT_LEVEL,
                evidence_count=p.evidence_count if p else 0,
                evidence_weight=p.evidence_weight if p else 0.0,
                strongest_source=(
                    p.strongest_source.value if p and p.strongest_source else None
                ),
                last_evidence_at=p.last_evidence_at if p else None,
                is_confident=bool(p) and p.evidence_weight >= MIN_WEIGHT_FOR_CONFIDENT_LEVEL,
            )
        )
    levels.sort(key=lambda c: c.competency_name)

    return SkillTwinOut(
        user=user,
        role_name=user.frac_role.name if user.frac_role else None,
        role_readiness=role_readiness(db, user=user),
        competencies=levels,
    )


@router.get("/skill-twin/me", response_model=SkillTwinOut)
def my_skill_twin(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SkillTwinOut:
    return _build_skill_twin(db, user)


@router.get("/skill-twin/{user_id}", response_model=SkillTwinOut)
def officer_skill_twin(
    user_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
) -> SkillTwinOut:
    return _build_skill_twin(db, _resolve_target(db, viewer, user_id))


@router.get("/gaps/me", response_model=list[GapOut])
def my_gaps(
    target_role_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GapOut]:
    """Gaps against the officer's current role, or against a role they are
    aiming for when `target_role_id` is supplied."""
    _require_role_exists(db, target_role_id)
    return [GapOut(**vars(g)) for g in analyse_gaps(db, user=user, target_role_id=target_role_id)]


@router.get("/gaps/{user_id}", response_model=list[GapOut])
def officer_gaps(
    user_id: int,
    target_role_id: int | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
) -> list[GapOut]:
    target = _resolve_target(db, viewer, user_id)
    _require_role_exists(db, target_role_id)
    return [
        GapOut(**vars(g))
        for g in analyse_gaps(db, user=target, target_role_id=target_role_id)
    ]


@router.get("/divergence/me", response_model=list[DivergenceOut])
def my_divergence(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[DivergenceOut]:
    return [DivergenceOut(**vars(f)) for f in detect_divergence(db, user_id=user.id)]


@router.get("/evidence/me", response_model=list[EvidenceOut])
def my_evidence(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProficiencyEvidence]:
    """The officer's own evidence timeline — every observation, newest first."""
    return list(
        db.scalars(
            select(ProficiencyEvidence)
            .where(ProficiencyEvidence.user_id == user.id)
            .order_by(ProficiencyEvidence.created_at.desc())
            .limit(min(limit, 500))
        ).all()
    )


@router.post("/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
def add_evidence(
    payload: EvidenceIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.SME, UserRole.ADMIN)),
) -> ProficiencyEvidence:
    """Append an observation.

    Supervisors may only record against officers in their own division. There is
    no endpoint to update or delete evidence — corrections are new rows.
    """
    try:
        source = EvidenceSource(payload.source)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown evidence source. Expected one of: "
            f"{', '.join(s.value for s in EvidenceSource)}",
        )

    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Officer not found")
    if not can_view_officer(actor, target):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only record evidence for your own division"
        )

    ev = record_evidence(
        db,
        user_id=payload.user_id,
        competency_id=payload.competency_id,
        level_estimate=payload.level_estimate,
        source=source,
        confidence=payload.confidence,
        source_ref=payload.source_ref,
        note=payload.note,
        recorded_by_id=actor.id,
    )
    db.commit()
    db.refresh(ev)
    return ev


@router.get("/lift/me")
def my_lift(
    days: int = 180,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """How this officer's competencies have moved.

    Historical levels are recomputed from the evidence that existed at the time,
    with decay measured from that date — not interpolated from today's figure.
    """
    return lift_service.officer_summary(db, user=user, days=max(30, min(days, 730)))


@router.get("/lift/{user_id}")
def officer_lift(
    user_id: int,
    days: int = 180,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    target = _resolve_target(db, viewer, user_id)
    return lift_service.officer_summary(db, user=target, days=max(30, min(days, 730)))


@router.get("/reports/evidence/me")
def my_evidence_report(
    days: int = 180,
    db: Session = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
    user: User = Depends(get_current_user),
):
    """Signable Competency Evidence Report as a PDF."""
    return _evidence_report(db, user, days, request, actor=user)


@router.get("/reports/evidence/{user_id}")
def officer_evidence_report(
    user_id: int,
    days: int = 180,
    db: Session = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
    viewer: User = Depends(get_current_user),
):
    target = _resolve_target(db, viewer, user_id)
    return _evidence_report(db, target, days, request, actor=viewer)


def _evidence_report(db: Session, subject: User, days: int, request, actor: User):
    pdf, digest = report_service.render_pdf(db, subject, window_days=max(30, min(days, 730)))

    # Producing a personnel document is worth recording, including who asked for
    # it and which version they got.
    write_audit(
        db,
        action="report.evidence_generated",
        actor_user_id=actor.id,
        entity_type="user",
        entity_id=str(subject.id),
        meta={"verification_hash": digest, "window_days": days, "bytes": len(pdf)},
        request=request,
    )
    db.commit()

    safe_name = "".join(
        ch for ch in subject.full_name if ch.isalnum() or ch in " -_"
    ).strip().replace(" ", "_")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'inline; filename="competency-evidence-{safe_name}.pdf"',
            "X-Verification-Hash": digest,
        },
    )
