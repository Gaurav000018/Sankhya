"""Role-based competency simulation — the endpoints an officer uses.

    POST /simulations              open an attempt (or resume the open one)
    POST /simulations/{id}/submit  submit the response, get the assessment
    GET  /simulations/{id}         re-read a scored attempt
    GET  /simulations/me           everything this officer has attempted

Two things the API will not do.

It never returns `expected_points` or `common_traps` for an attempt still in
progress. The rubric is the answer key; serving it beside the situation would
make the exercise a reading-comprehension test. They appear only after the
response is submitted, which is also when they become useful to the officer.

And it will not score a response below `MIN_RESPONSE_WORDS`. A sentence typed by
accident is not a decision, and scoring it would put a 1.0 into an append-only
record that cannot be deleted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, write_audit
from app.db import get_db
from app.models import User
from app.models_simulation import Scenario, SimulationAttempt, SimulationStatus
from app.schemas import (
    SimulationAttemptOut,
    SimulationResultOut,
    SimulationSubmitIn,
)
from app.services import simulation as simulation_service

router = APIRouter(tags=["simulation"])


def _attempt_out(attempt: SimulationAttempt, scenario: Scenario) -> SimulationAttemptOut:
    """The in-progress view: the situation, and nothing that gives it away."""
    return SimulationAttemptOut(
        attempt_id=attempt.id,
        status=attempt.status.value,
        scenario_code=scenario.code,
        title=scenario.title,
        competency_name=scenario.competency.name if scenario.competency else None,
        situation=scenario.situation,
        task=scenario.task,
        constraint=scenario.constraint,
        minutes=scenario.minutes,
        target_level=scenario.target_level,
        response=attempt.response,
    )


def _result_out(attempt: SimulationAttempt) -> SimulationResultOut:
    scenario = attempt.scenario
    return SimulationResultOut(
        attempt_id=attempt.id,
        status=attempt.status.value,
        scenario_code=scenario.code,
        title=scenario.title,
        competency_name=scenario.competency.name if scenario.competency else None,
        situation=scenario.situation,
        task=scenario.task,
        constraint=scenario.constraint,
        response=attempt.response,
        knowledge=attempt.knowledge,
        reasoning=attempt.reasoning,
        prioritisation=attempt.prioritisation,
        communication=attempt.communication,
        decision_making=attempt.decision_making,
        derived_level=attempt.derived_level,
        confidence=attempt.confidence,
        covered_points=list(attempt.covered_points or []),
        missed_points=list(attempt.missed_points or []),
        traps_hit=list(attempt.traps_hit or []),
        expected_points=list(scenario.expected_points or []),
        feedback=attempt.feedback,
        model_name=attempt.model_name,
        degraded=attempt.degraded,
        submitted_at=attempt.submitted_at,
    )


@router.post("/simulations", response_model=SimulationAttemptOut)
def start_simulation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Open an attempt, or hand back the one already open.

    Resuming rather than starting afresh: the page mounts on every navigation,
    and a new attempt per mount would burn a scenario the officer never read.
    """
    try:
        attempt = simulation_service.start_attempt(db, user=user)
    except simulation_service.NoScenarios as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No situations have been loaded on this deployment yet, so there is "
            "nothing to attempt. An administrator seeds the scenario library."
            if exc.library_empty
            else "You have worked through every situation currently in the "
            "library. New ones are added as they are authored and reviewed.",
        ) from exc
    db.commit()
    db.refresh(attempt)
    return _attempt_out(attempt, attempt.scenario)


@router.post("/simulations/{attempt_id}/submit", response_model=SimulationResultOut)
def submit_simulation(
    attempt_id: int,
    payload: SimulationSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = db.get(SimulationAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        # Same response for "not yours" as for "does not exist": distinguishing
        # them tells an authenticated caller which attempt ids are real.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if attempt.status != SimulationStatus.IN_PROGRESS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This attempt has already been submitted.",
        )

    response = (payload.response or "").strip()
    if len(response.split()) < simulation_service.MIN_RESPONSE_WORDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Write at least {simulation_service.MIN_RESPONSE_WORDS} words. This "
            "exercise asks what you would do and why — a short answer cannot be "
            "assessed fairly, and the score would stay on your record.",
        )

    simulation_service.score_attempt(db, attempt=attempt, response=response)
    write_audit(
        db,
        actor_user_id=user.id,
        action="simulation.submitted",
        entity_type="simulation_attempt",
        entity_id=str(attempt.id),
        meta={"scenario": attempt.scenario.code, "degraded": attempt.degraded},
    )
    db.commit()
    db.refresh(attempt)
    return _result_out(attempt)


# Declared before `/simulations/{attempt_id}`: FastAPI matches in registration
# order, and a literal "me" would otherwise be swallowed by the int path and
# return 422.
@router.get("/simulations/me", response_model=list[SimulationResultOut])
def my_simulations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempts = db.scalars(
        select(SimulationAttempt)
        .where(
            SimulationAttempt.user_id == user.id,
            SimulationAttempt.status == SimulationStatus.SCORED,
        )
        .order_by(SimulationAttempt.submitted_at.desc())
    ).all()
    return [_result_out(a) for a in attempts]


@router.get("/simulations/{attempt_id}", response_model=SimulationResultOut)
def read_simulation(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = db.get(SimulationAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if attempt.status != SimulationStatus.SCORED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This attempt has not been scored yet.",
        )
    return _result_out(attempt)
