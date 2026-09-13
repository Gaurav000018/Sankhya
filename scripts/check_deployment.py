"""Diagnose a deployed SANKHYA instance from the outside.

    python scripts/check_deployment.py https://your-project.vercel.app

Walks the same chain a browser does when someone tries to sign in, and stops at
the first thing that is actually broken. "I cannot log in" has about six
distinct causes that look identical in the browser — no API behind the
frontend, a missing rewrite, CORS, an unseeded database, an unconfirmed
account, a genuinely wrong password — and this says which one it is.

Nothing here needs credentials or access to the deployment. It only reads
public endpoints and makes one deliberately-wrong sign-in attempt.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

TIMEOUT = 15


class Stop(Exception):
    """A failure specific enough that later checks would only add noise."""


def _request(url: str, method: str = "GET", body: dict | None = None,
             origin: str | None = None) -> tuple[int, dict, str]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data:
        request.add_header("Content-Type", "application/json")
    if origin:
        # Makes it a cross-origin request, which is what reveals a CORS problem.
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers), response.read().decode()[:600]
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode()[:600]
    except Exception as exc:
        raise Stop(f"{type(exc).__name__}: {exc}") from exc


def _json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        return {}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    site = sys.argv[1].rstrip("/")
    api = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else f"{site}/api"

    print(f"\n  site : {site}")
    print(f"  api  : {api}")
    print("  " + "-" * 62)

    # 1. Is the frontend itself up, and does it serve deep links?
    try:
        status, _, _ = _request(site)
        print(f"  {'ok ' if status == 200 else 'FAIL'}  frontend responds ({status})")
    except Stop as exc:
        print(f"  FAIL  frontend unreachable — {exc}")
        return 1

    status, _, _ = _request(f"{site}/verify?token=probe")
    if status == 200:
        print("  ok   deep links serve index.html")
    else:
        print(f"  FAIL  /verify returned {status}, expected 200")
        print("        The SPA rewrite is missing. Every confirmation and")
        print("        password-reset link from an email will 404.")
        print("        Fix: frontend/vercel.json must be picked up — check that")
        print("        the Vercel project's Root Directory is `frontend`.")

    # 2. Is there an API behind it at all? This is the usual answer.
    try:
        status, _, text = _request(f"{api}/health")
    except Stop as exc:
        print(f"\n  FAIL  no API at {api} — {exc}")
        print("\n        Vercel hosts the frontend only. Nothing is serving the")
        print("        API, so every sign-in fails before it reaches a password")
        print("        check. Deploy backend/Dockerfile.prod somewhere that runs")
        print("        containers, then point /api/* at it. See VERCEL.md.")
        return 1

    if status != 200:
        print(f"\n  FAIL  {api}/health returned {status}")
        if status == 404:
            print("\n        The frontend is up but /api/* goes nowhere — the")
            print("        rewrite to your API host is missing from vercel.json,")
            print("        or VITE_API_BASE_URL was not set at build time.")
        print(f"        body: {text[:200]}")
        return 1

    env = _json(text).get("env", "?")
    print(f"  ok   API responds (env={env})")
    if env != "production":
        print(f"       ! APP_ENV is '{env}', not 'production'. The startup checks")
        print("         that enforce a real JWT secret and CORS are only warnings")
        print("         in this mode.")

    # 3. Can the API reach its database? No database, no users.
    status, _, text = _request(f"{api}/health/ready")
    ready = _json(text)
    detail = ready.get("detail", ready)
    database = detail.get("database", "?")
    email = detail.get("email", "?")

    if database == "ok":
        print("  ok   database reachable")
    else:
        print(f"  FAIL  database {database}")
        print("        The API is running but cannot reach Postgres. Check")
        print("        DATABASE_URL, and that the database allows connections")
        print("        from the API's host.")
        return 1

    print(f"  {'ok  ' if email == 'resend' else '!   '} email: {email}")
    if email != "resend":
        print("        EMAIL_ENABLED is false, so confirmation links are logged")
        print("        rather than sent — nobody can complete registration.")

    # 4. Does a sign-in attempt reach the password check?
    #    A deliberately wrong password against an address that should exist.
    origin = site
    status, headers, text = _request(
        f"{api}/auth/login",
        method="POST",
        body={"email": "venkatesan@sankhya.gov.in", "password": "deliberately-wrong"},
        origin=origin,
    )
    allow = headers.get("Access-Control-Allow-Origin")

    print("  " + "-" * 62)
    if allow:
        print(f"  ok   CORS allows {allow}")
    else:
        print("  !    no Access-Control-Allow-Origin on the response")
        print(f"       If the browser calls the API cross-origin, add {origin}")
        print("       to CORS_ORIGINS on the API and restart it. (Harmless if")
        print("       you are using a same-origin /api/* rewrite.)")

    if status == 401:
        print("\n  ==> The API is healthy and the sign-in path works.")
        print("      A wrong password was correctly rejected, which means the")
        print("      seeded demo account EXISTS in your database.\n")
        print("      Sign in with:  venkatesan@sankhya.gov.in / Sankhya@2026")
        print("      (also director.esd@ / sme@ / admin@sankhya.gov.in)")
        return 0

    if status == 429:
        print("\n  ==> Rate limited. Earlier failed attempts tripped the limiter;")
        print("      it clears within 15 minutes. Not a configuration problem.")
        return 0

    if status == 403:
        print("\n  ==> That account exists but is NOT CONFIRMED.")
        print("      Open the confirmation link, or use /auth/verify/resend.")
        return 0

    if status == 500:
        print(f"\n  FAIL  the API errored: {text[:300]}")
        return 1

    print("\n  ==> The demo accounts do not exist in this database.")
    print(f"      (login returned {status}, not the 401 a real-but-wrong")
    print("      password would give.)\n")
    print("      Your production database is empty. Credentials are rows in")
    print("      Postgres, not environment variables — there is no env var that")
    print("      creates a login. Either:\n")
    print("        a) Seed the demo corpus (DROPS every table first):")
    print("             docker run --rm --env-file .env sankhya-api:prod \\")
    print("               python -m app.seed.seed\n")
    print("        b) Register a real account at /register with a gov.in or")
    print("           nic.in address. This needs EMAIL_ENABLED=true and a")
    print("           working RESEND_API_KEY, or the confirmation link is only")
    print("           written to the API's log.")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Stop as exc:
        print(f"\n  FAIL  {exc}")
        raise SystemExit(1)
