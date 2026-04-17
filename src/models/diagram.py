"""DiagramLayout SQLModel definitions."""
import json as _json
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlalchemy import Column, ForeignKey, JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagramLayoutBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    cytoscape_json: dict[str, object] = Field(sa_column=Column(JSON))  # JSON not JSONB — SQLite compat for tests


class DiagramLayout(DiagramLayoutBase, table=True):
    __tablename__ = "diagram_layouts"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topology_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("topologies.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class DiagramLayoutCreate(DiagramLayoutBase):
    topology_id: Optional[uuid.UUID] = Field(
        default=None,
        description="If omitted, server binds the layout to the caller's default topology.",
    )
    version: Optional[int] = None

    @field_validator("cytoscape_json")
    @classmethod
    def validate_cytoscape_structure(cls, v: dict[str, object]) -> dict[str, object]:
        if not isinstance(v, dict) or not v:
            raise ValueError("cytoscape_json must be a non-empty JSON object")
        serialized = _json.dumps(v)
        if len(serialized) > 5_000_000:
            raise ValueError("cytoscape_json exceeds maximum size of 5MB")
        return v


class DiagramLayoutResponse(DiagramLayoutBase):
    id: uuid.UUID
    topology_id: Optional[uuid.UUID] = None
    version: int
    created_at: datetime
    updated_at: datetime


class DiagramLayoutSummary(SQLModel):
    id: uuid.UUID
    name: str
    topology_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class PaginatedDiagramSummary(SQLModel):
    items: list[DiagramLayoutSummary]
    total: int
    page: int
    limit: int


class DiagramLayoutUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cytoscape_json: Optional[dict[str, object]] = None
    version: int

    @field_validator("cytoscape_json")
    @classmethod
    def validate_cytoscape_structure(
        cls, v: Optional[dict[str, object]]
    ) -> Optional[dict[str, object]]:
        if v is None:
            return None
        if not isinstance(v, dict) or not v:
            raise ValueError("cytoscape_json must be a non-empty JSON object")
        serialized = _json.dumps(v)
        if len(serialized) > 5_000_000:
            raise ValueError("cytoscape_json exceeds maximum size of 5MB")
        return v
