"""Password hashing and JWT helpers.

Never store raw passwords — always hash via hash_password().
Never log JWT tokens or password hashes.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from src.utils.settings import settings

# All five claims are required on every issued token.
_REQUIRED_CLAIMS: tuple[str, ...] = ("sub", "role", "jti", "iat", "version")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* password."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_jwt(payload: dict[str, str | int]) -> str:
    """Sign *payload* with HS256 and append exp, jti, and iat claims.

    Args:
        payload: Must contain at minimum ``sub``, ``role``, and ``version``.
                 ``jti`` and ``iat`` are appended automatically.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    full_payload: dict[str, str | int] = {
        **payload,
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(full_payload, settings.secret_key, algorithm="HS256")


def decode_jwt(token: str) -> dict[str, str | int]:
    """Decode and verify *token*.

    Raises:
        jose.JWTError: when the token is invalid, tampered, expired, or
                       missing any of the required claims (sub, role, jti,
                       iat, version).
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    missing = [c for c in _REQUIRED_CLAIMS if c not in payload]
    if missing:
        raise JWTError(f"Missing required claims: {', '.join(missing)}")
    return payload


__all__ = ["hash_password", "verify_password", "create_jwt", "decode_jwt", "JWTError"]
