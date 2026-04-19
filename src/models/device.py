"""Device SQLModel definitions."""
import ipaddress
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from src.models.types import DeviceStatus, DeviceType
from src.models.tag import TagResponse
from src.models.custom_field import CustomFieldResponse
from src.models.device_network import DeviceNetworkNetworkRef
from src.models.service import ServiceResponse

_MAC_PATTERN = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    type: DeviceType
    status: DeviceStatus = Field(default=DeviceStatus.Active)
    ip: Optional[str] = Field(default=None, max_length=45)
    mac: Optional[str] = Field(default=None, max_length=17)
    os: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=5000)
    power_watts: Optional[int] = Field(default=None, ge=0)
    location_id: Optional[uuid.UUID] = Field(default=None, foreign_key="locations.id")
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="devices.id")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError(f"ip must be a valid IPv4 or IPv6 address, got '{v}'")
        return v

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MAC_PATTERN.match(v):
            raise ValueError("mac must be in format AA:BB:CC:DD:EE:FF")
        return v


class Device(DeviceBase, table=True):
    __tablename__ = "devices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Persist ownership on the inventory record itself so owner-scoped reads do
    # not have to infer visibility from current topology placement.
    owner_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id", index=True, ondelete="SET NULL"
    )
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[DeviceType] = None
    status: Optional[DeviceStatus] = None
    ip: Optional[str] = Field(default=None, max_length=45)
    mac: Optional[str] = Field(default=None, max_length=17)
    os: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=5000)
    power_watts: Optional[int] = Field(default=None, ge=0)
    location_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    version: int

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            raise ValueError("name cannot be set to null")
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError(f"ip must be a valid IPv4 or IPv6 address, got '{v}'")
        return v

    @field_validator('mac')
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MAC_PATTERN.match(v):
            raise ValueError('mac must be in format AA:BB:CC:DD:EE:FF')
        return v


class DeviceResponse(DeviceBase):
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class DeviceResponseEnriched(DeviceResponse):
    location_name: Optional[str] = None
    tags: list[TagResponse] = []
    custom_fields: list[CustomFieldResponse] = []
    services: list[ServiceResponse] = []
    networks: list[DeviceNetworkNetworkRef] = []
    children: list[DeviceResponse] = []
    parent_chain: list[DeviceResponse] = []


class PaginatedDeviceResponseEnriched(SQLModel):
    items: list[DeviceResponseEnriched]
    total: int
    page: int
    limit: int


class DevicePlacement(SQLModel):
    """A View (diagram layout) that contains a given device."""
    view_id: uuid.UUID
    view_name: str
    topology_name: str | None = None
