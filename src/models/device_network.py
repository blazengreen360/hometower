"""Device-network membership models (HT-022)."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from src.models.types import DeviceStatus, DeviceType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceNetwork(SQLModel, table=True):
    __tablename__ = "device_networks"

    device_id: uuid.UUID = Field(
        foreign_key="devices.id", primary_key=True, ondelete="CASCADE"
    )
    network_id: uuid.UUID = Field(
        foreign_key="networks.id", primary_key=True, ondelete="CASCADE"
    )
    ip_address: str = Field(max_length=45)
    created_at: datetime = Field(default_factory=_utcnow)


class DeviceNetworkCreate(SQLModel):
    network_id: uuid.UUID
    ip_address: str = Field(max_length=45)


class DeviceNetworkResponse(SQLModel):
    device_id: uuid.UUID
    network_id: uuid.UUID
    ip_address: str
    created_at: datetime


class DeviceNetworkNetworkRef(SQLModel):
    network_id: uuid.UUID
    name: str
    vlan_id: int | None = None
    cidr: str
    gateway: str | None = None
    color: str
    ip_address: str


class DeviceNetworkDeviceRef(SQLModel):
    device_id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus
    ip_address: str
