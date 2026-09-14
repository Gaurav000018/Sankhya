"""Load the hand-written MCQ bank as approved quiz items.

Quiz questions normally arrive through upload → generate → SME review, which
needs a model beside the API. Without one the bank is empty and the assessment
refuses to start — so a deployment with no GPU cannot demonstrate the feature
the platform is built around.

These are attached to a synthetic `Material` rather than to no material at all,
because the review queue, the citation trail and the question detail screen all
assume every item came from somewhere. Its title says plainly what it is, so
nobody mistakes it for an uploaded document.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competency, User, UserRole
from app.models_content import (
    GeneratedQuestion,
    Material,
    MaterialStatus,
    QuestionKind,
    QuestionStatus,
)
from app.seed.mcqs import BANK

MATERIAL_TITLE = "SANKHYA curated item bank (hand-written, pre-approved)"


def seed_quiz_bank(db: Session, competencies: dict[str, Competency]) -> int:
    """Insert every item in `mcqs.BANK`. Returns the number created.

    Idempotent on the material: re-running replaces the bank rather than
    doubling it, so a reseed does not leave two copies of every question in the
    pool and halve the chance of seeing any given one.
    """
    reviewer = db.scalar(select(User).where(User.role == UserRole.SME))

    existing = db.scalar(select(Material).where(Material.title == MATERIAL_TITLE))
    if existing is not None:
        for question in db.scalars(
            select(GeneratedQuestion).where(GeneratedQuestion.material_id == existing.id)
        ):
            db.delete(question)
        db.flush()
        material = existing
    else:
        material = Material(
            title=MATERIAL_TITLE,
            filename="curated-item-bank.md",
            content_type="text/markdown",
            status=MaterialStatus.READY,
            uploaded_by_id=reviewer.id if reviewer else None,
            char_count=sum(
                len(item[0]) for items in BANK.values() for item in items
            ),
        )
        db.add(material)
        db.flush()

    created = 0
    for code, items in BANK.items():
        competency = competencies.get(code)
        if competency is None:
            # A competency code in the bank that is not in the framework is a
            # typo worth failing loudly on, not silently skipping: the item
            # would be invisible to every quiz.
            raise KeyError(f"MCQ bank references unknown competency code {code!r}")

        for stem, options, correct_index, explanation, rationale, bloom in items:
            db.add(
                GeneratedQuestion(
                    material_id=material.id,
                    competency_id=competency.id,
                    kind=QuestionKind.MCQ,
                    stem=stem,
                    options=list(options),
                    correct_index=correct_index,
                    explanation=explanation,
                    distractor_rationale=list(rationale),
                    bloom_level=bloom,
                    # Approved on purpose: an author writing these deliberately is
                    # the review a generated item needs. The reviewer is recorded
                    # so the audit trail is not silently empty.
                    status=QuestionStatus.APPROVED,
                    reviewed_by_id=reviewer.id if reviewer else None,
                    review_note="Curated item, approved at seed time.",
                    citation_quote=None,
                    # Difficulty and discrimination are deliberately left unset.
                    # The IRT layer calibrates them from real responses; a
                    # guessed prior would pollute exactly the estimate the
                    # feedback loop exists to produce.
                )
            )
            created += 1

    db.flush()
    return created
