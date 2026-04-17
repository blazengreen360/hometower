"""Topology history entry SQLModel definitions (HT-072 foundation)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, ForeignKey
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TopologyHistoryEntryBase(SQLModel):
    topology_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("topologies.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    diagram_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("diagram_layouts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    snapshot_name: str = Field(min_length=1, max_length=255)
    action: str = Field(default="save_version", min_length=1, max_length=32)
    restored_from_history_entry_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("topology_history_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    created_by: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class TopologyHistoryEntry(TopologyHistoryEntryBase, table=True):
    __tablename__ = "topology_history_entries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)


class TopologyHistorySummary(SQLModel):
    id: uuid.UUID
    diagram_id: uuid.UUID
    snapshot_name: str
    action: str
    restored_from_history_entry_id: Optional[uuid.UUID] = None
    created_at: datetime
    is_current: bool = False


class PaginatedTopologyHistory(SQLModel):
    items: list[TopologyHistorySummary]
    total: int
    page: int
    limit: int
