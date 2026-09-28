"""Role-based competency simulation: selection, scoring, and evidence.

The selection rule is the one part worth explaining. A quiz picks the item that
tells it most about where an officer sits — Fisher information, maximising
measurement precision. A simulation cannot do that, and should not try: there
are eight scenarios, not a calibrated bank, and the exercise takes fifteen
minutes rather than thirty seconds. Spending it on the competency the officer is
already strongest in measures very precisely something nobody needed measured.

So it picks by *usefulness to the officer*: the widest critical gap against their
role, at a difficulty they can reach. That is a deliberately different objective
from the quiz's, and it is the right one for an exercise you only get to run a
few times.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.sim_judge import SimVerdict, get_sim_judge
from app.models import EvidenceSource, User
from app.models_simulation import Scenario, SimulationAttempt, SimulationStatus
from app.services.competency import analyse_gaps, record_evidence

log = logging.getLogger("sankhya.simulation")

# A scenario this far above the officer's current level is not a measurement,
# it is a wall. They learn nothing except that they failed, and the evidence it
# produces is dominated by unfamiliarity rather than by capability.
MAX_STRETCH = 1.5

# Below this the response is too short to have made a decision at all. Rejected
# at the API rather than scored, so an officer gets "write more" instead of a 1.0
# in their permanent record for a sentence they typed by accident.
MIN_RESPONSE_WORDS = 40


def _attempted_scenario_ids(db: Session, user_id: int) -> set[int]:
    """Scenarios this officer has already submitted.

    Repeating one measures recall of the feedback, not judgement, so a scenario
    is only offered again when nothing else is left.
    """
    rows = db.scalars(
        select(SimulationAttempt.scenario_id).where(
            SimulationAttempt.user_id == user_id,
            SimulationAttempt.status != SimulationStatus.ABANDONED,
        )
    ).all()
    return set(rows)


def select_scenario(db: Session, *, user: User) -> Scenario | None:
    """Pick the most useful situation for this officer, or None if there are none.

    Order of preference:
      1. A scenario on their widest critical gap, within reach of their level.
      2. Any unattempted scenario within reach.
      3. Any unattempted scenario at all.
      4. Nothing — every scenario has been done. The caller says so rather than
         serving a repeat and calling it new.
    """
    scenarios = db.scalars(
        select(Scenario).where(Scenario.is_active.is_(True))
    ).all()
    if not scenarios:
        return None

    done = _attempted_scenario_ids(db, user.id)
    fresh = [s for s in scenarios if s.id not in done]
    if not fresh:
        return None

    gaps = analyse_gaps(db, user=user)
    # Widest gap first, and only where there is a gap: a met competency has
    # nothing for the officer to gain from fifteen minutes of work.
    ranked = sorted(
        (g for g in gaps if g.is_gap), key=lambda g: g.gap, reverse=True
    )
    levels = {g.competency_id: g.current_level for g in gaps}

    def reachable(scenario: Scenario) -> bool:
        current = levels.get(scenario.competency_id)
        if current is None:
            # No profile for this competency yet — nothing says it is out of
            # reach, and a first measurement is exactly what is missing.
            return True
        return scenario.target_level <= current + MAX_STRETCH

    for gap in ranked:
        candidates = [
            s for s in fresh
            if s.competency_id == gap.competency_id and reachable(s)
        ]
        if candidates:
            # Hardest reachable one: within stretch, it is the more informative.
            return max(candidates, key=lambda s: s.target_level)

    within_reach = [s for s in fresh if reachable(s)]
    if within_reach:
        return min(within_reach, key=lambda s: s.target_level)

    # Nothing is within reach, which means the officer is early on every axis.
    # Give them the gentlest one rather than nothing at all.
    return min(fresh, key=lambda s: s.target_level)


def start_attempt(db: Session, *, user: User) -> SimulationAttempt | None:
    """Open an attempt, resuming one already in progress.

    Resuming matters: the page mounts on every navigation, and without this each
    mount would strand a fresh attempt and quietly burn a scenario the officer
    never saw.
    """
    existing = db.scalar(
        select(SimulationAttempt)
        .where(
            SimulationAttempt.user_id == user.id,
            SimulationAttempt.status == SimulationStatus.IN_PROGRESS,
        )
        .order_by(SimulationAttempt.started_at.desc())
    )
    if existing is not None:
        return existing

    scenario = select_scenario(db, user=user)
    if scenario is None:
        return None

    attempt = SimulationAttempt(
        user_id=user.id,
        scenario_id=scenario.id,
        status=SimulationStatus.IN_PROGRESS,
    )
    db.add(attempt)
    db.flush()
    return attempt


def score_attempt(
    db: Session, *, attempt: SimulationAttempt, response: str
) -> SimVerdict:
    """Score a submitted response and append the evidence it justifies.

    Evidence is written even when the verdict is degraded — at confidence 0, so
    it moves nobody's level. The alternative is an officer whose attempt simply
    vanishes from their record because our scorer was unreachable, which is the
    failure mode the append-only trail exists to prevent.
    """
    scenario = attempt.scenario
    verdict = get_sim_judge().score(scenario, response)

    attempt.response = response
    attempt.knowledge = verdict.knowledge
    attempt.reasoning = verdict.reasoning
    attempt.prioritisation = verdict.prioritisation
    attempt.communication = verdict.communication
    attempt.decision_making = verdict.decision_making
    attempt.derived_level = verdict.derived_level
    attempt.confidence = verdict.confidence
    attempt.covered_points = list(verdict.covered_points)
    attempt.missed_points = list(verdict.missed_points)
    attempt.traps_hit = list(verdict.traps_hit)
    attempt.feedback = verdict.feedback
    attempt.model_name = verdict.model_name
    attempt.degraded = verdict.degraded
    attempt.status = SimulationStatus.SCORED
    attempt.submitted_at = datetime.now(timezone.utc)

    record_evidence(
        db,
        user_id=attempt.user_id,
        competency_id=scenario.competency_id,
        level_estimate=verdict.derived_level,
        confidence=verdict.confidence,
        source=EvidenceSource.SIMULATION,
        source_ref=f"simulation_attempt:{attempt.id}",
        note=(
            "Knowledge and reasoning axes only; prioritisation, communication and "
            "decision-making are reported to the officer as feedback and are "
            "excluded from competency by design."
        ),
    )

    db.flush()
    return verdict
