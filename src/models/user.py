"""User SQLModel definitions.

password_hash is stored ONLY on the User table model.
UserResponse NEVER exposes password_hash.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from src.models.types import Role

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_username(value: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("username cannot be empty or whitespace-only")
    return normalized


def _normalize_email(value: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("email cannot be empty or whitespace-only")
    if not _EMAIL_PATTERN.match(normalized):
        raise ValueError("email must be a valid email address")
    return normalized


class UserBase(SQLModel):
    username: str = Field(max_length=100)
    email: str = Field(max_length=255)
    role: Role = Field(default=Role.Contributor)
    is_active: bool = Field(default=True)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _normalize_username(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _normalize_email(v)


class User(UserBase, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password_hash: str = Field(max_length=255)
    token_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class UserCreate(UserBase):
    """Incoming creation payload — password is hashed before storage."""
    password: str


class UserUpdate(SQLModel):
    """Partial update payload — all fields optional."""
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _normalize_username(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _normalize_email(v)


class UserResponse(UserBase):
    """API response schema — password_hash is never included."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
