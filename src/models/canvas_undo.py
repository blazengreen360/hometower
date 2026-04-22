"""API-only schemas for canvas undo/redo snapshot operations (HT-032)."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from src.models.types import (
    ConnectionType,
    DeviceStatus,
    DeviceType,
    ServiceProtocol,
    ServiceStatus,
)


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


class PublishedCustomFieldSnapshot(SQLModel):
    id: uuid.UUID
    key: str
    value: str


class PublishedServiceSnapshot(SQLModel):
    id: uuid.UUID
    name: str
    port: int | None = None
    protocol: ServiceProtocol
    url: str | None = None
    status: ServiceStatus
    notes: str | None = None


class PublishedServiceDependencySnapshot(SQLModel):
    service_id: uuid.UUID
    depends_on_id: uuid.UUID


class PublishedDeviceNetworkSnapshot(SQLModel):
    network_id: uuid.UUID
    ip_address: str


class PublishedAttachmentSnapshot(SQLModel):
    id: uuid.UUID
    filename: str
    stored_path: str
    content_type: str
    size_bytes: int
    created_at: datetime


class PublishedDeviceSnapshot(SQLModel):
    id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus
    ip: str | None = None
    mac: str | None = None
    os: str | None = None
    notes: str | None = None
    power_watts: int | None = None
    location_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    version: int


class PublishedDeviceDeleteSnapshot(SQLModel):
    device: PublishedDeviceSnapshot
    connections: list[PublishedConnectionSnapshot] = Field(default_factory=list)
    placements: list[DiagramPlacementSnapshot] = Field(default_factory=list)
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    custom_fields: list[PublishedCustomFieldSnapshot] = Field(default_factory=list)
    services: list[PublishedServiceSnapshot] = Field(default_factory=list)
    service_dependencies: list[PublishedServiceDependencySnapshot] = Field(default_factory=list)
    network_memberships: list[PublishedDeviceNetworkSnapshot] = Field(default_factory=list)
    attachments: list[PublishedAttachmentSnapshot] = Field(default_factory=list)
    attachment_stash_id: uuid.UUID | None = None
    restore_token: str | None = None


class PublishedDeviceCanvasDeleteResult(SQLModel):
    snapshot: PublishedDeviceDeleteSnapshot
    modified_diagrams: list[DiagramVersionRef] = Field(default_factory=list)


class PublishedDeviceCanvasRestoreResult(SQLModel):
    modified_diagrams: list[DiagramVersionRef] = Field(default_factory=list)
