"""Request dependencies: current user, and role gates."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import AuditLog, User, UserRole

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")

    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Sign in again.")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is not active")
    return user


def require_roles(*roles: UserRole):
    """Route guard. RBAC lives here, not scattered through handlers."""

    allowed = set(roles)

    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Your role does not have access to this action",
            )
        return user

    return _guard


def can_view_officer(viewer: User, target: User) -> bool:
    """Officers see themselves; supervisors see their division; admins see all."""
    if viewer.id == target.id or viewer.role == UserRole.ADMIN:
        return True
    if viewer.role == UserRole.SUPERVISOR:
        return viewer.division_id is not None and viewer.division_id == target.division_id
    return False


def write_audit(
    db: Session,
    *,
    action: str,
    actor_user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    meta: dict | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            meta=meta,
            ip_address=request.client.host if request and request.client else None,
        )
    )
