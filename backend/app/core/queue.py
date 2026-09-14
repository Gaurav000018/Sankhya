"""Work queue between the API and the speech worker.

A Redis list, not a task framework. The API pushes an answer id; the worker on
the host blocks on it, runs the pipeline against the GPU, and writes results
back to Postgres. Analysis takes ~20 seconds, which is why it can never happen
inside a request.
"""

from __future__ import annotations

import json
import logging

import redis

from app.config import settings

log = logging.getLogger("sankhya.queue")

# Blocking BRPOP holds a connection open for its whole timeout, and Docker
# Desktop's port forwarding on Windows will drop an idle one. Keepalives plus a
# periodic health check stop that surfacing as a socket timeout mid-wait.
_redis = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_keepalive=True,
    health_check_interval=30,
    retry_on_timeout=True,
)

# Errors a long-running worker should ride out rather than die on. A blocking
# pop that times out is handled in `dequeue_job` and never reaches here.
TRANSIENT_ERRORS = (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)

STATUS_KEY = "sankhya:analysis:status:{answer_id}"
STATUS_TTL = 3600


GENERATION_QUEUE = "sankhya:generation"


class QueueUnavailable(RuntimeError):
    """The queue could not be reached, so the job was never accepted."""


def enqueue_analysis(answer_id: int) -> None:
    """Hand an answer to the speech worker.

    This one does raise: silently dropping a recording would leave the officer
    watching a progress state that never resolves. The caller turns it into a
    503 that says analysis is unavailable.
    """
    try:
        _redis.lpush(settings.analysis_queue, json.dumps({"answer_id": answer_id}))
    except TRANSIENT_ERRORS as exc:
        raise QueueUnavailable(str(exc)) from exc
    set_status(answer_id, "queued")


def enqueue_generation(material_id: int, count: int = 3, bloom: str = "apply") -> None:
    _redis.lpush(GENERATION_QUEUE, json.dumps({
        "material_id": material_id, "count": count, "bloom": bloom,
    }))


def dequeue_job(timeout: int = 5) -> tuple[str, dict] | None:
    """Block for work on either queue.

    Returns (kind, payload), or None when there is nothing to do.

    redis-py passes a blocking command's timeout down as the socket read
    timeout, so the client can raise TimeoutError at the same moment the server
    would have returned nil. That is not a failure — it is an idle queue — so it
    is swallowed here rather than being reported as a connection problem. A
    genuine ConnectionError still propagates for the worker to retry.
    """
    try:
        item = _redis.brpop([settings.analysis_queue, GENERATION_QUEUE], timeout=timeout)
    except redis.exceptions.TimeoutError:
        return None

    if not item:
        return None
    queue_name, raw = item
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    kind = "analysis" if queue_name == settings.analysis_queue else "generation"
    return kind, payload


def dequeue_analysis(timeout: int = 5) -> int | None:
    """Analysis-only variant, kept for tests and single-purpose workers."""
    item = _redis.brpop(settings.analysis_queue, timeout=timeout)
    if not item:
        return None
    try:
        return int(json.loads(item[1])["answer_id"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def generation_depth() -> int:
    return _redis.llen(GENERATION_QUEUE)


def set_status(answer_id: int, status: str, detail: str | None = None) -> None:
    _redis.setex(
        STATUS_KEY.format(answer_id=answer_id),
        STATUS_TTL,
        json.dumps({"status": status, "detail": detail}),
    )


def get_status(answer_id: int) -> dict:
    """Progress of one analysis job.

    An unreachable store reads the same as an unknown job: in both cases we
    cannot say anything about it, and the caller polls again.
    """
    try:
        raw = _redis.get(STATUS_KEY.format(answer_id=answer_id))
    except TRANSIENT_ERRORS as exc:
        log.error("Queue unavailable reading status (%s)", type(exc).__name__)
        return {"status": "unknown", "detail": None}
    return json.loads(raw) if raw else {"status": "unknown", "detail": None}


def queue_depth() -> int:
    """How many answers are waiting. Zero when the queue cannot be reached —
    it is a number shown next to "queued", not a decision anything depends on."""
    try:
        return _redis.llen(settings.analysis_queue)
    except TRANSIENT_ERRORS as exc:
        log.error("Queue unavailable reading depth (%s)", type(exc).__name__)
        return 0


def worker_heartbeat(seconds: int = 30) -> None:
    _redis.setex("sankhya:worker:alive", seconds, "1")


def worker_is_alive() -> bool:
    """Whether a speech worker is actually running.

    Surfaced in the API response so a queued answer that will never be picked up
    is visible immediately, rather than looking like slow processing.

    An unreachable queue answers **False**, which is the truthful answer rather
    than a fallback: if the API cannot reach the queue, no worker is reading it
    either. Raising here took down the whole interview screen on any deployment
    without Redis — the session cannot even be opened, which is a long way from
    "recording will not be analysed".
    """
    try:
        return bool(_redis.exists("sankhya:worker:alive"))
    except TRANSIENT_ERRORS as exc:
        log.error("Queue unavailable checking worker (%s)", type(exc).__name__)
        return False
