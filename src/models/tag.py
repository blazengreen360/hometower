"""Tag and DeviceTag SQLModel definitions (HT-006)."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

_HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TagBase(SQLModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(max_length=7)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #4f46e5")
        return v


class Tag(TagBase, table=True):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", name="uq_tag_name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)


class TagCreate(TagBase):
    pass


class TagUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #4f46e5")
        return v


class TagResponse(TagBase):
    id: uuid.UUID
    created_at: datetime


class TagWithCountResponse(TagResponse):
    device_count: int


class DeviceTag(SQLModel, table=True):
    __tablename__ = "device_tags"

    device_id: uuid.UUID = Field(
        foreign_key="devices.id", primary_key=True, ondelete="CASCADE"
    )
    tag_id: uuid.UUID = Field(
        foreign_key="tags.id", primary_key=True, ondelete="CASCADE"
    )
