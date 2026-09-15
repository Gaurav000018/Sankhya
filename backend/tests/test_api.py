"""API-level tests against a real database.

The other test modules cover pure functions. These cover the layer where most
real bugs have actually turned up in this project: RBAC leaks, answer keys
reaching the wrong role, and endpoints that return an empty list where they
should return an error.

Skipped automatically when no database is reachable, so `pytest` still runs on a
laptop with nothing started.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine

PASSWORD = "Sankhya@2026"
LEARNER = "venkatesan@sankhya.gov.in"
SUPERVISOR = "director.esd@sankhya.gov.in"
SME = "sme@sankhya.gov.in"
ADMIN = "admin@sankhya.gov.in"


def database_ready() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM users LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not database_ready(),
    reason="needs a seeded database: docker compose up -d && "
    "docker compose exec api python -m app.seed.seed",
)


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def token_for(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def learner(client):
    return auth(token_for(client, LEARNER))


@pytest.fixture(scope="module")
def supervisor(client):
    return auth(token_for(client, SUPERVISOR))


@pytest.fixture(scope="module")
def sme(client):
    return auth(token_for(client, SME))


@pytest.fixture(scope="module")
def admin(client):
    return auth(token_for(client, ADMIN))


class TestAuthBoundary:
    def test_unauthenticated_is_rejected(self, client):
        assert client.get("/skill-twin/me").status_code == 401

    def test_a_forged_token_is_rejected(self, client):
        assert client.get("/skill-twin/me", headers=auth("not.a.token")).status_code == 401

    def test_wrong_password_does_not_leak_whether_the_account_exists(self, client):
        real = client.post("/auth/login", json={"email": LEARNER, "password": "wrong"})
        fake = client.post("/auth/login", json={"email": "nobody@x.gov.in", "password": "wrong"})
        assert real.status_code == fake.status_code == 401
        assert real.json()["detail"] == fake.json()["detail"]


class TestRoleBoundaries:
    """Every one of these is a leak if it regresses."""

    def test_learner_cannot_read_the_review_queue(self, client, learner):
        assert client.get("/questions/review-queue", headers=learner).status_code == 403

    def test_learner_cannot_read_national_analytics(self, client, learner):
        assert client.get("/analytics/overview", headers=learner).status_code == 403

    def test_learner_cannot_read_the_acbp(self, client, learner):
        assert client.get("/analytics/acbp", headers=learner).status_code == 403

    def test_supervisor_cannot_read_the_acbp(self, client, supervisor):
        """Division-level access does not imply ministry-level access."""
        assert client.get("/analytics/acbp", headers=supervisor).status_code == 403

    def test_learner_cannot_record_evidence(self, client, learner):
        me = client.get("/auth/me", headers=learner).json()
        response = client.post(
            "/evidence",
            json={"user_id": me["id"], "competency_id": 1, "level_estimate": 5,
                  "source": "self"},
            headers=learner,
        )
        assert response.status_code == 403

    def test_learner_cannot_upload_material(self, client, learner):
        response = client.post(
            "/materials",
            data={"title": "x", "competency_id": "1"},
            files={"file": ("a.txt", b"text", "text/plain")},
            headers=learner,
        )
        assert response.status_code == 403

    def test_supervisor_can_see_their_own_division(self, client, supervisor):
        assert client.get("/team/officers", headers=supervisor).status_code == 200


class TestSkillTwin:
    def test_every_competency_is_reported(self, client, learner):
        """Unmeasured competencies are reported at the default level, not dropped."""
        body = client.get("/skill-twin/me", headers=learner).json()
        assert len(body["competencies"]) == 12
        assert all("is_confident" in c for c in body["competencies"])

    def test_gaps_are_ranked_widest_first(self, client, learner):
        gaps = client.get("/gaps/me", headers=learner).json()
        assert gaps == sorted(gaps, key=lambda g: g["gap"], reverse=True)

    def test_unknown_target_role_is_an_error_not_an_empty_list(self, client, learner):
        """An empty gap list reads as 'you are ready', which is the worst
        possible wrong answer to a promotion question."""
        assert client.get("/gaps/me?target_role_id=999999", headers=learner).status_code == 404

    def test_evidence_is_append_only_with_no_delete_route(self, client, learner):
        me = client.get("/auth/me", headers=learner).json()
        assert client.delete(f"/evidence/{me['id']}", headers=learner).status_code in (404, 405)


class TestQuiz:
    """The adaptive assessment's contract with the browser.

    An adaptive test hands out one question at a time, which makes the key a
    sharper problem than it was for a fixed paper: the client now holds exactly
    the question on screen, so anything leaked is the answer to what the officer
    is looking at.
    """

    def _start(self, client, learner):
        response = client.post("/quizzes", json={}, headers=learner)
        if response.status_code == 409:
            pytest.skip("no approved questions in this database")
        assert response.status_code == 201
        return response.json()

    def test_the_open_question_carries_no_answer_key(self, client, learner):
        attempt = self._start(client, learner)
        item = attempt["current_item"]
        assert item is not None
        # Asserted as an absence of *fields*, not as null values: a future
        # serialiser that added `correct_index` set to the real key would pass a
        # None check written the other way round.
        assert "correct_index" not in item
        assert "explanation" not in item
        assert "distractor_rationale" not in item

    def test_no_item_list_is_handed_over_up_front(self, client, learner):
        """There is no item list to leak, because question seven depends on
        answer six. A client that received one could read ahead."""
        attempt = self._start(client, learner)
        assert "items" not in attempt

    def test_the_key_is_released_only_for_the_item_just_answered(self, client, learner):
        attempt = self._start(client, learner)
        item = attempt["current_item"]
        answer = client.post(
            f"/quizzes/{attempt['id']}/answer",
            json={"question_id": item["question_id"], "selected_index": 0},
            headers=learner,
        )
        assert answer.status_code == 200
        body = answer.json()

        assert body["graded"]["question_id"] == item["question_id"]
        assert body["graded"]["correct_index"] is not None
        if body["next_item"] is not None:
            assert "correct_index" not in body["next_item"]

    def test_answering_a_question_that_is_not_open_is_refused(self, client, learner):
        """Almost always a stale tab or a double submit. It must not be able to
        score against whichever question the client names."""
        attempt = self._start(client, learner)
        response = client.post(
            f"/quizzes/{attempt['id']}/answer",
            json={"question_id": 999999, "selected_index": 0},
            headers=learner,
        )
        assert response.status_code == 409

    def test_the_estimate_always_arrives_with_its_interval(self, client, learner):
        """A level reported without its width is a point estimate presented as a
        fact, which twelve multiple-choice items do not support."""
        attempt = self._start(client, learner)
        ability = attempt["ability"]
        assert ability["level_low"] <= ability["level"] <= ability["level_high"]
        assert ability["se"] > 0

    def test_an_attempt_belongs_to_the_officer_who_opened_it(self, client, learner, sme):
        attempt = self._start(client, learner)
        assert client.get(f"/quizzes/{attempt['id']}", headers=sme).status_code == 403

    def test_reloading_re_serves_the_same_question(self, client, learner):
        """Resuming must not re-choose. An officer who reloads the page cannot
        be allowed to shop for an easier item."""
        attempt = self._start(client, learner)
        again = client.get(f"/quizzes/{attempt['id']}", headers=learner).json()
        assert (
            again["current_item"]["question_id"]
            == attempt["current_item"]["question_id"]
        )

    def test_learners_never_receive_a_draft_question(self, client, learner):
        for question in client.get("/questions/approved", headers=learner).json():
            assert question["status"] == "approved"

    def test_the_answer_key_is_stripped_for_learners(self, client, learner):
        for question in client.get("/questions/approved", headers=learner).json():
            assert question["correct_index"] is None

    def test_an_sme_still_sees_the_key(self, client, sme):
        approved = client.get("/questions/approved", headers=sme).json()
        if not approved:
            pytest.skip("no approved questions in this database")
        assert any(q["correct_index"] is not None for q in approved)


class TestCameraAndGestureSubmission:
    """Exercised over HTTP. The endpoint once raised on every call — a bad
    keyword to the audit writer — and nothing noticed, because every earlier
    check wrote camera rows straight into the database."""

    PAYLOAD = {
        "screen_gaze_ratio": 0.7, "longest_look_away_seconds": 3.0, "look_away_count": 1,
        "blink_rate_per_minute": 17.0, "head_stability": 0.8, "face_present_ratio": 0.9,
        "frames_analysed": 300, "hands_visible_ratio": 0.6, "hand_movement": 0.4,
        "face_touch_count": 2, "consent_version": "camera-coaching-v1",
    }

    def _open(self, client, learner):
        interview = client.post("/interviews", json={}, headers=learner)
        if interview.status_code != 201:
            pytest.skip("no interview question bank in this database")
        body = interview.json()
        return body["interview_id"], body["questions"][0]["answer_id"]

    def test_the_officer_can_submit_camera_and_gesture_aggregates(self, client, learner):
        interview_id, answer_id = self._open(client, learner)
        response = client.post(
            f"/interviews/{interview_id}/answers/{answer_id}/attention",
            json=self.PAYLOAD, headers=learner,
        )
        assert response.status_code == 202, response.text
        assert response.json()["quality"] == "good"

    def test_an_out_of_range_aggregate_is_refused(self, client, learner):
        """Aggregates are validated at the schema, not trusted from the browser."""
        interview_id, answer_id = self._open(client, learner)
        response = client.post(
            f"/interviews/{interview_id}/answers/{answer_id}/attention",
            json={**self.PAYLOAD, "face_touch_count": -1}, headers=learner,
        )
        assert response.status_code == 422

    def test_a_supervisor_cannot_submit_on_an_officers_behalf(self, client, learner, supervisor):
        interview_id, answer_id = self._open(client, learner)
        response = client.post(
            f"/interviews/{interview_id}/answers/{answer_id}/attention",
            json=self.PAYLOAD, headers=supervisor,
        )
        assert response.status_code in (403, 404)


class TestInterviewContract:
    def test_no_composite_score_field_exists(self, client, learner):
        interview = client.post("/interviews", json={}, headers=learner)
        if interview.status_code != 201:
            pytest.skip("no interview question bank in this database")
        body = interview.json()
        banned = {"overall", "composite", "total_score", "final_score"}
        assert not banned & set(body)
        assert set(body["axes"]) == {
            "knowledge", "structure", "communication", "fluency", "confidence",
        }

    def test_the_report_carries_its_own_disclosure(self, client, learner):
        interview = client.post("/interviews", json={}, headers=learner)
        if interview.status_code != 201:
            pytest.skip("no interview question bank in this database")
        note = interview.json()["disclosure"]["note"].lower()
        assert "five independent axes" in note


class TestGovernanceOutput:
    def test_acbp_is_labelled_a_draft(self, client, admin):
        body = client.get("/analytics/acbp", headers=admin).json()
        assert body["status"] == "draft"
        assert "not an approved plan" in body["caveat"]

    def test_course_efficacy_states_the_correlation_caveat(self, client, admin):
        body = client.get("/analytics/course-efficacy", headers=admin).json()
        assert "correlational, not causal" in body["caveat"]

    def test_unmeasured_courses_are_not_scored_as_zero(self, client, admin):
        for course in client.get("/analytics/course-efficacy", headers=admin).json()["courses"]:
            if course["measured"] == 0:
                assert course["median_lift"] is None


class TestEvidenceReport:
    def test_report_is_a_pdf_with_a_verification_hash(self, client, learner):
        response = client.get("/reports/evidence/me", headers=learner)
        assert response.status_code == 200
        assert response.content[:5] == b"%PDF-"
        assert len(response.headers["x-verification-hash"]) == 64

    def test_a_learner_cannot_pull_another_officers_report(self, client, learner, supervisor):
        other = client.get("/auth/me", headers=supervisor).json()
        assert client.get(f"/reports/evidence/{other['id']}", headers=learner).status_code == 403


class TestAdminLearnerRecords:
    """The administrator's per-officer screen.

    This is the only place the platform shows a named person's assessment
    history, which makes it the place where a scope leak would matter most and
    the place where two screens disagreeing about a number would be most
    damaging.
    """

    def test_a_learner_cannot_read_the_roster(self, client, learner):
        assert client.get("/admin/learners", headers=learner).status_code == 403

    def test_a_learner_cannot_read_another_officers_record(self, client, learner, admin):
        roster = client.get("/admin/learners?page_size=1", headers=admin).json()
        officer_id = roster["learners"][0]["user_id"]
        assert (
            client.get(f"/admin/learners/{officer_id}", headers=learner).status_code == 403
        )

    def test_a_supervisor_sees_only_their_own_division(self, client, supervisor, admin):
        everyone = client.get("/admin/learners?page_size=1", headers=admin).json()
        theirs = client.get("/admin/learners?page_size=1", headers=supervisor).json()
        assert theirs["scope"] == "own division"
        assert theirs["total"] < everyone["total"]

    def test_a_supervisor_cannot_widen_scope_with_a_filter(
        self, client, supervisor, admin
    ):
        """`division_id` is a request, not an authorisation. A supervisor asking
        for another division must still get their own."""
        filters = client.get("/admin/filters", headers=admin).json()
        own = client.get("/admin/learners?page_size=1", headers=supervisor).json()

        other = next(
            (
                d for d in filters["divisions"]
                if d["name"]
                != (
                    client.get("/auth/me", headers=supervisor).json().get("division")
                )
            ),
            None,
        )
        if other is None:
            pytest.skip("only one division in this database")

        widened = client.get(
            f"/admin/learners?division_id={other['id']}&page_size=1",
            headers=supervisor,
        ).json()
        assert widened["total"] == own["total"]

    def test_a_supervisor_is_offered_only_their_own_division_as_a_filter(
        self, client, supervisor
    ):
        """The filter list itself discloses the shape of the organisation."""
        filters = client.get("/admin/filters", headers=supervisor).json()
        assert len(filters["divisions"]) <= 1

    def test_a_missing_officer_is_a_404_not_a_500(self, client, admin):
        assert client.get("/admin/learners/999999", headers=admin).status_code == 404

    def test_roster_readiness_matches_the_officers_own_figure(self, client, admin):
        """One definition of readiness, or the roster and the officer's own
        dashboard will disagree and a supervisor will conclude one is broken.

        The roster computes it in SQL for speed and the detail page calls
        `competency.role_readiness`. This is what stops the two drifting.
        """
        roster = client.get("/admin/learners?page_size=5", headers=admin).json()
        assert roster["learners"], "no officers in this database"

        for row in roster["learners"]:
            detail = client.get(
                f"/admin/learners/{row['user_id']}", headers=admin
            ).json()
            assert detail["summary"]["readiness"] == pytest.approx(
                row["readiness"], abs=0.15
            ), f"readiness disagrees for {row['full_name']}"
            assert detail["summary"]["critical_gaps"] == row["critical_gaps"]

    def test_the_record_carries_the_evidence_behind_every_level(self, client, admin):
        """A level with no evidence trail is an assertion. The officer's own
        screens show the trail; an administrator's must show the same one."""
        roster = client.get("/admin/learners?page_size=1", headers=admin).json()
        detail = client.get(
            f"/admin/learners/{roster['learners'][0]['user_id']}", headers=admin
        ).json()

        assert detail["competencies"]
        assert "evidence" in detail
        for competency in detail["competencies"]:
            assert "current_level" in competency
            assert "required_level" in competency
            assert "evidence_count" in competency

    def test_there_is_no_write_path_to_an_officers_record(self, client, admin):
        """Levels are derived from evidence. An administrator who could edit one
        directly would break the audit trail the design rests on."""
        roster = client.get("/admin/learners?page_size=1", headers=admin).json()
        officer_id = roster["learners"][0]["user_id"]
        for method in (client.patch, client.put, client.delete):
            assert method(f"/admin/learners/{officer_id}").status_code in (401, 404, 405)

    def test_reading_a_record_is_written_to_the_audit_log(self, client, admin):
        """Reading a named officer's assessment history is a privileged act
        against someone who cannot see that it happened."""
        from sqlalchemy import text as sql_text

        from app.db import engine

        roster = client.get("/admin/learners?page_size=1", headers=admin).json()
        officer_id = roster["learners"][0]["user_id"]

        with engine.connect() as conn:
            before = conn.execute(
                sql_text(
                    "SELECT count(*) FROM audit_log WHERE action = 'admin.learner_viewed'"
                )
            ).scalar_one()

        client.get(f"/admin/learners/{officer_id}", headers=admin)

        with engine.connect() as conn:
            after = conn.execute(
                sql_text(
                    "SELECT count(*) FROM audit_log WHERE action = 'admin.learner_viewed'"
                )
            ).scalar_one()

        assert after == before + 1


class TestAdminRecordQueryCost:
    """The officer record must not cost more to render the more an officer has
    done.

    Every relationship this page walks — an attempt's responses, an interview's
    answers, each answer's score — lazy-loads one query per row by default. It
    is invisible on seed data and quadratic in irritation on a real deployment:
    twenty interviews of six answers is a hundred and forty queries to draw a
    card showing three numbers. Asserted rather than trusted, because removing
    an `selectinload` breaks nothing that a functional test would notice.
    """

    def _count_queries(self, fn):
        from sqlalchemy import event

        from app.db import engine

        seen = {"n": 0}

        def _tick(*_args, **_kwargs):
            seen["n"] += 1

        event.listen(engine, "before_cursor_execute", _tick)
        try:
            fn()
        finally:
            event.remove(engine, "before_cursor_execute", _tick)
        return seen["n"]

    def test_rendering_a_record_does_not_scale_with_the_officers_history(self):
        from sqlalchemy import func, select

        from app.db import SessionLocal
        from app.models import User
        from app.models_quiz import AttemptStatus, QuizAttempt
        from app.services import admin as admin_service

        db = SessionLocal()
        try:
            busiest = db.execute(
                select(QuizAttempt.user_id, func.count())
                .where(QuizAttempt.status == AttemptStatus.SUBMITTED)
                .group_by(QuizAttempt.user_id)
                .order_by(func.count().desc())
                .limit(1)
            ).first()
            if busiest is None:
                pytest.skip("no submitted assessments in this database")

            user_id, attempts = busiest
            officer = db.get(User, user_id)

            detail = None

            def render():
                nonlocal detail
                db.expire_all()
                detail = admin_service.learner_detail(db, user=officer)

            queries = self._count_queries(render)

            # The bound is a fixed number of statements, not a function of how
            # much this officer has done — which is the whole property. Left
                # lazy, the same call runs roughly one query per attempt, per
            # interview and per interview answer on top of this.
            assert queries < 40, (
                f"{queries} queries for an officer with {attempts} assessments "
                f"and {len(detail.evidence)} evidence rows — an eager load has "
                f"probably been dropped"
            )
        finally:
            db.close()
