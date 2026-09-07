"""End-to-end smoke test against a running stack.

    python scripts/smoke.py

Walks the demo narrative: sign in as the Deputy Director with the GIS gap, read
the Digital Skill Twin, list gaps, check divergence, and confirm that the
append-only evidence path actually moves a derived level.
"""

from __future__ import annotations

import json
import subprocess
import time
import sys
import urllib.error
import urllib.request

# The Windows console defaults to cp1252, which cannot encode the arrows and
# dashes used below. Without this the script dies inside `print` rather than in
# anything it is testing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"
LEARNER = "venkatesan@sankhya.gov.in"
SUPERVISOR = "director.esd@sankhya.gov.in"
PASSWORD = "Sankhya@2026"

passed = 0
failed = 0


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    def _decode(payload: bytes):
        # A 500 returns an HTML/plain body, not JSON. Surface it instead of
        # dying inside the test harness with a JSONDecodeError.
        try:
            return json.loads(payload or b"null")
        except json.JSONDecodeError:
            return {"raw": payload.decode(errors="replace")[:300]}

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, _decode(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, _decode(e.read())


def upload(path: str, fields: dict, filename: str, content: bytes,
           field_name: str = "file", token: str | None = None):
    """Minimal multipart POST — urllib has no helper for this."""
    boundary = "----sankhyasmoke26101"
    parts = []
    for key, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n"
            f"{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
    )
    parts.append(content + f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        BASE + path, data=body, method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"null")
        except json.JSONDecodeError:
            return e.code, {"raw": raw.decode(errors="replace")[:300]}


def raw_get(path: str, token: str | None = None):
    """Fetch a binary response. The JSON helper would mangle a PDF."""
    req = urllib.request.Request(
        BASE + path,
        headers={**({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read(), {k.lower(): v for k, v in e.headers.items()}


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}" + (f"  ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def reset_environment() -> None:
    """Reseed and clear Redis before asserting anything.

    This script appends evidence, which changes the levels it later checks, and
    it burns OTP quota. Without a reset the second run reports failures that are
    artifacts of the first — so the reset is part of the test, not a convenience.
    """
    section("Reset")
    seeded = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-m", "app.seed.seed"],
        capture_output=True, text=True,
    )
    check("Database reseeded", seeded.returncode == 0,
          seeded.stderr.strip().splitlines()[-1] if seeded.returncode else "deterministic")

    # Delete only the OTP keys. FLUSHDB would also wipe the worker heartbeat and
    # anything queued, making a running worker look offline for several seconds.
    flushed = subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "EVAL",
         "local k=redis.call('keys','otp:*') "
         "for i=1,#k do redis.call('del',k[i]) end return #k", "0"],
        capture_output=True, text=True,
    )
    check("OTP state cleared", flushed.returncode == 0,
          f"{flushed.stdout.strip()} keys removed; heartbeat left intact")


def main() -> int:
    if "--no-reset" not in sys.argv:
        reset_environment()

    section("Health")
    status, health = call("GET", "/health")
    check("API responds", status == 200, str(health))

    section("Authentication")
    status, tok = call("POST", "/auth/login", {"email": LEARNER, "password": PASSWORD})
    check("Password sign-in", status == 200 and "access_token" in tok)
    token = tok.get("access_token", "")

    status, _ = call("POST", "/auth/login", {"email": LEARNER, "password": "wrong"})
    check("Wrong password rejected", status == 401)

    status, otp = call("POST", "/auth/otp/request", {"email": LEARNER})
    check("OTP issued", status == 200 and otp.get("dev_code"), "dev mode returns the code")

    status, unknown = call("POST", "/auth/otp/request", {"email": "nobody@example.gov.in"})
    check(
        "No account enumeration",
        status == 200 and unknown.get("message") == otp.get("message"),
        "identical response for unknown address",
    )

    if otp.get("dev_code"):
        status, otp_tok = call(
            "POST", "/auth/otp/verify", {"email": LEARNER, "code": otp["dev_code"]}
        )
        check("OTP sign-in", status == 200 and "access_token" in otp_tok)

    # Redis keeps the hourly quota across runs, so a repeated smoke test will
    # legitimately hit the limit. Both outcomes are correct behaviour: an
    # unexpired code is handed back unchanged, or the quota trips. Silently
    # minting a fresh code on every resend is the bug this guards against.
    status, first = call("POST", "/auth/otp/request", {"email": LEARNER})
    status2, second = call("POST", "/auth/otp/request", {"email": LEARNER})
    if status == 200 and status2 == 200:
        check("Resend reuses the live code", first.get("dev_code") == second.get("dev_code"),
              "no second email sent")
    else:
        check("Hourly quota enforced", 429 in (status, status2),
              "limit reached — restart redis to reset")

    status, me = call("GET", "/auth/me", token=token)
    check("Identity resolves", status == 200 and me.get("email") == LEARNER,
          f"{me.get('full_name')} — {me.get('role')}")

    status, _ = call("GET", "/auth/me")
    check("Unauthenticated request rejected", status == 401)

    section("Digital Skill Twin")
    status, twin = call("GET", "/skill-twin/me", token=token)
    check("Skill Twin derived", status == 200 and len(twin.get("competencies", [])) == 12,
          f"{len(twin.get('competencies', []))} competencies")
    check("Role readiness computed", isinstance(twin.get("role_readiness"), (int, float)),
          f"{twin.get('role_readiness')}% for {twin.get('role_name')}")

    by_code = {c["competency_code"]: c for c in twin.get("competencies", [])}
    gis = by_code.get("TECH-GIS", {})
    sampling = by_code.get("STAT-SAMP", {})
    # Relative, not absolute: the demo story is "strong on statistical method,
    # weak on GIS", which must hold regardless of seed noise.
    check("GIS is the weakest area, sampling the strongest",
          gis.get("level", 9) < sampling.get("level", 0),
          f"GIS L{gis.get('level')} vs Sampling L{sampling.get('level')}")
    check("Every level carries its evidence count",
          all(c["evidence_count"] > 0 for c in twin.get("competencies", [])))

    section("Gap analysis")
    status, gaps = call("GET", "/gaps/me", token=token)
    check("Gaps returned", status == 200 and len(gaps) == 12)
    if gaps:
        check("Widest gap ranked first",
              gaps[0]["gap"] >= gaps[-1]["gap"],
              f"{gaps[0]['competency_name']} — gap {gaps[0]['gap']}")
        check("Gap statuses assigned",
              all(g["status"] in {"critical", "at_risk", "near_target", "met"} for g in gaps))

    section("Promotion readiness (same engine, target role)")
    status, roles = call("GET", "/frac/roles", token=token)
    check("FRAC ladder exposed", status == 200 and len(roles) == 6,
          " < ".join(r["code"] for r in roles))
    check("Ladder is ordered by seniority",
          [r["level_order"] for r in roles] == sorted(r["level_order"] for r in roles))

    next_role = next((r for r in roles if r["code"] == "JD"), None)
    if next_role:
        status, promo = call("GET", f"/gaps/me?target_role_id={next_role['id']}", token=token)
        check("Gaps against a target role", status == 200 and len(promo) == 12,
              f"{next_role['name']} requirements")
        if promo and gaps:
            check("A senior role demands more",
                  sum(g["gap"] for g in promo) > sum(g["gap"] for g in gaps),
                  "total gap is larger against the target role")

    status, _ = call("GET", "/gaps/me?target_role_id=9999", token=token)
    check("Unknown target role fails loudly", status == 404,
          "an empty gap list would read as 'no gaps'")

    section("Confidence-competence divergence")
    status, div = call("GET", "/divergence/me", token=token)
    check("Divergence endpoint responds", status == 200)
    flagged = {d["competency_name"] for d in div}
    check("Inflated self-rating detected", any("GIS" in n for n in flagged),
          f"{len(div)} flag(s): {', '.join(flagged) or 'none'}")

    section("Evidence is append-only")
    status, before = call("GET", "/skill-twin/me", token=token)
    gis_before = {c["competency_code"]: c for c in before["competencies"]}["TECH-GIS"]

    status, sup = call("POST", "/auth/login", {"email": SUPERVISOR, "password": PASSWORD})
    sup_token = sup.get("access_token", "")
    check("Supervisor sign-in", status == 200)

    status, learner_me = call("GET", "/auth/me", token=token)
    status, created = call(
        "POST", "/evidence",
        {
            "user_id": learner_me["id"],
            "competency_id": gis_before["competency_id"],
            "level_estimate": 4.5,
            "source": "simulation",
            "confidence": 1.0,
            "note": "smoke test — demonstrated task",
        },
        token=sup_token,
    )
    check("Supervisor can append evidence", status == 201, f"evidence id {created.get('id')}")

    status, after = call("GET", "/skill-twin/me", token=token)
    gis_after = {c["competency_code"]: c for c in after["competencies"]}["TECH-GIS"]
    check("Derived level moved", gis_after["level"] > gis_before["level"],
          f"L{gis_before['level']} -> L{gis_after['level']}")
    check("History preserved, not overwritten",
          gis_after["evidence_count"] == gis_before["evidence_count"] + 1,
          f"{gis_before['evidence_count']} -> {gis_after['evidence_count']} observations")
    check("One strong observation does not erase the record",
          gis_after["level"] < 4.5,
          "demonstrated 4.5, derived level stays below it")

    section("RBAC")
    status, _ = call(
        "POST", "/evidence",
        {"user_id": learner_me["id"], "competency_id": gis_before["competency_id"],
         "level_estimate": 5.0, "source": "self"},
        token=token,
    )
    check("Learner cannot record evidence", status == 403)

    status, sup_me = call("GET", "/auth/me", token=sup_token)
    status, _ = call("GET", f"/skill-twin/{sup_me['id']}", token=token)
    check("Learner cannot read another officer", status == 403,
          f"blocked from officer {sup_me['id']}")

    section("AI interview")
    status, iv = call("POST", "/interviews", {}, token=token)
    check("Interview started", status == 201, f"interview {iv.get('interview_id')}")

    questions = iv.get("questions", [])
    check("Questions laid out", len(questions) >= 2, f"{len(questions)} including calibration")
    check("Calibration comes first",
          bool(questions) and questions[0].get("is_baseline"),
          "fluency cannot be scored fairly before the baseline is captured")

    axes = iv.get("axes", {})
    check("Four independent axes", set(axes) == {"knowledge", "structure", "fluency", "confidence"},
          ", ".join(sorted(axes)))
    banned = {"overall", "composite", "total_score", "final_score", "score"}
    top_level = banned & set(iv)
    per_answer = set()
    for a in iv.get("answers", []):
        per_answer |= banned & set(a)
        per_answer |= banned & set(a.get("scores") or {})
    check("No composite score field exists", not (top_level | per_answer),
          f"found {top_level | per_answer}" if (top_level | per_answer)
          else "four axes and nothing that aggregates them")
    check("Report carries its own disclosure",
          "four independent axes" in (iv.get("disclosure", {}).get("note", "") or "").lower())
    check("Accommodation setting captured on the session",
          isinstance(iv.get("fluency_scoring_enabled"), bool))
    check("Baseline not yet captured", iv.get("baseline", {}).get("captured") is False)

    iv_id = iv.get("interview_id")
    answer_id = questions[0]["answer_id"] if questions else 0

    status, _ = call("POST", f"/interviews/{iv_id}/answers/{answer_id}/transcript",
                     {"transcript": "x"}, token=token)
    check("Cannot correct a transcript that does not exist yet", status in (405, 409, 422))

    status, other = call("GET", f"/interviews/{iv_id}", token=sup_token)
    check("Supervisor may view an officer's interview", status == 200)

    status, listed = call("GET", "/interviews/me", token=token)
    check("Interview appears in history", status == 200 and any(
        i["id"] == iv_id for i in listed))

    status, done = call("POST", f"/interviews/{iv_id}/complete", {}, token=token)
    check("Interview can be completed", status == 200 and done["status"] == "completed")

    check("Worker status is reported honestly",
          isinstance(iv.get("worker_online"), bool),
          f"worker_online={iv.get('worker_online')}")

    section("Recommendation engine")
    status, courses = call("GET", "/courses", token=token)
    check("Catalogue imported", status == 200 and len(courses) >= 15,
          f"{len(courses)} courses")

    status, recs = call("GET", "/recommendations/me", token=token)
    check("Recommendations generated", status == 200 and len(recs) > 0,
          f"{len(recs)} across the officer's gaps")

    if recs:
        top = recs[0]
        check("Every recommendation states its reasoning",
              all(len(r["reason"]) > 60 for r in recs))
        check("Reason names both levels",
              f"L{top['current_level']}" in top["reason"]
              and f"L{top['required_level']}" in top["reason"],
              f"current L{top['current_level']} → required L{top['required_level']}")
        check("Contributing signals exposed separately",
              {"relevance", "level_fit", "urgency", "peers"} <= set(top["signals"]),
              "not a single opaque ranking number")
        check("Recommendations ranked",
              all(recs[i]["score"] >= recs[i + 1]["score"] for i in range(len(recs) - 1)))
        check("No course recommended below the officer's level",
              all(r["course"]["level_to"] > r["current_level"] for r in recs),
              "a course you are already past is not a recommendation")

    gis = next((g for g in gaps if g["competency_code"] == "TECH-GIS"), None)
    if gis:
        status, path = call(
            "POST", f"/learning-paths?competency_id={gis['competency_id']}", {}, token=token)
        check("Learning path built", status == 201 and len(path["items"]) >= 2,
              f"{len(path['items'])} courses, {path['total_hours']}h")
        if status == 201:
            items = path["items"]
            check("Prerequisites come before what needs them",
                  items[0]["course"]["level_from"] <= items[-1]["course"]["level_from"],
                  " → ".join(str(i["course"]["level_from"]) for i in items))
            check("Only the first step is open",
                  items[0]["status"] == "available"
                  and all(i["status"] == "locked" for i in items[1:]))
            check("Path reports how far it actually gets",
                  path["reaches_level"] >= path["target_level"],
                  f"reaches L{path['reaches_level']} vs required L{path['target_level']}")
            check("A forward step is not mislabelled as a prerequisite",
                  items[-1]["included_because"] is None,
                  "the last course is a step, not an unlock")

    section("Quiz generation and SME review")
    status, sme = call("POST", "/auth/login",
                       {"email": "sme@sankhya.gov.in", "password": PASSWORD})
    sme_token = sme.get("access_token", "")
    check("SME sign-in", status == 200)

    material_text = (
        "Design weights and non-response adjustment.\n\n"
        "Design weights are the inverse of the probability of selection at each "
        "stage of a multi-stage sample. Where a selected household does not "
        "respond, a further adjustment is applied so that responding units "
        "represent the non-responding ones within the same weighting class. "
        "Ignoring these weights produces biased estimates and understated "
        "standard errors.\n\n"
        "Post-stratification aligns the weighted sample totals to known "
        "population control totals, usually drawn from the most recent census "
        "projections. This reduces variance for characteristics correlated with "
        "the control variables, but it cannot repair a frame that has omitted "
        "part of the population altogether.\n\n"
        "Increasing the sample size does not correct non-response bias. A larger "
        "sample of the same responding population estimates the wrong quantity "
        "more precisely, which is why non-response follow-up matters more than "
        "raw sample size.\n"
    ).encode()

    status, comps = call("GET", "/frac/competencies", token=sme_token)
    est = next(c for c in comps if c["code"] == "STAT-EST")
    status, mat = upload(
        "/materials",
        {"title": "Weighting and Non-response", "competency_id": str(est["id"])},
        "weighting.txt", material_text, token=sme_token,
    )
    check("SME can upload material", status == 201, f"material {mat.get('id')}")
    check("Document split into citable passages", mat.get("chunk_count", 0) >= 1,
          f"{mat.get('chunk_count')} passages, {mat.get('char_count')} chars")

    status, _ = upload("/materials", {"title": "Nope", "competency_id": str(est["id"])},
                       "x.txt", b"data", token=token)
    check("Learner cannot upload material", status == 403)

    status, _ = upload("/materials", {"title": "No competency"}, "a.txt",
                       b"text", token=sme_token)
    check("Material without a competency refused", status == 422,
          "a question with no competency could never become evidence")

    status, _ = upload("/materials", {"title": "Bad type", "competency_id": str(est["id"])},
                       "notes.exe", b"data", token=sme_token)
    check("Unsupported file type refused", status == 415)

    material_id = mat.get("id")
    status, gen = call("POST", f"/materials/{material_id}/generate",
                       {"per_chunk": 2, "bloom_level": "understand"}, token=sme_token)
    check("Generation queued", status == 202,
          f"worker_online={gen.get('worker_online')}")

    # Generation is one model call per passage, plus one retry when the model
    # returns no verifiable citation. On a GPU that is seconds; on the CPU runner
    # a passage that needs the retry has been measured at ~135s. The budget has
    # to cover the slow path or this reports a broken pipeline every time the
    # GPU is unavailable.
    drafts = []
    worker_online = gen.get("worker_online")
    waited = 0.0
    if worker_online:
        for _ in range(140):
            status, drafts = call("GET", "/questions/review-queue",
                                  token=sme_token)
            if drafts:
                break
            time.sleep(1.5)
            waited += 1.5

    if drafts:
        detail = f"{len(drafts)} awaiting review after {waited:.0f}s"
    elif not worker_online:
        detail = "no worker running — start `python -m app.worker`"
    else:
        # Saying "no worker" here once sent someone looking for a process that
        # was running the whole time.
        detail = (
            f"the worker is online but produced nothing in {waited:.0f}s — "
            "check its log, and `python scripts/check_judge.py` for the model"
        )
    check("Questions reached the review queue", bool(drafts), detail)

    if drafts:
        first = drafts[0]
        check("Every draft carries a citation",
              all(d["citation"]["quote"] for d in drafts))
        check("Nothing is published on generation",
              all(d["status"] == "draft" for d in drafts),
              "draft is not 'probably fine'")

        status, src = call("GET", f"/questions/{first['id']}/source", token=sme_token)
        check("Citation verifies against the source passage",
              status == 200 and src.get("citation_verified") is True,
              src.get("verification_detail", ""))
        check("Reviewer sees the passage, not just the quote",
              len(src.get("passage", "")) > len(src.get("quote", "")))

        status, _ = call("GET", "/questions/review-queue", token=token)
        check("Learner cannot see the review queue", status == 403)

        status, approved = call("POST", f"/questions/{first['id']}/approve",
                                {"note": "Checked against source"}, token=sme_token)
        check("SME can approve", status == 200 and approved["status"] == "approved")

        status, _ = call("POST", f"/questions/{drafts[-1]['id']}/approve", {}, token=token)
        check("Learner cannot approve", status == 403)

        status, learner_view = call("GET", "/questions/approved", token=token)
        check("Learner sees approved questions", status == 200 and learner_view)
        if learner_view:
            check("Answer key withheld from the learner",
                  all(q["correct_index"] is None for q in learner_view),
                  "the person being assessed does not get the key")
            check("Learner never sees a draft",
                  all(q["status"] == "approved" for q in learner_view))

        status, sme_view = call("GET", "/questions/approved", token=sme_token)
        check("SME still sees the answer key",
              status == 200 and any(q["correct_index"] is not None for q in sme_view))

        status, stats = call("GET", "/questions", token=sme_token)
        check("Review statistics available", status == 200 and "by_status" in stats,
              f"{stats.get('by_status')}")

    section("Governance output")
    status, plan = call("GET", "/analytics/acbp", token=sup_token)
    check("ACBP is admin-only", status == 403, "supervisors cannot see the ministry plan")

    status, admin_tok = call("POST", "/auth/login",
                             {"email": "admin@sankhya.gov.in", "password": PASSWORD})
    atok = admin_tok.get("access_token", "")

    status, plan = call("GET", "/analytics/acbp", token=atok)
    check("ACBP draft generated", status == 200 and plan["priority_areas"],
          f"{plan['totals']['priority_areas']} areas, "
          f"{plan['totals']['estimated_officer_hours']:,.0f} officer-hours")
    check("Draft is labelled a draft", plan.get("status") == "draft")
    check("Caveat travels with the payload",
          "not an approved plan" in plan.get("caveat", ""),
          "a computed plan presented as finished is worse than none")
    check("Priority areas name their target group",
          all(a["officers_short"] > 0 and a["officers_assessed"] > 0
              for a in plan["priority_areas"]))
    check("Effort is costed",
          any(a["estimated_officer_hours"] > 0 for a in plan["priority_areas"]))

    status, eff = call("GET", "/analytics/course-efficacy", token=atok)
    check("Course efficacy measured", status == 200 and eff["summary"]["measurable"] > 0,
          f"{eff['summary']['measurable']} of {eff['summary']['total']} courses")
    check("Thin samples are labelled provisional, not asserted",
          all(c["verdict"] == "provisional"
              for c in eff["courses"] if 0 < c["measured"] < 5))
    check("Courses with no evidence are not scored as zero",
          all(c["median_lift"] is None
              for c in eff["courses"] if c["measured"] == 0),
          "absence of data is not absence of effect")
    check("Correlation caveat stated",
          "correlational, not causal" in eff.get("caveat", ""))

    section("Evidence report and lift tracking")
    status, lift = call("GET", "/lift/me?days=180", token=token)
    check("Officer lift computed", status == 200 and lift["summary"]["measured"] > 0,
          f"{lift['summary']['improved']} improved, {lift['summary']['declined']} declined, "
          f"mean {lift['summary']['mean_change']:+.3f}")
    check("Historical levels are reconstructed, not interpolated",
          all("level_then" in c and "evidence_then" in c for c in lift["competencies"]),
          "each level recomputed from the evidence that existed then")
    check("Decline is explained rather than left to be read as decay of skill",
          "evidence ageing" in lift.get("note", "") or "aged" in lift.get("note", ""))

    status, wl = call("GET", "/analytics/lift", token=atok)
    check("Workforce lift is supervisor/admin only",
          call("GET", "/analytics/lift", token=token)[0] == 403)
    check("Workforce movement aggregated", status == 200 and wl["overall"]["profiles_measured"] > 0,
          f"mean {wl['overall']['mean_level_then']} -> {wl['overall']['mean_level_now']} "
          f"across {wl['overall']['profiles_measured']} profiles")
    check("Attribution caveat stated",
          "not attributable to training on its own" in wl.get("caveat", ""))

    pdf_status, pdf_bytes, pdf_headers = raw_get("/reports/evidence/me", token=token)
    check("Evidence report generated", pdf_status == 200 and pdf_bytes[:5] == b"%PDF-",
          f"{len(pdf_bytes):,} bytes")
    check("Report carries a verification hash",
          len(pdf_headers.get("x-verification-hash", "")) == 64,
          "confirms a printout matches the record")
    check("Report is offered inline with a real filename",
          ".pdf" in pdf_headers.get("content-disposition", ""))

    other_status, _, _ = raw_get("/reports/evidence/2", token=token)
    check("Learner cannot pull another officer's report", other_status == 403)

    sup_status, sup_pdf, _ = raw_get(f"/reports/evidence/{learner_me['id']}", token=sup_token)
    check("Supervisor can pull a report for their own division",
          sup_status == 200 and sup_pdf[:5] == b"%PDF-")

    section("Parichay adapter")
    status, par = call("GET", "/auth/parichay/authorize")
    check("Stub is explicit, not fake", status == 501 and par.get("status") == "adapter_stub")

    print(f"\n{'=' * 58}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'=' * 58}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
