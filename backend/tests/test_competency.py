"""Tests for the derivation engine.

These run without a database — `derive_level` and friends operate on evidence
objects, not on a session. That is deliberate: the reliability model is the part
most likely to be argued with, so it should be the easiest part to check.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import EvidenceSource, ProficiencyEvidence
from app.services.competency import (
    DEFAULT_LEVEL,
    EVIDENCE_HALF_LIFE_DAYS,
    GAP_AT_RISK,
    SOURCE_WEIGHTS,
    _status_for,
    derive_level,
    evidence_weight,
)

NOW = datetime.now(timezone.utc)


def ev(level, source, days_ago=0, confidence=1.0):
    return ProficiencyEvidence(
        user_id=1,
        competency_id=1,
        level_estimate=level,
        confidence=confidence,
        source=source,
        created_at=NOW - timedelta(days=days_ago),
    )


class TestDeriveLevel:
    def test_no_evidence_gives_default_and_no_confidence(self):
        result = derive_level([])
        assert result.level == DEFAULT_LEVEL
        assert result.evidence_count == 0
        assert not result.is_confident

    def test_single_observation_returns_that_level(self):
        result = derive_level([ev(3.4, EvidenceSource.QUIZ)])
        assert result.level == pytest.approx(3.4, abs=0.01)
        assert result.evidence_count == 1
        assert result.strongest_source == EvidenceSource.QUIZ

    def test_demonstrated_work_outweighs_self_assessment(self):
        """The central claim of the reliability model.

        An officer self-rates 5 and performs at 2 on a real task. The derived
        level must sit close to the demonstrated result, not midway.
        """
        result = derive_level([
            ev(5.0, EvidenceSource.SELF),
            ev(2.0, EvidenceSource.SIMULATION),
        ])
        assert result.level < 2.6, (
            f"self-assessment pulled the level to {result.level}; "
            "demonstrated performance should dominate"
        )

    def test_recent_evidence_outweighs_stale_evidence(self):
        result = derive_level([
            ev(2.0, EvidenceSource.QUIZ, days_ago=int(EVIDENCE_HALF_LIFE_DAYS * 3)),
            ev(4.0, EvidenceSource.QUIZ, days_ago=0),
        ])
        assert result.level > 3.6

    def test_low_confidence_observation_counts_for_less(self):
        strong = derive_level([ev(2.0, EvidenceSource.QUIZ), ev(4.0, EvidenceSource.QUIZ)])
        weak = derive_level([
            ev(2.0, EvidenceSource.QUIZ, confidence=0.1),
            ev(4.0, EvidenceSource.QUIZ, confidence=1.0),
        ])
        assert weak.level > strong.level

    def test_retraction_by_zero_confidence_removes_influence(self):
        """There is no delete path. Confidence 0 is how a row is withdrawn."""
        with_retracted = derive_level([
            ev(4.0, EvidenceSource.QUIZ),
            ev(1.0, EvidenceSource.QUIZ, confidence=0.0),
        ])
        assert with_retracted.level == pytest.approx(4.0, abs=0.01)

    def test_level_is_clamped_to_the_frac_scale(self):
        assert derive_level([ev(9.0, EvidenceSource.QUIZ)]).level <= 5.0
        assert derive_level([ev(-3.0, EvidenceSource.QUIZ)]).level >= 1.0

    def test_thin_evidence_is_not_reported_as_confident(self):
        """One weak, stale, low-confidence observation is not a competency claim."""
        result = derive_level([
            ev(4.0, EvidenceSource.SELF, days_ago=900, confidence=0.3)
        ])
        assert not result.is_confident

    def test_strongest_source_is_the_heaviest_not_the_latest(self):
        result = derive_level([
            ev(3.0, EvidenceSource.SIMULATION, days_ago=10),
            ev(3.0, EvidenceSource.SELF, days_ago=0),
        ])
        assert result.strongest_source == EvidenceSource.SIMULATION


class TestEvidenceWeight:
    def test_weight_ordering_matches_the_published_table(self):
        """The weights are shown in the UI, so their ordering is a contract."""
        ordered = [
            EvidenceSource.SIMULATION,
            EvidenceSource.QUIZ,
            EvidenceSource.DIAGNOSTIC,
            EvidenceSource.INTERVIEW,
            EvidenceSource.CERTIFICATION,
            EvidenceSource.SUPERVISOR,
            EvidenceSource.LEARNING_ACTIVITY,
            EvidenceSource.HISTORICAL,
            EvidenceSource.SELF,
        ]
        weights = [SOURCE_WEIGHTS[s] for s in ordered]
        assert weights == sorted(weights, reverse=True)

    def test_course_completion_is_weak_evidence_of_skill(self):
        assert SOURCE_WEIGHTS[EvidenceSource.LEARNING_ACTIVITY] < SOURCE_WEIGHTS[EvidenceSource.QUIZ]

    def test_halves_at_the_half_life(self):
        fresh = evidence_weight(ev(3.0, EvidenceSource.QUIZ, days_ago=0), NOW)
        aged = evidence_weight(
            ev(3.0, EvidenceSource.QUIZ, days_ago=int(EVIDENCE_HALF_LIFE_DAYS)), NOW
        )
        assert aged == pytest.approx(fresh / 2, rel=0.02)


class TestGapStatus:
    @pytest.mark.parametrize(
        "gap,expected",
        [(2.2, "critical"), (2.0, "critical"), (1.4, "at_risk"),
         (0.5, "near_target"), (0.05, "met"), (0.0, "met")],
    )
    def test_thresholds(self, gap, expected):
        assert _status_for(gap) == expected

    def test_at_risk_boundary_is_inclusive(self):
        assert _status_for(GAP_AT_RISK) == "at_risk"


class TestHistoricalDerivation:
    """`as_of` reconstructs the level as it stood on a past date.

    Both halves matter: evidence recorded later must be excluded, AND decay must
    be measured from that date. Getting only the first half right applies months
    of extra decay to evidence that was fresh at the time, which quietly
    understates every historical level and inflates every reported improvement.
    """

    def test_later_evidence_is_excluded(self):
        as_of = NOW - timedelta(days=100)
        result = derive_level(
            [ev(2.0, EvidenceSource.QUIZ, days_ago=200),
             ev(5.0, EvidenceSource.QUIZ, days_ago=10)],
            as_of=as_of,
        )
        assert result.level == pytest.approx(2.0, abs=0.01)
        assert result.evidence_count == 1

    def test_decay_is_measured_from_the_reference_date(self):
        """Evidence one day old at the reference date should barely have decayed,
        even though it is a year old today."""
        as_of = NOW - timedelta(days=365)
        fresh_then = derive_level(
            [ev(4.0, EvidenceSource.QUIZ, days_ago=366)], as_of=as_of
        )
        assert fresh_then.total_weight > 0.8, (
            f"weight {fresh_then.total_weight} — decay is being measured from today, "
            "not from the reference date"
        )

    def test_no_evidence_before_the_date_gives_the_default(self):
        result = derive_level(
            [ev(4.0, EvidenceSource.QUIZ, days_ago=10)],
            as_of=NOW - timedelta(days=100),
        )
        assert result.level == DEFAULT_LEVEL and result.evidence_count == 0

    def test_omitting_as_of_uses_everything(self):
        rows = [ev(2.0, EvidenceSource.QUIZ, days_ago=200),
                ev(4.0, EvidenceSource.QUIZ, days_ago=10)]
        assert derive_level(rows).evidence_count == 2

    def test_improvement_is_visible_between_two_dates(self):
        rows = [ev(2.0, EvidenceSource.QUIZ, days_ago=300),
                ev(4.5, EvidenceSource.SIMULATION, days_ago=20)]
        then = derive_level(rows, as_of=NOW - timedelta(days=180))
        assert derive_level(rows).level > then.level
