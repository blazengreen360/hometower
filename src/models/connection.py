"""Connection SQLModel definitions."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from src.models.types import ConnectionType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionBase(SQLModel):
    source_id: uuid.UUID = Field(foreign_key="devices.id")
    target_id: uuid.UUID = Field(foreign_key="devices.id")
    type: ConnectionType
    label: Optional[str] = Field(default=None, max_length=255)


class Connection(ConnectionBase, table=True):
    __tablename__ = "connections"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionUpdate(SQLModel):
    type: Optional[ConnectionType] = None
    label: Optional[str] = None


class ConnectionResponse(ConnectionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
