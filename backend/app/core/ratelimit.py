"""Fixed-window rate limiting, in Redis.

Password login had no limit at all: an attacker could grind an officer's
password at whatever rate the network allowed. Registration and password reset
had none either, which makes the platform a free relay for sending mail to
arbitrary addresses.

Counted on two keys per attempt — the email and the client IP — because either
alone is trivially evaded. One attacker rotating through addresses is caught by
IP; a botnet against a single account is caught by email.

A fixed window rather than a sliding one: it allows a burst of at most 2x the
limit across a boundary, which does not matter at these numbers, and it costs
one `INCR` instead of a sorted set per attempt.

**Redis being down must not lock everybody out.** A failure here is logged and
allowed through. The limiter is a brake on abuse, not an authorisation
decision — the password check behind it is what actually protects the account.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import redis

from app.config import settings

log = logging.getLogger("sankhya.ratelimit")

_redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    retry_after_seconds: int


def _hit(key: str, limit: int, window_seconds: int) -> LimitResult:
    try:
        pipe = _redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = pipe.execute()

        # A key with no TTL is one we just created (INCR does not set one), or
        # one left without an expiry by a crash between the two commands.
        if ttl is None or ttl < 0:
            _redis.expire(key, window_seconds)
            ttl = window_seconds

        if count > limit:
            return LimitResult(False, max(1, int(ttl)))
        return LimitResult(True, 0)
    except redis.RedisError as exc:
        log.error("Rate limiter unavailable (%s); allowing request", type(exc).__name__)
        return LimitResult(True, 0)


def check(scope: str, identifiers: list[str], limit: int, window_seconds: int) -> LimitResult:
    """Count one attempt against every identifier, returning the worst result.

    Every identifier is incremented even once one has tripped, so an attacker
    cannot keep a second counter cold by deliberately tripping the first.
    """
    worst = LimitResult(True, 0)
    for identifier in identifiers:
        if not identifier:
            continue
        result = _hit(f"rl:{scope}:{identifier}", limit, window_seconds)
        if not result.allowed and result.retry_after_seconds > worst.retry_after_seconds:
            worst = result
    return worst


def clear(scope: str, identifiers: list[str]) -> None:
    """Reset counters after a success.

    Without this, ten typos during a genuine sign-in session would lock an
    officer out for the rest of the window even though they got in.
    """
    try:
        keys = [f"rl:{scope}:{i}" for i in identifiers if i]
        if keys:
            _redis.delete(*keys)
    except redis.RedisError:
        pass


def client_ip(request) -> str:
    """The caller's address, honouring one proxy hop.

    `X-Forwarded-For` is attacker-controlled unless something trusted rewrites
    it, so only the *first* entry is read and only when the app is knowingly
    behind a proxy. Behind a correctly configured load balancer that is the real
    client; with no proxy the socket address is used instead.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and not settings.is_dev:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
