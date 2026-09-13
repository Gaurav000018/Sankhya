from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analytics,
    auth,
    competency,
    content,
    interview,
    learning,
    onboarding,
    quiz,
)
from app.config import _require_production_settings, settings
from app.db import init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sankhya")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks, then schema.

    A production deployment refuses to boot on a misconfiguration rather than
    serving traffic with a known-public JWT secret or an open CORS policy. A
    crash loop is loud; signing tokens with `dev-only-change-me` is silent and
    every session issued that way is forgeable.
    """
    problems = _require_production_settings(settings)
    if settings.is_production and problems:
        for problem in problems:
            log.critical("Refusing to start: %s", problem)
        raise RuntimeError(
            f"{len(problems)} production setting(s) missing or unsafe — see the log above."
        )
    for problem in problems:
        log.warning("Not production-ready: %s", problem)

    if settings.is_production:
        # Migrations own the schema in production. `create_all` adds missing
        # tables but never alters existing ones, so it would silently leave a
        # renamed column behind and fail at query time instead of at deploy.
        log.info("Production: schema is managed by `alembic upgrade head`")
    else:
        init_db()

    log.info(
        "SANKHYA API ready (env=%s, email=%s, origins=%s)",
        settings.app_env,
        "resend" if settings.email_enabled else "dev/logged",
        ", ".join(settings.cors_origin_list),
    )
    yield


app = FastAPI(
    title="SANKHYA",
    description=(
        "Workforce intelligence for India's Official Statistical System. "
        "Competency is derived from append-only evidence, never declared."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Driven by CORS_ORIGINS. Never `*`: these endpoints carry an officer's
    # competency record and credentials travel with the request.
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Without this a browser on another origin cannot read the report's
    # verification hash or its filename.
    expose_headers=["X-Verification-Hash", "Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(competency.router)
app.include_router(interview.router)
app.include_router(content.router)
app.include_router(analytics.router)
app.include_router(learning.router)
app.include_router(quiz.router)
app.include_router(onboarding.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness. Deliberately does not touch the database.

    A health check that fails when Postgres blips gets the container killed
    mid-incident, which turns a brief database problem into an outage.
    """
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/ready", tags=["ops"])
def readiness() -> dict:
    """Readiness: can this instance actually serve a request?

    Checked by the load balancer before sending traffic to a new container.
    Reports the failing dependency by name and nothing about its address.
    """
    from sqlalchemy import text

    from app.db import engine

    checks: dict[str, str] = {}
    ok = True

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        ok = False

    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception:
        # Degraded, not down: the limiter fails open and OTP sign-in is one of
        # four methods. The instance can still serve everything else.
        checks["redis"] = "unavailable"

    checks["email"] = "resend" if settings.email_enabled else "disabled"

    if not ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=checks)
    return {"status": "ready", **checks}
