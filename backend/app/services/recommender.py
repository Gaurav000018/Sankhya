"""Hybrid course recommendation with stated reasoning.

Four signals, combined and — crucially — kept separately so the explanation can
name them:

* **relevance**  does this course address the competency that is short?
* **level fit**  does its band actually cover the officer's current level and
  move toward the requirement? A foundation course cannot take someone from L3
  to L4, and recommending it for that is how a recommender loses trust.
* **urgency**    how wide is the gap, and how critical is that competency to
  the role.
* **peers**      how many officers in the same role completed it.

Every recommendation records the gap as it stood when produced. Recomputing the
explanation later would make it drift once the officer's level moves; the reason
should still make sense in six months.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ml.embeddings import cosine, get_embedder
from app.models import Competency, Criticality, EvidenceSource, User
from app.models_learning import (
    Course,
    CourseCompletion,
    CoursePrerequisite,
    LearningPath,
    PathItem,
    PathItemStatus,
    Recommendation,
)
from app.services.competency import GapItem, analyse_gaps, record_evidence

log = logging.getLogger("sankhya.recommender")

WEIGHT_RELEVANCE = 0.40
WEIGHT_LEVEL_FIT = 0.25
WEIGHT_URGENCY = 0.20
WEIGHT_PEERS = 0.15

CRITICALITY_WEIGHT = {
    Criticality.CRITICAL.value: 1.0,
    Criticality.HIGH.value: 0.75,
    Criticality.MEDIUM.value: 0.5,
    Criticality.LOW.value: 0.25,
}

# A course below this is not worth an officer's time in this context.
MIN_SCORE = 0.15
# Study time assumed per week when estimating duration.
HOURS_PER_WEEK = 3.0


@dataclass
class Scored:
    course: Course
    gap: GapItem
    score: float
    signals: dict = field(default_factory=dict)
    reason: str = ""


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #

def level_fit(course: Course, current: float, required: float) -> float:
    """How much of the officer's gap this course's band actually covers.

    A course that starts well above the officer's level leaves them stranded; one
    that ends below the requirement cannot finish the job. Both are penalised
    rather than being treated as equally relevant.
    """
    if required <= current:
        return 0.0

    overlap = min(course.level_to, required) - max(course.level_from, current)
    if overlap <= 0:
        return 0.0

    coverage = overlap / (required - current)

    # Starting materially above where the officer is now is a real problem, not
    # a rounding detail.
    entry_penalty = 1.0
    if course.level_from > current + 0.5:
        entry_penalty = max(0.3, 1.0 - (course.level_from - current - 0.5) * 0.4)

    return round(min(1.0, coverage) * entry_penalty, 4)


def urgency(gap: GapItem) -> float:
    """Gap width scaled by how critical the competency is to the role."""
    width = min(gap.gap / 3.0, 1.0)
    return round(width * CRITICALITY_WEIGHT.get(gap.criticality, 0.5), 4)


def peer_signal(db: Session, course: Course, user: User) -> tuple[float, int]:
    """Share of officers in the same FRAC role who completed this course."""
    if user.frac_role_id is None:
        return 0.0, 0

    peers = db.scalar(
        select(func.count(User.id)).where(
            User.frac_role_id == user.frac_role_id,
            User.is_active.is_(True),
            User.id != user.id,
        )
    ) or 0
    if peers == 0:
        return 0.0, 0

    completions = db.scalar(
        select(func.count(CourseCompletion.id))
        .join(User, User.id == CourseCompletion.user_id)
        .where(
            CourseCompletion.course_id == course.id,
            User.frac_role_id == user.frac_role_id,
            User.id != user.id,
        )
    ) or 0

    return round(completions / peers, 4), completions


def relevance(course: Course, competency: Competency, gap_embedding: list[float] | None) -> float:
    """Direct competency match, else lexical or semantic similarity."""
    if course.competency_id == competency.id:
        return 1.0
    similarity = cosine(course.embedding, gap_embedding)
    # Cosine can be negative; anything below zero is simply unrelated.
    return round(max(0.0, similarity), 4)


# --------------------------------------------------------------------------- #
# Explanation
# --------------------------------------------------------------------------- #

def build_reason(scored: Scored, role_name: str | None, peer_count: int) -> str:
    """A sentence an officer can argue with.

    Only claims things that are true of the stored numbers — no invented peer
    percentages, no confident language about a weak signal.
    """
    gap = scored.gap
    course = scored.course
    parts = [
        f"Closes {gap.competency_name}, where you are assessed at L{gap.current_level} "
        f"and {role_name or 'your role'} requires L{gap.required_level}."
    ]

    if scored.signals.get("level_fit", 0) >= 0.6:
        parts.append(
            f"It covers L{course.level_from:g} to L{course.level_to:g}, which is the "
            f"band your gap sits in."
        )
    elif course.level_from > gap.current_level + 0.5:
        parts.append(
            f"It starts at L{course.level_from:g}, above your current level — take it "
            f"after the earlier course in this path."
        )
    else:
        parts.append(
            f"It covers L{course.level_from:g} to L{course.level_to:g}, so it closes "
            f"part of the gap."
        )

    if gap.criticality == Criticality.CRITICAL.value:
        parts.append("This competency is marked critical for your role.")

    if peer_count >= 3:
        share = round(100 * scored.signals.get("peers", 0))
        parts.append(
            f"{peer_count} other officers in your role have completed it "
            f"({share}% of that cohort)."
        )

    if gap.evidence_count and gap.strongest_source:
        source = gap.strongest_source.replace("_", " ")
        parts.append(
            f"Your level here rests on {gap.evidence_count} evidence records, "
            f"strongest from {source}."
        )

    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Recommending
# --------------------------------------------------------------------------- #

def score_courses(
    db: Session, *, user: User, gap: GapItem, limit: int = 3
) -> list[Scored]:
    competency = db.get(Competency, gap.competency_id)
    if competency is None:
        return []

    completed = {
        row[0] for row in db.execute(
            select(CourseCompletion.course_id).where(CourseCompletion.user_id == user.id)
        ).all()
    }

    embedder = get_embedder()
    gap_text = f"{competency.name}. {competency.description or ''}"
    gap_embedding = embedder.embed(gap_text)

    candidates = db.scalars(
        select(Course).where(Course.is_active.is_(True))
    ).all()

    scored: list[Scored] = []
    for course in candidates:
        if course.id in completed:
            continue

        rel = relevance(course, competency, gap_embedding)
        # The floor comes from the embedder because the scale does. A fixed 0.2
        # was right for the lexical embedder and admitted the entire catalogue
        # once a trained model replaced it — every unrelated pair scored above
        # it, so officers were shown a QGIS course against a leadership gap.
        if rel < embedder.relevance_floor:
            continue

        fit = level_fit(course, gap.current_level, gap.required_level)
        if fit <= 0:
            # No overlap with the gap: either the officer is already past this
            # course, or it starts above the requirement. Relevance alone was
            # enough to clear the threshold and put it in the list — which is
            # precisely how a recommender stops being believed.
            continue

        urg = urgency(gap)
        peers, peer_count = peer_signal(db, course, user)

        total = (
            WEIGHT_RELEVANCE * rel
            + WEIGHT_LEVEL_FIT * fit
            + WEIGHT_URGENCY * urg
            + WEIGHT_PEERS * peers
        )
        if total < MIN_SCORE:
            continue

        item = Scored(
            course=course, gap=gap, score=round(total, 4),
            signals={
                "relevance": rel, "level_fit": fit, "urgency": urg,
                "peers": peers, "peer_count": peer_count,
                "embedder": embedder.name, "semantic": embedder.is_semantic,
            },
        )
        item.reason = build_reason(
            item, user.frac_role.name if user.frac_role else None, peer_count
        )
        scored.append(item)

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


def recommend(
    db: Session, *, user: User, target_role_id: int | None = None,
    max_gaps: int = 5, per_gap: int = 3,
) -> list[Recommendation]:
    """Refresh this officer's recommendations.

    Previous recommendations are replaced: they describe a gap profile that has
    since changed, and keeping them would show an officer advice based on numbers
    that no longer hold.
    """
    gaps = [g for g in analyse_gaps(db, user=user, target_role_id=target_role_id) if g.is_gap]
    db.execute(delete(Recommendation).where(Recommendation.user_id == user.id))

    produced: list[Recommendation] = []
    for gap in gaps[:max_gaps]:
        for item in score_courses(db, user=user, gap=gap, limit=per_gap):
            recommendation = Recommendation(
                user_id=user.id,
                course_id=item.course.id,
                competency_id=gap.competency_id,
                target_role_id=target_role_id,
                current_level=gap.current_level,
                required_level=gap.required_level,
                score=item.score,
                signals=item.signals,
                reason=item.reason,
            )
            db.add(recommendation)
            produced.append(recommendation)

    db.flush()
    return produced


# --------------------------------------------------------------------------- #
# Learning paths
# --------------------------------------------------------------------------- #

def _prerequisite_closure(db: Session, course: Course, completed: set[int]) -> list[Course]:
    """Every unmet prerequisite, in an order that satisfies the graph.

    Depth-first with a visiting set, so a cycle in the catalogue produces a
    shorter path rather than infinite recursion.
    """
    ordered: list[Course] = []
    seen: set[int] = set()
    visiting: set[int] = set()

    def visit(node: Course) -> None:
        if node.id in seen or node.id in completed:
            return
        if node.id in visiting:
            log.warning("Prerequisite cycle at course %s; truncating the path", node.id)
            return
        visiting.add(node.id)

        edges = db.scalars(
            select(CoursePrerequisite).where(CoursePrerequisite.course_id == node.id)
        ).all()
        for edge in edges:
            required = db.get(Course, edge.requires_id)
            if required is not None:
                visit(required)

        visiting.discard(node.id)
        seen.add(node.id)
        ordered.append(node)

    visit(course)
    return ordered


def build_path(
    db: Session, *, user: User, competency_id: int, target_role_id: int | None = None
) -> LearningPath | None:
    """Build an ordered path closing one competency gap."""
    gaps = [
        g for g in analyse_gaps(db, user=user, target_role_id=target_role_id)
        if g.competency_id == competency_id
    ]
    if not gaps or not gaps[0].is_gap:
        return None
    gap = gaps[0]

    candidates = score_courses(db, user=user, gap=gap, limit=1)
    if not candidates:
        return None
    destination = candidates[0]

    completed = {
        row[0] for row in db.execute(
            select(CourseCompletion.course_id).where(CourseCompletion.user_id == user.id)
        ).all()
    }
    sequence = _prerequisite_closure(db, destination.course, completed)

    # Why each course is in the path. A step chosen on its own merits is not the
    # same as one dragged in to unlock a later step, and labelling them the same
    # way tells the officer something untrue.
    included_because: dict[int, str | None] = {
        c.id: (None if c.id == destination.course.id
               else f"Prerequisite for {destination.course.title}")
        for c in sequence
    }

    # The best single course rarely spans the whole gap. Keep going forward
    # until the sequence reaches the required level, otherwise the path promises
    # L4.0 and quietly stops at L3.8.
    reached = max((c.level_to for c in sequence), default=gap.current_level)
    chosen = {c.id for c in sequence}

    while reached < gap.required_level:
        follow_on = [
            c for c in db.scalars(
                select(Course).where(
                    Course.is_active.is_(True),
                    Course.competency_id == competency_id,
                    Course.level_to > reached,
                )
            ).all()
            if c.id not in chosen
            and c.id not in completed
            # Reachable from where the sequence has got to, not a leap.
            and c.level_from <= reached + 0.5
        ]
        if not follow_on:
            break

        # Prefer the course that advances furthest per hour of study.
        follow_on.sort(
            key=lambda c: (c.level_to - reached) / max(c.duration_hours, 0.5), reverse=True
        )
        nxt = follow_on[0]
        for course in _prerequisite_closure(db, nxt, completed | chosen):
            if course.id not in chosen:
                sequence.append(course)
                chosen.add(course.id)
                included_because[course.id] = (
                    None if course.id == nxt.id
                    else f"Prerequisite for {nxt.title}"
                )
        reached = max(reached, nxt.level_to)

    db.execute(
        delete(LearningPath).where(
            LearningPath.user_id == user.id, LearningPath.competency_id == competency_id
        )
    )

    total_hours = sum(c.duration_hours for c in sequence)
    reason = destination.reason
    if reached < gap.required_level:
        # Say so rather than letting the header imply the gap is closed.
        reason += (
            f" The catalogue currently reaches L{reached:g} on this competency, "
            f"short of the L{gap.required_level:g} the role requires."
        )

    path = LearningPath(
        user_id=user.id,
        competency_id=competency_id,
        target_role_id=target_role_id,
        current_level=gap.current_level,
        target_level=gap.required_level,
        reaches_level=round(reached, 2),
        total_hours=round(total_hours, 1),
        estimated_weeks=max(1, round(total_hours / HOURS_PER_WEEK)),
        reason=reason,
    )
    db.add(path)
    db.flush()

    for index, course in enumerate(sequence):
        db.add(PathItem(
            path_id=path.id,
            course_id=course.id,
            sequence=index,
            # Only the first step is open; the rest unlock as prerequisites clear.
            status=PathItemStatus.AVAILABLE if index == 0 else PathItemStatus.LOCKED,
            included_because=included_because.get(course.id),
        ))

    db.flush()
    return path


# --------------------------------------------------------------------------- #
# Completion
# --------------------------------------------------------------------------- #

def record_completion(
    db: Session, *, user: User, course: Course, actor_id: int | None = None
) -> CourseCompletion:
    """Register a completion and write the (low-weight) evidence it justifies.

    Completing a course is weak evidence of competence — it records attendance.
    It is written at LEARNING_ACTIVITY weight and capped at the course's own
    ceiling, so finishing a foundation course cannot claim an advanced level.
    """
    existing = db.scalar(
        select(CourseCompletion).where(
            CourseCompletion.user_id == user.id, CourseCompletion.course_id == course.id
        )
    )
    if existing is not None:
        return existing

    from app.models import CompetencyProfile

    profile = db.scalar(
        select(CompetencyProfile).where(
            CompetencyProfile.user_id == user.id,
            CompetencyProfile.competency_id == course.competency_id,
        )
    )
    level_now = profile.level if profile else 1.0

    completion = CourseCompletion(
        user_id=user.id, course_id=course.id, level_at_completion=level_now,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(completion)

    if course.competency_id is not None:
        record_evidence(
            db,
            user_id=user.id,
            competency_id=course.competency_id,
            # Never above what this course actually teaches.
            level_estimate=min(course.level_to, level_now + course.level_gain * 0.5),
            source=EvidenceSource.LEARNING_ACTIVITY,
            confidence=0.7,
            source_ref=f"course:{course.id}",
            note=f"Completed {course.title}",
            recorded_by_id=actor_id,
        )

    db.flush()
    return completion


def embed_catalogue(db: Session) -> int:
    """Populate course embeddings so similarity works beyond exact matches."""
    embedder = get_embedder()
    courses = db.scalars(select(Course).where(Course.is_active.is_(True))).all()
    for course in courses:
        course.embedding = embedder.embed(f"{course.title}. {course.description}")
    db.flush()
    log.info("Embedded %d courses using %s", len(courses), embedder.name)
    return len(courses)
