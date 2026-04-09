"""Device SQLModel definitions."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from src.models.types import DeviceType

_MAC_PATTERN = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceBase(SQLModel):
    name: str = Field(max_length=255)
    type: DeviceType
    ip: Optional[str] = Field(default=None, max_length=45)
    mac: Optional[str] = Field(default=None, max_length=17)
    os: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)
    location_id: Optional[uuid.UUID] = Field(default=None)

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MAC_PATTERN.match(v):
            raise ValueError("mac must be in format AA:BB:CC:DD:EE:FF")
        return v


class Device(DeviceBase, table=True):
    __tablename__ = "devices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=255)
    type: Optional[DeviceType] = None
    ip: Optional[str] = Field(default=None, max_length=45)
    mac: Optional[str] = Field(default=None, max_length=17)
    os: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    location_id: Optional[uuid.UUID] = None

    @field_validator('mac')
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MAC_PATTERN.match(v):
            raise ValueError('mac must be in format AA:BB:CC:DD:EE:FF')
        return v


class DeviceResponse(DeviceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
