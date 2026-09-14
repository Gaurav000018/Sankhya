"""Technical-term detection and grounded mistake finding.

Both put words in front of an officer about their own answer, so most of these
check what the code refuses to claim.
"""

from app.ml.mistakes import (
    OllamaMistakeChecker,
    _explanation,
    candidate_pairs,
    split_sentences,
)
from app.services.coaching import build_coaching
from app.services.technical_terms import GLOSSARY, analyse_terms


class TestTechnicalTerms:
    def test_a_term_split_by_speech_recognition_still_counts(self):
        """Whisper hears "undercoverage" as "under coverage". An officer who said
        the word correctly must not be told they never used it."""
        result = analyse_terms("I would check for under coverage", "STAT-SAMP", [])
        assert "undercoverage" in result.used

    def test_hyphen_and_case_do_not_matter(self):
        result = analyse_terms("Non Response was high", "STAT-EST", [])
        assert "non-response" in result.used

    def test_a_substring_inside_another_word_is_not_a_match(self):
        """"frame" inside "frameworks" is not a mention of the sampling frame."""
        result = analyse_terms("our frameworks were reviewed", "STAT-SAMP", [])
        assert "sampling frame" not in result.used

    def test_expected_terms_come_from_the_question_not_the_whole_glossary(self):
        """An answer about frames is not short of vocabulary for not mentioning
        Neyman allocation."""
        result = analyse_terms(
            "the sampling frame was out of date", "STAT-SAMP",
            ["Refresh the sampling frame against the census"],
        )
        assert result.expected == ["sampling frame"]
        assert result.missing == []
        assert result.coverage == 1.0

    def test_missing_terms_are_reported(self):
        result = analyse_terms(
            "I would weight the data", "STAT-EST",
            ["Adjust for non-response within weighting classes"],
        )
        assert "non-response" in result.missing

    def test_no_expected_terms_means_no_coverage_figure(self):
        """None, not 0 — "nothing was expected" is not "you got none of it"."""
        assert analyse_terms("anything", "STAT-SAMP", ["Something unrelated"]).coverage is None

    def test_an_unknown_competency_yields_nothing_rather_than_crashing(self):
        assert analyse_terms("text", "NOPE", ["x"]).used == []

    def test_every_competency_has_a_glossary(self):
        for code in ("STAT-SAMP", "STAT-EST", "STAT-NAS", "STAT-INDEX", "TECH-ANL",
                     "TECH-GIS", "TECH-BIG", "TECH-VIZ", "DG-QUAL", "DG-PRIV",
                     "BEH-COMM", "BEH-LEAD"):
            assert GLOSSARY.get(code), code


class TestSentenceSplitting:
    def test_vocal_fillers_are_removed(self):
        [s] = split_sentences("Um, the design weights, uh, are inverse selection probabilities.")
        assert "um" not in s.lower().split() and "uh" not in s.lower()

    def test_so_that_is_not_mangled(self):
        """"so" is a filler at the start of a clause and a word in "so that".
        Stripping it everywhere turned a correct claim into a garbled one."""
        [s] = split_sentences(
            "I would use Neyman allocation, so that high variance strata get more sample."
        )
        assert "so that" in s

    def test_two_claims_joined_by_and_are_checked_separately(self):
        """A sentence is flagged at most once, so two wrong claims in one
        sentence would otherwise report only the first."""
        parts = split_sentences(
            "The design weights are the sample size divided by population, and "
            "non-response does not matter if the sample is large enough."
        )
        assert len(parts) == 2

    def test_short_fragments_are_not_checked(self):
        assert split_sentences("Yes. I think so.") == []


class TestCandidatePairs:
    def test_unrelated_pairs_are_never_checked(self):
        """No shared vocabulary means no contradiction worth reporting, and no
        model call spent on it."""
        pairs = candidate_pairs(
            ["The weather in Delhi was very pleasant yesterday afternoon"],
            ["Design weights are the inverse of the selection probability"],
        )
        assert pairs == []

    def test_related_pairs_are_checked_most_overlapping_first(self):
        sentences = ["Design weights are the sample size over the population",
                     "The weights were stored in a spreadsheet file"]
        pairs = candidate_pairs(
            sentences, ["Design weights are the inverse of the selection probability"]
        )
        assert pairs[0] == (0, 0)


class FakeChecker(OllamaMistakeChecker):
    """Answers from a table instead of a model."""

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.calls = []

    def _contradicts(self, fact, statement):
        self.calls.append((fact, statement))
        return self.verdicts.get((fact, statement), (False, ""))


class TestFindingMistakes:
    FACT = "Design weights are the inverse of the selection probability"

    def test_the_quote_is_the_officers_own_sentence(self):
        statement = "The design weights are the sample size divided by the population"
        checker = FakeChecker({(self.FACT, statement): (True, "Inverted.")})
        [m] = checker.find(statement, [self.FACT])
        assert m.quote == statement

    def test_the_correction_is_the_approved_fact_not_model_prose(self):
        statement = "The design weights are the sample size divided by the population"
        checker = FakeChecker({(self.FACT, statement): (True, "Anything the model says")})
        [m] = checker.find(statement, [self.FACT])
        assert m.correction == self.FACT

    def test_nothing_is_flagged_without_reference_facts(self):
        """No rubric, nothing to contradict — an unusual answer is not wrong for
        being unusual."""
        checker = FakeChecker({})
        assert checker.find("The design weights are the sample size over the population.", []) == []
        assert checker.calls == []

    def test_a_failed_check_is_skipped_not_counted_as_a_mistake(self):
        statement = "The design weights are the sample size divided by the population"
        checker = FakeChecker({(self.FACT, statement): None})
        assert checker.find(statement, [self.FACT]) == []

    def test_an_echoed_explanation_is_replaced(self):
        quote = "Non-response does not matter if the sample is large enough"
        assert _explanation(quote, quote) != quote
        assert _explanation("Weights are inverted.", quote) == "Weights are inverted."


class TestCoachingUsesThem:
    def test_a_mistake_leads_the_weaknesses(self):
        report = {"answers": [{
            "mistakes": [{"quote": "weights are n over N", "problem": "Inverted.",
                          "correction": "Weights are N over n"}],
            "technical_terms": {"used": [], "missing": []},
        }]}
        coaching = build_coaching(report)
        assert coaching.weaknesses[0].startswith('You said "weights are n over N"')

    def test_missing_terms_become_a_suggestion(self):
        report = {"answers": [{"technical_terms": {"used": [], "missing": ["non-response"]}}]}
        assert any("non-response" in s for s in build_coaching(report).suggestions)


class TestGroundedKnowledge:
    """The Knowledge rating has to agree with the coverage and mistakes shown
    next to it. A 3B judge was measured scoring 1.0 while reporting three of four
    points covered."""

    def test_good_coverage_lifts_a_contradictory_model_score(self):
        from app.services.interview import grounded_knowledge

        knowledge, grounded = grounded_knowledge(1.0, covered=3, expected=4, mistakes=0)
        assert grounded == 4.0
        assert knowledge > 2.5

    def test_a_verified_mistake_lowers_the_score(self):
        from app.services.interview import grounded_knowledge

        clean, _ = grounded_knowledge(3.0, covered=3, expected=4, mistakes=0)
        wrong, _ = grounded_knowledge(3.0, covered=3, expected=4, mistakes=2)
        assert wrong < clean

    def test_a_mistake_costs_more_than_an_omission(self):
        """Covering a point but getting it wrong is worse than leaving it out."""
        from app.services.interview import grounded_knowledge

        omitted, _ = grounded_knowledge(3.0, covered=2, expected=4, mistakes=0)
        mistaken, _ = grounded_knowledge(3.0, covered=3, expected=4, mistakes=2)
        assert mistaken < omitted + 0.5

    def test_the_score_stays_in_range(self):
        from app.services.interview import grounded_knowledge

        low, _ = grounded_knowledge(1.0, covered=0, expected=4, mistakes=4)
        high, _ = grounded_knowledge(5.0, covered=4, expected=4, mistakes=0)
        assert low == 1.0 and high == 5.0

    def test_without_expected_points_the_model_score_stands(self):
        from app.services.interview import grounded_knowledge

        assert grounded_knowledge(3.4, covered=0, expected=0, mistakes=0) == (3.4, None)
