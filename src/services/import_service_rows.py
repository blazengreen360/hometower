"""Row insertion helpers for full snapshot imports."""

import secrets

from sqlmodel import Session

from src.domain.export import topological_sort_devices, topological_sort_locations
from src.models.connection import Connection
from src.models.custom_field import CustomField
from src.models.device import Device
from src.models.device_network import DeviceNetwork
from src.models.diagram import DiagramLayout
from src.models.export_schema import ExportSchema
from src.models.location import Location, LocationCreate
from src.models.network import Network
from src.models.service import Service
from src.models.service_dependency import ServiceDependency
from src.models.tag import DeviceTag, Tag
from src.models.topology import Topology
from src.models.user import User
from src.models.workspace import Workspace
from src.utils.auth import hash_password


def insert_snapshot_rows(session: Session, payload: ExportSchema) -> None:
    """Insert all payload rows in dependency-safe order for full imports."""
    user_password_sentinel = (
        hash_password(secrets.token_hex(32)) if payload.users else ""
    )

    for user in payload.users:
        session.add(
            User(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                password_hash=user_password_sentinel,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
    session.flush()

    for workspace in payload.workspaces:
        session.add(
            Workspace(
                id=workspace.id,
                owner_id=workspace.owner_id,
                name=workspace.name,
                created_at=workspace.created_at,
                updated_at=workspace.updated_at,
            )
        )
    session.flush()

    for topology in payload.topologies:
        session.add(
            Topology(
                id=topology.id,
                workspace_id=topology.workspace_id,
                name=topology.name,
                tags=topology.tags,
                created_at=topology.created_at,
                updated_at=topology.updated_at,
            )
        )
    session.flush()

    for location in topological_sort_locations(payload.locations):
        validated = LocationCreate(
            name=location.name,
            type=location.type,
            lat=location.lat,
            lng=location.lng,
            rack=location.rack,
            row=location.row,
            parent_id=location.parent_id,
        )
        session.add(
            Location(
                id=location.id,
                name=validated.name,
                type=validated.type,
                lat=validated.lat,
                lng=validated.lng,
                rack=validated.rack,
                row=validated.row,
                parent_id=validated.parent_id,
                created_at=location.created_at,
                updated_at=location.updated_at,
            )
        )

    for tag in payload.tags:
        session.add(
            Tag(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                created_at=tag.created_at,
            )
        )

    for network in payload.networks:
        session.add(
            Network(
                id=network.id,
                name=network.name,
                vlan_id=network.vlan_id,
                cidr=network.cidr,
                gateway=network.gateway,
                description=network.description,
                color=network.color,
                created_at=network.created_at,
                updated_at=network.updated_at,
            )
        )

    for device in topological_sort_devices(payload.devices):
        session.add(
            Device(
                id=device.id,
                name=device.name,
                type=device.type,
                status=device.status,
                ip=device.ip,
                mac=device.mac,
                os=device.os,
                notes=device.notes,
                location_id=device.location_id,
                parent_id=device.parent_id,
                created_at=device.created_at,
                updated_at=device.updated_at,
            )
        )

    for membership in payload.device_networks:
        session.add(
            DeviceNetwork(
                device_id=membership.device_id,
                network_id=membership.network_id,
                ip_address=membership.ip_address,
                created_at=membership.created_at,
            )
        )

    for service in payload.services:
        session.add(
            Service(
                id=service.id,
                device_id=service.device_id,
                name=service.name,
                port=service.port,
                protocol=service.protocol,
                url=service.url,
                status=service.status,
                notes=service.notes,
                created_at=service.created_at,
                updated_at=service.updated_at,
            )
        )

    for dependency in payload.service_dependencies:
        session.add(
            ServiceDependency(
                service_id=dependency.service_id,
                depends_on_id=dependency.depends_on_id,
            )
        )

    for connection in payload.connections:
        session.add(
            Connection(
                id=connection.id,
                source_id=connection.source_id,
                target_id=connection.target_id,
                type=connection.type,
                label=connection.label,
                created_at=connection.created_at,
                updated_at=connection.updated_at,
            )
        )

    for device_tag in payload.device_tags:
        session.add(DeviceTag(device_id=device_tag.device_id, tag_id=device_tag.tag_id))

    for custom_field in payload.custom_fields:
        session.add(
            CustomField(
                id=custom_field.id,
                device_id=custom_field.device_id,
                key=custom_field.key,
                value=custom_field.value,
                created_at=custom_field.created_at,
                updated_at=custom_field.updated_at,
            )
        )

    for diagram in payload.diagram_layouts:
        session.add(
            DiagramLayout(
                id=diagram.id,
                name=diagram.name,
                cytoscape_json=diagram.cytoscape_json,
                topology_id=diagram.topology_id,
                version=diagram.version,
                created_at=diagram.created_at,
                updated_at=diagram.updated_at,
            )
        )

    session.flush()
