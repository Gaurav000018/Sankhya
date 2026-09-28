"""Load the authored scenarios.

Idempotent on `Scenario.code`: re-running updates the wording in place rather
than inserting a second copy. That matters more here than for quiz items,
because a `SimulationAttempt` points at a scenario and an officer's feedback
report renders the situation they actually read. Deleting and re-inserting would
break that link and leave scored attempts pointing at nothing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competency
from app.models_simulation import Scenario
from app.seed.scenarios import SCENARIOS


def seed_scenarios(db: Session, competencies: dict[str, Competency]) -> int:
    """Insert or refresh every authored scenario. Returns the number written."""
    written = 0

    for (
        code, competency_code, title, situation, task, constraint,
        expected, traps, level, minutes,
    ) in SCENARIOS:
        competency = competencies.get(competency_code)
        if competency is None:
            # A typo here would make the scenario unreachable by every officer,
            # silently. Worth failing the seed over.
            raise KeyError(
                f"Scenario {code!r} references unknown competency {competency_code!r}"
            )

        scenario = db.scalar(select(Scenario).where(Scenario.code == code))
        if scenario is None:
            scenario = Scenario(code=code)
            db.add(scenario)

        scenario.title = title
        scenario.competency_id = competency.id
        scenario.situation = situation
        scenario.task = task
        scenario.constraint = constraint
        scenario.expected_points = list(expected)
        scenario.common_traps = list(traps)
        scenario.target_level = level
        scenario.minutes = minutes
        scenario.is_active = True
        written += 1

    db.flush()
    return written
