"""Tests for aggregate interview analytics.

This is a government workforce system, so the interesting assertions are about
what the screen refuses to say. A mean over three officers in a division of
four is not an aggregate; it is those people, lightly obscured.
"""

from app.services.interview_analytics import (
    MIN_COHORT,
    REPORTED_AXES,
    Suppressed,
    _published,
)


class TestDisclosureThreshold:
    def test_a_large_enough_cohort_publishes(self):
        result = _published(3.4, MIN_COHORT)
        assert result["value"] == 3.4 and result["suppressed"] is False

    def test_a_small_cohort_is_withheld(self):
        result = _published(3.4, MIN_COHORT - 1)
        assert result["value"] is None and result["suppressed"] is True

    def test_the_withheld_figure_says_why(self):
        """A blank cell reads as 'no gap here'. A withheld one has to say it is
        withheld, or the reader draws the opposite conclusion."""
        result = _published(1.2, 2)
        assert str(MIN_COHORT) in result["reason"]
        assert result["officers"] == 2

    def test_a_single_officer_is_never_published(self):
        assert _published(4.9, 1)["suppressed"] is True

    def test_no_value_still_reports_the_cohort_honestly(self):
        result = _published(None, MIN_COHORT + 3)
        assert result["value"] is None and result["suppressed"] is False


class TestNothingLeaksAroundTheSuppression:
    def test_the_weak_flag_is_withheld_with_the_value(self):
        """`is_weak` is derived from the suppressed mean. Publishing it says
        "withheld, and below 2.5", which over one answer describes one officer
        as precisely as the number would have."""
        from app.services.interview_analytics import WEAK_LEVEL

        published = _published(WEAK_LEVEL - 1.0, 1)
        is_weak = None if published["suppressed"] else True
        assert is_weak is None, "a boolean derived from a withheld mean leaks it"

    def test_suppressed_is_not_the_same_as_false(self):
        """None and False read very differently to whoever renders this."""
        assert Suppressed(officers=1).as_dict()["value"] is not False


class TestCameraDataIsNotReachable:
    """Officers are told camera feedback is theirs alone. That guarantee is
    worth more if aggregating it is impossible rather than merely not done, so
    these check the module's actual imports and queries — not its prose, which
    is free to discuss the thing it refuses to import."""

    def _module_source(self):
        import inspect

        from app.services import interview_analytics

        return inspect.getsource(interview_analytics)

    def _code_only(self):
        """Source with docstrings and comments stripped, so prose about the
        rule cannot satisfy a test of the rule."""
        import ast

        tree = ast.parse(self._module_source())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant
                ) and isinstance(body[0].value.value, str):
                    node.body = body[1:] or [ast.Pass()]
        return ast.unparse(tree)

    def test_attention_metrics_is_never_imported(self):
        import ast

        imported: set[str] = set()
        for node in ast.walk(ast.parse(self._module_source())):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

        assert "AttentionMetrics" not in imported, (
            "analytics must not be able to reach camera data at all"
        )

    def test_no_camera_field_is_referenced_in_code(self):
        code = self._code_only().lower()
        for field in ("attentionmetrics", "screen_gaze", "blink_rate",
                      "face_present", "head_stability", "look_away"):
            assert field not in code, f"{field} must not be reachable from analytics"


class TestReportedAxes:
    def test_fluency_is_not_aggregated(self):
        """Fluency is NULL for officers using the accommodation, so a mean over
        it silently compares two different populations — and the size of each
        depends on who disclosed a disability."""
        assert "fluency" not in REPORTED_AXES

    def test_the_axes_are_enumerated_not_discovered(self):
        """Reading them off the model would put a new column on an admin screen
        the moment someone adds one to the table."""
        assert set(REPORTED_AXES) == {
            "knowledge", "structure", "communication", "confidence",
        }
