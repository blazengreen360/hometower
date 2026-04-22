"""Helper mappers for canvas undo snapshot persistence."""

import uuid
from datetime import datetime, timezone

from src.models.attachment import DeviceAttachment
from src.models.canvas_undo import (
    PublishedAttachmentSnapshot,
    PublishedConnectionSnapshot,
    PublishedCustomFieldSnapshot,
    PublishedDeviceNetworkSnapshot,
    PublishedDeviceSnapshot,
    PublishedServiceDependencySnapshot,
    PublishedServiceSnapshot,
)
from src.models.connection import Connection
from src.models.custom_field import CustomField
from src.models.device import Device
from src.models.service import Service
from src.models.service_dependency import ServiceDependency

_RESTORE_OWNER_KEY = "__hometower_owner_id"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_device_snapshot(device: Device) -> PublishedDeviceSnapshot:
    return PublishedDeviceSnapshot(
        id=device.id,
        name=device.name,
        type=device.type,
        status=device.status,
        ip=device.ip,
        mac=device.mac,
        os=device.os,
        notes=device.notes,
        power_watts=device.power_watts,
        location_id=device.location_id,
        parent_id=device.parent_id,
        version=device.version,
    )


def _to_connection_snapshot(connection: Connection) -> PublishedConnectionSnapshot:
    return PublishedConnectionSnapshot(
        id=connection.id,
        source_id=connection.source_id,
        target_id=connection.target_id,
        type=connection.type,
        label=connection.label,
    )


def _to_custom_field_snapshot(custom_field: CustomField) -> PublishedCustomFieldSnapshot:
    return PublishedCustomFieldSnapshot(
        id=custom_field.id,
        key=custom_field.key,
        value=custom_field.value,
    )


def _to_service_snapshot(service: Service) -> PublishedServiceSnapshot:
    return PublishedServiceSnapshot(
        id=service.id,
        name=service.name,
        port=service.port,
        protocol=service.protocol,
        url=service.url,
        status=service.status,
        notes=service.notes,
    )


def _to_service_dependency_snapshot(
    dependency: ServiceDependency,
) -> PublishedServiceDependencySnapshot:
    return PublishedServiceDependencySnapshot(
        service_id=dependency.service_id,
        depends_on_id=dependency.depends_on_id,
    )


def _to_network_membership_snapshot(
    network_id: uuid.UUID,
    ip_address: str,
) -> PublishedDeviceNetworkSnapshot:
    return PublishedDeviceNetworkSnapshot(
        network_id=network_id,
        ip_address=ip_address,
    )


def _to_attachment_snapshot(attachment: DeviceAttachment) -> PublishedAttachmentSnapshot:
    return PublishedAttachmentSnapshot(
        id=attachment.id,
        filename=attachment.filename,
        stored_path=attachment.stored_path,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        created_at=attachment.created_at,
    )


def _snapshot_node_with_owner(
    node: dict[str, object],
    owner_id: uuid.UUID | None,
) -> dict[str, object]:
    snapshot = dict(node)
    if owner_id is None:
        return snapshot
    snapshot[_RESTORE_OWNER_KEY] = str(owner_id)
    return snapshot


def _restore_node_without_owner(node: dict[str, object]) -> dict[str, object]:
    restored = dict(node)
    restored.pop(_RESTORE_OWNER_KEY, None)
    return restored