"""The adaptive assessment: one question at a time, chosen from the last answer.

A fixed paper is decided before the officer arrives. This is decided as they go,
and the difference is not cosmetic — against the same bank, scored by the same
model, twelve adaptively chosen items reach the precision of roughly twenty-four
fixed ones, and the margin is widest for officers furthest from the average.
Those are exactly the people a capacity-building programme exists to find.

The mechanics live in `app.ml.irt`, which has no database in it. This module is
the part that has to be careful about state:

**The estimate lives on the attempt, not in the client.** An adaptive test has
no item list to hand over up front — question seven depends on answer six. So
the posterior is persisted between requests, and the browser is told what to ask
next rather than being trusted to work it out. A client that could choose its
own next item could choose easy ones.

**The answer key never leaves the server while an item is open.** Same rule the
fixed-form quiz had, and it matters more here: the client now holds one question
at a time, so a leaked key is a leaked answer to the question on screen.

**Every attempt ends somewhere explicit.** Precision reached, item ceiling, or
bank exhausted — recorded on the attempt and shown to the officer. An assessment
that stops without saying why reads as a crash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml import irt
from app.models import AuditLog, Competency, CompetencyProfile, EvidenceSource, User
from app.models_content import GeneratedQuestion, QuestionStatus
from app.models_quiz import AttemptStatus, ItemResponse, QuizAttempt
from app.services.competency import analyse_gaps, record_evidence

log = logging.getLogger("sankhya.adaptive_quiz")

# An adaptive test needs somewhere to move. Below this many items in a
# competency there is no meaningful choice of difficulty, and running one would
# be a fixed paper wearing an adaptive label.
MIN_POOL = 6


class QuizError(Exception):
    """Something the caller did wrong, surfaced as a 4xx."""


# --------------------------------------------------------------------------- #
# Reading items out of the database
# --------------------------------------------------------------------------- #


def _as_irt_item(question: GeneratedQuestion) -> irt.Item:
    """The model's view of a stored question."""
    return irt.Item(
        id=question.id,
        a=question.irt_a,
        b=question.irt_b,
        c=question.irt_c,
        competency_id=question.competency_id,
        calibrated=question.is_calibrated,
    )


def _approved(db: Session, competency_id: int) -> list[GeneratedQuestion]:
    return list(db.scalars(
        select(GeneratedQuestion).where(
            GeneratedQuestion.status == QuestionStatus.APPROVED,
            GeneratedQuestion.competency_id == competency_id,
        )
    ).all())


def _remaining(db: Session, attempt: QuizAttempt) -> list[GeneratedQuestion]:
    """Approved items in this competency the officer has not already seen here."""
    seen = {r.question_id for r in attempt.responses}
    return [
        q for q in _approved(db, attempt.competency_id) if q.id not in seen
    ]


# --------------------------------------------------------------------------- #
# Choosing what to assess
# --------------------------------------------------------------------------- #


def _competency_with_a_bank(db: Session, *, user: User) -> int | None:
    """The officer's widest gap that actually has enough items to adapt over.

    Quizzing someone on what they already know measures nothing, so gaps come
    first. But a gap with four items in the bank cannot be assessed adaptively,
    and falling through to it would produce a worse measurement than moving to
    the next gap down.
    """
    for gap in analyse_gaps(db, user=user):
        if not gap.is_gap:
            continue
        if len(_approved(db, gap.competency_id)) >= MIN_POOL:
            return gap.competency_id

    # A newly registered officer has no FRAC role yet, so no gaps — refusing
    # would leave them unassessable until an administrator acts. Any competency
    # with a bank still produces real evidence; it is simply not aimed at a gap,
    # because no gap is known yet.
    return db.scalar(
        select(GeneratedQuestion.competency_id)
        .where(
            GeneratedQuestion.status == QuestionStatus.APPROVED,
            GeneratedQuestion.competency_id.is_not(None),
        )
        .group_by(GeneratedQuestion.competency_id)
        .having(func.count(GeneratedQuestion.id) >= MIN_POOL)
        .order_by(func.random())
    )


def _starting_level(db: Session, *, user: User, competency_id: int) -> float | None:
    """Where the officer's existing record puts them in this competency.

    Used to aim the *first question* and nothing else. The posterior always
    starts at the population prior — see `irt.select_opening`, which is where
    that separation is argued. If prior evidence seeded the estimate, a quiz
    would partly re-report what the Skill Twin already believed and the platform
    would be marking its own homework.
    """
    profile = db.scalar(
        select(CompetencyProfile).where(
            CompetencyProfile.user_id == user.id,
            CompetencyProfile.competency_id == competency_id,
        )
    )
    # A profile with almost no weight behind it is a default dressed as a
    # measurement. Aiming the opening question at it would be worse than aiming
    # at the middle of the scale, which at least makes no claim.
    if profile is None or profile.evidence_count == 0:
        return None
    return profile.level


# --------------------------------------------------------------------------- #
# The ability estimate
# --------------------------------------------------------------------------- #


def _answered(attempt: QuizAttempt) -> list[ItemResponse]:
    return [r for r in attempt.responses if r.answered_at is not None]


def _ability(db: Session, attempt: QuizAttempt) -> irt.Ability:
    """Re-estimate from every answer in this attempt.

    Recomputed from the responses rather than updated incrementally. A running
    posterior would be faster and would also mean a lost update silently
    corrupts a measurement; a hundred and sixty grid points times twelve items
    is not a cost worth that risk.
    """
    observations: list[tuple[irt.Item, bool]] = []
    for response in _answered(attempt):
        if response.question is None:
            continue
        observations.append((_as_irt_item(response.question), bool(response.is_correct)))
    return irt.estimate(observations)


def _candidates(pool: list[GeneratedQuestion]) -> list[irt.Item]:
    return [_as_irt_item(q) for q in pool]


def _best_information(pool: list[GeneratedQuestion], theta: float) -> float:
    """How much the most useful remaining item would tell us at this ability.

    Computed rather than discovered by trying to select, because selection is
    randomised for exposure control — asking it twice would give two different
    answers, and the stopping decision must be made on the same pool the next
    item is drawn from.
    """
    return max(
        (irt.information(theta, item) for item in _candidates(pool)), default=0.0
    )


def _serve_next(
    db: Session,
    attempt: QuizAttempt,
    ability: irt.Ability,
    *,
    first: bool,
    pool: list[GeneratedQuestion] | None = None,
) -> ItemResponse | None:
    """Pick the next item, record why, and open a response row for it."""
    pool = _remaining(db, attempt) if pool is None else pool
    if not pool:
        return None

    by_id = {q.id: q for q in pool}
    candidates = _candidates(pool)

    if first:
        chosen = irt.select_opening(
            candidates,
            starting_level=_starting_level(
                db, user=attempt.user, competency_id=attempt.competency_id
            ),
        )
    else:
        chosen = irt.select(candidates, ability)

    if chosen is None:
        return None

    question = by_id[chosen.id]
    response = ItemResponse(
        attempt_id=attempt.id,
        question_id=question.id,
        sequence=len(attempt.responses),
        theta_before=ability.theta,
        item_information=round(irt.information(ability.theta, chosen), 4),
        item_difficulty=chosen.b,
        asked_because=irt.why_this_item(chosen, ability, first=first),
    )
    db.add(response)
    attempt.responses.append(response)
    db.flush()
    return response


# --------------------------------------------------------------------------- #
# Starting
# --------------------------------------------------------------------------- #


def start(
    db: Session, *, user: User, competency_id: int | None = None
) -> QuizAttempt:
    """Open an adaptive attempt and serve its first question."""
    if competency_id is None:
        competency_id = _competency_with_a_bank(db, user=user)

    if competency_id is None:
        raise QuizError(
            "No competency has enough approved questions to assess adaptively. "
            f"An adaptive test needs at least {MIN_POOL} items in one competency "
            "so it has a range of difficulty to choose from."
        )

    pool = _approved(db, competency_id)
    if len(pool) < MIN_POOL:
        raise QuizError(
            f"That competency has {len(pool)} approved question"
            f"{'' if len(pool) == 1 else 's'}; an adaptive test needs at least "
            f"{MIN_POOL} so it has somewhere to move when an answer is right or "
            f"wrong. An expert needs to review more items first."
        )

    # Abandon any attempt this officer left open on the same competency. Without
    # this every abandoned test stays IN_PROGRESS forever, and resuming picks an
    # arbitrary one of them.
    for stale in db.scalars(
        select(QuizAttempt).where(
            QuizAttempt.user_id == user.id,
            QuizAttempt.competency_id == competency_id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    ).all():
        stale.status = AttemptStatus.ABANDONED

    prior = irt.estimate([])
    attempt = QuizAttempt(
        user_id=user.id,
        competency_id=competency_id,
        status=AttemptStatus.IN_PROGRESS,
        is_adaptive=True,
        item_count=0,
        theta=prior.theta,
        theta_se=prior.se,
    )
    db.add(attempt)
    db.flush()

    if _serve_next(db, attempt, prior, first=True) is None:
        raise QuizError("No item could be selected for that competency.")

    db.flush()
    return attempt


def open_item(attempt: QuizAttempt) -> ItemResponse | None:
    """The question currently on screen — the one served but not yet answered."""
    for response in attempt.responses:
        if response.answered_at is None:
            return response
    return None


# --------------------------------------------------------------------------- #
# Answering
# --------------------------------------------------------------------------- #


@dataclass
class AnswerOutcome:
    """What happened to one answer, and what comes next."""

    response: ItemResponse
    ability: irt.Ability
    next_item: ItemResponse | None
    finished: bool
    stop: irt.Stop


def answer(
    db: Session,
    *,
    attempt: QuizAttempt,
    question_id: int,
    selected_index: int | None,
    seconds_taken: float | None = None,
) -> AnswerOutcome:
    """Score one answer, move the estimate, and decide what to ask next.

    `selected_index` of None is a deliberate skip. It is scored as incorrect —
    the same rule the fixed-form quiz used, for the same reason: declining to
    answer a question pitched at your own estimated ability is a result, not an
    absence. It is recorded as a skip rather than a wrong answer so an officer
    reading their report can tell the two apart.
    """
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise QuizError("This attempt has already finished.")

    current = open_item(attempt)
    if current is None:
        raise QuizError("There is no question open on this attempt.")
    if current.question_id != question_id:
        # Almost always a double-submit or a stale tab. Naming the expected
        # question makes it recoverable instead of mysterious.
        raise QuizError(
            f"That is not the question currently open — this attempt is waiting "
            f"on question {current.question_id}."
        )

    question = current.question
    if question is None:
        raise QuizError("The question for this item is no longer available.")

    if selected_index is not None and not (
        0 <= selected_index < len(question.options or [])
    ):
        raise QuizError("That option does not exist on this question.")

    now = datetime.now(timezone.utc)
    current.selected_index = selected_index
    current.is_correct = (
        selected_index is not None and selected_index == question.correct_index
    )
    current.answered_at = now
    current.seconds_taken = seconds_taken

    # Item exposure statistics, which classical analysis and IRT calibration
    # both read later.
    question.times_attempted += 1
    if current.is_correct:
        question.times_correct += 1

    db.flush()

    ability = _ability(db, attempt)
    current.theta_after = ability.theta
    current.se_after = ability.se

    attempt.theta = ability.theta
    attempt.theta_se = ability.se
    attempt.item_count = len(_answered(attempt))
    attempt.correct_count = sum(1 for r in _answered(attempt) if r.is_correct)

    pool = _remaining(db, attempt)
    stop = irt.should_stop(
        asked=attempt.item_count,
        ability=ability,
        remaining=len(pool),
        informative_left=(
            _best_information(pool, ability.theta) >= irt.MIN_USEFUL_INFORMATION
        ),
    )

    next_item = None
    if stop.should_stop:
        _finish(db, attempt=attempt, ability=ability, stop=stop)
    else:
        next_item = _serve_next(db, attempt, ability, first=False, pool=pool)
        if next_item is None:
            # Belt and braces: selection declined even though the stop check
            # allowed it. Leaving the attempt open with no question would render
            # as a blank screen, so close it rather than trusting the two checks
            # to agree forever.
            stop = irt.Stop(
                True, "no_informative_items",
                "No remaining item for this competency would tell us anything "
                "further at your estimated level.",
            )
            _finish(db, attempt=attempt, ability=ability, stop=stop)

    db.flush()
    return AnswerOutcome(
        response=current,
        ability=ability,
        next_item=next_item,
        finished=attempt.status == AttemptStatus.SUBMITTED,
        stop=stop,
    )


def _finish(
    db: Session, *, attempt: QuizAttempt, ability: irt.Ability, stop: irt.Stop
) -> None:
    """Close the attempt and append the evidence it justifies."""
    now = datetime.now(timezone.utc)
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = now
    attempt.stop_reason = stop.reason
    attempt.derived_level = round(ability.level, 2)

    answered = _answered(attempt)
    # Kept for the existing reports, which show how hard the paper was. Under
    # IRT this is the mean difficulty of the items the officer was actually
    # steered to, which is a more interesting number than it was before: for a
    # well-adapted test it should land near their own ability.
    if answered:
        difficulties = [
            r.item_difficulty for r in answered if r.item_difficulty is not None
        ]
        if difficulties:
            attempt.mean_difficulty = round(
                irt.theta_to_level(sum(difficulties) / len(difficulties)), 2
            )

    # The confidence is the marginal reliability of the estimate — literally how
    # much of the population spread this test resolved. Every other source in the
    # platform has to argue for its confidence number; this one has a definition.
    confidence = round(ability.reliability, 3)

    if attempt.competency_id is not None:
        record_evidence(
            db,
            user_id=attempt.user_id,
            competency_id=attempt.competency_id,
            level_estimate=ability.level,
            source=EvidenceSource.QUIZ,
            confidence=confidence,
            source_ref=f"quiz_attempt:{attempt.id}",
            note=(
                f"Adaptive assessment, {attempt.item_count} items, "
                f"{attempt.correct_count} correct. "
                f"theta {ability.theta:+.2f} +/- {ability.se:.2f} "
                f"(95% CI L{ability.level_low:.1f}-L{ability.level_high:.1f})."
            ),
        )

    db.add(AuditLog(
        actor_user_id=attempt.user_id,
        action="quiz.submitted",
        entity_type="quiz_attempt",
        entity_id=str(attempt.id),
        meta={
            "competency_id": attempt.competency_id,
            "adaptive": True,
            "items": attempt.item_count,
            "correct": attempt.correct_count,
            "theta": ability.theta,
            "theta_se": ability.se,
            "derived_level": attempt.derived_level,
            "confidence": confidence,
            "stop_reason": stop.reason,
        },
    ))
    db.flush()


def abandon(db: Session, *, attempt: QuizAttempt) -> None:
    """Walk away without a result.

    No evidence is written. A half-finished test is a real measurement of
    something, but not of competency, and recording it would put a low level on
    the officer's record for having been interrupted.
    """
    if attempt.status == AttemptStatus.IN_PROGRESS:
        attempt.status = AttemptStatus.ABANDONED
        db.flush()


# --------------------------------------------------------------------------- #
# Reporting an attempt
# --------------------------------------------------------------------------- #


def ability_of(attempt: QuizAttempt) -> irt.Ability:
    """The attempt's estimate, rebuilt as an `Ability` for its interval."""
    theta = attempt.theta if attempt.theta is not None else irt.PRIOR_MEAN
    se = attempt.theta_se if attempt.theta_se is not None else irt.PRIOR_SD
    return irt.Ability(
        theta=theta,
        se=se,
        level=round(irt.theta_to_level(theta), 2),
        reliability=round(irt.marginal_reliability(se), 4),
    )


def trace(attempt: QuizAttempt) -> list[dict]:
    """The path the estimate took, item by item.

    This is the officer's explanation of what just happened to them, and it is
    also the best short answer to "what is adaptive testing" that the product
    contains: difficulty tracking ability, and the interval closing.
    """
    rows = []
    for response in attempt.responses:
        if response.answered_at is None:
            continue
        rows.append({
            "sequence": response.sequence,
            "question_id": response.question_id,
            "difficulty_level": (
                round(irt.theta_to_level(response.item_difficulty), 2)
                if response.item_difficulty is not None else None
            ),
            "difficulty_theta": response.item_difficulty,
            "is_correct": response.is_correct,
            "skipped": response.selected_index is None,
            "information": response.item_information,
            "theta_before": response.theta_before,
            "theta_after": response.theta_after,
            "se_after": response.se_after,
            "level_after": (
                round(irt.theta_to_level(response.theta_after), 2)
                if response.theta_after is not None else None
            ),
            "asked_because": response.asked_because,
        })
    return rows


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def calibrate(db: Session, *, dry_run: bool = False) -> dict:
    """Re-estimate item difficulty and discrimination from real responses.

    Every item ships with the difficulty its author intended. That is a
    necessary starting point — an uncalibrated bank cannot adapt at all — but it
    is a guess, and authors are reliably wrong in one direction: an expert who
    knows the answer cannot see what is hard about the question. This is the
    loop that fixes it, and it is the reason the platform keeps item responses
    at all.

    **Person abilities are taken as known.** Each response is paired with the
    ability estimated from the attempt it belonged to, and item parameters are
    fitted to those. This is the joint-estimation shortcut rather than marginal
    maximum likelihood, and it has a known cost: person estimates carry error,
    and treating them as exact biases discrimination slightly downward. Full
    MML with an EM loop would remove that, at the price of a numerical
    integration this codebase would then own forever. The bias is small next to
    the sampling error on a few hundred responses, and it is in the
    conservative direction — items look slightly less discriminating than they
    are, so nothing is over-trusted.

    Items below the response threshold keep the author's parameters and are
    reported as untouched, so a thin bank reads as thin rather than as
    calibrated.
    """
    attempts = db.scalars(
        select(QuizAttempt).where(
            QuizAttempt.status == AttemptStatus.SUBMITTED,
            QuizAttempt.theta.is_not(None),
        )
    ).all()
    if not attempts:
        return {
            "calibrated": 0, "skipped": 0, "changes": [],
            "min_responses": irt.MIN_RESPONSES_TO_CALIBRATE,
            "note": "No submitted attempts yet, so there is nothing to calibrate from.",
        }

    theta_by_attempt = {a.id: a.theta for a in attempts}
    responses = db.scalars(
        select(ItemResponse).where(
            ItemResponse.attempt_id.in_(list(theta_by_attempt)),
            ItemResponse.answered_at.is_not(None),
        )
    ).all()

    by_question: dict[int, list[tuple[float, bool]]] = {}
    for response in responses:
        theta = theta_by_attempt.get(response.attempt_id)
        if theta is None:
            continue
        by_question.setdefault(response.question_id, []).append(
            (theta, bool(response.is_correct))
        )

    calibrated = 0
    skipped = 0
    changes: list[dict] = []
    now = datetime.now(timezone.utc)

    for question_id, observations in by_question.items():
        question = db.get(GeneratedQuestion, question_id)
        if question is None:
            continue

        # Calibration is always measured against what the author intended, not
        # against the last calibration. Chaining would let an item drift a long
        # way from its authored difficulty one small shrinkage step at a time,
        # and the drift is the signal a reviewer needs.
        authored = irt.Item(
            id=question.id, a=irt.DEFAULT_DISCRIMINATION,
            b=question.irt_b_authored, c=question.irt_c,
        )
        result = irt.calibrate_item(authored, observations)
        if result is None:
            skipped += 1
            continue

        before_a, before_b = question.irt_a, question.irt_b
        if not dry_run:
            question.irt_a = result.a
            question.irt_b = result.b
            question.irt_sample_size = result.responses
            question.irt_calibrated_at = now

        calibrated += 1
        # Only report items that actually moved, or the output is a wall of
        # rows saying nothing changed.
        if abs(result.b - before_b) >= 0.15 or abs(result.a - before_a) >= 0.15:
            changes.append({
                "question_id": question.id,
                "stem": question.stem[:110],
                "competency_id": question.competency_id,
                "responses": result.responses,
                "authored_level": round(irt.theta_to_level(question.irt_b_authored), 2),
                "calibrated_level": round(irt.theta_to_level(result.b), 2),
                "b_before": round(before_b, 3),
                "b_after": result.b,
                "a_before": round(before_a, 3),
                "a_after": result.a,
                "drift": result.b_shift,
                "note": result.note,
            })

    if not dry_run:
        db.flush()

    changes.sort(key=lambda c: abs(c["drift"]), reverse=True)
    return {
        "calibrated": calibrated,
        "skipped": skipped,
        "changes": changes,
        "min_responses": irt.MIN_RESPONSES_TO_CALIBRATE,
        "dry_run": dry_run,
        "note": (
            f"Items with at least {irt.MIN_RESPONSES_TO_CALIBRATE} responses were "
            f"re-fitted against the author's stated difficulty. Items below that "
            f"keep what the author gave them — {skipped} of them here. A large "
            f"drift usually means a miskeyed item or a defensible second answer, "
            f"so these are surfaced for review rather than applied silently."
        ),
    }


def bank_health(db: Session) -> list[dict]:
    """Can each competency's bank actually measure anybody, and across what range?

    A bank can be large and still useless: twenty items all pitched at L3
    measure L3 precisely and everything else not at all. This reports the
    *information curve* per competency, which is the only honest answer to "is
    this assessment ready" — and it is the question an administrator asks before
    letting a division loose on it.
    """
    rows = db.execute(
        select(
            GeneratedQuestion.competency_id, GeneratedQuestion.id,
            GeneratedQuestion.irt_a, GeneratedQuestion.irt_b, GeneratedQuestion.irt_c,
            GeneratedQuestion.irt_calibrated_at,
        ).where(
            GeneratedQuestion.status == QuestionStatus.APPROVED,
            GeneratedQuestion.competency_id.is_not(None),
        )
    ).all()

    by_competency: dict[int, list[irt.Item]] = {}
    calibrated_count: dict[int, int] = {}
    for competency_id, qid, a, b, c, cal_at in rows:
        by_competency.setdefault(competency_id, []).append(
            irt.Item(id=qid, a=a, b=b, c=c)
        )
        if cal_at is not None:
            calibrated_count[competency_id] = calibrated_count.get(competency_id, 0) + 1

    out = []
    for competency_id, items in by_competency.items():
        competency = db.get(Competency, competency_id)
        # Sampled at the five FRAC levels, which is the axis everyone reads.
        curve = []
        for level in (1.0, 2.0, 3.0, 4.0, 5.0):
            theta = irt.level_to_theta(level)
            info = irt.test_information(items, theta)
            curve.append({
                "level": level,
                "information": round(info, 3),
                "se": round(irt.se_from_information(info), 3),
            })
        difficulties = sorted(item.b for item in items)
        out.append({
            "competency_id": competency_id,
            "competency_name": competency.name if competency else None,
            "competency_code": competency.code if competency else None,
            "items": len(items),
            "calibrated": calibrated_count.get(competency_id, 0),
            "adaptive_ready": len(items) >= MIN_POOL,
            "difficulty_range": {
                "lowest_level": round(irt.theta_to_level(difficulties[0]), 2),
                "highest_level": round(irt.theta_to_level(difficulties[-1]), 2),
            },
            "information_curve": curve,
            # Where the bank is thinnest, which is what to write next.
            "weakest_level": min(curve, key=lambda c: c["information"])["level"],
        })

    out.sort(key=lambda r: (not r["adaptive_ready"], -r["items"]))
    return out
