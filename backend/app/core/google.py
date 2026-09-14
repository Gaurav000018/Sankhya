"""Google Sign-In: verifying the ID token the browser hands us.

The browser runs Google Identity Services, which returns a signed JWT (the
"credential"). That token is the entire claim of identity, so it is verified
here from first principles rather than decoded and trusted:

* **Signature**, against Google's published keys. Without this the token is a
  base64 string anyone can write.
* **`aud`**, against our own client ID. A token minted for a *different*
  application is validly signed by Google and would otherwise be accepted —
  this is the check that stops someone replaying a token from any other site
  that uses Google Sign-In.
* **`iss`**, so only Google's issuer is honoured.
* **`exp`**, enforced by PyJWT.
* **`email_verified`**, because a Google account can carry an address it has
  not proven. Accepting one would let someone claim an officer's identity by
  putting their address on an unverified account.

Google's signing keys rotate, so `PyJWKClient` fetches and caches the key set
and re-fetches when it sees an unknown key id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.config import settings

log = logging.getLogger("sankhya.google")

CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# Cached across requests: it holds the key set, and rebuilding it per sign-in
# would fetch Google's certs every time.
_jwks_client: PyJWKClient | None = None


def _client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(CERTS_URL, cache_keys=True)
    return _jwks_client


class GoogleAuthError(Exception):
    """The token is not a valid, current assertion for this application."""


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    full_name: str
    subject: str
    picture: str | None


def verify_id_token(credential: str) -> GoogleIdentity:
    """Validate a Google ID token and return the identity it asserts.

    Raises `GoogleAuthError` for anything not currently valid. The message is
    safe to show a user: it never distinguishes between token shapes in a way
    that would help someone forge one.
    """
    if not settings.google_client_id:
        raise GoogleAuthError("Google sign-in is not configured on this server.")

    try:
        signing_key = _client().get_signing_key_from_jwt(credential)
        claims = jwt.decode(
            credential,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=ISSUERS,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise GoogleAuthError("That Google sign-in has expired. Try again.") from exc
    except jwt.InvalidAudienceError as exc:
        # Almost always a misconfiguration: the frontend was built with a
        # different client ID than the API checks against.
        log.error("Google token audience mismatch — check GOOGLE_CLIENT_ID on both sides")
        raise GoogleAuthError("This Google sign-in was not issued for SANKHYA.") from exc
    except jwt.PyJWTError as exc:
        log.warning("Rejected Google token: %s", type(exc).__name__)
        raise GoogleAuthError("Could not verify that Google sign-in.") from exc

    email = (claims.get("email") or "").lower().strip()
    if not email:
        raise GoogleAuthError("That Google account has no email address.")

    if not claims.get("email_verified"):
        # A Google account can carry an unverified address. Honouring one would
        # let someone claim an officer's identity by typing their address in.
        raise GoogleAuthError(
            "That Google account's email address is not verified with Google."
        )

    return GoogleIdentity(
        email=email,
        # `name` is absent on some accounts; the local part is a better
        # placeholder than an empty string an administrator has to fix later.
        full_name=(claims.get("name") or email.split("@")[0]).strip(),
        subject=str(claims["sub"]),
        picture=claims.get("picture"),
    )
