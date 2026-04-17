"""Authentication service — orchestrates user repository + JWT/bcrypt helpers."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlmodel import Session

from src.domain.auth import validate_password_strength
from src.models.types import Role
from src.models.user import User
from src.repositories import user_repository
from src.utils.auth import create_jwt, hash_password, verify_password
from src.utils.logger import logger
from src.utils.settings import settings


def authenticate(email: str, password: str, session: Session) -> tuple[str, int, str]:
    """Verify credentials and return a signed JWT plus expiry and role.

    Args:
        email: The user's email address.
        password: The plaintext password to verify.
        session: Active database session.

    Returns:
        A tuple of (jwt_token, token_exp_unix, role_value).

    Raises:
        HTTPException(401): when credentials are invalid or the account is disabled.
    """
    user = user_repository.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        logger.warning("Login failed")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        logger.warning("Login attempt on disabled account")
        raise HTTPException(status_code=401, detail="Account disabled")
    expire_unix = int(
        (datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)).timestamp()
    )
    token = create_jwt({
        "sub": str(user.id),
        "role": user.role.value,
        "version": user.token_version,
    })
    logger.debug("Login successful: user_id={} role={}", user.id, user.role.value)
    return token, expire_unix, user.role.value


def change_own_password(
    user_id: uuid.UUID, current: str, new: str, session: Session
) -> None:
    """Change the authenticated caller's own password.

    Args:
        user_id: The caller's UUID (extracted from JWT by the router).
        current: The caller's current plaintext password.
        new: The desired new plaintext password.
        session: Active database session.

    Raises:
        HTTPException(404): when the user cannot be found.
        HTTPException(401): when the current password does not match.
        HTTPException(422): when the new password fails strength rules or equals current.
    """
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(current, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    try:
        validate_password_strength(new)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if verify_password(new, user.password_hash):
        raise HTTPException(
            status_code=422,
            detail="New password must be different from current password",
        )
    user.password_hash = hash_password(new)
    user.updated_at = datetime.now(timezone.utc)
    user_repository.update(session, user)
    user_repository.increment_token_version(session, user_id)
    session.commit()
    logger.info("Password changed for user_id={}", user_id)


def revoke_tokens(user_id: uuid.UUID, session: Session) -> None:
    """Invalidate all tokens for a user by incrementing their token_version.

    Args:
        user_id: The user whose tokens should be invalidated.
        session: Active database session.
    """
    user_repository.increment_token_version(session, user_id)
    session.commit()
    logger.debug("Token version incremented for user_id={}", user_id)


def create_first_admin_if_needed(session: Session) -> None:
    """On first boot, create an admin account from environment variables.

    No-op when at least one user already exists. Logs a warning when
    ADMIN_PASSWORD is still set in .env after first boot (HT-025).
    """
    if user_repository.count(session) == 0:
        admin = User(
            username="admin",
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role=Role.Admin,
        )
        session.add(admin)
        session.commit()
        logger.info("First-boot admin created")
    else:
        if settings.admin_password:
            logger.warning(
                "ADMIN_PASSWORD is set in .env but first-boot seeding has already run; "
                "this value is ignored. Remove it from .env to silence this warning."
            )
