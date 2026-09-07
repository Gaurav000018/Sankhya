"""Taking a quiz, and what the results are worth.

Two things here are deliberate:

**Only approved questions are ever served.** There is no parameter that lets a
draft through. Everything an officer sees has been read by a subject expert.

**Difficulty is part of the score.** 80% on a hard paper is not the same result
as 80% on an easy one, so the derived level is anchored on the mean difficulty
of the items actually asked. Reporting accuracy alone would make an easy quiz
look like competence.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, EvidenceSource, User
from app.models_content import GeneratedQuestion, QuestionStatus
from app.models_quiz import AttemptStatus, ItemResponse, QuizAttempt
from app.services.competency import analyse_gaps, record_evidence

DEFAULT_ITEM_COUNT = 8
MIN_ITEMS = 3

# An attempt this short says very little; the evidence it produces is weighted
# down accordingly rather than being refused.
CONFIDENCE_FLOOR = 0.4
CONFIDENCE_PER_ITEM = 0.08

# Difficulty of a "neutral" paper. Harder than this lifts the derived level for
# the same accuracy; easier lowers it.
NEUTRAL_DIFFICULTY = 3.0
DIFFICULTY_WEIGHT = 0.5

# A question carries no authored difficulty — it carries a Bloom level, which is
# already a statement about cognitive demand. Mapping that to a number keeps the
# two ideas connected rather than asking an author to guess on a second scale.
# `difficulty_p` is not a substitute: it is the *observed* p-value and only
# exists once people have attempted the item.
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
    return BLOOM_DIFFICULTY.get((question.bloom_level or "").lower(), NEUTRAL_DIFFICULTY)


class QuizError(Exception):
    """Something the caller did wrong, surfaced as a 4xx."""


@dataclass
class QuizResult:
    attempt: QuizAttempt
    derived_level: float
    confidence: float
    correct: int
    total: int


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


def start_attempt(
    db: Session,
    *,
    user: User,
    competency_id: int | None = None,
    item_count: int = DEFAULT_ITEM_COUNT,
) -> QuizAttempt:
    """Open an attempt over approved questions.

    With no competency named, items are drawn from the officer's widest gap —
    quizzing someone on what they already know measures nothing.
    """
    if competency_id is None:
        gaps = [g for g in analyse_gaps(db, user=user) if g.is_gap]
        for gap in gaps:
            if available_questions(db, competency_id=gap.competency_id):
                competency_id = gap.competency_id
                break

    if competency_id is None:
        # Everything here exists to produce competency evidence. An attempt with
        # no competency runs, scores, and silently records nothing — worse than
        # refusing, because the officer thinks they were assessed.
        raise QuizError(
            "No competency could be selected for this quiz. Either every gap "
            "already has enough approved questions, or the approved questions "
            "are not linked to a competency."
        )

    pool = available_questions(db, competency_id=competency_id)
    if len(pool) < MIN_ITEMS:
        raise QuizError(
            "Not enough approved questions yet for that competency. "
            "An expert needs to review more of the generated items first."
        )

    # Prefer items nobody has attempted much: it spreads psychometric coverage
    # instead of endlessly re-measuring the same handful.
    pool.sort(key=lambda q: (q.times_attempted, random.random()))
    chosen = pool[: min(item_count, len(pool))]
    random.shuffle(chosen)

    attempt = QuizAttempt(
        user_id=user.id,
        competency_id=competency_id,
        status=AttemptStatus.IN_PROGRESS,
        item_count=len(chosen),
        mean_difficulty=round(
            sum(question_difficulty(q) for q in chosen) / len(chosen), 2
        ),
    )
    db.add(attempt)
    db.flush()

    for index, question in enumerate(chosen):
        db.add(ItemResponse(
            attempt_id=attempt.id, question_id=question.id, sequence=index
        ))

    db.flush()
    return attempt


def submit_attempt(
    db: Session, *, attempt: QuizAttempt, answers: dict[int, int]
) -> QuizResult:
    """Mark the attempt, write evidence, and update item statistics.

    `answers` maps question id to the selected option index. Unanswered items
    count as incorrect — leaving one blank is a result, not an absence.
    """
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise QuizError("This attempt has already been submitted")

    now = datetime.now(timezone.utc)
    correct = 0
    difficulties: list[float] = []

    for response in attempt.responses:
        question = response.question
        if question is None:
            continue
        selected = answers.get(question.id)
        response.selected_index = selected
        response.is_correct = selected is not None and selected == question.correct_index
        response.answered_at = now
        if response.is_correct:
            correct += 1

        # Item statistics accumulate on the question itself.
        question.times_attempted += 1
        if response.is_correct:
            question.times_correct += 1

        difficulties.append(question_difficulty(question))

    attempt.correct_count = correct
    attempt.mean_difficulty = (
        round(sum(difficulties) / len(difficulties), 2) if difficulties else NEUTRAL_DIFFICULTY
    )
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = now

    accuracy = correct / attempt.item_count if attempt.item_count else 0.0
    level = 1.0 + 4.0 * accuracy
    # Adjust for how hard the paper was.
    level += (attempt.mean_difficulty - NEUTRAL_DIFFICULTY) * DIFFICULTY_WEIGHT
    level = round(max(1.0, min(5.0, level)), 2)
    attempt.derived_level = level

    confidence = round(
        min(1.0, CONFIDENCE_FLOOR + CONFIDENCE_PER_ITEM * attempt.item_count), 2
    )

    db.flush()

    if attempt.competency_id is not None:
        record_evidence(
            db,
            user_id=attempt.user_id,
            competency_id=attempt.competency_id,
            level_estimate=level,
            source=EvidenceSource.QUIZ,
            confidence=confidence,
            source_ref=f"quiz_attempt:{attempt.id}",
            note=f"{correct} of {attempt.item_count} correct",
        )

    db.add(AuditLog(
        actor_user_id=attempt.user_id,
        action="quiz.submitted",
        entity_type="quiz_attempt",
        entity_id=str(attempt.id),
        meta={
            "competency_id": attempt.competency_id,
            "correct": correct,
            "items": attempt.item_count,
            "derived_level": level,
            "confidence": confidence,
        },
    ))
    db.flush()

    return QuizResult(
        attempt=attempt, derived_level=level, confidence=confidence,
        correct=correct, total=attempt.item_count,
    )


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
    return {
        "approved_items": total,
        "with_statistics": measured,
        "min_attempts": MIN_ATTEMPTS_FOR_STATS,
    }
