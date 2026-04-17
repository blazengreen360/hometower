"""Export schema — Pydantic-only wire format for backup/restore (HT-012/HT-013).

This module hides the canonical wire format. No table=True — never persisted.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.models.types import (
    ConnectionType,
    DeviceStatus,
    DeviceType,
    LocationType,
    Role,
    ServiceProtocol,
    ServiceStatus,
)


class ExportedDevice(BaseModel):
    id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus = DeviceStatus.Active
    ip: Optional[str] = None
    mac: Optional[str] = None
    os: Optional[str] = None
    notes: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    parent_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ExportedConnection(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    type: ConnectionType
    label: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExportedLocation(BaseModel):
    id: uuid.UUID
    name: str
    type: LocationType
    lat: Optional[float] = None
    lng: Optional[float] = None
    rack: Optional[str] = None
    row: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ExportedTag(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    created_at: datetime
    # Note: Tag model has no updated_at field


class ExportedDeviceTag(BaseModel):
    # DeviceTag is a composite-PK join table with no id or created_at
    device_id: uuid.UUID
    tag_id: uuid.UUID


class ExportedNetwork(BaseModel):
    id: uuid.UUID
    name: str
    vlan_id: Optional[int] = None
    cidr: str
    gateway: Optional[str] = None
    description: Optional[str] = None
    color: str
    created_at: datetime
    updated_at: datetime


class ExportedDeviceNetwork(BaseModel):
    device_id: uuid.UUID
    network_id: uuid.UUID
    ip_address: str
    created_at: datetime


class ExportedCustomField(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    key: str
    value: str
    created_at: datetime
    updated_at: datetime


class ExportedService(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    name: str
    port: Optional[int] = None
    protocol: ServiceProtocol
    url: Optional[str] = None
    status: ServiceStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExportedServiceDependency(BaseModel):
    service_id: uuid.UUID
    depends_on_id: uuid.UUID


class ExportedWorkspace(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


class ExportedTopology(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class ExportedDiagramLayout(BaseModel):
    id: uuid.UUID
    name: str
    cytoscape_json: dict[str, object]
    topology_id: Optional[uuid.UUID] = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class ExportedUser(BaseModel):
    """password_hash is intentionally absent from this schema."""
    id: uuid.UUID
    username: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExportSchema(BaseModel):
    version: str
    exported_at: datetime
    devices: list[ExportedDevice]
    connections: list[ExportedConnection]
    locations: list[ExportedLocation]
    tags: list[ExportedTag]
    device_tags: list[ExportedDeviceTag]
    networks: list[ExportedNetwork] = []
    device_networks: list[ExportedDeviceNetwork] = []
    custom_fields: list[ExportedCustomField]
    services: list[ExportedService] = []
    service_dependencies: list[ExportedServiceDependency] = []
    workspaces: list[ExportedWorkspace] = []
    topologies: list[ExportedTopology] = []
    diagram_layouts: list[ExportedDiagramLayout]
    users: list[ExportedUser]
