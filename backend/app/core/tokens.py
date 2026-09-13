"""Single-use email tokens: address verification and password reset.

In Postgres rather than Redis, unlike the sign-in OTP. A sign-in code is worth
nothing ten minutes later and losing the store just means asking for another
one; a verification link is the only route into an account and a password reset
is a security event that has to stay auditable. Neither should evaporate when
the cache is flushed.

Three properties the table enforces:

* **Only a hash is stored.** The token exists in the recipient's mailbox and
  nowhere else. A dump of this table does not let anyone reset an account.
* **Single use.** `used_at` is set inside the same transaction that consumes
  the token, so a link cannot be replayed from a browser back button or a mail
  gateway that pre-fetches URLs.
* **Superseded on reissue.** Requesting a second reset invalidates the first,
  so an old link left in an inbox stops working.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import settings
from app.db import Base


class TokenPurpose(str, enum.Enum):
    VERIFY_EMAIL = "verify_email"
    PASSWORD_RESET = "password_reset"


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purpose: Mapped[TokenPurpose] = mapped_column(Enum(TokenPurpose), nullable=False)
    # SHA-256 of the token, keyed with the app secret. 64 hex characters.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        # The lookup on every verify: hash plus purpose.
        Index("ix_email_tokens_hash_purpose", "token_hash", "purpose"),
    )


def _digest(raw: str) -> str:
    """Keyed so a stolen database alone cannot be brute-forced offline.

    The tokens are 43 characters of URL-safe base64 (256 bits), so plain
    SHA-256 would already be out of reach; the HMAC key means an attacker also
    needs the application secret before they can even start.
    """
    return hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def issue(db: Session, user_id: int, purpose: TokenPurpose) -> str:
    """Create a token, returning the raw value — the only time it exists.

    Any earlier unused token for the same user and purpose is consumed first:
    two live reset links for one account is one more than necessary.
    """
    now = datetime.now(timezone.utc)
    db.execute(
        select(EmailToken).where(
            EmailToken.user_id == user_id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
    )
    for stale in db.scalars(
        select(EmailToken).where(
            EmailToken.user_id == user_id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
    ):
        stale.used_at = now

    hours = (
        settings.email_token_ttl_hours
        if purpose is TokenPurpose.VERIFY_EMAIL
        else settings.password_reset_ttl_hours
    )
    raw = secrets.token_urlsafe(32)
    db.add(
        EmailToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_digest(raw),
            expires_at=now + timedelta(hours=hours),
        )
    )
    db.flush()
    return raw


def consume(db: Session, raw: str, purpose: TokenPurpose) -> int | None:
    """Validate and burn a token, returning the user id it belonged to.

    Returns None for anything not currently usable — unknown, wrong purpose,
    expired, or already used. The caller must not distinguish between those
    cases to the client: "expired" and "already used" together tell someone
    holding a stolen link that it was real.
    """
    if not raw:
        return None

    token = db.scalar(
        select(EmailToken).where(
            EmailToken.token_hash == _digest(raw),
            EmailToken.purpose == purpose,
        )
    )
    if token is None or token.used_at is not None:
        return None

    # Rows written before a timezone-aware column existed can come back naive.
    expires = token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None

    token.used_at = datetime.now(timezone.utc)
    db.flush()
    return token.user_id


def purge_expired(db: Session) -> int:
    """Delete tokens that can no longer be used. Safe to call at any time."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = db.scalars(select(EmailToken).where(EmailToken.created_at < cutoff)).all()
    for row in rows:
        db.delete(row)
    return len(rows)
