"""Network SQLModel definitions (HT-022)."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from src.models.device_network import DeviceNetworkDeviceRef

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NetworkBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    vlan_id: Optional[int] = Field(default=None)
    cidr: str = Field(min_length=3, max_length=64)
    gateway: Optional[str] = Field(default=None, max_length=45)
    description: Optional[str] = Field(default=None, max_length=1000)
    color: str = Field(max_length=7)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #3b82f6")
        return v


class Network(NetworkBase, table=True):
    __tablename__ = "networks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class NetworkCreate(NetworkBase):
    pass


class NetworkUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vlan_id: Optional[int] = Field(default=None)
    cidr: Optional[str] = Field(default=None, min_length=3, max_length=64)
    gateway: Optional[str] = Field(default=None, max_length=45)
    description: Optional[str] = Field(default=None, max_length=1000)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #3b82f6")
        return v


class NetworkResponse(NetworkBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class NetworkListResponse(NetworkResponse):
    device_count: int = 0


class NetworkResponseEnriched(NetworkResponse):
    devices: list[DeviceNetworkDeviceRef] = []
