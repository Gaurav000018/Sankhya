"""Tests for the promotion simulator.

The thing under guard here is honesty. A simulator that flatters — crediting a
course the officer has already outgrown, or counting a competency the role never
asked for — produces a plan someone follows for six months and gets nowhere. So
most of these assert that a step is worth *nothing* and says so.
"""

import pytest

from app.models_learning import Course
from app.services.competency import GapItem
from app.services.simulator import COURSE_YIELD, _weighted_readiness, simulate


def course(cid: int, competency_id: int, level_from: float, level_to: float,
           title: str = "A course", hours: float = 8.0) -> Course:
    c = Course(
        source=None, external_id=f"X{cid}", title=title, description="",
        level_from=level_from, level_to=level_to, duration_hours=hours,
        competency_id=competency_id,
    )
    c.id = cid
    return c


def gap(competency_id: int, current: float, required: float,
        criticality: str = "high", name: str = "A competency") -> GapItem:
    return GapItem(
        competency_id=competency_id, competency_code=f"C{competency_id}",
        competency_name=name, domain="technical",
        current_level=current, required_level=required,
        gap=round(max(0.0, required - current), 2),
        criticality=criticality, status="critical", evidence_count=4,
        evidence_weight=1.0, strongest_source="quiz", last_evidence_at=None,
    )


class FakeDB:
    """Enough Session surface for simulate(): get() and scalars()."""

    def __init__(self, courses, competency_names, role=None):
        self._courses = {c.id: c for c in courses}
        self._names = competency_names
        self._role = role

    def get(self, model, pk):
        if model is Course:
            return self._courses.get(pk)
        return self._role

    def scalars(self, _stmt):
        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        class _Competency:
            def __init__(self, cid, name):
                self.id, self.name = cid, name

        return _Result([_Competency(k, v) for k, v in self._names.items()])


def run(gaps, courses, course_ids, monkeypatch):
    monkeypatch.setattr("app.services.simulator.analyse_gaps",
                        lambda db, **kw: gaps)
    db = FakeDB(courses, {g.competency_id: g.competency_name for g in gaps})
    return simulate(db, user=object(), course_ids=course_ids, target_role_id=1)


class TestWeightedReadiness:
    def test_meeting_every_requirement_is_a_hundred(self):
        gaps = [gap(1, 3.0, 3.0), gap(2, 4.0, 4.0)]
        assert _weighted_readiness(gaps, {1: 3.0, 2: 4.0}) == 100.0

    def test_exceeding_a_requirement_does_not_score_above_a_hundred(self):
        """Being brilliant at one thing does not cover a shortfall in another."""
        gaps = [gap(1, 5.0, 3.0), gap(2, 1.0, 4.0)]
        assert _weighted_readiness(gaps, {1: 5.0, 2: 1.0}) < 100.0

    def test_critical_competencies_weigh_more(self):
        critical_short = [gap(1, 1.0, 4.0, "critical"), gap(2, 4.0, 4.0, "low")]
        trivial_short = [gap(1, 4.0, 4.0, "critical"), gap(2, 1.0, 4.0, "low")]
        assert (_weighted_readiness(critical_short, {1: 1.0, 2: 4.0})
                < _weighted_readiness(trivial_short, {1: 4.0, 2: 1.0}))


class TestSimulation:
    def test_a_course_moves_the_level_by_the_yield_not_the_headline(self, monkeypatch):
        """Course completion is weak evidence, so the projection is discounted."""
        gaps = [gap(1, 2.0, 4.0)]
        result = run(gaps, [course(10, 1, 2.0, 4.0)], [10], monkeypatch)
        step = result["steps"][0]
        assert step["level_after"] == pytest.approx(2.0 + 2.0 * COURSE_YIELD)
        assert step["level_after"] < 4.0, "must not promise the full band"

    def test_only_the_part_above_the_officer_counts(self, monkeypatch):
        gaps = [gap(1, 3.0, 5.0)]
        result = run(gaps, [course(10, 1, 1.0, 4.0)], [10], monkeypatch)
        # Headroom is 4.0 - 3.0, not 4.0 - 1.0.
        assert result["steps"][0]["level_after"] == pytest.approx(3.0 + 1.0 * COURSE_YIELD)

    def test_a_course_below_the_officer_gains_nothing_and_explains_why(self, monkeypatch):
        gaps = [gap(1, 3.5, 5.0)]
        result = run(gaps, [course(10, 1, 1.0, 2.0)], [10], monkeypatch)
        step = result["steps"][0]
        assert step["level_after"] == step["level_before"]
        assert step["readiness_gain"] == 0.0
        assert step["note"] and "already at" in step["note"]

    def test_two_courses_over_the_same_band_do_not_stack(self, monkeypatch):
        """The second is applied to where the first left the officer, not to the
        original level — otherwise a plan of six overlapping courses reads as a
        guaranteed promotion."""
        gaps = [gap(1, 2.0, 5.0)]
        courses = [course(10, 1, 2.0, 4.0, "First"), course(11, 1, 2.0, 4.0, "Second")]
        result = run(gaps, courses, [10, 11], monkeypatch)
        first, second = result["steps"]
        assert second["level_before"] == first["level_after"]
        assert second["level_after"] - second["level_before"] < \
            first["level_after"] - first["level_before"]

    def test_a_competency_the_role_does_not_need_is_reported_not_dropped(self, monkeypatch):
        gaps = [gap(1, 2.0, 4.0)]
        courses = [course(10, 1, 2.0, 4.0), course(11, 99, 1.0, 5.0, "Unrelated")]
        result = run(gaps, courses, [10, 11], monkeypatch)
        assert len(result["steps"]) == 1
        assert len(result["excluded"]) == 1
        assert result["excluded"][0]["title"] == "Unrelated"
        assert "does not require" in result["excluded"][0]["reason"]

    def test_an_unknown_course_id_is_reported(self, monkeypatch):
        result = run([gap(1, 2.0, 4.0)], [], [404], monkeypatch)
        assert result["excluded"][0]["course_id"] == 404

    def test_raising_a_competency_past_what_the_role_asks_adds_no_readiness(
            self, monkeypatch):
        """The level genuinely rises; readiness does not, because readiness is
        measured against what the role demands."""
        gaps = [gap(1, 3.0, 3.0), gap(2, 1.0, 4.0)]
        result = run(gaps, [course(10, 1, 3.0, 5.0)], [10], monkeypatch)
        step = result["steps"][0]
        assert step["level_after"] > step["level_before"]
        assert step["readiness_gain"] == 0.0
        assert step["note"] and "does not move readiness" in step["note"]

    def test_the_projection_is_labelled_as_one(self, monkeypatch):
        result = run([gap(1, 2.0, 4.0)], [course(10, 1, 2.0, 4.0)], [10], monkeypatch)
        assert "not a commitment" in result["caveat"]

    def test_no_role_requirements_is_an_error_not_a_perfect_score(self, monkeypatch):
        result = run([], [], [], monkeypatch)
        assert "error" in result
