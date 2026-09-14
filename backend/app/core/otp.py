"""Email OTP, stored in Redis with TTL.

The rule that keeps us far below any free-tier sending cap: an unexpired code is
*reused* on resend rather than regenerated. A user hammering "resend" costs one
email, not ten.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

import logging

import redis

from app.config import settings

log = logging.getLogger("sankhya.otp")

_redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)

CODE_KEY = "otp:code:{email}"
COOLDOWN_KEY = "otp:cooldown:{email}"
QUOTA_KEY = "otp:quota:{email}"


def _digest(code: str) -> str:
    """Never store the code itself."""
    return hmac.new(
        settings.jwt_secret.encode(), code.encode(), hashlib.sha256
    ).hexdigest()


@dataclass
class OtpIssue:
    code: str | None
    reused: bool
    cooldown_remaining: int
    quota_exceeded: bool
    # Redis is the only store for codes, so without it this method cannot work
    # at all. Distinct from `quota_exceeded` because the officer has done
    # nothing wrong and a different sign-in method will work.
    unavailable: bool = False

    @property
    def ok(self) -> bool:
        return self.code is not None


def issue(email: str) -> OtpIssue:
    """Mint or reuse a sign-in code.

    Every path through here needs Redis; there is no in-memory fallback,
    because a code held in one worker's memory is invisible to the worker that
    handles the verify. So a store outage is reported rather than papered over,
    and the caller steers the officer to password or authenticator sign-in.
    """
    email = email.lower().strip()
    code_key = CODE_KEY.format(email=email)
    cooldown_key = COOLDOWN_KEY.format(email=email)
    quota_key = QUOTA_KEY.format(email=email)

    try:
        existing = _redis.get(code_key)
        cooldown = _redis.ttl(cooldown_key)
    except redis.RedisError as exc:
        log.error("OTP store unavailable (%s)", type(exc).__name__)
        return OtpIssue(None, False, 0, False, unavailable=True)

    if existing and cooldown and cooldown > 0:
        # Still inside the cooldown window and a live code exists: hand back the
        # same one. No new email is sent.
        payload = json.loads(existing)
        return OtpIssue(payload["code"], True, cooldown, False)

    sent_this_hour = int(_redis.get(quota_key) or 0)
    if sent_this_hour >= settings.otp_max_per_hour:
        return OtpIssue(None, False, max(cooldown, 0), True)

    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        _redis.setex(
            code_key,
            settings.otp_ttl_seconds,
            json.dumps({"digest": _digest(code), "attempts": 0, "code": code}),
        )
        _redis.setex(cooldown_key, settings.otp_resend_cooldown_seconds, "1")

        pipe = _redis.pipeline()
        pipe.incr(quota_key)
        pipe.expire(quota_key, 3600)
        pipe.execute()
    except redis.RedisError as exc:
        log.error("OTP store unavailable while issuing (%s)", type(exc).__name__)
        return OtpIssue(None, False, 0, False, unavailable=True)

    return OtpIssue(code, False, settings.otp_resend_cooldown_seconds, False)


def verify(email: str, code: str) -> bool:
    email = email.lower().strip()
    code_key = CODE_KEY.format(email=email)

    try:
        raw = _redis.get(code_key)
    except redis.RedisError as exc:
        # Indistinguishable from a wrong code to the caller, which is correct:
        # no code can be valid when the store holding them is unreachable.
        log.error("OTP store unavailable while verifying (%s)", type(exc).__name__)
        return False
    if not raw:
        return False

    payload = json.loads(raw)
    if payload["attempts"] >= settings.otp_max_attempts:
        _redis.delete(code_key)
        return False

    if hmac.compare_digest(payload["digest"], _digest(code)):
        _redis.delete(code_key)
        return True

    payload["attempts"] += 1
    try:
        ttl = _redis.ttl(code_key)
        _redis.setex(code_key, max(ttl, 1), json.dumps(payload))
    except redis.RedisError:
        # The attempt counter is lost, not the rejection.
        pass
    return False
