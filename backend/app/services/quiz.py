"""The item catalogue, and classical item analysis over it.

Taking an assessment moved to `app.services.adaptive_quiz` when the fixed form
was replaced by an adaptive one. What stayed here is everything about the
*items* rather than the sitting: which are servable, how they have behaved, and
whether the bank is healthy enough to be trusted.

**Only approved questions are ever served.** There is no parameter that lets a
draft through. Everything an officer sees has been read by a subject expert.

**Classical statistics are kept alongside IRT, not replaced by it.** A p-value
and a point-biserial need no model to be believed, and a negative point-biserial
is still the fastest way to find a miskeyed item — it shows up after a dozen
responses, where an IRT calibration needs twenty-five. The two answer different
questions and a reviewer wants both.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml import irt
from app.models import User
from app.models_content import GeneratedQuestion, QuestionStatus
from app.models_quiz import AttemptStatus, ItemResponse, QuizAttempt

# A Bloom level is already a statement about cognitive demand, so it is the
# natural prior for an item whose author gave no explicit difficulty. This maps
# one to the other and is used when seeding the bank; from there `irt_b` takes
# over and is calibrated from responses.
#
# `difficulty_p` is not a substitute for either: it is the *observed* p-value,
# it only exists once people have attempted the item, and it says more about who
# attempted it than about the item.
BLOOM_DIFFICULTY: dict[str, float] = {
    "remember": 2.0,
    "understand": 2.6,
    "apply": 3.3,
    "analyse": 3.9,
    "analyze": 3.9,
    "evaluate": 4.4,
    "create": 4.8,
}


def question_difficulty(question: GeneratedQuestion) -> float:
    """The Bloom-implied difficulty on the FRAC L1-L5 axis.

    A prior for an item nobody has given an explicit difficulty to. Seeding uses
    it; nothing that serves an item does, because by then `irt_b` exists.
    """
    return BLOOM_DIFFICULTY.get((question.bloom_level or "").lower(), 3.0)


class QuizError(Exception):
    """Something the caller did wrong, surfaced as a 4xx."""


def available_questions(
    db: Session, *, competency_id: int | None = None, limit: int = 50
) -> list[GeneratedQuestion]:
    """Approved questions only. Draft is not 'probably fine'."""
    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.status == QuestionStatus.APPROVED
    )
    if competency_id is not None:
        stmt = stmt.where(GeneratedQuestion.competency_id == competency_id)
    return list(db.scalars(stmt.limit(limit)).all())


# --------------------------------------------------------------------------- #
# Item psychometrics
# --------------------------------------------------------------------------- #

# Below this, statistics on an item are noise.
MIN_ATTEMPTS_FOR_STATS = 8

# Classical thresholds. An item everyone gets right, or that better candidates
# get wrong more often than weaker ones, is not measuring anything.
TOO_EASY = 0.95
TOO_HARD = 0.05
POOR_DISCRIMINATION = 0.10


def recompute_item_statistics(db: Session) -> dict:
    """Classical item analysis over every submitted response.

    `difficulty_p` is the proportion answering correctly — the standard p-value,
    where *higher means easier*, which reads backwards until you know it.

    `discrimination` is the point-biserial correlation between getting this item
    right and scoring well overall. A negative value means stronger candidates
    did worse on it, which almost always indicates a wrong key or an ambiguous
    stem.

    Items are **flagged, not auto-retired**. Everything else in this platform
    puts a human in front of a decision about assessment content, and silently
    withdrawing an item an expert approved would break that.
    """
    attempts = db.scalars(
        select(QuizAttempt).where(QuizAttempt.status == AttemptStatus.SUBMITTED)
    ).all()
    if not attempts:
        return {"items_updated": 0, "flagged": [], "note": "No submitted attempts yet."}

    scores = {a.id: a.accuracy for a in attempts}
    mean_score = sum(scores.values()) / len(scores)
    score_sd = (
        sum((s - mean_score) ** 2 for s in scores.values()) / len(scores)
    ) ** 0.5

    responses = db.scalars(
        select(ItemResponse).where(ItemResponse.attempt_id.in_(list(scores)))
    ).all()

    by_question: dict[int, list[ItemResponse]] = {}
    for response in responses:
        by_question.setdefault(response.question_id, []).append(response)

    updated = 0
    flagged: list[dict] = []

    for question_id, rows in by_question.items():
        question = db.get(GeneratedQuestion, question_id)
        if question is None or len(rows) < MIN_ATTEMPTS_FOR_STATS:
            continue

        correct = [r for r in rows if r.is_correct]
        p_value = len(correct) / len(rows)
        question.difficulty_p = round(p_value, 3)

        # Point-biserial: how far above average the people who got it right scored.
        if score_sd > 0 and 0 < len(correct) < len(rows):
            mean_correct = sum(scores[r.attempt_id] for r in correct) / len(correct)
            question.discrimination = round(
                ((mean_correct - mean_score) / score_sd)
                * ((p_value * (1 - p_value)) ** 0.5),
                3,
            )
        else:
            # Everyone right or everyone wrong: it separates nobody.
            question.discrimination = 0.0

        updated += 1

        reasons = []
        if p_value >= TOO_EASY:
            reasons.append(f"answered correctly by {p_value:.0%} — too easy to be informative")
        elif p_value <= TOO_HARD:
            reasons.append(f"answered correctly by only {p_value:.0%} — check the key")
        if question.discrimination is not None and question.discrimination < POOR_DISCRIMINATION:
            reasons.append(
                f"discrimination {question.discrimination:.2f} — stronger candidates "
                f"are not doing better on it"
            )

        if reasons:
            existing = [f for f in (question.quality_flags or []) if not f.startswith("Psychometrics:")]
            question.quality_flags = existing + [f"Psychometrics: {'; '.join(reasons)}"]
            flagged.append({
                "question_id": question.id,
                "stem": question.stem[:110],
                "attempts": len(rows),
                "difficulty_p": question.difficulty_p,
                "discrimination": question.discrimination,
                "reasons": reasons,
            })

    db.flush()
    return {
        "items_updated": updated,
        "items_below_threshold": len(by_question) - updated,
        "min_attempts": MIN_ATTEMPTS_FOR_STATS,
        "flagged": flagged,
        "note": (
            "difficulty_p is the proportion answering correctly, so a higher value "
            "means an easier item. Flagged items are left approved and in use — an "
            "expert decides whether to retire them."
        ),
    }


def attempt_history(db: Session, *, user: User, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user.id,
               QuizAttempt.status == AttemptStatus.SUBMITTED)
        .order_by(QuizAttempt.submitted_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": a.id,
            "competency_id": a.competency_id,
            "competency_name": a.competency.name if a.competency else None,
            "correct": a.correct_count,
            "items": a.item_count,
            "accuracy": round(100 * a.accuracy, 1),
            "derived_level": a.derived_level,
            "submitted_at": a.submitted_at,
            "adaptive": a.is_adaptive,
            "theta": a.theta,
            "theta_se": a.theta_se,
            # The interval, so two sittings can be compared honestly rather than
            # by their point estimates. L3.1 +/- 0.7 and L3.4 +/- 0.7 are not a
            # measured improvement, and a history table that shows only the
            # points invites reading them as one.
            "level_low": (
                round(irt.theta_to_level(a.theta - 1.96 * a.theta_se), 2)
                if a.theta is not None and a.theta_se is not None else None
            ),
            "level_high": (
                round(irt.theta_to_level(a.theta + 1.96 * a.theta_se), 2)
                if a.theta is not None and a.theta_se is not None else None
            ),
            "stop_reason": a.stop_reason,
        }
        for a in rows
    ]


def catalogue_item_health(db: Session) -> dict:
    """How much of the approved bank has enough data to be trusted."""
    total = db.scalar(
        select(func.count(GeneratedQuestion.id)).where(
            GeneratedQuestion.status == QuestionStatus.APPROVED
        )
    ) or 0
    measured = db.scalar(
        select(func.count(GeneratedQuestion.id)).where(
            GeneratedQuestion.status == QuestionStatus.APPROVED,
            GeneratedQuestion.times_attempted >= MIN_ATTEMPTS_FOR_STATS,
        )
    ) or 0
    calibrated = db.scalar(
        select(func.count(GeneratedQuestion.id)).where(
            GeneratedQuestion.status == QuestionStatus.APPROVED,
            GeneratedQuestion.irt_calibrated_at.is_not(None),
        )
    ) or 0
    return {
        "approved_items": total,
        "with_statistics": measured,
        "min_attempts": MIN_ATTEMPTS_FOR_STATS,
        # Separate from `with_statistics` on purpose: an item can have a solid
        # p-value and still not have enough responses for its difficulty to be
        # estimated on the ability scale.
        "irt_calibrated": calibrated,
        "min_responses_to_calibrate": irt.MIN_RESPONSES_TO_CALIBRATE,
    }
