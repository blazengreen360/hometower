"""Topology editor API schemas for history and personal drafts (HT-072)."""
import json as _json
import uuid
from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class TopologyEditorStateResponse(SQLModel):
    topology_id: uuid.UUID
    current_diagram_id: uuid.UUID | None = None
    current_diagram_version: int | None = None
    draft_version: int | None = None
    has_unsaved_changes: bool = False
    source: str
    cytoscape_json: dict[str, object]


class TopologySaveVersionRequest(SQLModel):
    snapshot_name: str | None = Field(default=None, min_length=1, max_length=255)
    cytoscape_json: dict[str, object] | None = None
    base_diagram_version: int | None = None

    @field_validator("cytoscape_json")
    @classmethod
    def validate_cytoscape_structure(
        cls,
        v: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if v is None:
            return None
        if not isinstance(v, dict) or not v:
            raise ValueError("cytoscape_json must be a non-empty JSON object")
        serialized = _json.dumps(v)
        if len(serialized) > 5_000_000:
            raise ValueError("cytoscape_json exceeds maximum size of 5MB")
        return v


class TopologyRestoreHistoryRequest(SQLModel):
    base_diagram_version: int | None = None


class TopologySaveVersionResponse(SQLModel):
    topology_id: uuid.UUID
    history_entry_id: uuid.UUID
    current_diagram_id: uuid.UUID
    current_diagram_version: int
    snapshot_name: str
    action: str
    restored_from_history_entry_id: uuid.UUID | None = None
    created_at: datetime
    draft_version: int | None = None
    has_unsaved_changes: bool = False
    cytoscape_json: dict[str, object]
