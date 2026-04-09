"""Authentication service — orchestrates user repository + JWT/bcrypt helpers."""
from fastapi import HTTPException
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.repositories import user_repository
from src.utils.auth import create_jwt, hash_password, verify_password
from src.utils.logger import logger
from src.utils.settings import settings


def authenticate(email: str, password: str, session: Session) -> str:
    """Verify credentials and return a signed JWT.

    Args:
        email: The user's email address.
        password: The plaintext password to verify.
        session: Active database session.

    Returns:
        Signed JWT string.

    Raises:
        HTTPException(401): when credentials are invalid or the account is disabled.
    """
    user = user_repository.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        logger.warning("Login failed for email={}", email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        logger.warning("Login attempt on disabled account: email={}", email)
        raise HTTPException(status_code=401, detail="Account disabled")
    logger.info("Login successful: user_id={} role={}", user.id, user.role.value)
    return create_jwt({"sub": str(user.id), "role": user.role.value})


def create_first_admin_if_needed(session: Session) -> None:
    """On first boot, create an admin account from environment variables.

    No-op when at least one user already exists.
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
        logger.info("First-boot admin created: email={}", settings.admin_email)
