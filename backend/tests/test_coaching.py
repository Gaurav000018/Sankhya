"""Tests for the interview coaching output.

The report is the thing an officer reads. Wrong advice here is worse than no
advice, because it sends someone to spend a fortnight on the wrong course.
"""

from app.services.coaching import PRACTICE_CEILING, STRONG, WEAK, build_coaching


def report(axes=None, answers=None):
    return {
        "axes": {k: {"label": k.title(), "score": v, "answers_scored": 1}
                 for k, v in (axes or {}).items()},
        "answers": answers or [],
    }


def answer(competency_id=1, competency="Sampling", knowledge=3.0,
           missed=None, covered=None, **metrics):
    return {
        "competency_id": competency_id,
        "competency": competency,
        "scores": {"knowledge": knowledge},
        "missed_points": missed or [],
        "covered_points": covered or [],
        "metrics": {"wpm": metrics.get("wpm"), "filler_rate": metrics.get("filler_rate"),
                    "long_pause_count": metrics.get("long_pause_count", 0)},
    }


class TestStrengthsAndWeaknesses:
    def test_a_strong_axis_becomes_a_strength(self):
        coaching = build_coaching(report(axes={"knowledge": STRONG + 0.5}))
        assert any("substance" in s for s in coaching.strengths)

    def test_a_weak_axis_becomes_a_weakness_with_a_suggestion(self):
        coaching = build_coaching(report(axes={"structure": WEAK - 0.5}))
        assert coaching.weaknesses and coaching.suggestions

    def test_a_middling_axis_is_neither(self):
        coaching = build_coaching(report(axes={"knowledge": 3.2}))
        assert not any("substance" in s for s in coaching.strengths)

    def test_an_unscored_axis_is_skipped_rather_than_read_as_zero(self):
        """Fluency is None when the officer has delivery scoring switched off.
        Reading that as a failing score would penalise the accommodation."""
        coaching = build_coaching(report(axes={"fluency": None, "knowledge": 4.5}))
        assert not any("baseline" in w for w in coaching.weaknesses)

    def test_missed_points_are_named_specifically(self):
        coaching = build_coaching(report(
            answers=[answer(missed=["Non-response adjustment"])],
        ))
        assert any("Non-response adjustment" in w for w in coaching.weaknesses)

    def test_a_repeated_miss_says_how_often(self):
        coaching = build_coaching(report(answers=[
            answer(missed=["Design weights"]), answer(missed=["Design weights"]),
        ]))
        assert any("2 times" in w for w in coaching.weaknesses)

    def test_a_clean_session_says_so_without_inventing_a_weakness(self):
        coaching = build_coaching(report(axes={"knowledge": 4.6}))
        assert len(coaching.weaknesses) == 1
        assert "one interview is a handful of observations" in coaching.weaknesses[0]


class TestPracticeList:
    def test_a_weak_competency_is_recommended(self):
        coaching = build_coaching(report(
            answers=[answer(competency_id=7, competency="GIS", knowledge=2.0)],
        ))
        assert any("GIS" in p for p in coaching.practice)
        assert coaching.focus_competency_ids == [7]

    def test_a_competency_answered_well_is_never_recommended(self):
        """Ranking weakest-first and taking the top three recommended the
        officer's *best* competency whenever a session covered fewer than three."""
        coaching = build_coaching(report(answers=[
            answer(competency_id=1, competency="Weak area", knowledge=2.0),
            answer(competency_id=2, competency="Strong area", knowledge=4.3),
        ]))
        assert any("Weak area" in p for p in coaching.practice)
        assert not any("Strong area" in p for p in coaching.practice)
        assert 2 not in coaching.focus_competency_ids

    def test_the_ceiling_is_what_decides_it(self):
        below = build_coaching(report(answers=[
            answer(competency_id=1, competency="A", knowledge=PRACTICE_CEILING - 0.1),
        ]))
        above = build_coaching(report(answers=[
            answer(competency_id=1, competency="A", knowledge=PRACTICE_CEILING + 0.1),
        ]))
        assert below.focus_competency_ids == [1]
        assert above.focus_competency_ids == []

    def test_nothing_weak_still_offers_a_next_step(self):
        coaching = build_coaching(report(answers=[
            answer(competency_id=1, competency="A", knowledge=4.5),
        ]))
        assert coaching.practice
        assert "more senior target role" in coaching.practice[0]


class TestSpeechObservations:
    def test_fast_speech_is_noted_without_being_called_a_fault(self):
        coaching = build_coaching(report(answers=[answer(wpm=200.0)]))
        line = next(s for s in coaching.suggestions if "words a minute" in s)
        assert "not the score" in line

    def test_ordinary_pace_is_not_mentioned(self):
        coaching = build_coaching(report(answers=[answer(wpm=130.0)]))
        assert not any("words a minute" in s for s in coaching.suggestions)

    def test_a_high_filler_rate_explains_what_fillers_mean(self):
        coaching = build_coaching(report(answers=[answer(filler_rate=20.0)]))
        assert any("still being planned" in s for s in coaching.suggestions)

    def test_missing_metrics_do_not_crash_the_report(self):
        coaching = build_coaching(report(answers=[
            {"competency_id": 1, "competency": "A", "scores": {}, "metrics": None},
        ]))
        assert isinstance(coaching.suggestions, list)

    def test_an_empty_report_produces_a_usable_one(self):
        coaching = build_coaching({})
        assert coaching.weaknesses and coaching.practice
