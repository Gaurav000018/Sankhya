"""Tests for citation verification, candidate parsing and quality flags.

Citation verification is the integrity claim of the whole quiz module, so it
gets the most attention here: a fabricated quote must fail, and a legitimately
reflowed one must not.
"""

import pytest

from app.ml.ingest import Page, chunk_pages
from app.services.quizgen import (
    Candidate,
    normalise,
    parse_candidates,
    quality_flags,
    verify_citation,
)

PASSAGE = (
    "Design weights are the inverse of the probability of selection at each "
    "stage of the sample. Where non-response occurs, a further adjustment is "
    "applied so that the responding units represent the non-responding ones. "
    "Ignoring these weights produces biased estimates and understated standard "
    "errors."
)


class TestCitationVerification:
    def test_exact_quote_verifies(self):
        assert verify_citation(
            PASSAGE,
            "Design weights are the inverse of the probability of selection at each stage of the sample.",
        )

    def test_fabricated_quote_is_rejected(self):
        """The failure this module exists to prevent: a plausible sentence that
        is not in the source."""
        check = verify_citation(
            PASSAGE,
            "Design weights should always be recomputed annually by the state office.",
        )
        assert not check
        assert "does not appear" in check.reason

    def test_reflowed_whitespace_still_verifies(self):
        """Models drop line breaks and double spaces. That does not make the
        citation false."""
        assert verify_citation(
            PASSAGE,
            "Ignoring these weights   produces biased estimates\nand understated standard errors.",
        )

    def test_curly_quotes_and_dashes_do_not_break_it(self):
        chunk = "The officer's report — dated March — was revised accordingly."
        assert verify_citation(chunk, "The officer’s report — dated March — was revised accordingly.")

    def test_case_difference_still_verifies(self):
        assert verify_citation(PASSAGE, "DESIGN WEIGHTS ARE THE INVERSE OF THE PROBABILITY OF SELECTION")

    def test_short_quote_is_rejected(self):
        """'the sample' appears in almost any passage and proves nothing."""
        check = verify_citation(PASSAGE, "the sample")
        assert not check and "too short" in check.reason

    @pytest.mark.parametrize("quote", ["", "   ", None])
    def test_missing_quote_is_rejected(self, quote):
        assert not verify_citation(PASSAGE, quote)

    def test_elided_quote_verifies_when_both_halves_are_real(self):
        assert verify_citation(
            PASSAGE,
            "Design weights are the inverse of the probability ... produces biased estimates",
        )

    def test_elision_cannot_smuggle_in_an_invented_half(self):
        check = verify_citation(
            PASSAGE,
            "Design weights are the inverse of the probability ... and must be signed off by the Director",
        )
        assert not check

    def test_elided_halves_must_appear_in_order(self):
        """Otherwise a quote could reverse the meaning of the source."""
        assert not verify_citation(
            PASSAGE,
            "produces biased estimates and understated standard errors ... Design weights are the inverse",
        )

    def test_normalise_is_idempotent(self):
        once = normalise(PASSAGE)
        assert normalise(once) == once


class TestCandidateParsing:
    def test_parses_a_well_formed_reply(self):
        raw = """{"questions": [{"stem": "What are design weights?",
          "options": ["Inverse selection probability", "Sample size", "A constant"],
          "correct_index": 0, "citation_quote": "Design weights are the inverse"}]}"""
        candidates = parse_candidates(raw)
        assert len(candidates) == 1 and candidates[0].correct_index == 0

    def test_recovers_from_a_code_fence(self):
        raw = '```json\n{"questions": [{"stem": "Q?", "options": ["a","b","c"], "correct_index": 1}]}\n```'
        assert len(parse_candidates(raw)) == 1

    @pytest.mark.parametrize("raw", ["", "not json", "{}", '{"questions": "nope"}'])
    def test_unusable_output_yields_nothing(self, raw):
        assert parse_candidates(raw) == []

    def test_drops_an_item_with_too_few_options(self):
        raw = '{"questions": [{"stem": "Q?", "options": ["only one"], "correct_index": 0}]}'
        assert parse_candidates(raw) == []

    def test_drops_an_item_whose_answer_index_is_out_of_range(self):
        """Silently clamping would change which option is marked correct."""
        raw = '{"questions": [{"stem": "Q?", "options": ["a","b","c"], "correct_index": 7}]}'
        assert parse_candidates(raw) == []

    def test_drops_an_item_with_a_non_numeric_index(self):
        raw = '{"questions": [{"stem": "Q?", "options": ["a","b","c"], "correct_index": "first"}]}'
        assert parse_candidates(raw) == []

    def test_keeps_good_items_alongside_bad_ones(self):
        raw = """{"questions": [
          {"stem": "Good?", "options": ["a","b","c"], "correct_index": 0},
          {"stem": "Bad?", "options": ["a"], "correct_index": 0}]}"""
        assert [c.stem for c in parse_candidates(raw)] == ["Good?"]


class TestQualityFlags:
    def make(self, **kw) -> Candidate:
        base = dict(stem="Which statement about design weights is correct?",
                    options=["Inverse of selection probability", "The sample size",
                             "A fixed constant", "The response rate"],
                    correct_index=0, explanation="Because they invert selection probability.")
        base.update(kw)
        return Candidate(**base)

    def test_clean_question_has_no_flags(self):
        assert quality_flags(self.make()) == []

    def test_flags_duplicate_options(self):
        flags = quality_flags(self.make(options=["Same", "Same", "Other", "Another"]))
        assert "Duplicate options" in flags

    def test_flags_all_of_the_above(self):
        flags = quality_flags(self.make(options=["A", "B", "C", "All of the above"]))
        assert any("above" in f for f in flags)

    def test_flags_a_giveaway_long_correct_option(self):
        """Test-wise officers pick the longest option. That is a defect."""
        flags = quality_flags(self.make(
            options=["A very long and carefully qualified correct answer that "
                     "explains itself at length", "No", "Maybe", "Never"],
            correct_index=0,
        ))
        assert any("longer" in f for f in flags)

    def test_flags_missing_explanation(self):
        assert "No explanation provided" in quality_flags(self.make(explanation=""))

    def test_flags_absolute_wording(self):
        flags = quality_flags(self.make(stem="Design weights are always applied before editing?"))
        assert any("Absolute" in f for f in flags)


class TestChunking:
    def test_chunks_never_span_pages(self):
        """A citation names one page; a passage crossing two makes that a lie."""
        pages = [Page(1, "alpha. " * 200), Page(2, "beta. " * 200)]
        for chunk in chunk_pages(pages):
            assert not ("alpha" in chunk.text and "beta" in chunk.text)

    def test_short_page_still_produces_a_citable_chunk(self):
        chunks = chunk_pages([Page(1, "A short but complete paragraph about weighting. " * 4)])
        assert len(chunks) == 1 and chunks[0].page == 1

    def test_ordinals_are_sequential(self):
        chunks = chunk_pages([Page(1, "para one. " * 150), Page(2, "para two. " * 150)])
        assert [c.ordinal for c in chunks] == list(range(len(chunks)))

    def test_empty_input_is_safe(self):
        assert chunk_pages([]) == []


class TestGeneratorRetriesForAVerifiableQuote:
    """A question whose quote is not in the passage is discarded, so a batch
    where none verify is a wasted passage. Observed with qwen2.5:3b: it writes a
    good question and omits `citation_quote` entirely."""

    PASSAGE = (
        "Design weights are the reciprocal of the selection probability. They "
        "must be adjusted for non-response before estimation begins."
    )

    def _generator(self, responses):
        from app.ml.generator import OllamaGenerator

        generator = OllamaGenerator(model="test-model")
        generator._sent = []

        def _fake(prompt):
            generator._sent.append(prompt)
            return responses[min(len(generator._sent) - 1, len(responses) - 1)]

        generator._generate = _fake
        return generator

    def _payload(self, quote):
        import json

        return json.dumps({"questions": [{
            "stem": "What are design weights?",
            "options": ["The reciprocal of the selection probability",
                        "The sample size", "The stratum count", "The variance"],
            "correct_index": 0,
            "explanation": "Stated in the passage.",
            "citation_quote": quote,
            "bloom_level": "understand",
        }]})

    def test_a_missing_quote_triggers_one_retry(self):
        good = "Design weights are the reciprocal of the selection probability."
        generator = self._generator([self._payload(""), self._payload(good)])
        result = generator.generate(self.PASSAGE, competency="Sampling",
                                    count=1, bloom="understand")
        assert len(generator._sent) == 2, "should have asked a second time"
        assert result[0].citation_quote == good

    def test_the_retry_says_what_was_wrong(self):
        generator = self._generator([self._payload(""), self._payload("")])
        generator.generate(self.PASSAGE, competency="Sampling", count=1,
                           bloom="understand")
        assert "word for word" in generator._sent[1]

    def test_a_verifiable_quote_first_time_is_not_retried(self):
        good = "They must be adjusted for non-response before estimation begins."
        generator = self._generator([self._payload(good)])
        generator.generate(self.PASSAGE, competency="Sampling", count=1,
                           bloom="understand")
        assert len(generator._sent) == 1, "a good batch must not cost a second call"

    def test_a_paraphrased_quote_counts_as_unverifiable(self):
        """The point of the citation is that it is copied, not summarised."""
        paraphrase = "Design weights are one over the probability of selection."
        generator = self._generator([self._payload(paraphrase), self._payload(paraphrase)])
        generator.generate(self.PASSAGE, competency="Sampling", count=1,
                           bloom="understand")
        assert len(generator._sent) == 2

    def test_we_never_fill_the_quote_in_ourselves(self):
        """Repairing the citation locally would make verification check our own
        work rather than the model's."""
        generator = self._generator([self._payload(""), self._payload("")])
        result = generator.generate(self.PASSAGE, competency="Sampling", count=1,
                                    bloom="understand")
        assert all(not (c.citation_quote or "").strip() for c in result)
