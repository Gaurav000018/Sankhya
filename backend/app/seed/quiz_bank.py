"""Load the hand-written MCQ bank as approved, IRT-parameterised quiz items.

Quiz questions normally arrive through upload → generate → SME review, which
needs a model beside the API. Without one the bank is empty and the assessment
refuses to start — so a deployment with no GPU cannot demonstrate the feature
the platform is built around.

These are attached to a synthetic `Material` rather than to no material at all,
because the review queue, the citation trail and the question detail screen all
assume every item came from somewhere. Its title says plainly what it is, so
nobody mistakes it for an uploaded document.

Two things happen here that are not simply inserting rows.

**Every item gets an IRT difficulty.** An adaptive test selects on `irt_b`, so
an item without one is unservable in practice — it would sit at exactly L3 with
every other unparameterised item and the engine could not tell them apart.
`mcqs_extended` states its difficulty explicitly; `mcqs` predates the ability
scale and takes its difficulty from the Bloom level its author did give.

**Options are shuffled.** Not cosmetics — a correctness fix. Written as
authored, 98% of the extended bank had its key at position B and 66% of the
original did, because an author writing a plausible distractor first and the
right answer second is following the shape of the explanation in their head.
A candidate who noticed would outscore one who knew the material. The shuffle is
seeded from the stem, so it is stable across reseeds — an item does not silently
change shape under a reviewer who has already read it — and rationales move with
their options, since `distractor_rationale[i]` explains `options[i]`.
"""

from __future__ import annotations

import hashlib
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import irt
from app.models import Competency, User, UserRole
from app.models_content import (
    GeneratedQuestion,
    Material,
    MaterialStatus,
    QuestionKind,
    QuestionStatus,
)
from app.seed.mcqs import BANK
from app.seed.mcqs_extended import EXTENDED, FOUNDATION
from app.services.quiz import BLOOM_DIFFICULTY

MATERIAL_TITLE = "SANKHYA curated item bank (hand-written, pre-approved)"

# Discrimination assumed for a curated item before anyone has answered it.
#
# Slightly above the neutral 1.0 because these items are written deliberately,
# with distractors built from real misconceptions rather than from noise, and
# such items normally do separate stronger candidates from weaker ones a little
# better than average. It is still an assumption, and a generous one — which is
# why `irt.calibrate_item` centres its prior on 1.0 rather than here. Calibration
# should have to be *persuaded* that an item discriminates well.
AUTHORED_DISCRIMINATION = 1.3


def _shuffled(stem: str, options: list[str], correct_index: int, rationales: list[str]):
    """Reorder the options deterministically, carrying the key and rationales.

    Seeded from a hash of the stem rather than from `random` so the same item
    lands the same way on every reseed, and so two deployments of the same
    version agree. `hash()` would not do: Python randomises string hashing per
    process, so the bank would reshuffle on every restart.
    """
    order = list(range(len(options)))
    random.Random(
        int(hashlib.sha256(stem.encode("utf-8")).hexdigest()[:8], 16)
    ).shuffle(order)

    return (
        [options[i] for i in order],
        order.index(correct_index),
        [rationales[i] for i in order] if rationales else rationales,
    )


def _normalise(code: str) -> list[tuple]:
    """Both authoring formats as one list of (stem, options, key, expl, rats, bloom, level).

    `mcqs` tuples carry six fields and no difficulty; theirs comes from the Bloom
    level, which is the only statement about cognitive demand those items make.
    `mcqs_extended` tuples carry a seventh field with the author's explicit
    estimate, which is what lets that half of the bank cover the ability range
    smoothly instead of clumping on five Bloom values.
    """
    items: list[tuple] = []
    for item in BANK.get(code, []):
        stem, options, key, explanation, rationales, bloom = item
        level = BLOOM_DIFFICULTY.get((bloom or "").lower(), 3.0)
        items.append((stem, options, key, explanation, rationales, bloom, level))
    for item in EXTENDED.get(code, []):
        items.append(item)
    # The L1-L2 band, added after `/item-bank/health` showed the bank could not
    # resolve an officer at the bottom of the scale.
    for item in FOUNDATION.get(code, []):
        items.append(item)
    return items


def seed_quiz_bank(db: Session, competencies: dict[str, Competency]) -> int:
    """Insert every curated item. Returns the number created.

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
        )
        db.add(material)
        db.flush()

    codes = sorted(set(BANK) | set(EXTENDED) | set(FOUNDATION))
    created = 0
    char_count = 0

    for code in codes:
        competency = competencies.get(code)
        if competency is None:
            # A competency code in the bank that is not in the framework is a
            # typo worth failing loudly on, not silently skipping: the item
            # would be invisible to every quiz.
            raise KeyError(f"MCQ bank references unknown competency code {code!r}")

        for stem, options, key, explanation, rationales, bloom, level in _normalise(code):
            options, key, rationales = _shuffled(stem, list(options), key, list(rationales))
            difficulty = irt.level_to_theta(level)
            char_count += len(stem)

            db.add(
                GeneratedQuestion(
                    material_id=material.id,
                    competency_id=competency.id,
                    kind=QuestionKind.MCQ,
                    stem=stem,
                    options=options,
                    correct_index=key,
                    explanation=explanation,
                    distractor_rationale=rationales,
                    bloom_level=bloom,
                    # Approved on purpose: an author writing these deliberately is
                    # the review a generated item needs. The reviewer is recorded
                    # so the audit trail is not silently empty.
                    status=QuestionStatus.APPROVED,
                    reviewed_by_id=reviewer.id if reviewer else None,
                    review_note="Curated item, approved at seed time.",
                    citation_quote=None,
                    # `irt_b` is what the adaptive engine selects on; the authored
                    # copy beside it never moves, so the gap between the two after
                    # calibration measures how far the author's judgement was out.
                    irt_b=difficulty,
                    irt_b_authored=difficulty,
                    irt_a=AUTHORED_DISCRIMINATION,
                    irt_c=1.0 / len(options) if options else 0.25,
                )
            )
            created += 1

    material.char_count = char_count
    db.flush()
    return created
