"""Topology SQLModel definitions."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, ForeignKey, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TopologyBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(sa_column=Column(JSON), default=[])


class Topology(TopologyBase, table=True):
    __tablename__ = "topologies"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "name", name="uq_topology_workspace_name"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    current_diagram_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey(
                "diagram_layouts.id",
                ondelete="SET NULL",
                name="fk_topologies_current_diagram_id",
                use_alter=True,
            ),
            nullable=True,
        ),
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TopologyCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(default=[])


class TopologyUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    tags: Optional[list[str]] = None


class TopologyResponse(TopologyBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    current_diagram_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class TopologySummary(SQLModel):
    id: uuid.UUID
    name: str
    tags: list[str]
    last_modified: datetime


class PaginatedTopologySummary(SQLModel):
    items: list[TopologySummary]
    total: int
    page: int
    limit: int
