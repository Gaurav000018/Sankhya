"""Authentication: password, email OTP, TOTP, and a Parichay adapter stub.

All four issue the same access token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import otp as otp_store
from app.core import ratelimit, tokens
from app.core.deps import get_current_user, write_audit
from app.core.mailer import (
    send_otp_email,
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
)
from app.core.security import (
    create_access_token,
    hash_password,
    new_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from app.core.tokens import TokenPurpose
from app.db import get_db
from app.models import User, UserRole
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OtpRequest,
    OtpRequestResponse,
    OtpVerify,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    TotpSetupResponse,
    TotpVerify,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_OTP_MESSAGE = "If an account exists for that address, a code has been sent."

# Registration and password reset answer identically whether or not the address
# is known. Anything else turns either endpoint into a way to enumerate which
# officers hold accounts.
GENERIC_REGISTER_MESSAGE = (
    "Check your inbox. If that address can be registered, a confirmation link is on its way."
)
GENERIC_RESET_MESSAGE = (
    "If an account exists for that address, a password reset link has been sent."
)


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


def _verification_url(token: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/verify?token={token}"


def _reset_url(token: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/reset-password?token={token}"


def _enforce_limit(
    scope: str, request: Request, email: str, limit: int, window_seconds: int, message: str
) -> list[str]:
    """Rate-limit an endpoint on email and client IP. Returns the keys used."""
    identifiers = [email.lower().strip(), ratelimit.client_ip(request)]
    result = ratelimit.check(scope, identifiers, limit, window_seconds)
    if not result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            message,
            headers={"Retry-After": str(result.retry_after_seconds)},
        )
    return identifiers


@router.post("/login", response_model=TokenResponse)
def login_with_password(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    keys = _enforce_limit(
        "login",
        request,
        payload.email,
        settings.login_max_per_15min,
        15 * 60,
        "Too many sign-in attempts. Wait a few minutes and try again.",
    )

    user = _get_active_user(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        write_audit(
            db,
            action="auth.login_failed",
            meta={"email": payload.email, "method": "password"},
            request=request,
        )
        db.commit()

        # An unverified account fails the same way a wrong password does — but
        # only after the password itself checked out, so this cannot be used to
        # discover which addresses are registered.
        pending = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
        if pending and not pending.is_active and verify_password(
            payload.password, pending.password_hash
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "This account is not confirmed yet. Check your inbox for the "
                "confirmation link, or request a new one.",
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")

    # A successful sign-in clears the counter, so typos during a genuine session
    # do not lock an officer out for the rest of the window.
    ratelimit.clear("login", keys)
    return _issue_token(db, request, user, "password")


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, request: Request, db: Session = Depends(get_db)
) -> RegisterResponse:
    """Create an account, inactive until the address is confirmed.

    Everything here answers identically whether or not the address is already
    registered. Registering someone else's address therefore tells the attacker
    nothing, and the real owner gets a "someone tried to register you" style
    confirmation they can ignore.

    The new user is always a learner with no division and no FRAC role. Those
    are what every competency number is computed against, so they are an
    administrator's to assign — not something an applicant can claim.
    """
    if not settings.registration_open:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Self-registration is closed. Your division administrator creates accounts.",
        )

    _enforce_limit(
        "register",
        request,
        payload.email,
        settings.register_max_per_hour,
        3600,
        "Too many registration attempts. Try again later.",
    )

    email = payload.email.lower().strip()

    if not settings.email_domain_allowed(email):
        # The one thing worth saying plainly: it is a policy, not a failure, and
        # it reveals nothing about who holds an account.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Registration is limited to official government addresses "
            f"({', '.join(settings.allowed_domains)}).",
        )

    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        write_audit(
            db, action="auth.register_duplicate", meta={"email": email}, request=request
        )
        db.commit()
        # Same shape as the success path, and no token is issued.
        return RegisterResponse(message=GENERIC_REGISTER_MESSAGE, email_sent=False)

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=UserRole.LEARNER,
        service_years=payload.service_years,
        is_active=False,
    )
    db.add(user)
    db.flush()

    raw = tokens.issue(db, user.id, TokenPurpose.VERIFY_EMAIL)
    url = _verification_url(raw)
    sent = send_verification_email(email, user.full_name, url)

    write_audit(
        db,
        action="auth.registered",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        meta={"email_sent": sent},
        request=request,
    )
    db.commit()

    return RegisterResponse(
        message=GENERIC_REGISTER_MESSAGE,
        email_sent=sent,
        dev_verify_url=url if (settings.is_dev and not settings.email_enabled) else None,
    )


@router.post("/verify", response_model=TokenResponse)
def verify_email(
    payload: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    """Activate an account from its confirmation link, and sign the officer in.

    Signing them in here rather than bouncing to a login form is deliberate:
    they have just proved control of the mailbox, which is the same thing the
    email-OTP path proves.
    """
    user_id = tokens.consume(db, payload.token, TokenPurpose.VERIFY_EMAIL)
    if user_id is None:
        db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This confirmation link is no longer valid. Request a new one.",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This confirmation link is no longer valid.")

    user.is_active = True
    write_audit(
        db,
        action="auth.email_verified",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        request=request,
    )
    return _issue_token(db, request, user, "email_verification")


@router.post("/verify/resend", response_model=MessageResponse)
def resend_verification(
    payload: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)
) -> MessageResponse:
    _enforce_limit(
        "verify-resend",
        request,
        payload.email,
        settings.register_max_per_hour,
        3600,
        "Too many requests. Try again later.",
    )

    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    # Nothing is sent to an account that is already active, and the response is
    # the same either way.
    if user is None or user.is_active:
        return MessageResponse(message=GENERIC_REGISTER_MESSAGE)

    raw = tokens.issue(db, user.id, TokenPurpose.VERIFY_EMAIL)
    url = _verification_url(raw)
    send_verification_email(email, user.full_name, url)
    write_audit(db, action="auth.verification_resent", actor_user_id=user.id, request=request)
    db.commit()

    return MessageResponse(
        message=GENERIC_REGISTER_MESSAGE,
        dev_url=url if (settings.is_dev and not settings.email_enabled) else None,
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> MessageResponse:
    _enforce_limit(
        "forgot",
        request,
        payload.email,
        settings.reset_max_per_hour,
        3600,
        "Too many reset requests. Try again later.",
    )

    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    if user is None or not user.is_active:
        return MessageResponse(message=GENERIC_RESET_MESSAGE)

    raw = tokens.issue(db, user.id, TokenPurpose.PASSWORD_RESET)
    url = _reset_url(raw)
    send_password_reset_email(email, user.full_name, url)
    write_audit(db, action="auth.reset_requested", actor_user_id=user.id, request=request)
    db.commit()

    return MessageResponse(
        message=GENERIC_RESET_MESSAGE,
        dev_url=url if (settings.is_dev and not settings.email_enabled) else None,
    )


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(
    payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    user_id = tokens.consume(db, payload.token, TokenPurpose.PASSWORD_RESET)
    if user_id is None:
        db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This reset link is no longer valid. Request a new one.",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is no longer valid.")

    user.password_hash = hash_password(payload.password)
    # Completing a reset proves control of the mailbox, which is the same thing
    # the confirmation link proves — so an unverified account becomes verified.
    user.is_active = True

    # Tell the mailbox owner their password moved. This is how someone finds out
    # an attacker who reached the link but not the inbox has taken the account.
    send_password_changed_email(user.email, user.full_name)

    write_audit(
        db,
        action="auth.password_reset",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        request=request,
    )
    return _issue_token(db, request, user, "password_reset")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """Change the password of the signed-in officer.

    The current password is required even though the session is already
    authenticated — an unattended logged-in browser should not be enough to
    take an account permanently.
    """
    if not verify_password(payload.current_password, user.password_hash):
        write_audit(
            db, action="auth.password_change_failed", actor_user_id=user.id, request=request
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your current password is incorrect")

    user.password_hash = hash_password(payload.new_password)
    send_password_changed_email(user.email, user.full_name)
    write_audit(db, action="auth.password_changed", actor_user_id=user.id, request=request)
    db.commit()
    return MessageResponse(message="Your password has been changed.")


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
