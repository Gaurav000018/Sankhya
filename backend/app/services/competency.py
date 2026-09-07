"""Digital Skill Twin — derivation of competency levels from evidence.

This module is the only place that writes evidence and the only place that
computes a level. Two rules hold everywhere else in the codebase:

1. Feature code never writes to `competency_profile`. It appends evidence and
   the profile is recomputed.
2. Not every assessment signal is evidence. The AI interview's Fluency and
   Confidence axes describe *communication delivery*, not competency, and are
   deliberately excluded — see `record_interview_evidence`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Competency,
    CompetencyProfile,
    Criticality,
    EvidenceSource,
    ProficiencyEvidence,
    RoleCompetencyRequirement,
    User,
)

# --------------------------------------------------------------------------- #
# Reliability model
# --------------------------------------------------------------------------- #

# How much each kind of evidence is trusted. Demonstrated performance on a real
# task outranks everything; self-assessment counts for very little. These weights
# are published in the UI — an officer can always see why their level is what it
# is, and a reviewer can argue with the weighting rather than with a black box.
SOURCE_WEIGHTS: dict[EvidenceSource, float] = {
    EvidenceSource.SIMULATION: 1.00,        # did the thing, on real data
    EvidenceSource.QUIZ: 0.85,
    EvidenceSource.DIAGNOSTIC: 0.80,
    EvidenceSource.INTERVIEW: 0.70,         # Knowledge axis only
    EvidenceSource.CERTIFICATION: 0.60,
    EvidenceSource.SUPERVISOR: 0.55,
    EvidenceSource.LEARNING_ACTIVITY: 0.40,  # completion is weak evidence of skill
    EvidenceSource.HISTORICAL: 0.35,
    EvidenceSource.SELF: 0.20,
}

# Skills decay and old evidence should not outvote recent evidence forever.
EVIDENCE_HALF_LIFE_DAYS = 365.0

# Below this total weight we hold an opinion too weak to act on.
MIN_WEIGHT_FOR_CONFIDENT_LEVEL = 0.5

DEFAULT_LEVEL = 1.0


def _recency_factor(created_at: datetime, now: datetime) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max((now - created_at).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / EVIDENCE_HALF_LIFE_DAYS)


def evidence_weight(ev: ProficiencyEvidence, now: datetime | None = None) -> float:
    """Applied weight of one observation: source reliability x self-reported
    confidence x recency decay."""
    now = now or datetime.now(timezone.utc)
    base = SOURCE_WEIGHTS.get(ev.source, 0.3)
    return base * max(0.0, min(1.0, ev.confidence)) * _recency_factor(ev.created_at, now)


# --------------------------------------------------------------------------- #
# Writing evidence
# --------------------------------------------------------------------------- #

def record_evidence(
    db: Session,
    *,
    user_id: int,
    competency_id: int,
    level_estimate: float,
    source: EvidenceSource,
    confidence: float = 1.0,
    source_ref: str | None = None,
    note: str | None = None,
    recorded_by_id: int | None = None,
    recompute: bool = True,
) -> ProficiencyEvidence:
    """Append one observation. The only supported way to affect a competency level.

    There is no update path and no delete path by design. To correct a mistake,
    append a new observation; to retract one, append with confidence 0 and a note.
    """
    level_estimate = max(1.0, min(5.0, float(level_estimate)))
    confidence = max(0.0, min(1.0, float(confidence)))

    ev = ProficiencyEvidence(
        user_id=user_id,
        competency_id=competency_id,
        level_estimate=level_estimate,
        confidence=confidence,
        source=source,
        source_ref=source_ref,
        note=note,
        recorded_by_id=recorded_by_id,
    )
    db.add(ev)
    db.flush()

    db.add(
        AuditLog(
            actor_user_id=recorded_by_id,
            action="evidence.recorded",
            entity_type="proficiency_evidence",
            entity_id=str(ev.id),
            meta={
                "user_id": user_id,
                "competency_id": competency_id,
                "level_estimate": level_estimate,
                "confidence": confidence,
                "source": source.value,
                "source_ref": source_ref,
            },
        )
    )

    if recompute:
        recompute_profile(db, user_id=user_id, competency_id=competency_id)

    return ev


def record_interview_evidence(
    db: Session,
    *,
    user_id: int,
    competency_id: int,
    knowledge_level: float,
    knowledge_confidence: float,
    interview_answer_ref: str,
) -> ProficiencyEvidence:
    """Write competency evidence from an AI interview — Knowledge axis only.

    Fluency and Confidence are reported to the officer as delivery feedback and
    are never converted into competency evidence. Hesitation tracks cognitive
    load and utterance planning, not knowledge; an expert explaining a hard idea
    often produces *more* disfluency than someone reciting a memorised answer.
    Scoring it as competency would also contradict the platform's own
    confidence-competence divergence check, and would route speech-delivery
    signal into promotion readiness. So it stops here.
    """
    return record_evidence(
        db,
        user_id=user_id,
        competency_id=competency_id,
        level_estimate=knowledge_level,
        confidence=knowledge_confidence,
        source=EvidenceSource.INTERVIEW,
        source_ref=interview_answer_ref,
        note="Knowledge axis only; delivery axes excluded from competency by design.",
    )


# --------------------------------------------------------------------------- #
# Deriving the profile
# --------------------------------------------------------------------------- #

@dataclass
class DerivedLevel:
    level: float
    evidence_count: int
    total_weight: float
    strongest_source: EvidenceSource | None
    last_evidence_at: datetime | None

    @property
    def is_confident(self) -> bool:
        return self.total_weight >= MIN_WEIGHT_FOR_CONFIDENT_LEVEL


def derive_level(
    evidence: list[ProficiencyEvidence], as_of: datetime | None = None
) -> DerivedLevel:
    """Weight-averaged level across all observations.

    `as_of` reconstructs the level as it stood at a past date: evidence recorded
    later is excluded, and recency decay is measured from that date rather than
    from today. Without both, "the level six months ago" would silently apply
    six months of extra decay to evidence that was fresh at the time.
    """
    now = as_of or datetime.now(timezone.utc)
    if as_of is not None:
        evidence = [
            e for e in evidence
            if (e.created_at if e.created_at.tzinfo else e.created_at.replace(tzinfo=timezone.utc))
            <= as_of
        ]
    if not evidence:
        return DerivedLevel(DEFAULT_LEVEL, 0, 0.0, None, None)

    weighted_sum = 0.0
    total_weight = 0.0
    strongest: tuple[float, EvidenceSource] | None = None
    latest: datetime | None = None

    for ev in evidence:
        w = evidence_weight(ev, now)
        weighted_sum += w * ev.level_estimate
        total_weight += w

        if strongest is None or w > strongest[0]:
            strongest = (w, ev.source)

        created = ev.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if latest is None or created > latest:
            latest = created

    level = weighted_sum / total_weight if total_weight > 0 else DEFAULT_LEVEL
    return DerivedLevel(
        level=round(max(1.0, min(5.0, level)), 2),
        evidence_count=len(evidence),
        total_weight=round(total_weight, 4),
        strongest_source=strongest[1] if strongest else None,
        last_evidence_at=latest,
    )


def recompute_profile(
    db: Session, *, user_id: int, competency_id: int | None = None
) -> None:
    """Rebuild the derived cache. Safe to call at any time; idempotent."""
    stmt = select(ProficiencyEvidence).where(ProficiencyEvidence.user_id == user_id)
    if competency_id is not None:
        stmt = stmt.where(ProficiencyEvidence.competency_id == competency_id)

    by_competency: dict[int, list[ProficiencyEvidence]] = {}
    for ev in db.scalars(stmt).all():
        by_competency.setdefault(ev.competency_id, []).append(ev)

    for comp_id, rows in by_competency.items():
        derived = derive_level(rows)
        profile = db.scalar(
            select(CompetencyProfile).where(
                CompetencyProfile.user_id == user_id,
                CompetencyProfile.competency_id == comp_id,
            )
        )
        if profile is None:
            profile = CompetencyProfile(user_id=user_id, competency_id=comp_id)
            db.add(profile)

        profile.level = derived.level
        profile.evidence_count = derived.evidence_count
        profile.evidence_weight = derived.total_weight
        profile.strongest_source = derived.strongest_source
        profile.last_evidence_at = derived.last_evidence_at
        profile.computed_at = datetime.now(timezone.utc)

    db.flush()


# --------------------------------------------------------------------------- #
# Gap analysis
# --------------------------------------------------------------------------- #

GAP_CRITICAL = 2.0
GAP_AT_RISK = 1.0
GAP_MET = 0.1


@dataclass
class GapItem:
    competency_id: int
    competency_code: str
    competency_name: str
    domain: str
    current_level: float
    required_level: float
    gap: float
    criticality: str
    status: str
    evidence_count: int
    evidence_weight: float
    strongest_source: str | None
    last_evidence_at: datetime | None

    @property
    def is_gap(self) -> bool:
        return self.gap > GAP_MET


def _status_for(gap: float) -> str:
    if gap >= GAP_CRITICAL:
        return "critical"
    if gap >= GAP_AT_RISK:
        return "at_risk"
    if gap > GAP_MET:
        return "near_target"
    return "met"


_CRITICALITY_RANK = {
    Criticality.CRITICAL: 3,
    Criticality.HIGH: 2,
    Criticality.MEDIUM: 1,
    Criticality.LOW: 0,
}


def analyse_gaps(
    db: Session, *, user: User, target_role_id: int | None = None
) -> list[GapItem]:
    """Compare the Skill Twin against a role's requirements.

    Defaults to the officer's current role. Pass `target_role_id` to ask the same
    question about a role they are aiming for — which is exactly what the
    Promotion Readiness Engine does.
    """
    role_id = target_role_id or user.frac_role_id
    if role_id is None:
        return []

    requirements = db.scalars(
        select(RoleCompetencyRequirement).where(
            RoleCompetencyRequirement.frac_role_id == role_id
        )
    ).all()

    profiles = {
        p.competency_id: p
        for p in db.scalars(
            select(CompetencyProfile).where(CompetencyProfile.user_id == user.id)
        ).all()
    }
    competencies = {
        c.id: c
        for c in db.scalars(
            select(Competency).where(
                Competency.id.in_([r.competency_id for r in requirements])
            )
        ).all()
    }

    items: list[GapItem] = []
    for req in requirements:
        comp = competencies.get(req.competency_id)
        if comp is None:
            continue
        profile = profiles.get(req.competency_id)
        current = profile.level if profile else DEFAULT_LEVEL
        gap = round(max(0.0, req.required_level - current), 2)

        items.append(
            GapItem(
                competency_id=comp.id,
                competency_code=comp.code,
                competency_name=comp.name,
                domain=comp.domain.value,
                current_level=round(current, 2),
                required_level=req.required_level,
                gap=gap,
                criticality=req.criticality.value,
                status=_status_for(gap),
                evidence_count=profile.evidence_count if profile else 0,
                evidence_weight=profile.evidence_weight if profile else 0.0,
                strongest_source=(
                    profile.strongest_source.value
                    if profile and profile.strongest_source
                    else None
                ),
                last_evidence_at=profile.last_evidence_at if profile else None,
            )
        )

    # Widest gap first, broken by how critical the competency is to the role.
    items.sort(
        key=lambda i: (i.gap, _CRITICALITY_RANK.get(Criticality(i.criticality), 0)),
        reverse=True,
    )
    return items


def role_readiness(db: Session, *, user: User, target_role_id: int | None = None) -> float:
    """Percentage of the role's requirement actually met, weighted by criticality."""
    gaps = analyse_gaps(db, user=user, target_role_id=target_role_id)
    if not gaps:
        return 0.0

    achieved = 0.0
    demanded = 0.0
    for g in gaps:
        w = 1.0 + _CRITICALITY_RANK.get(Criticality(g.criticality), 0)
        achieved += w * min(g.current_level, g.required_level)
        demanded += w * g.required_level

    return round(100.0 * achieved / demanded, 1) if demanded else 0.0


# --------------------------------------------------------------------------- #
# Confidence–competence divergence
# --------------------------------------------------------------------------- #

@dataclass
class DivergenceFlag:
    competency_id: int
    competency_name: str
    self_rated_level: float
    assessed_level: float
    divergence: float


DIVERGENCE_THRESHOLD = 1.0


def detect_divergence(
    db: Session, *, user_id: int, lookback_days: int = 365
) -> list[DivergenceFlag]:
    """Find competencies where self-rating markedly exceeds assessed level.

    Not a judgement about the officer — it is a signal that a conversation is
    worth having, and it is the reason self-assessment carries the lowest weight
    in the model rather than being excluded outright.
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    self_rows = db.scalars(
        select(ProficiencyEvidence).where(
            ProficiencyEvidence.user_id == user_id,
            ProficiencyEvidence.source == EvidenceSource.SELF,
            ProficiencyEvidence.created_at >= since,
        )
    ).all()
    if not self_rows:
        return []

    latest_self: dict[int, ProficiencyEvidence] = {}
    for ev in self_rows:
        prior = latest_self.get(ev.competency_id)
        if prior is None or ev.created_at > prior.created_at:
            latest_self[ev.competency_id] = ev

    flags: list[DivergenceFlag] = []
    for comp_id, self_ev in latest_self.items():
        objective = db.scalars(
            select(ProficiencyEvidence).where(
                ProficiencyEvidence.user_id == user_id,
                ProficiencyEvidence.competency_id == comp_id,
                ProficiencyEvidence.source != EvidenceSource.SELF,
            )
        ).all()
        if not objective:
            continue

        derived = derive_level(objective)
        divergence = round(self_ev.level_estimate - derived.level, 2)
        if divergence >= DIVERGENCE_THRESHOLD and derived.is_confident:
            comp = db.get(Competency, comp_id)
            flags.append(
                DivergenceFlag(
                    competency_id=comp_id,
                    competency_name=comp.name if comp else str(comp_id),
                    self_rated_level=self_ev.level_estimate,
                    assessed_level=derived.level,
                    divergence=divergence,
                )
            )

    flags.sort(key=lambda f: f.divergence, reverse=True)
    return flags
