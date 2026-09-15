"""Tests for the IRT engine behind the adaptive assessment.

Three kinds of claim are worth asserting here, and they need different tests.

**The model is the model.** The 3PL has closed-form properties — the probability
at the difficulty, the guessing floor, where information peaks — and getting one
of them subtly wrong produces an assessment that works, reports plausible
numbers, and measures the wrong thing. These are cheap to check and they are the
only defence against a sign error that nothing else would surface.

**The estimator recovers what is there.** The only question that matters about an
ability estimate is whether an officer who truly sits at L4 is reported near L4.
That is tested by simulation: generate answers from a known ability, run the real
selection and estimation loop, and check where it lands. Bias and RMSE are
asserted against thresholds that reflect what twelve four-option items can
actually deliver, not against what would be nice.

**Adaptation beats not adapting.** The whole justification for this machinery is
that choosing items well is worth more than asking more of them. If that stops
being true the feature should be deleted, so it is asserted directly rather than
assumed.

No database and no container: everything here runs on the pure functions.
"""

import math
import random

import pytest

from app.ml import irt


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def bank(n=24, a=1.3, low=-2.6, high=2.6, c=0.25) -> list[irt.Item]:
    """An evenly spread bank, of the shape the curated one aims at."""
    step = (high - low) / (n - 1)
    return [irt.Item(id=i, a=a, b=round(low + i * step, 3), c=c) for i in range(n)]


def sit(true_theta: float, items: list[irt.Item], seed: int, **stop_kwargs):
    """Run one complete adaptive test against a simulated officer.

    This is the real loop — `select_opening`, `estimate`, `select`, `should_stop`
    — with only the answers simulated. A test that reimplemented the loop would
    pass while the product was broken.
    """
    rng = random.Random(seed)
    responses: list[tuple[irt.Item, bool]] = []
    used: set[int] = set()
    ability = irt.estimate(responses)
    reason = None

    while True:
        pool = [item for item in items if item.id not in used]
        best = max(
            (irt.information(ability.theta, item) for item in pool), default=0.0
        )
        stop = irt.should_stop(
            asked=len(responses),
            ability=ability,
            remaining=len(pool),
            informative_left=best >= irt.MIN_USEFUL_INFORMATION,
            **stop_kwargs,
        )
        if stop.should_stop:
            reason = stop.reason
            break

        chosen = (
            irt.select_opening(pool, rng=rng)
            if not responses
            else irt.select(pool, ability, rng=rng)
        )
        if chosen is None:
            reason = "no_informative_items"
            break

        used.add(chosen.id)
        responses.append((chosen, rng.random() < irt.probability(true_theta, chosen)))
        ability = irt.estimate(responses)

    return ability, len(responses), reason


# --------------------------------------------------------------------------- #
# The model
# --------------------------------------------------------------------------- #


def test_probability_at_difficulty_is_halfway_above_the_guessing_floor():
    """At theta == b the logistic is 0.5, so P is c + (1-c)/2, not 0.5.

    This is the single easiest place to introduce a 3PL bug that looks fine: a
    2PL implementation returns 0.5 here and every estimate it produces is
    biased upward for weak candidates.
    """
    item = irt.Item(id=1, a=1.0, b=0.0, c=0.25)
    assert irt.probability(0.0, item) == pytest.approx(0.625)


def test_probability_floors_at_the_guessing_parameter():
    item = irt.Item(id=1, a=1.5, b=0.0, c=0.25)
    assert irt.probability(-50.0, item) == pytest.approx(0.25, abs=1e-9)
    assert irt.probability(50.0, item) == pytest.approx(1.0, abs=1e-9)


def test_probability_does_not_overflow_on_extreme_ability():
    """A far-off item with high discrimination overflows a naive exp()."""
    item = irt.Item(id=1, a=2.5, b=-4.0, c=0.2)
    assert 0.0 <= irt.probability(400.0, item) <= 1.0
    assert 0.0 <= irt.probability(-400.0, item) <= 1.0


def test_probability_increases_with_ability():
    item = irt.Item(id=1, a=1.2, b=0.5, c=0.25)
    values = [irt.probability(t, item) for t in (-2, -1, 0, 1, 2)]
    assert values == sorted(values)


def test_information_peaks_above_difficulty_for_a_guessable_item():
    """A 3PL item is most informative slightly above b, because guessing
    muddies everything below it. For c=0 the peak sits exactly at b."""
    guessable = irt.Item(id=1, a=1.0, b=0.0, c=0.25)
    peak = max(irt.GRID, key=lambda t: irt.information(t, guessable))
    assert peak > 0.0

    clean = irt.Item(id=2, a=1.0, b=0.0, c=0.0)
    assert max(irt.GRID, key=lambda t: irt.information(t, clean)) == pytest.approx(
        0.0, abs=irt.GRID_STEP
    )


def test_information_rises_with_discrimination():
    low = irt.Item(id=1, a=0.8, b=0.0)
    high = irt.Item(id=2, a=1.8, b=0.0)
    assert irt.information(0.0, high) > irt.information(0.0, low)


def test_information_falls_away_from_the_target():
    item = irt.Item(id=1, a=1.3, b=0.0)
    assert irt.information(0.0, item) > irt.information(1.5, item)
    assert irt.information(1.5, item) > irt.information(3.0, item)


def test_level_and_theta_round_trip():
    for level in (1.0, 2.5, 3.0, 4.25, 5.0):
        assert irt.theta_to_level(irt.level_to_theta(level)) == pytest.approx(level)


def test_level_is_clamped_to_the_frac_scale():
    assert irt.theta_to_level(-10.0) == 1.0
    assert irt.theta_to_level(10.0) == 5.0


# --------------------------------------------------------------------------- #
# Estimation
# --------------------------------------------------------------------------- #


def test_no_responses_returns_the_prior():
    ability = irt.estimate([])
    assert ability.theta == pytest.approx(irt.PRIOR_MEAN, abs=0.01)
    assert ability.se == pytest.approx(irt.PRIOR_SD, abs=0.05)
    assert ability.reliability == pytest.approx(0.0, abs=0.01)


def test_all_correct_on_hard_items_raises_the_estimate():
    items = [irt.Item(id=i, a=1.3, b=1.0 + 0.2 * i) for i in range(6)]
    ability = irt.estimate([(item, True) for item in items])
    assert ability.theta > 0.8


def test_all_wrong_on_easy_items_lowers_the_estimate():
    items = [irt.Item(id=i, a=1.3, b=-1.0 - 0.2 * i) for i in range(6)]
    ability = irt.estimate([(item, False) for item in items])
    assert ability.theta < -0.8


def test_estimate_stays_finite_when_every_answer_is_correct():
    """Maximum likelihood is undefined here — it runs to infinity. The prior is
    what keeps an all-correct opening run reportable, and the assessment shows
    the estimate live, so an infinity would reach a screen."""
    items = [irt.Item(id=i, a=1.5, b=0.0) for i in range(12)]
    ability = irt.estimate([(item, True) for item in items])
    assert math.isfinite(ability.theta)
    assert math.isfinite(ability.se)
    assert ability.theta < irt.THETA_MAX


def test_more_answers_narrow_the_interval():
    items = bank(n=10)
    short = irt.estimate([(items[i], i % 2 == 0) for i in range(3)])
    long = irt.estimate([(items[i], i % 2 == 0) for i in range(10)])
    assert long.se < short.se


def test_reliability_is_zero_at_the_prior_and_rises_as_the_interval_closes():
    assert irt.marginal_reliability(irt.PRIOR_SD) == pytest.approx(0.0)
    assert irt.marginal_reliability(0.5) > irt.marginal_reliability(0.9)
    assert 0.0 <= irt.marginal_reliability(0.01) <= 1.0


def test_interval_brackets_the_point_estimate():
    ability = irt.estimate([(irt.Item(id=1, a=1.3, b=0.5), True)])
    assert ability.level_low < ability.level < ability.level_high


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def test_selection_prefers_items_near_the_estimate():
    items = bank(n=24)
    ability = irt.estimate([])           # theta 0
    rng = random.Random(0)
    picks = [irt.select(items, ability, rng=rng).b for _ in range(40)]
    assert all(abs(b) < 1.2 for b in picks), picks


def test_selection_follows_the_estimate_upward():
    items = bank(n=24)
    high = irt.Ability(theta=1.8, se=0.6, level=irt.theta_to_level(1.8), reliability=0.5)
    rng = random.Random(1)
    picks = [irt.select(items, high, rng=rng).b for _ in range(40)]
    assert all(b > 0.5 for b in picks), picks


def test_selection_spreads_across_the_top_few_items():
    """Always serving the single best item burns the top of the bank and leaks
    the questions. Exposure control is what stops that."""
    items = bank(n=24)
    ability = irt.estimate([])
    rng = random.Random(2)
    seen = {irt.select(items, ability, rng=rng).id for _ in range(60)}
    assert len(seen) > 1


def test_selection_returns_nothing_when_every_item_is_uninformative():
    """The bug this exists for: an officer at the bottom of the scale, with only
    very hard items left, was served three questions carrying information of
    0.001 — each one unanswerable and each one costing them time."""
    far = [irt.Item(id=i, a=1.3, b=3.5 + i) for i in range(4)]
    bottom = irt.Ability(theta=-2.5, se=0.7, level=1.3, reliability=0.6)
    assert irt.select(far, bottom) is None


def test_selection_ignores_an_empty_pool():
    assert irt.select([], irt.estimate([])) is None


def test_opening_item_is_aimed_at_the_officers_existing_level():
    items = bank(n=24)
    high = irt.select_opening(items, starting_level=4.5, rng=random.Random(3))
    mid = irt.select_opening(items, starting_level=None, rng=random.Random(3))
    assert high.b > mid.b


# --------------------------------------------------------------------------- #
# Stopping
# --------------------------------------------------------------------------- #


def test_does_not_stop_before_the_minimum_on_precision_alone():
    tight = irt.Ability(theta=0.0, se=0.1, level=3.0, reliability=0.99)
    stop = irt.should_stop(asked=2, ability=tight, remaining=20)
    assert not stop.should_stop


def test_stops_on_precision_once_past_the_minimum():
    tight = irt.Ability(theta=0.0, se=0.1, level=3.0, reliability=0.99)
    stop = irt.should_stop(asked=irt.MIN_ITEMS, ability=tight, remaining=20)
    assert stop.should_stop and stop.reason == "precision"


def test_stops_at_the_item_ceiling():
    wide = irt.Ability(theta=0.0, se=1.0, level=3.0, reliability=0.3)
    stop = irt.should_stop(asked=irt.MAX_ITEMS, ability=wide, remaining=20)
    assert stop.should_stop and stop.reason == "max_items"


def test_exhaustion_outranks_the_minimum_item_count():
    """A five-item floor cannot buy coverage the bank does not contain, and
    forcing three more useless questions to reach it makes the officer pay for
    a gap in the item bank."""
    wide = irt.Ability(theta=0.0, se=1.0, level=3.0, reliability=0.3)
    assert irt.should_stop(asked=1, ability=wide, remaining=0).reason == "exhausted"
    assert (
        irt.should_stop(
            asked=1, ability=wide, remaining=9, informative_left=False
        ).reason
        == "no_informative_items"
    )


def test_every_stop_reason_has_an_explanation():
    """The reason code is persisted and the sentence is rendered from it. A
    reason with no wording would reach an officer as a blank."""
    ability = irt.estimate([])
    for reason in ("precision", "max_items", "exhausted", "no_informative_items"):
        text = irt.explain_stop(reason, ability, asked=8)
        assert text and len(text) > 20
    assert irt.explain_stop(None, ability, asked=0) is None


def test_every_stop_path_produces_a_reason_the_renderer_knows():
    """should_stop and explain_stop must not drift apart."""
    ability = irt.Ability(theta=0.0, se=0.1, level=3.0, reliability=0.9)
    for kwargs in (
        {"asked": 1, "remaining": 0},
        {"asked": 1, "remaining": 5, "informative_left": False},
        {"asked": irt.MAX_ITEMS, "remaining": 5},
        {"asked": irt.MIN_ITEMS, "remaining": 5},
    ):
        stop = irt.should_stop(ability=ability, **kwargs)
        assert stop.should_stop
        assert stop.explanation == irt.explain_stop(
            stop.reason, ability, asked=kwargs["asked"],
            max_items=kwargs.get("max_items", irt.MAX_ITEMS),
        )


# --------------------------------------------------------------------------- #
# Recovery — the claim that actually matters
# --------------------------------------------------------------------------- #

# Thresholds set from what twelve four-option items can deliver, measured rather
# than hoped for. A 4-option item peaks at about 0.30 of Fisher information at
# a=1.4, so twelve of them cap the achievable standard error near 0.5. Asserting
# anything tighter would be asserting that the guessing parameter does not exist.
RECOVERY_RMSE = 0.75
RECOVERY_BIAS = 0.45


@pytest.mark.parametrize("true_theta", [-1.5, -0.5, 0.0, 0.5, 1.5])
def test_the_estimate_recovers_a_known_ability(true_theta):
    items = bank(n=24, a=1.4)
    errors = [sit(true_theta, items, seed)[0].theta - true_theta for seed in range(150)]
    bias = sum(errors) / len(errors)
    rmse = (sum(e * e for e in errors) / len(errors)) ** 0.5

    assert rmse < RECOVERY_RMSE, f"rmse {rmse:.3f} at theta {true_theta}"
    assert abs(bias) < RECOVERY_BIAS, f"bias {bias:+.3f} at theta {true_theta}"


def test_shrinkage_pulls_towards_the_middle_not_away_from_it():
    """EAP is biased towards the prior mean at low information. That is the
    Bayes estimator behaving correctly, and it is why the interval is reported
    beside the level — but the direction must be inward. Outward drift would
    mean a sign error somewhere in the posterior update."""
    items = bank(n=24, a=1.4)
    for true_theta in (-1.5, 1.5):
        estimates = [sit(true_theta, items, seed)[0].theta for seed in range(150)]
        mean = sum(estimates) / len(estimates)
        assert abs(mean) < abs(true_theta) + 0.1
        assert (mean - true_theta) * (0.0 - true_theta) > 0


def test_a_random_guesser_is_not_reported_as_competent():
    """The reason the model is 3PL rather than 2PL. Someone guessing at random
    on four-option items scores 25% and must not be read as mid-scale."""
    items = bank(n=24, a=1.4)
    rng = random.Random(9)
    levels = []
    for seed in range(60):
        responses, used = [], set()
        ability = irt.estimate([])
        for _ in range(irt.MAX_ITEMS):
            pool = [i for i in items if i.id not in used]
            chosen = irt.select(pool, ability, rng=rng)
            if chosen is None:
                break
            used.add(chosen.id)
            responses.append((chosen, rng.random() < 0.25))
            ability = irt.estimate(responses)
        levels.append(ability.level)

    assert sum(levels) / len(levels) < 2.5


def test_the_test_stops_itself_within_the_ceiling():
    items = bank(n=40, a=1.4)
    for seed in range(30):
        _, asked, reason = sit(0.0, items, seed)
        assert asked <= irt.MAX_ITEMS
        assert reason is not None


# --------------------------------------------------------------------------- #
# Adaptation is worth doing
# --------------------------------------------------------------------------- #


def test_adaptive_selection_beats_a_fixed_paper_of_the_same_length():
    """The justification for the whole feature. Same bank, same scoring model,
    same number of items — only the choice of which items differs.

    Asserted at the extremes, where adaptation helps most and where the officers
    a capacity-building programme most needs to identify actually sit.
    """
    items = bank(n=24, a=1.4)

    def fixed(true_theta, seed):
        rng = random.Random(seed + 9000)
        chosen = rng.sample(items, irt.MAX_ITEMS)
        return irt.estimate(
            [(i, rng.random() < irt.probability(true_theta, i)) for i in chosen]
        )

    for true_theta in (-2.0, 2.0):
        adaptive_err = [
            sit(true_theta, items, s)[0].theta - true_theta for s in range(200)
        ]
        fixed_err = [fixed(true_theta, s).theta - true_theta for s in range(200)]

        adaptive_rmse = (sum(e * e for e in adaptive_err) / len(adaptive_err)) ** 0.5
        fixed_rmse = (sum(e * e for e in fixed_err) / len(fixed_err)) ** 0.5
        assert adaptive_rmse < fixed_rmse, (
            f"at theta {true_theta}: adaptive {adaptive_rmse:.3f} "
            f"vs fixed {fixed_rmse:.3f}"
        )


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def test_calibration_declines_without_enough_responses():
    """An author who wrote the item had a view about its difficulty, and a
    dozen responses is not evidence enough to overrule it."""
    item = irt.Item(id=1, a=1.3, b=0.0)
    responses = [(0.0, True)] * 10
    assert irt.calibrate_item(item, responses) is None


def test_calibration_recovers_a_misjudged_difficulty():
    """The loop's whole purpose: an author who knows the answer cannot see what
    is hard about the question, and is reliably wrong in one direction."""
    true_item = irt.Item(id=1, a=1.3, b=1.4, c=0.25)
    authored = irt.Item(id=1, a=1.3, b=-0.2, c=0.25)   # author guessed far too easy

    rng = random.Random(4)
    responses = []
    for _ in range(400):
        theta = rng.gauss(0, 1.2)
        responses.append((theta, rng.random() < irt.probability(theta, true_item)))

    result = irt.calibrate_item(authored, responses)
    assert result is not None
    assert result.b == pytest.approx(true_item.b, abs=0.5)
    assert result.b > authored.b
    # The drift is what a reviewer is shown, so it has to be the real distance
    # travelled from the authored value rather than from wherever the item
    # happened to sit last time calibration ran.
    assert result.b_shift == pytest.approx(result.b - authored.b, abs=1e-9)
    assert result.b_shift > 1.0
    assert result.responses == len(responses)
    assert "harder" in result.note


def test_calibration_is_pulled_back_towards_the_author_when_data_are_thin():
    """Shrinkage, and the reason the prior exists: 25 responses should move the
    estimate without letting it run to wherever the noise points."""
    authored = irt.Item(id=1, a=1.3, b=0.0, c=0.25)
    rng = random.Random(5)
    true_item = irt.Item(id=1, a=1.3, b=2.0, c=0.25)

    thin = [
        (t, rng.random() < irt.probability(t, true_item))
        for t in (rng.gauss(0, 1.2) for _ in range(25))
    ]
    plenty = [
        (t, rng.random() < irt.probability(t, true_item))
        for t in (rng.gauss(0, 1.2) for _ in range(600))
    ]

    near = irt.calibrate_item(authored, thin)
    far = irt.calibrate_item(authored, plenty)
    assert abs(near.b - authored.b) < abs(far.b - authored.b)


def test_calibration_clamps_discrimination_to_a_sane_range():
    """A single miskeyed item must not be able to swing an estimate on its own."""
    authored = irt.Item(id=1, a=1.3, b=0.0, c=0.25)
    rng = random.Random(6)
    # A perfectly deterministic item implies infinite discrimination.
    responses = [(t, t > 0.0) for t in (rng.gauss(0, 1.2) for _ in range(300))]
    result = irt.calibrate_item(authored, responses)
    assert irt.MIN_DISCRIMINATION <= result.a <= irt.MAX_DISCRIMINATION


def test_bank_information_reports_where_a_bank_is_blind():
    """Item count is the wrong question on its own — twenty items all pitched at
    L3 measure L3 well and nothing else at all."""
    clumped = [irt.Item(id=i, a=1.3, b=0.0) for i in range(20)]
    spread = bank(n=20)

    at_middle = irt.level_to_theta(3.0)
    at_bottom = irt.level_to_theta(1.5)

    assert irt.test_information(clumped, at_middle) > irt.test_information(
        spread, at_middle
    )
    assert irt.test_information(spread, at_bottom) > irt.test_information(
        clumped, at_bottom
    )
    assert irt.se_from_information(0.0) == irt.PRIOR_SD
    assert irt.se_from_information(100.0) < 0.2
