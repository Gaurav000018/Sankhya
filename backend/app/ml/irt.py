"""Item Response Theory: what an item is worth, and what one answer tells us.

A fixed paper asks everybody the same questions, which means most of them are
wrong for most people. An item far below someone's ability is answered
correctly and teaches us nothing; an item far above is missed and teaches us
nothing either. Both still cost the officer two minutes.

IRT fixes that by putting *items* and *people* on one scale. An item has a
difficulty ``b`` — the ability at which someone has an even chance on it. A
person has an ability ``theta``. The distance between them is what predicts the
answer, so the most informative question is always the one nearest the current
estimate. That is the whole idea, and everything below is machinery for it.

**The model is 3PL with a fixed lower asymptote.** These are four-option
multiple choice items: somebody who knows nothing still scores 25% by guessing.
A 2PL model has no way to express that, so it reads guessing as ability and
biases every low estimate upward — exactly the officers whose gaps matter most.
``c`` is therefore fixed at ``1/options`` rather than estimated: estimating a
lower asymptote well needs thousands of responses per item, and a badly
estimated one is worse than a principled constant.

    P(correct | theta) = c + (1 - c) / (1 + exp(-a (theta - b)))

**Ability is estimated as a posterior, not a point.** The grid below holds the
full distribution over theta, so the platform can report how *certain* it is,
not only what it thinks. That number is load-bearing: it decides when the test
stops, and it becomes the confidence on the evidence record. A level asserted
without an interval is a level that cannot be argued with.

**Everything here is pure Python on a fixed grid.** 161 points, a handful of
items, a few hundred calibration rows — the arithmetic is trivial and the
dependency is not worth it. `numpy` in this image would exist solely for this
file.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# The ability scale
# --------------------------------------------------------------------------- #

# Ability is reported on the FRAC L1-L5 axis everywhere an officer can see it,
# and on theta everywhere the model works. These two constants are the whole
# translation, and they match the adaptive demo on the landing page so the thing
# being advertised and the thing being run are the same thing.
LEVEL_AT_ZERO_THETA = 3.0
LEVELS_PER_THETA = 2.0 / 3.0        # theta -3..+3 spans L1..L5

# Beyond +/-4 the logistic is flat to four decimal places; a wider grid costs
# arithmetic and buys nothing.
THETA_MIN = -4.0
THETA_MAX = 4.0
GRID_STEP = 0.05
GRID: tuple[float, ...] = tuple(
    THETA_MIN + i * GRID_STEP
    for i in range(int((THETA_MAX - THETA_MIN) / GRID_STEP) + 1)
)

# The population prior. Officers are not a standard normal sample and we do not
# pretend to know their spread, so this is deliberately wide: it keeps the first
# two or three answers from dominating without asserting much about anybody.
PRIOR_MEAN = 0.0
PRIOR_SD = 1.2

# Discrimination for an item nobody has calibrated yet, and the centre of the
# prior that calibration shrinks towards. 1.0 is the conventional neutral value
# and means "an ordinary item" — not a good one, not a bad one. Curated items in
# this bank are authored a little above it, which is what a deliberately written
# item with misconception-based distractors normally measures out at.
DEFAULT_DISCRIMINATION = 1.0

# Guards. A discrimination near zero makes an item informative about nothing and
# a very high one lets a single answer swing the estimate, which is how a
# miskeyed item destroys a result.
MIN_DISCRIMINATION = 0.35
MAX_DISCRIMINATION = 2.5


def theta_to_level(theta: float) -> float:
    """Ability on the FRAC L1-L5 axis, clamped to it."""
    level = LEVEL_AT_ZERO_THETA + theta * LEVELS_PER_THETA
    return max(1.0, min(5.0, level))


def level_to_theta(level: float) -> float:
    """The inverse, for reading an existing competency level as a starting point."""
    return (level - LEVEL_AT_ZERO_THETA) / LEVELS_PER_THETA


# --------------------------------------------------------------------------- #
# The model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Item:
    """One item's parameters, detached from the database row.

    A plain value object so the maths can be tested without a session, and so
    calibration can work on items that are not persisted yet.
    """

    id: int
    a: float                       # discrimination
    b: float                       # difficulty, on the theta scale
    c: float = 0.25                # lower asymptote — guessing
    competency_id: int | None = None
    calibrated: bool = False       # b from real responses, or from the author?

    @property
    def level(self) -> float:
        """Difficulty read as a FRAC level, for anything an officer sees."""
        return theta_to_level(self.b)


def probability(theta: float, item: Item) -> float:
    """P(correct) for this ability on this item.

    The exponent is clamped before `exp` because a far-off-target item and a
    high discrimination together overflow a float, and the answer at that point
    is 0 or 1 to every decimal place anybody cares about.
    """
    z = item.a * (theta - item.b)
    if z < -40:
        psi = 0.0
    elif z > 40:
        psi = 1.0
    else:
        psi = 1.0 / (1.0 + math.exp(-z))
    return item.c + (1.0 - item.c) * psi


def information(theta: float, item: Item) -> float:
    """Fisher information — how much this item would tell us at this ability.

    This is the number that makes a test adaptive. It peaks slightly *above*
    ``b`` for a 3PL item (guessing muddies the low end), falls away fast in both
    directions, and scales with the square of discrimination. Picking the item
    that maximises it is what lets eight questions do the work of forty.
    """
    p = probability(theta, item)
    if p <= 0.0 or p >= 1.0:
        return 0.0
    # dP/dtheta for the 3PL. Written out rather than simplified, because the
    # simplified forms in the literature differ in which factor of (1-c) they
    # carry and the difference is silent.
    psi = (p - item.c) / (1.0 - item.c)
    slope = item.a * (1.0 - item.c) * psi * (1.0 - psi)
    return (slope * slope) / (p * (1.0 - p))


# --------------------------------------------------------------------------- #
# Estimating ability
# --------------------------------------------------------------------------- #


@dataclass
class Ability:
    """A posterior over theta, summarised.

    `se` is the posterior standard deviation. It is the honest width of the
    estimate and it drives two decisions — when to stop asking, and how much the
    resulting evidence is worth — so it is carried around rather than recomputed.
    """

    theta: float
    se: float
    level: float
    reliability: float

    @property
    def level_low(self) -> float:
        """Bottom of the 95% interval, on the L1-L5 axis."""
        return theta_to_level(self.theta - 1.96 * self.se)

    @property
    def level_high(self) -> float:
        return theta_to_level(self.theta + 1.96 * self.se)


def marginal_reliability(se: float) -> float:
    """How much of the population spread this estimate actually resolves.

    The classical definition: 1 - (error variance / total variance). At the
    prior it is 0 — we have learned nothing — and it approaches 1 as the
    interval closes. Used directly as the confidence on the evidence record,
    because "how reliable is this measurement" is exactly the question the
    evidence weight is asking.
    """
    ratio = (se * se) / (PRIOR_SD * PRIOR_SD)
    return max(0.0, min(1.0, 1.0 - ratio))


def _prior_weights() -> list[float]:
    return [
        math.exp(-0.5 * ((t - PRIOR_MEAN) / PRIOR_SD) ** 2) for t in GRID
    ]


def estimate(responses: list[tuple[Item, bool]]) -> Ability:
    """Expected a posteriori ability given every answer so far.

    EAP rather than maximum likelihood, for one practical reason: maximum
    likelihood is undefined until the officer has got at least one item right
    *and* one wrong. An all-correct opening run would produce an infinite
    estimate, which is not a number the rest of the platform can carry. The
    prior keeps every intermediate estimate finite and reportable, which matters
    because this one is shown live while the test is still running.

    EAP pulls towards the prior mean, and at the information a twelve-item
    multiple-choice test carries that pull is not small: an officer whose true
    ability is L1.7 is estimated around L2.0 on average. That is the Bayes
    estimator behaving correctly — it is the choice that minimises squared error
    when the data are this thin — but it is a real property of the number, not a
    rounding detail, and it is why the interval is reported beside every level
    rather than the point estimate alone.
    """
    weights = _prior_weights()

    for item, correct in responses:
        for k, t in enumerate(GRID):
            p = probability(t, item)
            weights[k] *= p if correct else (1.0 - p)

    total = sum(weights)
    if total <= 0.0:
        # Every grid point assigned probability zero to what we observed. Only
        # reachable through degenerate item parameters, and the honest answer is
        # the prior rather than a NaN propagating into an evidence record.
        return Ability(
            theta=PRIOR_MEAN, se=PRIOR_SD,
            level=theta_to_level(PRIOR_MEAN), reliability=0.0,
        )

    mean = sum(t * w for t, w in zip(GRID, weights)) / total
    variance = sum(((t - mean) ** 2) * w for t, w in zip(GRID, weights)) / total
    se = math.sqrt(max(variance, 1e-9))

    return Ability(
        theta=round(mean, 4),
        se=round(se, 4),
        level=round(theta_to_level(mean), 2),
        reliability=round(marginal_reliability(se), 4),
    )


# --------------------------------------------------------------------------- #
# Choosing the next item
# --------------------------------------------------------------------------- #

# Below this, an item tells us essentially nothing at the current estimate.
#
# A well-targeted item here carries about 0.26. The floor exists because
# max-information selection is only as good as the pool: once an officer has
# consumed everything near their ability, the "best remaining" item can be one
# pitched two levels away carrying 0.001 — and the engine will serve it, three
# times, with a confident-sounding rationale, because it is technically the
# maximum. Asking a question that cannot move the estimate is worse than
# stopping: it costs the officer time and buys the measurement nothing.
MIN_USEFUL_INFORMATION = 0.02

# Pick at random from the best few rather than always the single best. Without
# this, every officer at the same ability sees the same item in the same order,
# the top of the bank is burned through while the rest is never used, and the
# questions leak. Randomesque selection is the standard cheap fix and costs very
# little information.
EXPOSURE_POOL = 4


def select(
    candidates: list[Item],
    ability: Ability,
    *,
    rng: random.Random | None = None,
    exposure_pool: int = EXPOSURE_POOL,
    min_information: float = MIN_USEFUL_INFORMATION,
) -> Item | None:
    """The most informative unused item at the current estimate.

    Returns None when nothing left is worth asking — either the pool is empty or
    everything in it carries less information than `min_information`. Both are
    real outcomes and stopping reasons, not errors.
    """
    if not candidates:
        return None

    scored = sorted(
        candidates, key=lambda item: information(ability.theta, item), reverse=True
    )
    if information(ability.theta, scored[0]) < min_information:
        return None

    # Exposure control must not reach past the floor: with three usable items
    # left, randomising over the top four would reintroduce the useless one.
    top = [
        item for item in scored[: max(1, exposure_pool)]
        if information(ability.theta, item) >= min_information
    ]
    return (rng or random).choice(top)


def select_opening(
    candidates: list[Item],
    *,
    starting_level: float | None = None,
    rng: random.Random | None = None,
) -> Item | None:
    """The first item, before any answer exists.

    `starting_level` is the officer's current derived level for this competency,
    used to aim the opening question somewhere plausible instead of at the
    population mean. It deliberately affects **selection only** and never the
    posterior, which always starts at the population prior. That split matters:
    if prior evidence seeded the estimate, a quiz would partly re-report what
    the Skill Twin already believed, and the platform would be scoring its own
    homework. Where we aim the first question is an efficiency choice; what we
    conclude from the answer is a measurement.
    """
    target = level_to_theta(starting_level) if starting_level is not None else PRIOR_MEAN
    anchor = Ability(
        theta=target, se=PRIOR_SD, level=theta_to_level(target), reliability=0.0
    )
    return select(candidates, anchor, rng=rng)


# --------------------------------------------------------------------------- #
# When to stop
# --------------------------------------------------------------------------- #

# What a four-option item is actually worth, because this surprised us and the
# number drives every constant below.
#
# Peak Fisher information for one 3PL item with c=0.25 is 0.155 at a=1.0 and
# 0.303 at a=1.4. Since SE = 1/sqrt(total information), an SE of 0.32 — the
# figure that looks respectable and that we reached for first — needs roughly
# *sixty* well-targeted items at ordinary discrimination. Guessing is what costs
# it: the same item with c=0 carries 0.25 at a=1.0, over half as much again.
#
# So 0.50 is set from what twelve items can actually deliver, not from what
# sounds precise. It corresponds to a 95% interval about +/- 0.65 of a FRAC
# level, and the interval is reported everywhere the level is. An assessment
# that claimed +/- 0.2 from twelve multiple-choice questions would be lying, and
# the lie would be invisible.
TARGET_SE = 0.50

# A short test that happens to hit the SE target early has usually done so
# because the officer answered consistently, not because we know enough. The
# floor buys content coverage that precision alone would skip.
#
# The ceiling is the officer's patience, and it is where adaptation earns its
# place: against a fixed paper drawn from the same bank and scored by the same
# model, twelve adaptively chosen items reach the accuracy of about twenty-four
# fixed ones, and the gap is widest for officers furthest from the average —
# the ones a capacity-building programme most needs to identify.
MIN_ITEMS = 5
MAX_ITEMS = 12


@dataclass(frozen=True)
class Stop:
    should_stop: bool
    reason: str | None = None
    explanation: str | None = None


def explain_stop(
    reason: str | None, ability: Ability, *, asked: int, max_items: int = MAX_ITEMS
) -> str | None:
    """Why the test ended, in words.

    Only the reason code is persisted on the attempt, and this is the single
    place that renders it. Storing the sentence instead would freeze the wording
    of every attempt ever taken at whatever it said that day, so a later
    correction would apply to new results and not to the report an officer
    already has open.
    """
    if reason is None:
        return None
    if reason == "exhausted":
        return "The bank has no further items for this competency at any difficulty."
    if reason == "no_informative_items":
        return (
            f"The remaining items for this competency are all pitched well away "
            f"from L{ability.level:.1f}, so none of them would change the "
            f"estimate. Stopping here rather than asking questions that cannot "
            f"tell us anything."
        )
    if reason == "max_items":
        return (
            f"Reached the {max_items}-item ceiling. The estimate is reported with "
            f"the interval it actually has."
        )
    if reason == "precision":
        return (
            f"The ability estimate is precise enough — the 95% interval is "
            f"L{ability.level_low:.1f} to L{ability.level_high:.1f}. More items "
            f"would not change the recorded level."
        )
    return None


def should_stop(
    *,
    asked: int,
    ability: Ability,
    remaining: int,
    informative_left: bool = True,
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
    target_se: float = TARGET_SE,
) -> Stop:
    """Whether the test has learned enough, run long enough, or run out.

    Four reasons, and they are reported to the officer rather than kept
    internal, because "why did that stop after six questions" is the first thing
    anybody asks about an adaptive test and "it stopped when it was sure enough"
    is a much better answer than silence.

    The two exhaustion reasons deliberately outrank `min_items`. A floor of five
    items is there to buy coverage, and it cannot buy coverage that the bank does
    not contain — forcing three more worthless questions to reach it would make
    the officer pay for a gap in the item bank.
    """
    def stop(reason: str) -> Stop:
        return Stop(
            True, reason,
            explain_stop(reason, ability, asked=asked, max_items=max_items),
        )

    if remaining <= 0:
        return stop("exhausted")
    if not informative_left:
        # Distinct from "exhausted" on purpose. The bank still has items; none
        # of them is pitched anywhere near this officer. That is a statement
        # about the bank, it is actionable — write items at this level — and
        # collapsing it into "we ran out" would hide it.
        return stop("no_informative_items")
    if asked >= max_items:
        return stop("max_items")
    if asked >= min_items and ability.se <= target_se:
        return stop("precision")
    return Stop(False)


def why_this_item(item: Item, ability: Ability, *, first: bool) -> str:
    """The sentence the officer reads next to the question.

    Every other adaptive decision in this platform explains itself and this one
    is the most visible, so it does too. An assessment that silently changes
    difficulty feels like it is reacting to something it will not say.
    """
    if first:
        return (
            f"Opening at L{item.level:.1f}, pitched near where your record already "
            f"puts you — so the first answer is informative whichever way it goes."
        )
    gap = item.b - ability.theta
    if gap > 0.25:
        return (
            f"You are tracking around L{ability.level:.1f}, so this one steps up to "
            f"L{item.level:.1f} to find where it stops being easy."
        )
    if gap < -0.25:
        return (
            f"The last answer pulled the estimate down, so this one steps back to "
            f"L{item.level:.1f} to find solid ground."
        )
    return (
        f"Pitched at L{item.level:.1f}, right at the current estimate — where an "
        f"answer tells us the most either way."
    )


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #

# Item parameters estimated from a handful of responses are noise wearing a
# decimal point. This is the number below which an item keeps whatever the
# author gave it. It is far above the threshold for classical p-values, because
# a p-value is one number and this is two.
MIN_RESPONSES_TO_CALIBRATE = 25

# How tightly estimates are held to the author's intent. These are the standard
# deviations of the priors, so a larger value trusts the data sooner. With 25
# responses the likelihood already dominates; with 200 the prior is irrelevant.
B_PRIOR_SD = 0.8
LOG_A_PRIOR_SD = 0.35

_A_GRID = [0.4 + 0.1 * i for i in range(22)]           # 0.4 .. 2.5
_B_GRID = [-3.0 + 0.1 * i for i in range(61)]          # -3.0 .. 3.0


@dataclass
class Calibration:
    """What calibration concluded about one item."""

    item_id: int
    a: float
    b: float
    responses: int
    b_shift: float               # how far it moved from the authored difficulty
    note: str


def calibrate_item(
    item: Item,
    responses: list[tuple[float, bool]],
    *,
    min_responses: int = MIN_RESPONSES_TO_CALIBRATE,
) -> Calibration | None:
    """Re-estimate ``a`` and ``b`` from people who actually answered it.

    `responses` pairs each respondent's ability estimate with whether they got
    this item right. Maximises the penalised likelihood over a grid rather than
    by Newton's method: the surface is well behaved, the grid is 1,342 points,
    and a derivative-based optimiser is one more thing that can silently return
    a local optimum on a sparse item.

    Returns None when there is not enough data, which leaves the authored
    parameters in place. That is the right default — an author who wrote the
    item had a view about its difficulty, and 12 responses is not evidence
    enough to overrule it.
    """
    if len(responses) < min_responses:
        return None

    log_a_prior_mean = math.log(DEFAULT_DISCRIMINATION)
    best: tuple[float, float, float] | None = None   # (penalised ll, a, b)

    for a in _A_GRID:
        log_a_penalty = 0.5 * ((math.log(a) - log_a_prior_mean) / LOG_A_PRIOR_SD) ** 2
        for b in _B_GRID:
            candidate = Item(id=item.id, a=a, b=b, c=item.c)
            ll = 0.0
            for theta, correct in responses:
                p = probability(theta, candidate)
                # Clamped so a confidently wrong prediction costs a large finite
                # number rather than -inf, which would discard the whole cell.
                p = min(max(p, 1e-6), 1.0 - 1e-6)
                ll += math.log(p) if correct else math.log(1.0 - p)

            penalised = (
                ll
                - log_a_penalty
                - 0.5 * ((b - item.b) / B_PRIOR_SD) ** 2
            )
            if best is None or penalised > best[0]:
                best = (penalised, a, b)

    assert best is not None
    _, a_hat, b_hat = best
    a_hat = max(MIN_DISCRIMINATION, min(MAX_DISCRIMINATION, a_hat))
    shift = b_hat - item.b

    if abs(shift) >= 0.8:
        note = (
            f"Calibrated difficulty moved {shift:+.1f} theta from the authored "
            f"value — the item is markedly "
            f"{'harder' if shift > 0 else 'easier'} in practice than intended."
        )
    elif a_hat <= MIN_DISCRIMINATION + 0.05:
        note = (
            "Discrimination is at the floor: answers on this item barely track "
            "ability, which usually means an ambiguous stem or a defensible "
            "second answer."
        )
    else:
        note = "Parameters updated from live responses."

    return Calibration(
        item_id=item.id,
        a=round(a_hat, 3),
        b=round(b_hat, 3),
        responses=len(responses),
        b_shift=round(shift, 3),
        note=note,
    )


def test_information(items: list[Item], theta: float) -> float:
    """Total information a set of items carries at one ability.

    Used for bank health rather than for scoring: it answers "can this
    competency actually measure someone at L2" separately from "did anyone
    score L2", which is the difference between a thin bank and a strong cohort.
    """
    return sum(information(theta, item) for item in items)


def se_from_information(info: float) -> float:
    """Standard error implied by total information, floored for a sane display."""
    if info <= 0:
        return PRIOR_SD
    return min(PRIOR_SD, 1.0 / math.sqrt(info))
