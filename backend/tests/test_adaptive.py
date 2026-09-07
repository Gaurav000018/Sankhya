"""Tests for adaptive question selection and follow-up validation.

The interview writes competency evidence from questions the model invented
mid-session, with nobody reviewing them first. Most of what is asserted here is
therefore about what the system *refuses* to do with that output.
"""

import pytest

from app.ml.followup import FollowUp, parse_followup
from app.models_interview import AnswerScore, InterviewAnswer, InterviewQuestion
from app.services.adaptive import (
    GENERATED_CONFIDENCE_FACTOR,
    MAX_PER_COMPETENCY,
    MIN_CONFIDENCE_TO_ADAPT,
    _classify,
    evidence_confidence,
)


def answer(knowledge=None, confidence=0.8, missed=None) -> InterviewAnswer:
    a = InterviewAnswer()
    if knowledge is not None:
        score = AnswerScore()
        score.knowledge = knowledge
        score.knowledge_confidence = confidence
        score.missed_points = missed or []
        a.score = score
    return a


class TestWhatTheLastAnswerDecides:
    def test_a_strong_answer_pushes_further(self):
        assert _classify(answer(knowledge=4.5)) == "extend"

    def test_a_weak_answer_steps_back_to_the_foundation(self):
        assert _classify(answer(knowledge=1.5)) == "ground"

    def test_a_middling_answer_with_a_gap_is_probed(self):
        assert _classify(answer(knowledge=3.0, missed=["design weights"])) == "probe"

    def test_a_middling_answer_that_covered_everything_moves_on(self):
        assert _classify(answer(knowledge=3.0, missed=[])) == "move_on"

    def test_an_unscored_answer_opens_rather_than_guessing(self):
        assert _classify(answer()) == "open"

    def test_a_verdict_the_judge_could_not_parse_does_not_steer_the_interview(self):
        """A degraded verdict carries confidence 0 and knowledge 1.0. Reading
        that as 'they struggled' would spend the rest of the session asking
        remedial questions because a model call failed."""
        degraded = answer(knowledge=1.0, confidence=0.0)
        assert _classify(degraded) == "move_on"
        assert _classify(degraded) != "ground"

    def test_the_confidence_floor_is_what_separates_the_two(self):
        just_below = answer(knowledge=1.0, confidence=MIN_CONFIDENCE_TO_ADAPT - 0.01)
        just_above = answer(knowledge=1.0, confidence=MIN_CONFIDENCE_TO_ADAPT + 0.01)
        assert _classify(just_below) == "move_on"
        assert _classify(just_above) == "ground"


class TestGeneratedQuestionsWeighLess:
    def test_an_approved_question_keeps_its_confidence(self):
        bank = InterviewQuestion(prompt="q", is_generated=False)
        assert evidence_confidence(bank, 0.8) == 0.8

    def test_a_generated_question_is_discounted(self):
        """No SME has agreed that it measures the competency it is filed under."""
        generated = InterviewQuestion(prompt="q", is_generated=True)
        assert evidence_confidence(generated, 0.8) == pytest.approx(
            0.8 * GENERATED_CONFIDENCE_FACTOR
        )

    def test_the_discount_never_flips_the_sign_or_exceeds_the_original(self):
        generated = InterviewQuestion(prompt="q", is_generated=True)
        for value in (0.0, 0.15, 0.5, 1.0):
            discounted = evidence_confidence(generated, value)
            assert 0.0 <= discounted <= value

    def test_a_missing_question_does_not_crash_evidence_writing(self):
        assert evidence_confidence(None, 0.7) == 0.7


class TestOneCompetencyCannotEatTheSession:
    def test_the_cap_leaves_room_for_other_competencies(self):
        """With a budget of 6 and a cap of 3, at least two competencies are
        reached however badly the officer does on the first."""
        assert MAX_PER_COMPETENCY < 6


class TestFollowUpValidation:
    """The follow-up is shown to an officer and its answer becomes evidence, so
    unusable output has to be detectable rather than merely unlikely."""

    def _payload(self, question, **extra):
        import json

        return json.dumps({"question": question, "expected_points": ["a point"],
                           "rationale": "because", **extra})

    def test_a_well_formed_question_parses(self):
        result = parse_followup(self._payload(
            "How would you choose between proportional and Neyman allocation?"
        ))
        assert isinstance(result, FollowUp)
        assert result.expected_points == ["a point"]

    def test_an_imperative_counts_as_a_question(self):
        assert parse_followup(self._payload(
            "Describe how you would verify that frame against field data."
        )) is not None

    def test_a_statement_is_rejected(self):
        """A follow-up that is not a question leaves the officer with nothing to
        answer, and the recording that follows is scored against it anyway."""
        assert parse_followup(self._payload(
            "Stratified sampling is a useful technique for official statistics."
        )) is None

    def test_an_empty_question_is_rejected(self):
        assert parse_followup(self._payload("")) is None

    def test_a_one_word_question_is_rejected(self):
        assert parse_followup(self._payload("Why?")) is None

    def test_an_essay_is_rejected(self):
        assert parse_followup(self._payload("Why " + "and so on " * 100 + "?")) is None

    def test_unparseable_output_returns_none_rather_than_raising(self):
        for junk in ("", "   ", "not json at all", "{broken", "[1,2,3]", "null"):
            assert parse_followup(junk) is None

    def test_a_fenced_block_is_tolerated(self):
        raw = '```json\n{"question": "What is a sampling frame?"}\n```'
        result = parse_followup(raw)
        assert result is not None and result.prompt == "What is a sampling frame?"

    def test_the_rationale_is_carried_through_for_the_officer(self):
        result = parse_followup(self._payload(
            "What is a sampling frame?", rationale="Going back to the basics here."
        ))
        assert result.rationale == "Going back to the basics here."


class TestCameraMetricsStayWithTheOfficer:
    """A supervisor can legitimately open a subordinate's interview. The camera
    block must not be in what they receive.

    This was wrong once: the guarantee existed only as a sentence in a
    docstring, while `build_report` returned the block to whoever asked.
    """

    def items(self):
        return [
            {"answer_id": 1, "attention": {"screen_gaze_ratio": 0.6}},
            {"answer_id": 2, "attention": None},
            {"answer_id": 3},
        ]

    def test_the_officer_keeps_their_own_camera_feedback(self):
        from app.services.interview import apply_officer_only_redaction

        items = self.items()
        apply_officer_only_redaction(items, viewer_id=7, officer_id=7)
        assert items[0]["attention"] == {"screen_gaze_ratio": 0.6}

    def test_a_supervisor_does_not_receive_it(self):
        from app.services.interview import apply_officer_only_redaction

        items = self.items()
        apply_officer_only_redaction(items, viewer_id=99, officer_id=7)
        assert "attention" not in items[0]

    def test_omitting_the_viewer_withholds_rather_than_discloses(self):
        """Fail closed: a caller that forgets to say who is asking gets the safe
        answer, not the officer's camera data."""
        from app.services.interview import apply_officer_only_redaction

        items = self.items()
        apply_officer_only_redaction(items, viewer_id=None, officer_id=7)
        assert "attention" not in items[0]

    def test_redaction_leaves_everything_else_alone(self):
        from app.services.interview import apply_officer_only_redaction

        items = self.items()
        apply_officer_only_redaction(items, viewer_id=99, officer_id=7)
        assert [i["answer_id"] for i in items] == [1, 2, 3]
