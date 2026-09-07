"""Password hashing, JWT issuance, and TOTP.

All four authentication methods (password, email OTP, TOTP, Parichay) converge
on the same access token, so authorisation logic never needs to know how someone
signed in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.config import settings

_hasher = PasswordHasher()


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        _hasher.verify(hashed, raw)
        return True
    except (VerifyMismatchError, VerificationError):
        return False


def create_access_token(user_id: int, role: str, method: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        # Which method authenticated this session. Recorded in the audit log and
        # available if a future policy wants to gate an action on a stronger factor.
        "amr": method,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None


# --------------------------------------------------------------------------- #
# TOTP — no delivery, no quota, works with the network off.
# --------------------------------------------------------------------------- #

def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="SANKHYA")


def verify_totp(secret: str | None, code: str) -> bool:
    if not secret:
        return False
    # One step of drift either way, for clock skew on the officer's phone.
    return pyotp.TOTP(secret).verify(code, valid_window=1)
