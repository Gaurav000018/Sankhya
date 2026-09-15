"""The adaptive assessment, and the item statistics it produces.

One question at a time. The client is never given the item list, because there
is no item list — question seven is chosen from answer six — and it is never
given the answer key for a question still on screen.

The endpoints an officer uses:

    POST /quizzes                  open an attempt, get the first question
    POST /quizzes/{id}/answer      answer it, get the next one or the result
    GET  /quizzes/{id}             resume, or read a finished attempt
    POST /quizzes/{id}/abandon     walk away without recording evidence

and the ones an expert uses:

    POST /item-bank/calibrate              re-fit item difficulty from responses
    GET  /item-bank/health                 can each bank actually measure anyone
    POST /questions/statistics/recompute   classical p-value and point-biserial

The two bank-level routes sit under `/item-bank` rather than `/questions`
because `/questions/{question_id}` is already registered in `api.content` and
matches first: a literal `/questions/bank-health` is swallowed by it and returns
422 for a question id that is not an integer. They are about the bank as a
whole rather than about one question, so the separate prefix is honest as well
as necessary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles, write_audit
from app.db import get_db
from app.ml import irt
from app.models import User, UserRole
from app.models_content import GeneratedQuestion
from app.models_quiz import AttemptStatus, ItemResponse, QuizAttempt
from app.schemas import (
    AbilityOut,
    AdaptiveAnswerIn,
    AdaptiveAnswerOut,
    AdaptiveAttemptOut,
    AdaptiveItemOut,
    AdaptiveResultOut,
    GradedItemOut,
    QuizStartIn,
)
from app.services import adaptive_quiz, quiz as quiz_service

router = APIRouter(tags=["quiz"])


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _ability_out(ability: irt.Ability) -> AbilityOut:
    return AbilityOut(
        theta=round(ability.theta, 3),
        se=round(ability.se, 3),
        level=round(ability.level, 2),
        level_low=round(ability.level_low, 2),
        level_high=round(ability.level_high, 2),
        reliability=round(ability.reliability, 3),
    )


def _item_out(response: ItemResponse) -> AdaptiveItemOut:
    """The open question. Deliberately has no field that could carry the key."""
    question = response.question
    return AdaptiveItemOut(
        sequence=response.sequence,
        question_id=response.question_id,
        stem=question.stem,
        options=question.options,
        bloom_level=question.bloom_level,
        difficulty_level=round(
            irt.theta_to_level(
                response.item_difficulty
                if response.item_difficulty is not None
                else question.irt_b
            ),
            2,
        ),
        is_calibrated=question.is_calibrated,
        information=response.item_information or 0.0,
        asked_because=response.asked_because,
    )


def _graded_out(response: ItemResponse) -> GradedItemOut:
    question = response.question
    return GradedItemOut(
        question_id=response.question_id,
        stem=question.stem,
        options=question.options,
        selected_index=response.selected_index,
        correct_index=question.correct_index,
        is_correct=bool(response.is_correct),
        skipped=response.selected_index is None,
        difficulty_level=round(
            irt.theta_to_level(
                response.item_difficulty
                if response.item_difficulty is not None
                else question.irt_b
            ),
            2,
        ),
        explanation=question.explanation,
        distractor_rationale=question.distractor_rationale,
        citation=(
            {"page": question.citation_page, "quote": question.citation_quote}
            if question.citation_quote
            else None
        ),
    )


def _attempt_out(
    attempt: QuizAttempt, *, stop: irt.Stop | None = None
) -> AdaptiveAttemptOut:
    ability = adaptive_quiz.ability_of(attempt)
    current = adaptive_quiz.open_item(attempt)
    finished = attempt.status != AttemptStatus.IN_PROGRESS

    return AdaptiveAttemptOut(
        id=attempt.id,
        competency_id=attempt.competency_id,
        competency_name=attempt.competency.name if attempt.competency else None,
        status=attempt.status.value,
        asked=attempt.item_count,
        correct=attempt.correct_count,
        min_items=irt.MIN_ITEMS,
        max_items=irt.MAX_ITEMS,
        target_se=irt.TARGET_SE,
        ability=_ability_out(ability),
        current_item=(
            _item_out(current) if current is not None and not finished else None
        ),
        finished=finished,
        stop_reason=attempt.stop_reason,
        stop_explanation=(
            stop.explanation if stop else _stop_text(attempt, ability)
        ),
    )


def _result_out(
    attempt: QuizAttempt, *, stop: irt.Stop | None = None
) -> AdaptiveResultOut:
    ability = adaptive_quiz.ability_of(attempt)
    answered = [r for r in attempt.responses if r.answered_at is not None]
    return AdaptiveResultOut(
        attempt_id=attempt.id,
        competency_id=attempt.competency_id,
        competency_name=attempt.competency.name if attempt.competency else None,
        asked=attempt.item_count,
        correct=attempt.correct_count,
        accuracy=(
            round(100 * attempt.correct_count / attempt.item_count, 1)
            if attempt.item_count else 0.0
        ),
        ability=_ability_out(ability),
        derived_level=attempt.derived_level or round(ability.level, 2),
        confidence=round(ability.reliability, 3),
        stop_reason=attempt.stop_reason,
        stop_explanation=stop.explanation if stop else _stop_text(attempt, ability),
        mean_item_level=attempt.mean_difficulty,
        trace=adaptive_quiz.trace(attempt),
        review=[_graded_out(r) for r in answered],
        note=(
            f"Recorded as quiz evidence at L{ability.level:.2f}, weighted "
            f"{ability.reliability:.2f} — the marginal reliability of the estimate, "
            f"which is how much of the ability range this test actually resolved."
        ),
    )


def _stop_text(attempt: QuizAttempt, ability: irt.Ability) -> str | None:
    """The stop explanation for an attempt read back later.

    Rendered from the stored reason rather than stored as prose, so the wording
    tracks the code instead of freezing at whatever it said the day the officer
    sat the test.
    """
    return irt.explain_stop(
        attempt.stop_reason, ability, asked=attempt.item_count
    )


# --------------------------------------------------------------------------- #
# Taking one
# --------------------------------------------------------------------------- #


def _load_attempt(db: Session, attempt_id: int, user: User) -> QuizAttempt:
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your attempt")
    return attempt


@router.post(
    "/quizzes", response_model=AdaptiveAttemptOut, status_code=status.HTTP_201_CREATED
)
def start_quiz(
    payload: QuizStartIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Open an adaptive attempt and return its first question.

    Without a competency, the widest gap that has a usable item bank is chosen.
    The response carries one question — there is no item list to return, because
    what comes after depends on how this one is answered.
    """
    try:
        attempt = adaptive_quiz.start(
            db, user=user, competency_id=payload.competency_id
        )
    except adaptive_quiz.QuizError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    write_audit(
        db, action="quiz.started", actor_user_id=user.id,
        entity_type="quiz_attempt", entity_id=str(attempt.id),
        meta={"competency_id": attempt.competency_id, "adaptive": True},
        request=request,
    )
    db.commit()
    db.refresh(attempt)
    return _attempt_out(attempt)


@router.get("/quizzes/{attempt_id}", response_model=AdaptiveAttemptOut)
def get_quiz(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Resume an open attempt, or read the state of a finished one.

    Resuming re-serves whatever question was open. It does not re-choose one: an
    officer who reloads the page must not be able to shop for an easier item.
    """
    return _attempt_out(_load_attempt(db, attempt_id, user))


@router.post("/quizzes/{attempt_id}/answer", response_model=AdaptiveAnswerOut)
def answer_quiz(
    attempt_id: int,
    payload: AdaptiveAnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Answer the open question and get the next one, or the result.

    The key for the item just answered is released here and nowhere earlier.
    Immediate feedback is a deliberate choice — this is meant to teach as well as
    measure — and it is safe because the estimate has already moved by the time
    the explanation is shown, and no item is served twice.
    """
    attempt = _load_attempt(db, attempt_id, user)
    try:
        outcome = adaptive_quiz.answer(
            db,
            attempt=attempt,
            question_id=payload.question_id,
            selected_index=payload.selected_index,
            seconds_taken=payload.seconds_taken,
        )
    except adaptive_quiz.QuizError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    db.commit()
    db.refresh(attempt)

    return AdaptiveAnswerOut(
        graded=_graded_out(outcome.response),
        ability=_ability_out(outcome.ability),
        next_item=_item_out(outcome.next_item) if outcome.next_item else None,
        attempt=_attempt_out(attempt, stop=outcome.stop),
        result=_result_out(attempt, stop=outcome.stop) if outcome.finished else None,
    )


@router.get("/quizzes/{attempt_id}/result", response_model=AdaptiveResultOut)
def quiz_result(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The full result of a finished attempt, including the adaptive trace."""
    attempt = _load_attempt(db, attempt_id, user)
    if attempt.status != AttemptStatus.SUBMITTED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This attempt has not finished yet."
        )
    return _result_out(attempt)


@router.post("/quizzes/{attempt_id}/abandon", status_code=status.HTTP_204_NO_CONTENT)
def abandon_quiz(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Leave without recording evidence.

    A half-finished test measures something, but not competency. Recording it
    would put a low level on the officer's record for having been interrupted.
    """
    attempt = _load_attempt(db, attempt_id, user)
    adaptive_quiz.abandon(db, attempt=attempt)
    db.commit()


@router.get("/quizzes")
def my_attempts(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return {
        "attempts": quiz_service.attempt_history(db, user=user),
        "item_health": quiz_service.catalogue_item_health(db),
        "settings": {
            "min_items": irt.MIN_ITEMS,
            "max_items": irt.MAX_ITEMS,
            "target_se": irt.TARGET_SE,
        },
    }


# --------------------------------------------------------------------------- #
# Item psychometrics
# --------------------------------------------------------------------------- #


@router.get("/item-bank/health")
def bank_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Whether each competency's bank can actually measure anyone, and where.

    Item count is the wrong question on its own — twenty items all pitched at L3
    measure L3 well and nothing else at all. This reports information across the
    whole L1-L5 range, so a thin spot is visible before an officer falls into it.
    """
    return {
        "competencies": adaptive_quiz.bank_health(db),
        "min_pool": adaptive_quiz.MIN_POOL,
        "note": (
            "Information is additive across items and standard error is its "
            "inverse square root, so a level with information below about 1.0 "
            "cannot be measured to better than a full FRAC level."
        ),
    }


@router.post("/item-bank/calibrate")
def calibrate_items(
    request: Request,
    dry_run: bool = Query(
        default=False,
        description="Report what would change without writing it.",
    ),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Re-fit item difficulty and discrimination from real responses.

    Every item ships with the difficulty its author intended, which is a guess —
    an expert who knows the answer cannot see what is hard about the question.
    This replaces the guess with a measurement wherever enough people have
    answered, and reports the drift so a reviewer can look at the items whose
    difficulty was most badly misjudged.
    """
    result = adaptive_quiz.calibrate(db, dry_run=dry_run)
    if not dry_run:
        write_audit(
            db, action="quiz.items_calibrated", actor_user_id=actor.id,
            meta={
                "calibrated": result["calibrated"],
                "skipped": result["skipped"],
                "moved": len(result["changes"]),
            },
            request=request,
        )
        db.commit()
    return result


@router.post("/questions/statistics/recompute")
def recompute_statistics(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Classical item statistics — p-value and point-biserial discrimination.

    Kept alongside IRT rather than replaced by it. The classical numbers need no
    model to be believed and are what a reviewer reaches for first; a negative
    point-biserial is the fastest way to spot a miskeyed item, and it needs far
    fewer responses than a calibration does.

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
        "irt_b": question.irt_b,
        "irt_a": question.irt_a,
    }
