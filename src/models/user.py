"""User SQLModel definitions.

password_hash is stored ONLY on the User table model.
UserResponse NEVER exposes password_hash.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from src.models.types import Role


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserBase(SQLModel):
    username: str = Field(max_length=100)
    email: str = Field(max_length=255)
    role: Role = Field(default=Role.Contributor)
    is_active: bool = Field(default=True)


class User(UserBase, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password_hash: str = Field(max_length=255)
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


class UserResponse(UserBase):
    """API response schema — password_hash is never included."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
