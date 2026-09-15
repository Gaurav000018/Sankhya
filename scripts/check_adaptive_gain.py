"""Is adapting actually worth it, and does the estimate recover the truth?

    python scripts/check_adaptive_gain.py

Two questions, and the whole adaptive assessment rests on both being yes.

**Does the estimate recover a known ability?** Simulated officers of known
ability sit the real selection-and-estimation loop, and we check where it lands.
If an officer who truly sits at L4 is reported at L2.5, everything downstream —
the gap ranking, the promotion forecast, the ACBP priorities — is built on a
number that does not mean what it says.

**Does choosing items well beat asking more of them?** Adaptive testing is a
substantial amount of machinery, and if a fixed paper of the same length did as
well it should be deleted. Same bank, same scoring model, same number of items:
only the choice of which items differs.

This exists because the README publishes the second table, and a published
number nobody can reproduce is a claim rather than a measurement. It needs no
database and no containers — everything runs on `app.ml.irt`.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ml import irt  # noqa: E402

TRIALS = 400
BANK_SIZE = 24

# The ability points to test. Reported as FRAC levels because that is what
# everyone reads, and theta because that is what the model works in.
POINTS = (-2.0, -1.0, 0.0, 1.0, 2.0)

# What counts as a failure. Deliberately generous on absolute accuracy — twelve
# four-option items cannot do better — and strict on the comparison, because
# that is the claim the feature exists to support.
MAX_RMSE = 0.80
MAX_BIAS = 0.55


def build_bank(seed: int = 7) -> list[irt.Item]:
    """A bank of the shape the curated one aims at: spread, mixed discrimination."""
    rng = random.Random(seed)
    return [
        irt.Item(
            id=i,
            a=round(1.1 + 0.6 * rng.random(), 2),
            b=round(-2.2 + 4.4 * i / (BANK_SIZE - 1), 2),
            c=0.25,
        )
        for i in range(BANK_SIZE)
    ]


def sit_adaptive(true_theta: float, bank: list[irt.Item], seed: int) -> irt.Ability:
    """One officer through the real loop, with only the answers simulated."""
    rng = random.Random(seed)
    responses: list[tuple[irt.Item, bool]] = []
    used: set[int] = set()
    ability = irt.estimate(responses)

    for _ in range(irt.MAX_ITEMS):
        pool = [item for item in bank if item.id not in used]
        chosen = (
            irt.select_opening(pool, rng=rng)
            if not responses
            else irt.select(pool, ability, rng=rng)
        )
        if chosen is None:
            break
        used.add(chosen.id)
        responses.append((chosen, rng.random() < irt.probability(true_theta, chosen)))
        ability = irt.estimate(responses)

    return ability


def sit_fixed(
    true_theta: float, bank: list[irt.Item], seed: int, items: int
) -> irt.Ability:
    """The same officer on a paper drawn at random and scored the same way."""
    rng = random.Random(seed + 9000)
    chosen = rng.sample(bank, min(items, len(bank)))
    return irt.estimate(
        [(item, rng.random() < irt.probability(true_theta, item)) for item in chosen]
    )


def summarise(errors: list[float]) -> tuple[float, float]:
    bias = sum(errors) / len(errors)
    rmse = (sum(e * e for e in errors) / len(errors)) ** 0.5
    return bias, rmse


def main() -> int:
    bank = build_bank()
    failures: list[str] = []

    print(
        f"\n{BANK_SIZE} items, difficulty L{bank[0].level:.2f}-L{bank[-1].level:.2f}, "
        f"discrimination {min(i.a for i in bank)}-{max(i.a for i in bank)}, "
        f"guessing {bank[0].c}."
    )
    print(f"{TRIALS} simulated officers per row. Ceiling {irt.MAX_ITEMS} items.\n")

    print("Recovery — does the estimate land where the officer actually is?")
    print(f"{'true':>12}  {'bias':>7}  {'rmse':>7}  {'mean SE':>8}")
    for theta in POINTS:
        results = [sit_adaptive(theta, bank, s) for s in range(TRIALS)]
        bias, rmse = summarise([r.theta - theta for r in results])
        mean_se = sum(r.se for r in results) / len(results)
        flag = ""
        if rmse > MAX_RMSE:
            failures.append(f"rmse {rmse:.3f} at theta {theta:+.1f}")
            flag = "  <-- FAIL"
        if abs(bias) > MAX_BIAS:
            failures.append(f"bias {bias:+.3f} at theta {theta:+.1f}")
            flag = "  <-- FAIL"
        print(
            f"{f'{theta:+.1f} (L{irt.theta_to_level(theta):.2f})':>12}  "
            f"{bias:+7.3f}  {rmse:7.3f}  {mean_se:8.3f}{flag}"
        )

    print(
        "\nBias towards the middle is EAP behaving correctly — it is the estimator\n"
        "that minimises squared error when the data are this thin. It is also why\n"
        "the interval is reported beside every level rather than the point alone.\n"
    )

    print("Gain — is choosing items worth more than asking more of them?")
    print(
        f"{'true':>12}  {'adaptive-' + str(irt.MAX_ITEMS):>12}  "
        f"{'fixed-' + str(irt.MAX_ITEMS):>12}  {'fixed-' + str(2 * irt.MAX_ITEMS):>12}"
    )
    for theta in POINTS:
        _, adaptive = summarise(
            [sit_adaptive(theta, bank, s).theta - theta for s in range(TRIALS)]
        )
        _, fixed_same = summarise(
            [
                sit_fixed(theta, bank, s, irt.MAX_ITEMS).theta - theta
                for s in range(TRIALS)
            ]
        )
        _, fixed_double = summarise(
            [
                sit_fixed(theta, bank, s, 2 * irt.MAX_ITEMS).theta - theta
                for s in range(TRIALS)
            ]
        )
        flag = ""
        if adaptive >= fixed_same:
            failures.append(
                f"adaptive {adaptive:.3f} did not beat fixed {fixed_same:.3f} "
                f"at theta {theta:+.1f}"
            )
            flag = "  <-- FAIL"
        print(
            f"{f'{theta:+.1f} (L{irt.theta_to_level(theta):.2f})':>12}  "
            f"{adaptive:12.3f}  {fixed_same:12.3f}  {fixed_double:12.3f}{flag}"
        )

    print(
        "\nRMSE in theta; lower is better. The claim in the README is that the\n"
        "adaptive column beats fixed at the same length everywhere, and comes\n"
        "close to fixed at double the length — worst case at the extremes, which\n"
        "is where a capacity-building programme most needs to identify people.\n"
    )

    if failures:
        print(f"FAILED — {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        print(
            "\nIf these have drifted, the likely causes are a change to TARGET_SE,\n"
            "MAX_ITEMS or MIN_USEFUL_INFORMATION, or a sign error in the posterior\n"
            "update. Both tables move together when the model is wrong and\n"
            "separately when a constant was merely retuned.\n"
        )
        return 1

    print("All checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
