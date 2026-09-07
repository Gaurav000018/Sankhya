"""Taking a quiz, and item statistics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles, write_audit
from app.db import get_db
from app.models import User, UserRole
from app.models_quiz import QuizAttempt
from app.schemas import (
    QuizAttemptOut,
    QuizItemOut,
    QuizResultOut,
    QuizStartIn,
    QuizSubmitIn,
)
from app.services import quiz as quiz_service

router = APIRouter(tags=["quiz"])


def _attempt_out(attempt: QuizAttempt, *, reveal: bool) -> QuizAttemptOut:
    """`reveal` gates the answer key: withheld while the attempt is open."""
    return QuizAttemptOut(
        id=attempt.id,
        competency_id=attempt.competency_id,
        competency_name=attempt.competency.name if attempt.competency else None,
        status=attempt.status.value,
        item_count=attempt.item_count,
        mean_difficulty=attempt.mean_difficulty,
        items=[
            QuizItemOut(
                sequence=response.sequence,
                question_id=response.question_id,
                stem=response.question.stem,
                options=response.question.options,
                bloom_level=response.question.bloom_level,
                selected_index=response.selected_index,
                correct_index=response.question.correct_index if reveal else None,
                is_correct=response.is_correct if reveal else None,
                explanation=response.question.explanation if reveal else None,
                citation=(
                    {
                        "page": response.question.citation_page,
                        "quote": response.question.citation_quote,
                    }
                    if reveal
                    else None
                ),
            )
            for response in attempt.responses
            if response.question is not None
        ],
    )


def _load_attempt(db: Session, attempt_id: int, user: User) -> QuizAttempt:
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your attempt")
    return attempt


@router.post("/quizzes", response_model=QuizAttemptOut, status_code=status.HTTP_201_CREATED)
def start_quiz(
    payload: QuizStartIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Open an attempt.

    Without a competency, items are drawn from the officer's widest gap.
    Only SME-approved questions are ever served, and the answer key is withheld
    until submission.
    """
    try:
        attempt = quiz_service.start_attempt(
            db, user=user, competency_id=payload.competency_id,
            item_count=payload.item_count,
        )
    except quiz_service.QuizError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    write_audit(
        db, action="quiz.started", actor_user_id=user.id,
        entity_type="quiz_attempt", entity_id=str(attempt.id),
        meta={"competency_id": attempt.competency_id, "items": attempt.item_count},
        request=request,
    )
    db.commit()
    db.refresh(attempt)
    return _attempt_out(attempt, reveal=False)


@router.get("/quizzes/{attempt_id}", response_model=QuizAttemptOut)
def get_quiz(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = _load_attempt(db, attempt_id, user)
    return _attempt_out(attempt, reveal=attempt.status.value == "submitted")


@router.post("/quizzes/{attempt_id}/submit", response_model=QuizResultOut)
def submit_quiz(
    attempt_id: int,
    payload: QuizSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark the attempt and write the evidence it justifies.

    The derived level accounts for how hard the paper was, not just the
    proportion correct.
    """
    attempt = _load_attempt(db, attempt_id, user)
    try:
        result = quiz_service.submit_attempt(
            db, attempt=attempt,
            answers={a.question_id: a.selected_index for a in payload.answers},
        )
    except quiz_service.QuizError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    db.commit()
    db.refresh(attempt)

    return QuizResultOut(
        attempt=_attempt_out(attempt, reveal=True),
        correct=result.correct,
        total=result.total,
        accuracy=round(100 * result.correct / result.total, 1) if result.total else 0.0,
        derived_level=result.derived_level,
        confidence=result.confidence,
        note=(
            "Recorded as quiz evidence. The level accounts for how hard the paper "
            "was, and its weight reflects how many items you answered."
        ),
    )


@router.get("/quizzes")
def my_attempts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return {
        "attempts": quiz_service.attempt_history(db, user=user),
        "item_health": quiz_service.catalogue_item_health(db),
    }


@router.post("/questions/statistics/recompute")
def recompute_statistics(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Recompute classical item statistics across the approved bank.

    Items that look broken are **flagged, not withdrawn** — an expert approved
    them, and an expert decides whether to retire them.
    """
    result = quiz_service.recompute_item_statistics(db)
    write_audit(
        db, action="quiz.statistics_recomputed", actor_user_id=actor.id,
        meta={"items_updated": result["items_updated"],
              "flagged": len(result["flagged"])},
        request=request,
    )
    db.commit()
    return result


@router.post("/questions/{question_id}/retire")
def retire_question(
    question_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Withdraw an approved item, usually on psychometric grounds."""
    from app.models_content import GeneratedQuestion
    from app.services import quizgen

    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    quizgen.retire(db, question, actor, "Retired on psychometric grounds")
    db.commit()
    return {
        "question_id": question.id,
        "status": question.status.value,
        "difficulty_p": question.difficulty_p,
        "discrimination": question.discrimination,
    }
