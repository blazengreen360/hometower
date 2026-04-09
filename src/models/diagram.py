"""DiagramLayout SQLModel definitions."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagramLayoutBase(SQLModel):
    name: str = Field(max_length=255)
    cytoscape_json: dict[str, object] = Field(sa_column=Column(JSON))  # JSON not JSONB — SQLite compat for tests


class DiagramLayout(DiagramLayoutBase, table=True):
    __tablename__ = "diagram_layouts"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class DiagramLayoutCreate(DiagramLayoutBase):
    @field_validator("cytoscape_json")
    @classmethod
    def validate_cytoscape_structure(cls, v: dict[str, object]) -> dict[str, object]:
        if not isinstance(v, dict) or not v:
            raise ValueError("cytoscape_json must be a non-empty JSON object")
        return v


class DiagramLayoutResponse(DiagramLayoutBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DiagramLayoutSummary(SQLModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class PaginatedDiagramSummary(SQLModel):
    items: list[DiagramLayoutSummary]
    total: int
    page: int
    limit: int
