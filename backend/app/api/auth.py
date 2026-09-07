"""Authentication: password, email OTP, TOTP, and a Parichay adapter stub.

All four issue the same access token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import otp as otp_store
from app.core.deps import get_current_user, write_audit
from app.core.mailer import send_otp_email
from app.core.security import (
    create_access_token,
    new_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from app.db import get_db
from app.models import User
from app.schemas import (
    LoginRequest,
    OtpRequest,
    OtpRequestResponse,
    OtpVerify,
    TokenResponse,
    TotpSetupResponse,
    TotpVerify,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_OTP_MESSAGE = "If an account exists for that address, a code has been sent."


def _get_active_user(db: Session, email: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    return user if user and user.is_active else None


def _issue_token(db: Session, request: Request, user: User, method: str) -> TokenResponse:
    write_audit(
        db,
        action="auth.login",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        meta={"method": method},
        request=request,
    )
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value, method),
        method=method,
    )


@router.post("/login", response_model=TokenResponse)
def login_with_password(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    user = _get_active_user(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        write_audit(
            db,
            action="auth.login_failed",
            meta={"email": payload.email, "method": "password"},
            request=request,
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return _issue_token(db, request, user, "password")


@router.post("/otp/request", response_model=OtpRequestResponse)
def request_otp(
    payload: OtpRequest, request: Request, db: Session = Depends(get_db)
) -> OtpRequestResponse:
    """Send a sign-in code.

    The response is identical whether or not the account exists. Rate limiting
    and code reuse happen in the OTP store.
    """
    user = _get_active_user(db, payload.email)

    if user is None:
        return OtpRequestResponse(message=GENERIC_OTP_MESSAGE, cooldown_seconds=settings.otp_resend_cooldown_seconds)

    issued = otp_store.issue(payload.email)

    if issued.quota_exceeded:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many codes requested. Try again in an hour, or sign in with your password.",
        )

    if not issued.reused:
        send_otp_email(payload.email, issued.code or "")

    write_audit(
        db,
        action="auth.otp_requested",
        actor_user_id=user.id,
        meta={"reused": issued.reused},
        request=request,
    )
    db.commit()

    return OtpRequestResponse(
        message=GENERIC_OTP_MESSAGE,
        cooldown_seconds=issued.cooldown_remaining,
        dev_code=issued.code if (settings.is_dev and not settings.email_enabled) else None,
    )


@router.post("/otp/verify", response_model=TokenResponse)
def verify_otp(
    payload: OtpVerify, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    user = _get_active_user(db, payload.email)
    if user is None or not otp_store.verify(payload.email, payload.code):
        write_audit(
            db,
            action="auth.login_failed",
            meta={"email": payload.email, "method": "email_otp"},
            request=request,
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code is not valid or has expired")
    return _issue_token(db, request, user, "email_otp")


@router.post("/totp/setup", response_model=TotpSetupResponse)
def setup_totp(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TotpSetupResponse:
    """Start authenticator-app enrolment.

    TOTP needs no delivery channel, so it has no quota and works with the network
    off — which is why it is the method to demo on stage.
    """
    secret = new_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = False
    write_audit(db, action="auth.totp_setup_started", actor_user_id=user.id, request=request)
    db.commit()
    return TotpSetupResponse(
        secret=secret, provisioning_uri=totp_provisioning_uri(secret, user.email)
    )


@router.post("/totp/enable", response_model=UserOut)
def enable_totp(
    payload: TotpVerify,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if not verify_totp(user.totp_secret, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code did not match. Try the next one.")
    user.totp_enabled = True
    write_audit(db, action="auth.totp_enabled", actor_user_id=user.id, request=request)
    db.commit()
    return user


@router.post("/totp/login", response_model=TokenResponse)
def login_with_totp(
    payload: TotpVerify, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    user = _get_active_user(db, payload.email)
    if user is None or not user.totp_enabled or not verify_totp(user.totp_secret, payload.code):
        write_audit(
            db,
            action="auth.login_failed",
            meta={"email": payload.email, "method": "totp"},
            request=request,
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code is not valid")
    return _issue_token(db, request, user, "totp")


@router.get("/parichay/authorize", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def parichay_authorize() -> dict:
    """Parichay (GoI SSO) adapter — deliberately a stub.

    Real integration needs ministry onboarding and a registered client, which is
    not available outside a sanctioned deployment. The seam exists so that the
    production path is a configuration change rather than a rewrite: Parichay
    would resolve to a User and call the same `_issue_token`.
    """
    return {
        "detail": "Parichay SSO is not enabled in this deployment",
        "status": "adapter_stub",
        "production_path": "OIDC authorisation code flow against the Parichay tenant",
    }


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
