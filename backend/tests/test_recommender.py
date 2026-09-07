"""Tests for the ranking signals and the lexical embedder.

`level_fit` gets the most attention: recommending a course that starts above
where an officer is, or ends below what the role needs, is the failure that
makes people stop trusting a recommender.
"""

import pytest

from app.ml.embeddings import HashingEmbedder, cosine, tokenise
from app.models_learning import Course
from app.services.competency import GapItem
from app.services.recommender import build_reason, level_fit, urgency
from app.services.recommender import Scored


def course(level_from: float, level_to: float, **kw) -> Course:
    return Course(
        source=kw.get("source"), external_id="X", title=kw.get("title", "A course"),
        description="", level_from=level_from, level_to=level_to,
        duration_hours=kw.get("hours", 6.0), competency_id=kw.get("competency_id", 1),
    )


def gap(current: float, required: float, **kw) -> GapItem:
    return GapItem(
        competency_id=1, competency_code="TECH-GIS", competency_name="GIS & Spatial Analysis",
        domain="technical", current_level=current, required_level=required,
        gap=round(max(0.0, required - current), 2),
        criticality=kw.get("criticality", "high"),
        status=kw.get("status", "critical"),
        evidence_count=kw.get("evidence_count", 5),
        evidence_weight=1.2, strongest_source=kw.get("strongest_source", "interview"),
        last_evidence_at=None,
    )


class TestLevelFit:
    def test_course_covering_the_whole_gap_scores_highest(self):
        assert level_fit(course(1.5, 4.0), 1.8, 4.0) == pytest.approx(1.0, abs=0.01)

    def test_course_entirely_below_the_officer_is_useless(self):
        """Already past it: an L1-2 course does nothing for someone at L3."""
        assert level_fit(course(1.0, 2.0), 3.0, 4.0) == 0.0

    def test_course_entirely_above_the_officer_is_useless(self):
        assert level_fit(course(4.5, 5.0), 1.8, 4.0) == 0.0

    def test_course_starting_well_above_the_officer_is_penalised(self):
        """Both cover the same span, but one strands the officer at the start."""
        reachable = level_fit(course(1.8, 3.5), 1.8, 4.0)
        stranding = level_fit(course(3.2, 4.9), 1.8, 4.0)
        assert reachable > stranding

    def test_partial_coverage_scores_between(self):
        partial = level_fit(course(1.5, 3.0), 1.8, 4.0)
        assert 0 < partial < 1

    def test_no_gap_means_no_fit(self):
        assert level_fit(course(1.0, 5.0), 4.0, 4.0) == 0.0
        assert level_fit(course(1.0, 5.0), 4.5, 4.0) == 0.0


class TestUrgency:
    def test_wider_gaps_are_more_urgent(self):
        assert urgency(gap(1.0, 4.0)) > urgency(gap(3.5, 4.0))

    def test_criticality_raises_urgency_for_the_same_gap(self):
        assert urgency(gap(2.0, 4.0, criticality="critical")) > urgency(
            gap(2.0, 4.0, criticality="low")
        )

    def test_urgency_is_bounded(self):
        assert 0.0 <= urgency(gap(1.0, 5.0, criticality="critical")) <= 1.0


class TestReason:
    def test_names_the_competency_and_both_levels(self):
        item = Scored(course=course(1.5, 4.0), gap=gap(1.8, 4.0), score=0.8,
                      signals={"level_fit": 0.9, "peers": 0.0})
        reason = build_reason(item, "Deputy Director", peer_count=0)
        assert "GIS & Spatial Analysis" in reason
        assert "L1.8" in reason and "L4.0" in reason
        assert "Deputy Director" in reason

    def test_does_not_invent_a_peer_claim_without_peers(self):
        item = Scored(course=course(1.5, 4.0), gap=gap(1.8, 4.0), score=0.8,
                      signals={"level_fit": 0.9, "peers": 0.0})
        assert "officers in your role" not in build_reason(item, "Deputy Director", 0)

    def test_states_the_peer_count_when_there_is_one(self):
        item = Scored(course=course(1.5, 4.0), gap=gap(1.8, 4.0), score=0.8,
                      signals={"level_fit": 0.9, "peers": 0.4})
        assert "7 other officers" in build_reason(item, "Deputy Director", 7)

    def test_warns_when_the_course_starts_above_the_officer(self):
        item = Scored(course=course(3.5, 4.8), gap=gap(1.8, 4.0), score=0.4,
                      signals={"level_fit": 0.2, "peers": 0.0})
        assert "after the earlier course" in build_reason(item, "Deputy Director", 0)

    def test_flags_a_critical_competency(self):
        item = Scored(course=course(1.5, 4.0), gap=gap(1.8, 4.0, criticality="critical"),
                      score=0.8, signals={"level_fit": 0.9, "peers": 0.0})
        assert "critical" in build_reason(item, "Deputy Director", 0)


class TestLexicalEmbedder:
    def setup_method(self):
        self.embedder = HashingEmbedder()

    def test_identical_text_is_identical(self):
        a = self.embedder.embed("geo-spatial sampling frames")
        assert cosine(a, self.embedder.embed("geo-spatial sampling frames")) == pytest.approx(1.0, abs=1e-6)

    def test_shared_vocabulary_scores_higher_than_unrelated_text(self):
        gis = self.embedder.embed("spatial data handling with QGIS raster vector layers")
        related = self.embedder.embed("geo-spatial sampling frames using satellite imagery")
        unrelated = self.embedder.embed("national accounts deflators and base year revision")
        assert cosine(gis, related) > cosine(gis, unrelated)

    def test_is_deterministic_across_calls(self):
        assert self.embedder.embed("index numbers") == self.embedder.embed("index numbers")

    def test_empty_text_does_not_divide_by_zero(self):
        assert cosine(self.embedder.embed(""), self.embedder.embed("anything")) == 0.0

    def test_vector_has_the_expected_width(self):
        from app.models_content import EMBEDDING_DIM
        assert len(self.embedder.embed("weighting")) == EMBEDDING_DIM

    def test_reports_itself_as_lexical_not_semantic(self):
        """It matches shared words, not meaning. Saying otherwise would oversell it."""
        assert self.embedder.is_semantic is False

    def test_stopwords_are_dropped(self):
        assert "the" not in tokenise("the survey and the frame")

    def test_cosine_handles_mismatched_or_missing_vectors(self):
        assert cosine(None, [1.0]) == 0.0
        assert cosine([1.0, 0.0], [1.0]) == 0.0


class TestRelevanceFloorBelongsToTheEmbedder:
    """The floor is a property of the similarity scale, not of the recommender.

    A fixed 0.20 was correct for the lexical embedder and, once a trained model
    replaced it, admitted every course in the catalogue — unrelated pairs score
    around 0.48 under nomic-embed-text, so nothing was ever filtered. The bug
    was invisible because the recommender still returned plausible-looking
    results, just with nonsense mixed in.
    """

    def test_every_embedder_declares_one(self):
        from app.ml.embeddings import HashingEmbedder, OllamaEmbedder

        for cls in (HashingEmbedder, OllamaEmbedder):
            assert isinstance(getattr(cls, "relevance_floor", None), float), (
                f"{cls.__name__} must declare a relevance_floor; the recommender "
                "reads it instead of hard-coding a constant"
            )

    def test_a_semantic_embedder_needs_a_higher_floor_than_a_lexical_one(self):
        """Not a style preference — a trained model puts unrelated text in a
        high, narrow band, so the same number means different things."""
        from app.ml.embeddings import HashingEmbedder, OllamaEmbedder

        assert OllamaEmbedder.relevance_floor > HashingEmbedder.relevance_floor

    def test_an_exact_competency_match_bypasses_the_floor(self):
        """A course in the right competency is relevant by definition, whatever
        its wording scores."""
        from app.models import Competency
        from app.services.recommender import relevance

        competency = Competency(name="GIS & Spatial Analysis", description="")
        competency.id = 1
        assert relevance(course(1.0, 3.0, competency_id=1), competency, None) == 1.0

    def test_an_unrelated_course_scores_below_the_semantic_floor(self):
        from app.ml.embeddings import OllamaEmbedder
        from app.models import Competency
        from app.services.recommender import relevance

        competency = Competency(name="Team Leadership", description="")
        competency.id = 2
        unrelated = course(1.0, 3.0, competency_id=99)
        unrelated.embedding = [1.0] + [0.0] * 767
        score = relevance(unrelated, competency, [0.0, 1.0] + [0.0] * 766)
        assert score < OllamaEmbedder.relevance_floor
