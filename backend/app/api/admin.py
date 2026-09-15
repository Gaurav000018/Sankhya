"""Per-officer administration: the roster, and one officer's whole record.

Every other administrator endpoint returns an aggregate. These return named
people, which changes what the route has to do:

**Scope is enforced here, not requested.** An administrator sees every officer;
a supervisor sees their own division and nothing else, whatever `division_id`
they pass. A filter parameter is a request; a role boundary is not negotiable.

**Every drill-down is audited.** Reading a named officer's assessment history is
a privileged act against someone who cannot see that it happened. The platform
already refuses to let competency data be used against the person who supplied
it; the least it can do is record who looked.

**There is no write path.** Nothing here can change a level. Levels are derived
from evidence, and the only way to affect one is to append evidence with a
source and a confidence through `POST /evidence`, which is audited and
attributed. An administrator who could edit a number directly would break the
audit trail the entire design rests on.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles, write_audit
from app.db import get_db
from app.models import User, UserRole
from app.services import admin as admin_service

router = APIRouter(tags=["admin"])


@router.get("/admin/learners")
def list_learners(
    request: Request,
    search: str | None = Query(default=None, max_length=120),
    division_id: int | None = None,
    frac_role_id: int | None = None,
    only_with_critical_gaps: bool = False,
    include_inactive: bool = False,
    sort: str = Query(default="readiness", pattern="^(readiness|readiness_desc|name|recent)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=admin_service.PAGE_SIZE, ge=1, le=admin_service.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
):
    """The officer roster, lowest readiness first.

    Sorted that way by default because this list exists to find who needs
    attention, not to rank anybody. The readiness column is the share of an
    officer's required competencies they currently meet — a coarser figure than
    the criticality-weighted one on the detail page, and labelled as such so the
    two are not read as the same number.
    """
    return admin_service.list_learners(
        db,
        viewer=viewer,
        search=search,
        division_id=division_id,
        frac_role_id=frac_role_id,
        only_with_critical_gaps=only_with_critical_gaps,
        include_inactive=include_inactive,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/filters")
def learner_filters(
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
):
    """Divisions and roles this viewer may filter by.

    A supervisor is offered their own division only — otherwise the filter list
    itself discloses the shape of the organisation outside their scope.
    """
    return admin_service.filter_options(db, viewer=viewer)


@router.get("/admin/assessment-coverage")
def assessment_coverage(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """How much of the workforce has been measured, and how sharply.

    Coverage, not performance. A readiness figure built mostly on self-ratings
    and course completions means something very different from one built on
    assessments, and this is the number that says which it is.
    """
    return admin_service.workforce_assessment_summary(db)


@router.get("/admin/learners/{user_id}")
def learner_detail(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
):
    """One officer's complete record.

    Competency levels, gaps, the self-rating divergence, every adaptive
    assessment with its trace, interviews reported per axis, course completions
    and the full evidence trail — assembled from the same services the officer's
    own screens use, so both see the same number derived the same way.
    """
    subject = db.get(User, user_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Officer not found")

    if viewer.role != UserRole.ADMIN and (
        viewer.division_id is None or subject.division_id != viewer.division_id
    ):
        # 404 rather than 403: a supervisor probing ids should not be able to
        # learn that an officer exists in a division they cannot see.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Officer not found")

    detail = admin_service.learner_detail(db, user=subject)

    write_audit(
        db,
        action="admin.learner_viewed",
        actor_user_id=viewer.id,
        entity_type="user",
        entity_id=str(subject.id),
        meta={
            "subject_email": subject.email,
            "viewer_role": viewer.role.value,
            "assessments": len(detail.assessments),
            "evidence_records": len(detail.evidence),
        },
        request=request,
    )
    db.commit()

    return {
        "profile": detail.profile,
        "summary": detail.summary,
        "competencies": detail.competencies,
        "gaps": detail.gaps,
        "divergence": detail.divergence,
        "assessments": detail.assessments,
        "interviews": detail.interviews,
        "learning": detail.learning,
        "evidence": detail.evidence,
        "note": (
            "Every level here is derived from the evidence listed below it and "
            "traces back to the artifact that produced it. Nothing on this "
            "screen can be edited — to correct a level, append evidence."
        ),
    }
