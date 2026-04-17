"""API-only schemas for canvas undo/redo snapshot operations (HT-032)."""

import uuid

from sqlmodel import Field, SQLModel

from src.models.types import ConnectionType, DeviceStatus, DeviceType


class DiagramVersionRef(SQLModel):
    diagram_id: uuid.UUID
    version: int


class DiagramPlacementSnapshot(SQLModel):
    diagram_id: uuid.UUID
    node: dict[str, object]
    was_collapsed: bool = False


class PublishedConnectionSnapshot(SQLModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    type: ConnectionType
    label: str | None = None


class PublishedDeviceSnapshot(SQLModel):
    id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus
    ip: str | None = None
    mac: str | None = None
    os: str | None = None
    notes: str | None = None
    location_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    version: int


class PublishedDeviceDeleteSnapshot(SQLModel):
    device: PublishedDeviceSnapshot
    connections: list[PublishedConnectionSnapshot] = Field(default_factory=list)
    placements: list[DiagramPlacementSnapshot] = Field(default_factory=list)


class PublishedDeviceCanvasDeleteResult(SQLModel):
    snapshot: PublishedDeviceDeleteSnapshot
    modified_diagrams: list[DiagramVersionRef] = Field(default_factory=list)


class PublishedDeviceCanvasRestoreResult(SQLModel):
    modified_diagrams: list[DiagramVersionRef] = Field(default_factory=list)
