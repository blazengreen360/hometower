"""CustomField SQLModel definitions (HT-007)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomFieldBase(SQLModel):
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(default="", max_length=1024)

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) == 0:
            raise ValueError("key must be at least 1 character after stripping whitespace")
        return stripped


class CustomField(CustomFieldBase, table=True):
    __tablename__ = "custom_fields"
    __table_args__ = (
        UniqueConstraint("device_id", "key", name="uq_custom_field_device_key"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class CustomFieldCreate(CustomFieldBase):
    pass


class CustomFieldUpdate(SQLModel):
    key: Optional[str] = Field(default=None, min_length=1, max_length=64)
    value: Optional[str] = Field(default=None, max_length=1024)

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if len(stripped) == 0:
                raise ValueError("key must be at least 1 character after stripping")
            return stripped
        return v


class CustomFieldResponse(CustomFieldBase):
    id: uuid.UUID
    device_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
