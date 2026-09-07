from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
from app.config import settings
from app.db import init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sankhya")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("SANKHYA API ready (env=%s)", settings.app_env)
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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    return {"status": "ok", "env": settings.app_env}
