"""Topology personal draft SQLModel definitions (HT-072 foundation)."""
import json as _json
import uuid
from datetime import datetime, timezone

from pydantic import field_validator
from sqlalchemy import Column, ForeignKey, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TopologyPersonalDraftBase(SQLModel):
    topology_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("topologies.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    cytoscape_json: dict[str, object] = Field(sa_column=Column(JSON))


class TopologyPersonalDraft(TopologyPersonalDraftBase, table=True):
    __tablename__ = "topology_personal_drafts"
    __table_args__ = (
        UniqueConstraint(
            "topology_id",
            "user_id",
            name="uq_topology_personal_drafts_topology_user",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TopologyPersonalDraftUpsert(SQLModel):
    cytoscape_json: dict[str, object]
    base_version: int | None = None

    @field_validator("cytoscape_json")
    @classmethod
    def validate_cytoscape_structure(cls, v: dict[str, object]) -> dict[str, object]:
        if not isinstance(v, dict) or not v:
            raise ValueError("cytoscape_json must be a non-empty JSON object")
        serialized = _json.dumps(v)
        if len(serialized) > 5_000_000:
            raise ValueError("cytoscape_json exceeds maximum size of 5MB")
        return v


class TopologyPersonalDraftSaveResponse(SQLModel):
    topology_id: uuid.UUID
    version: int
    has_unsaved_changes: bool = False
    updated_at: datetime


class TopologyPersonalDraftDiscardResponse(SQLModel):
    topology_id: uuid.UUID
    discarded: bool
    has_unsaved_changes: bool = False
