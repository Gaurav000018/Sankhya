"""Courses, recommendations and learning paths."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import can_view_officer, get_current_user, require_roles, write_audit
from app.db import get_db
from app.models import Competency, User, UserRole
from app.models_learning import Course, LearningPath, Recommendation
from app.schemas import CourseOut, LearningPathOut, PathItemOut, RecommendationOut
from app.services import igot, recommender, simulator

router = APIRouter(tags=["learning"])


def _course_out(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        external_id=course.external_id,
        source=course.source.value,
        title=course.title,
        description=course.description,
        provider=course.provider,
        competency_id=course.competency_id,
        level_from=course.level_from,
        level_to=course.level_to,
        duration_hours=course.duration_hours,
    )


def _recommendation_out(r: Recommendation, competency_names: dict[int, str]) -> RecommendationOut:
    return RecommendationOut(
        id=r.id,
        course=_course_out(r.course),
        competency_id=r.competency_id,
        competency_name=competency_names.get(r.competency_id, ""),
        current_level=r.current_level,
        required_level=r.required_level,
        gap=round(max(0.0, r.required_level - r.current_level), 2),
        score=r.score,
        signals=r.signals or {},
        reason=r.reason,
    )


@router.post("/learning/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_catalogue(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Import or refresh the course catalogue, then embed it."""
    result = igot.sync_catalogue(db)
    result["embedded"] = recommender.embed_catalogue(db)
    write_audit(
        db, action="learning.catalogue_synced", actor_user_id=actor.id,
        meta=result, request=request,
    )
    db.commit()
    return result


@router.get("/courses", response_model=list[CourseOut])
def list_courses(
    competency_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Course).where(Course.is_active.is_(True))
    if competency_id is not None:
        stmt = stmt.where(Course.competency_id == competency_id)
    return [_course_out(c) for c in db.scalars(stmt.order_by(Course.level_from)).all()]


@router.get("/recommendations/me", response_model=list[RecommendationOut])
def my_recommendations(
    target_role_id: int | None = None,
    refresh: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recommendations for the signed-in officer.

    Generated on first request so the dashboard is never empty on a fresh
    account. Pass `target_role_id` to ask what would close the gap to a role
    they are aiming for instead.
    """
    existing = db.scalars(
        select(Recommendation)
        .where(Recommendation.user_id == user.id)
        .order_by(Recommendation.score.desc())
    ).all()

    if refresh or not existing or target_role_id is not None:
        recommender.recommend(db, user=user, target_role_id=target_role_id)
        db.commit()
        existing = db.scalars(
            select(Recommendation)
            .where(Recommendation.user_id == user.id)
            .order_by(Recommendation.score.desc())
        ).all()

    names = {c.id: c.name for c in db.scalars(select(Competency)).all()}
    return [_recommendation_out(r, names) for r in existing]


@router.get("/recommendations/{user_id}", response_model=list[RecommendationOut])
def officer_recommendations(
    user_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Officer not found")
    if not can_view_officer(viewer, target):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only view officers in your own division"
        )

    if not db.scalar(select(Recommendation.id).where(Recommendation.user_id == target.id)):
        recommender.recommend(db, user=target)
        db.commit()

    rows = db.scalars(
        select(Recommendation)
        .where(Recommendation.user_id == target.id)
        .order_by(Recommendation.score.desc())
    ).all()
    names = {c.id: c.name for c in db.scalars(select(Competency)).all()}
    return [_recommendation_out(r, names) for r in rows]


@router.post("/learning-paths", response_model=LearningPathOut, status_code=status.HTTP_201_CREATED)
def create_path(
    competency_id: int,
    target_role_id: int | None = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Build an ordered path closing one competency gap.

    Prerequisites are resolved from the course graph, so the officer is never
    told to start with something they are not ready for.
    """
    path = recommender.build_path(
        db, user=user, competency_id=competency_id, target_role_id=target_role_id
    )
    if path is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No gap to close on that competency, or no suitable course in the catalogue",
        )
    write_audit(
        db, action="learning.path_created", actor_user_id=user.id,
        entity_type="learning_path", entity_id=str(path.id),
        meta={"competency_id": competency_id}, request=request,
    )
    db.commit()
    db.refresh(path)
    return _path_out(db, path)


@router.get("/learning-paths/me", response_model=list[LearningPathOut])
def my_paths(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    paths = db.scalars(
        select(LearningPath)
        .where(LearningPath.user_id == user.id)
        .order_by(LearningPath.created_at.desc())
    ).all()
    return [_path_out(db, p) for p in paths]


def _path_out(db: Session, path: LearningPath) -> LearningPathOut:
    competency = db.get(Competency, path.competency_id)
    return LearningPathOut(
        id=path.id,
        competency_id=path.competency_id,
        competency_name=competency.name if competency else "",
        current_level=path.current_level,
        target_level=path.target_level,
        reaches_level=path.reaches_level,
        total_hours=path.total_hours,
        estimated_weeks=path.estimated_weeks,
        reason=path.reason,
        items=[
            PathItemOut(
                sequence=item.sequence,
                status=item.status.value,
                included_because=item.included_because,
                course=_course_out(item.course),
            )
            for item in path.items
        ],
    )


@router.post("/courses/{course_id}/complete", status_code=status.HTTP_201_CREATED)
def complete_course(
    course_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a course complete.

    Writes a low-weight LEARNING_ACTIVITY observation capped at the course's own
    ceiling — finishing a foundation course cannot claim an advanced level.
    """
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")

    completion = recommender.record_completion(db, user=user, course=course)
    write_audit(
        db, action="learning.course_completed", actor_user_id=user.id,
        entity_type="course", entity_id=str(course.id), request=request,
    )
    db.commit()

    return {
        "course_id": course.id,
        "title": course.title,
        "completed_at": completion.completed_at,
        "note": (
            "Recorded as a learning activity. Course completion is weak evidence of "
            "competence, so it carries low weight until an assessment confirms it."
        ),
    }


class SimulationIn(BaseModel):
    course_ids: list[int] = Field(default_factory=list, max_length=12)
    target_role_id: int | None = None


@router.post("/promotion/simulate")
def simulate_promotion(
    payload: SimulationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Project readiness if these courses were completed.

    Applied in order, because a course only counts for the part of its band
    above where the officer already is.
    """
    return simulator.simulate(
        db, user=user, course_ids=payload.course_ids,
        target_role_id=payload.target_role_id,
    )


@router.get("/promotion/forecast")
def forecast_promotion(
    target_role_id: int | None = None,
    window_days: int = 180,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """When the officer reaches the target at their measured rate of progress."""
    return simulator.forecast(
        db, user=user, target_role_id=target_role_id,
        window_days=max(30, min(window_days, 730)),
    )
