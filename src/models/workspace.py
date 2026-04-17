"""Workspace SQLModel definitions."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkspaceBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class Workspace(WorkspaceBase, table=True):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_workspace_owner_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class WorkspaceCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class WorkspaceResponse(WorkspaceBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    topology_count: int = 0
    created_at: datetime
    updated_at: datetime


class WorkspaceSummary(SQLModel):
    id: uuid.UUID
    name: str
    topology_count: int = 0
    last_modified: datetime


class PaginatedWorkspaceSummary(SQLModel):
    items: list[WorkspaceSummary]
    total: int
    page: int
    limit: int
