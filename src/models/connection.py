"""Connection SQLModel definitions."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import model_validator
from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from src.models.types import ConnectionType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionBase(SQLModel):
    source_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE")
    target_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE")
    type: ConnectionType
    label: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> "ConnectionBase":
        if self.source_id == self.target_id:
            raise ValueError("source and target must be different devices")
        return self


class Connection(ConnectionBase, table=True):
    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint("source_id <> target_id", name="ck_connection_no_self_loop"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionUpdate(SQLModel):
    source_id: Optional[uuid.UUID] = None
    target_id: Optional[uuid.UUID] = None
    type: Optional[ConnectionType] = None
    label: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> "ConnectionUpdate":
        if (
            self.source_id is not None
            and self.target_id is not None
            and self.source_id == self.target_id
        ):
            raise ValueError("source and target must be different devices")
        return self


class ConnectionResponse(ConnectionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
