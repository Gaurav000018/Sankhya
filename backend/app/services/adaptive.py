"""Decide what to ask next.

A fixed questionnaire spends most of an interview confirming what the Skill Twin
already knows. This picks each question from what just happened instead:

* answered well      -> push harder in the same competency
* missed something   -> probe that specific gap
* struggled          -> step back to the foundation it rests on
* competency settled -> move to the next widest gap

Two rules keep it honest.

**It always has somewhere to go.** Every decision falls back to the SME-approved
bank, so a model that is slow, absent or returns nonsense produces a fixed
interview rather than a broken one.

**It says why.** Every question carries `asked_because` in the officer's own
report. An interview that changes direction without explaining itself is a
black box, and this one is meant to be a coaching tool the officer can argue
with.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.followup import FollowUp, get_followup_writer
from app.models import Competency, User
from app.models_interview import (
    Interview,
    InterviewAnswer,
    InterviewQuestion,
)
from app.services.competency import analyse_gaps

log = logging.getLogger("sankhya.adaptive")

# Knowledge thresholds on the 1-5 axis.
STRONG_ANSWER = 4.0
WEAK_ANSWER = 2.0

# Below this the judge is not sure enough about its own Knowledge score to steer
# the interview on it. Adapting on a guess produces a conversation that lurches.
MIN_CONFIDENCE_TO_ADAPT = 0.35

# How many questions one competency may take before moving on, however the
# officer is doing. Without this a single weak area consumes the whole session
# and the report covers one competency out of twelve.
MAX_PER_COMPETENCY = 3

# Evidence from a question no subject-matter expert has approved is worth less.
# It still counts — the officer answered a real question about a real
# competency — but it should not outweigh a reviewed one.
GENERATED_CONFIDENCE_FACTOR = 0.75


@dataclass
class NextQuestion:
    """What to ask, and why."""

    question: InterviewQuestion
    asked_because: str
    intent: str                  # "open" | "probe" | "extend" | "ground" | "move_on"
    is_generated: bool = False


@dataclass
class InterviewPlan:
    """Where the session has got to."""

    asked: int
    competencies_touched: dict[int, int]
    last_answer: InterviewAnswer | None


def _plan(db: Session, interview: Interview) -> InterviewPlan:
    answers = db.scalars(
        select(InterviewAnswer)
        .where(InterviewAnswer.interview_id == interview.id)
        .order_by(InterviewAnswer.sequence)
    ).all()

    touched: dict[int, int] = {}
    scored: list[InterviewAnswer] = []
    for answer in answers:
        question = answer.question
        if question is None or question.is_baseline:
            continue
        if question.competency_id is not None:
            touched[question.competency_id] = touched.get(question.competency_id, 0) + 1
        if answer.score is not None:
            scored.append(answer)

    return InterviewPlan(
        asked=sum(touched.values()),
        competencies_touched=touched,
        last_answer=scored[-1] if scored else None,
    )


def _classify(answer: InterviewAnswer) -> str:
    """What the last answer tells us to do next.

    Returns the *intent*, not the question. Kept separate from question
    selection so the decision can be tested without a database.
    """
    score = answer.score
    if score is None:
        return "open"

    # A degraded verdict carries confidence 0. Steering the interview on output
    # the judge itself could not parse would compound one failure into a whole
    # session of misdirected questions.
    if score.knowledge_confidence < MIN_CONFIDENCE_TO_ADAPT:
        return "move_on"

    if score.knowledge >= STRONG_ANSWER:
        return "extend"
    if score.knowledge <= WEAK_ANSWER:
        return "ground"
    if score.missed_points:
        return "probe"
    return "move_on"


RATIONALES = {
    "open": "Opening question for the competency with the widest gap against your target role.",
    "extend": "You covered that well, so this one pushes further into the same competency.",
    "ground": "This steps back to the idea the last question rests on, so the next attempt has something to build from.",
    "probe": "This returns to a point the last answer did not reach.",
    "move_on": "Moving to the next competency where your evidence is thinnest.",
}


def _bank_question(
    db: Session, *, competency_id: int | None, exclude: set[int],
    harder_than: float | None = None, easier_than: float | None = None,
) -> InterviewQuestion | None:
    """A question from the approved bank, optionally by difficulty."""
    stmt = select(InterviewQuestion).where(
        InterviewQuestion.is_active.is_(True),
        InterviewQuestion.is_baseline.is_(False),
        InterviewQuestion.is_generated.is_(False),
    )
    if competency_id is not None:
        stmt = stmt.where(InterviewQuestion.competency_id == competency_id)
    if harder_than is not None:
        stmt = stmt.where(InterviewQuestion.difficulty > harder_than)
        stmt = stmt.order_by(InterviewQuestion.difficulty.asc())
    elif easier_than is not None:
        stmt = stmt.where(InterviewQuestion.difficulty < easier_than)
        stmt = stmt.order_by(InterviewQuestion.difficulty.desc())

    for question in db.scalars(stmt.limit(12)).all():
        if question.id not in exclude:
            return question
    return None


def _ranked_gaps(db: Session, *, user: User, target_role_id: int | None):
    gaps = analyse_gaps(db, user=user, target_role_id=target_role_id)
    open_gaps = [g for g in gaps if g.is_gap]
    return open_gaps or gaps


def _asked_question_ids(db: Session, interview: Interview) -> set[int]:
    return {
        row for row in db.scalars(
            select(InterviewAnswer.question_id)
            .where(InterviewAnswer.interview_id == interview.id)
        ).all()
    }


def decide_next(
    db: Session, *, interview: Interview, max_questions: int = 8,
) -> NextQuestion | None:
    """The next question, or None when the interview should end.

    Ending is a real outcome: the bank runs out, the officer has covered enough
    ground, or every competency has had its turn. Returning a repeat question to
    keep the session going would produce evidence about nothing.
    """
    plan = _plan(db, interview)
    if plan.asked >= max_questions:
        return None

    asked_ids = _asked_question_ids(db, interview)
    gaps = _ranked_gaps(db, user=interview.user, target_role_id=interview.target_role_id)
    intent = _classify(plan.last_answer) if plan.last_answer else "open"

    last_question = plan.last_answer.question if plan.last_answer else None
    current_competency = last_question.competency_id if last_question else None

    # A competency that has had its turn is retired even when the officer is
    # still struggling with it, so one weak area cannot eat the session.
    if (
        current_competency is not None
        and plan.competencies_touched.get(current_competency, 0) >= MAX_PER_COMPETENCY
    ):
        intent = "move_on"

    if intent == "move_on" or current_competency is None:
        return _open_next_competency(db, gaps=gaps, plan=plan, exclude=asked_ids)

    # Still on this competency: try the model first, fall back to the bank.
    generated = _generate_followup(
        db, interview=interview, answer=plan.last_answer, intent=intent,
        competency_id=current_competency,
    )
    if generated is not None:
        return generated

    return _bank_followup(
        db, intent=intent, competency_id=current_competency,
        last_question=last_question, exclude=asked_ids, gaps=gaps, plan=plan,
    )


def _open_next_competency(db: Session, *, gaps, plan: InterviewPlan, exclude: set[int]):
    """Move to the widest gap that has not had its turn."""
    for gap in gaps:
        if plan.competencies_touched.get(gap.competency_id, 0) >= MAX_PER_COMPETENCY:
            continue
        question = _bank_question(db, competency_id=gap.competency_id, exclude=exclude)
        if question is not None:
            first_time = gap.competency_id not in plan.competencies_touched
            because = (
                f"{gap.competency_name} is the widest gap against your target role "
                f"— you are assessed at L{gap.current_level:.1f} against L"
                f"{gap.required_level:.1f}."
                if first_time
                else f"Returning to {gap.competency_name} from a different angle."
            )
            return NextQuestion(
                question=question, asked_because=because,
                intent="open" if first_time else "move_on",
            )

    # Nothing left in the officer's gaps: take anything unasked rather than
    # ending abruptly, but say that is what happened.
    question = _bank_question(db, competency_id=None, exclude=exclude)
    if question is None:
        return None
    return NextQuestion(
        question=question, intent="open",
        asked_because="Your gap competencies have all been covered, so this one "
                      "samples more broadly.",
    )


def _bank_followup(
    db: Session, *, intent: str, competency_id: int, last_question, exclude, gaps, plan
):
    """Adapt using the approved bank when no model wrote a follow-up.

    Difficulty is the only lever the bank offers, which is a weaker form of
    adaptation than a written follow-up but is still adaptation: a strong answer
    gets a harder question in the same competency, a weak one an easier.
    """
    difficulty = last_question.difficulty if last_question else 3.0
    question = None

    if intent == "extend":
        question = _bank_question(
            db, competency_id=competency_id, exclude=exclude, harder_than=difficulty
        )
    elif intent == "ground":
        question = _bank_question(
            db, competency_id=competency_id, exclude=exclude, easier_than=difficulty
        )
    else:
        question = _bank_question(db, competency_id=competency_id, exclude=exclude)

    if question is None:
        # The bank has nothing left at the right level for this competency.
        return _open_next_competency(db, gaps=gaps, plan=plan, exclude=exclude)

    return NextQuestion(
        question=question, intent=intent, asked_because=RATIONALES[intent],
    )


def _generate_followup(
    db: Session, *, interview: Interview, answer: InterviewAnswer, intent: str,
    competency_id: int,
) -> NextQuestion | None:
    """Ask the model for a follow-up and persist it as a question row.

    Persisted rather than held in memory because the officer's report has to
    show what they were actually asked, and because an answer needs a
    `question_id` to point at.
    """
    transcript = (answer.transcript or "").strip()
    if not transcript:
        return None

    competency = db.get(Competency, competency_id)
    score = answer.score
    writer = get_followup_writer()

    follow_up: FollowUp | None = writer.write(
        competency=competency.name if competency else "this competency",
        previous_question=answer.question.prompt if answer.question else "",
        transcript=transcript,
        missed_points=list((score.missed_points or []) if score else []),
        covered_points=list((score.covered_points or []) if score else []),
        intent=intent,
    )
    if follow_up is None:
        return None

    if not _is_on_topic(follow_up.prompt, competency):
        # The model followed the officer's answer rather than the competency.
        # That is easy to do when someone drifts off-topic, and the consequence
        # is not cosmetic: the answer to this question would be filed as
        # evidence for a competency it does not measure. Fall back to the bank,
        # where a human decided what each question is about.
        log.info(
            "Discarded a follow-up as off-topic for %s: %r",
            competency.name if competency else competency_id, follow_up.prompt[:80],
        )
        return None

    question = InterviewQuestion(
        competency_id=competency_id,
        frac_role_id=interview.target_role_id,
        prompt=follow_up.prompt,
        expected_points=follow_up.expected_points or None,
        bloom_level="analyse" if intent == "extend" else "understand",
        difficulty=_difficulty_for(answer, intent),
        language=interview.language,
        is_baseline=False,
        is_active=True,
        is_generated=True,
        generated_from_answer_id=answer.id,
    )
    db.add(question)
    db.flush()

    because = follow_up.rationale or RATIONALES[intent]
    return NextQuestion(
        question=question, asked_because=because, intent=intent, is_generated=True,
    )


def _difficulty_for(answer: InterviewAnswer, intent: str) -> float:
    base = answer.question.difficulty if answer.question else 3.0
    if intent == "extend":
        return min(5.0, base + 0.5)
    if intent == "ground":
        return max(1.0, base - 0.7)
    return base


def evidence_confidence(question: InterviewQuestion, judged_confidence: float) -> float:
    """How much the evidence from this question should weigh.

    A generated question is discounted: it measured something real, but no SME
    has agreed that it measures the competency it is filed under. The discount
    is applied here rather than inside the judge so that the judge's own
    certainty and the question's provenance stay separate numbers.
    """
    if question is not None and question.is_generated:
        return round(judged_confidence * GENERATED_CONFIDENCE_FACTOR, 4)
    return judged_confidence


def _is_on_topic(prompt: str, competency: Competency | None) -> bool:
    """Is this generated question actually about the competency it is filed under?

    The model is told to stay on the competency and mostly does, but when the
    officer's answer wanders the model follows the answer — it was given both,
    and the transcript is the more vivid of the two. A question about Neyman
    allocation filed under Team Leadership then produces evidence for the wrong
    competency, which is worse than asking nothing.

    Reuses the recommender's threshold rather than inventing a second one: it is
    the same question — is this text about that competency — measured with the
    same embedder, so it should have the same answer.
    """
    if competency is None:
        return True

    from app.ml.embeddings import cosine, get_embedder

    embedder = get_embedder()
    if not getattr(embedder, "is_semantic", False):
        # A lexical embedder cannot tell a paraphrase from a different subject,
        # and refusing every follow-up on a machine with no embedding model
        # would turn adaptation off for the wrong reason.
        return True

    try:
        similarity = cosine(
            embedder.embed(prompt),
            embedder.embed(f"{competency.name}. {competency.description or ''}"),
        )
    except Exception:
        # An embedding failure must not silently stop the interview adapting.
        log.warning("Could not check follow-up topicality; allowing it", exc_info=True)
        return True

    return similarity >= embedder.relevance_floor
