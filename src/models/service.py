"""Service SQLModel definitions (HT-023)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from src.models.types import ServiceProtocol, ServiceStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServiceBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: ServiceProtocol = Field(default=ServiceProtocol.other)
    url: Optional[str] = Field(default=None, max_length=2048)
    status: ServiceStatus = Field(default=ServiceStatus.unknown)
    notes: Optional[str] = Field(default=None, max_length=5000)


class Service(ServiceBase, table=True):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("device_id", "name", name="uq_service_device_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: Optional[ServiceProtocol] = None
    url: Optional[str] = Field(default=None, max_length=2048)
    status: Optional[ServiceStatus] = None
    notes: Optional[str] = Field(default=None, max_length=5000)


class ServiceResponse(ServiceBase):
    id: uuid.UUID
    device_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ServiceListResponse(ServiceResponse):
    """Flat list response — includes device_name for cross-device listing."""
    device_name: str


class DependencyRef(SQLModel):
    """Compact reference used in ServiceWithDependencies."""
    id: uuid.UUID
    name: str
    device_name: str


class ServiceWithDependencies(ServiceResponse):
    depends_on: list[DependencyRef] = []
    depended_by: list[DependencyRef] = []
