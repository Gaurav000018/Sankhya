"""Tests for the delivery axes.

These are the fairness argument in executable form. If someone later "simplifies"
the baseline out of the fluency calculation, these fail.
"""

import pytest

from app.services.interview_scoring import (
    Baseline,
    SpeechSignal,
    compute_baseline,
    count_fillers,
    count_hedges,
    score_confidence,
    score_delivery,
    score_fluency,
)


def signal(**kw) -> SpeechSignal:
    base = dict(words=120, wpm=140.0, filler_count=4, filler_rate=3.3,
                long_pause_count=0, latency_to_first_word=1.0, hedge_count=0)
    base.update(kw)
    return SpeechSignal(**base)


class TestFairness:
    """The claims we make in the pitch, asserted."""

    def test_accent_does_not_affect_the_score(self):
        """Two officers, very different natural speaking rates, each performing
        exactly at their own baseline. They must score the same."""
        fast = score_fluency(
            signal(wpm=185.0, filler_rate=3.0),
            Baseline(wpm=185.0, filler_rate=3.0),
        )[0]
        slow = score_fluency(
            signal(wpm=105.0, filler_rate=3.0),
            Baseline(wpm=105.0, filler_rate=3.0),
        )[0]
        assert fast == slow, (
            "identical relative performance scored differently — "
            "the baseline is not cancelling out"
        )

    def test_same_absolute_fillers_score_differently_by_baseline(self):
        """The whole point: 6 fillers per 100 words is unremarkable for someone
        who always speaks that way, and a real signal for someone who doesn't."""
        habitual = score_fluency(
            signal(filler_rate=6.0), Baseline(wpm=140.0, filler_rate=6.0)
        )[0]
        unusual = score_fluency(
            signal(filler_rate=6.0), Baseline(wpm=140.0, filler_rate=1.5)
        )[0]
        assert habitual > unusual

    def test_no_baseline_means_no_fluency_score(self):
        """Scoring against a population mean is the bias the baseline removes.
        Absent a baseline we decline to score rather than guess."""
        score, notes = score_fluency(signal(), Baseline())
        assert score is None
        assert any("population" in n for n in notes)

    def test_accommodation_mode_suppresses_fluency_only(self):
        result = score_delivery(
            signal(hedge_count=2), Baseline(wpm=140.0, filler_rate=3.0),
            fluency_enabled=False,
        )
        assert result.fluency is None
        assert result.confidence is not None, (
            "disabling fluency scoring must not affect the other axes"
        )

    def test_a_single_um_does_not_punish_a_very_fluent_speaker(self):
        """Floor on the reference rate: someone whose baseline is near zero
        should not lose a point for one hesitation."""
        score = score_fluency(
            signal(filler_count=1, filler_rate=0.8),
            Baseline(wpm=140.0, filler_rate=0.1),
        )[0]
        assert score >= 4.5


class TestFluency:
    def test_more_fillers_than_usual_lowers_the_score(self):
        baseline = Baseline(wpm=140.0, filler_rate=2.0)
        steady = score_fluency(signal(filler_rate=2.0), baseline)[0]
        fumbling = score_fluency(signal(filler_rate=9.0), baseline)[0]
        assert fumbling < steady

    def test_long_pauses_lower_the_score(self):
        baseline = Baseline(wpm=140.0, filler_rate=3.0)
        assert (
            score_fluency(signal(long_pause_count=5), baseline)[0]
            < score_fluency(signal(long_pause_count=0), baseline)[0]
        )

    def test_small_rate_variation_is_free(self):
        """A 10% wobble is normal speech, not a defect."""
        baseline = Baseline(wpm=140.0, filler_rate=3.0)
        assert (
            score_fluency(signal(wpm=154.0), baseline)[0]
            == score_fluency(signal(wpm=140.0), baseline)[0]
        )

    def test_silence_is_not_scored(self):
        assert score_fluency(signal(words=0), Baseline(wpm=140.0, filler_rate=3.0))[0] is None

    def test_score_stays_on_the_scale(self):
        baseline = Baseline(wpm=140.0, filler_rate=1.0)
        worst = score_fluency(
            signal(filler_rate=90.0, long_pause_count=40, wpm=15.0,
                   latency_to_first_word=30.0),
            baseline,
        )[0]
        assert 1.0 <= worst <= 5.0


class TestConfidence:
    def test_hedging_lowers_confidence(self):
        assert score_confidence(signal(hedge_count=14))[0] < score_confidence(signal())[0]

    def test_slow_start_lowers_confidence(self):
        assert (
            score_confidence(signal(latency_to_first_word=9.0))[0]
            < score_confidence(signal(latency_to_first_word=0.5))[0]
        )

    def test_confidence_does_not_depend_on_pitch(self):
        """Deliberate: inferring emotional state from voice quality is weak
        science and does not belong on an officer's record. SpeechSignal has no
        pitch field for confidence to read."""
        assert not hasattr(signal(), "pitch_mean")


class TestBaselineDerivation:
    def test_derives_from_a_long_enough_reading(self):
        b = compute_baseline(SpeechSignal(words=90, wpm=132.0, filler_rate=2.4))
        assert b.is_usable and b.wpm == 132.0

    def test_too_short_a_reading_yields_no_baseline(self):
        assert not compute_baseline(SpeechSignal(words=8, wpm=120.0, filler_rate=1.0)).is_usable


class TestTokenCounting:
    def test_counts_english_and_hindi_fillers(self):
        assert count_fillers(["so", "um", "the", "matlab", "estimator", "uh"]) == 4

    def test_filler_counting_ignores_punctuation_and_case(self):
        assert count_fillers(["Um,", "UH.", "yes"]) == 2

    def test_counts_hedges(self):
        assert count_hedges("I think it is maybe roughly the right estimator") == 2

    @pytest.mark.parametrize("text", ["", None])
    def test_empty_transcript_is_safe(self, text):
        assert count_hedges(text) == 0
