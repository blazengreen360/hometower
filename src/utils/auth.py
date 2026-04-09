"""Password hashing and JWT helpers.

Never store raw passwords — always hash via hash_password().
Never log JWT tokens or password hashes.
"""
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from src.utils.settings import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* password."""
    return _pwd_context.verify(plain, hashed)


def create_jwt(payload: dict[str, str | int]) -> str:
    """Sign *payload* with HS256 and append an expiry claim.

    Args:
        payload: Must contain at minimum ``sub`` (user id string) and ``role``.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode({**payload, "exp": expire}, settings.secret_key, algorithm="HS256")


def decode_jwt(token: str) -> dict[str, str | int]:
    """Decode and verify *token*.

    Raises:
        jose.JWTError: when the token is invalid, tampered, or expired.
    """
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


__all__ = ["hash_password", "verify_password", "create_jwt", "decode_jwt", "JWTError"]
