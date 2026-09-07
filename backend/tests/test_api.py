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
    def test_answer_key_is_withheld_while_the_attempt_is_open(self, client, learner):
        response = client.post("/quizzes", json={"item_count": 3}, headers=learner)
        if response.status_code == 409:
            pytest.skip("no approved questions in this database")
        attempt = response.json()
        assert all(item["correct_index"] is None for item in attempt["items"])
        assert all(item["explanation"] is None for item in attempt["items"])

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
