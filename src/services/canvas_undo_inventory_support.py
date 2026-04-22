"""Inventory and attachment helpers for published canvas delete/restore."""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from src.models.attachment import DeviceAttachment
from src.models.canvas_undo import (
    PublishedAttachmentSnapshot,
    PublishedCustomFieldSnapshot,
    PublishedDeviceDeleteSnapshot,
    PublishedDeviceNetworkSnapshot,
    PublishedServiceDependencySnapshot,
    PublishedServiceSnapshot,
)
from src.models.custom_field import CustomField
from src.models.device_network import DeviceNetwork
from src.models.service import Service
from src.models.service_dependency import ServiceDependency
from src.repositories import (
    attachment_repository,
    custom_field_repository,
    network_repository,
    service_repository,
    tag_repository,
)
from src.services.attachment_service_storage import (
    restore_staged_device_storage,
    stage_device_storage,
)
from src.services.canvas_undo_service_support import _to_attachment_snapshot
from src.services.canvas_undo_service_support import _to_custom_field_snapshot
from src.services.canvas_undo_service_support import _to_network_membership_snapshot
from src.services.canvas_undo_service_support import _to_service_dependency_snapshot
from src.services.canvas_undo_service_support import _to_service_snapshot
from src.utils.logger import logger


def _capture_service_dependency_snapshots(
    session: Session,
    service_ids: set[uuid.UUID],
) -> list[PublishedServiceDependencySnapshot]:
    dependency_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for service_id in service_ids:
        for dependency in service_repository.get_dependency_edges_for_service(session, service_id):
            snapshot = _to_service_dependency_snapshot(dependency)
            dependency_pairs.add((snapshot.service_id, snapshot.depends_on_id))
        for dependency in service_repository.get_reverse_dependency_edges(session, service_id):
            snapshot = _to_service_dependency_snapshot(dependency)
            dependency_pairs.add((snapshot.service_id, snapshot.depends_on_id))
    return [
        PublishedServiceDependencySnapshot(service_id=service_id, depends_on_id=depends_on_id)
        for service_id, depends_on_id in sorted(dependency_pairs, key=lambda pair: (str(pair[0]), str(pair[1])))
    ]


def capture_related_snapshot_data(
    device_id: uuid.UUID,
    session: Session,
) -> tuple[
    list[uuid.UUID],
    list[PublishedCustomFieldSnapshot],
    list[PublishedServiceSnapshot],
    list[PublishedServiceDependencySnapshot],
    list[PublishedDeviceNetworkSnapshot],
    list[PublishedAttachmentSnapshot],
]:
    services = service_repository.get_by_device(session, device_id)
    return (
        [tag.id for tag in tag_repository.get_by_device(session, device_id)],
        [
            _to_custom_field_snapshot(custom_field)
            for custom_field in custom_field_repository.get_by_device(session, device_id)
        ],
        [_to_service_snapshot(service) for service in services],
        _capture_service_dependency_snapshots(session, {service.id for service in services}),
        [
            _to_network_membership_snapshot(network.id, ip_address)
            for network, ip_address in network_repository.get_by_device(session, device_id)
        ],
        [
            _to_attachment_snapshot(attachment)
            for attachment in attachment_repository.list_by_device(session, device_id)
        ],
    )


def stage_snapshot_attachments(
    device_id: uuid.UUID,
    attachment_stash_id: uuid.UUID | None,
    has_attachments: bool,
) -> None:
    if not has_attachments or attachment_stash_id is None:
        return
    try:
        staged = stage_device_storage(device_id, attachment_stash_id)
    except OSError as exc:
        raise HTTPException(status_code=409, detail="Attachment staging failed") from exc
    if not staged:
        raise HTTPException(status_code=409, detail="Attachment staging failed")


def delete_snapshot_inventory(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
) -> None:
    device_id = snapshot.device.id
    for dependency_snapshot in snapshot.service_dependencies:
        service_repository.remove_dependency(
            session,
            dependency_snapshot.service_id,
            dependency_snapshot.depends_on_id,
        )
    for service_snapshot in snapshot.services:
        service = service_repository.get_by_id(session, service_snapshot.id)
        if service is not None:
            service_repository.delete(session, service)
    for custom_field_snapshot in snapshot.custom_fields:
        custom_field = custom_field_repository.get_by_id(session, custom_field_snapshot.id)
        if custom_field is not None:
            custom_field_repository.delete(session, custom_field)
    for tag_id in snapshot.tag_ids:
        tag_repository.detach_from_device(session, device_id, tag_id)
    for membership_snapshot in snapshot.network_memberships:
        network_repository.detach_from_device(session, device_id, membership_snapshot.network_id)
    if snapshot.attachments:
        attachment_repository.delete_by_device(session, device_id)


def restore_snapshot_inventory(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
) -> None:
    device_id = snapshot.device.id
    for tag_id in snapshot.tag_ids:
        tag_repository.attach_to_device(session, device_id, tag_id)
    for custom_field_snapshot in snapshot.custom_fields:
        custom_field_repository.create(
            session,
            CustomField(
                id=custom_field_snapshot.id,
                device_id=device_id,
                key=custom_field_snapshot.key,
                value=custom_field_snapshot.value,
            ),
        )
    for service_snapshot in snapshot.services:
        service_repository.create(
            session,
            Service(
                id=service_snapshot.id,
                device_id=device_id,
                name=service_snapshot.name,
                port=service_snapshot.port,
                protocol=service_snapshot.protocol,
                url=service_snapshot.url,
                status=service_snapshot.status,
                notes=service_snapshot.notes,
            ),
        )
    for dependency_snapshot in snapshot.service_dependencies:
        service_repository.add_dependency(
            session,
            ServiceDependency(
                service_id=dependency_snapshot.service_id,
                depends_on_id=dependency_snapshot.depends_on_id,
            ),
        )
    for membership_snapshot in snapshot.network_memberships:
        network_repository.attach_to_device(
            session,
            DeviceNetwork(
                device_id=device_id,
                network_id=membership_snapshot.network_id,
                ip_address=membership_snapshot.ip_address,
            ),
        )
    for attachment_snapshot in snapshot.attachments:
        attachment_repository.create(
            session,
            DeviceAttachment(
                id=attachment_snapshot.id,
                device_id=device_id,
                filename=attachment_snapshot.filename,
                stored_path=attachment_snapshot.stored_path,
                content_type=attachment_snapshot.content_type,
                size_bytes=attachment_snapshot.size_bytes,
                created_at=attachment_snapshot.created_at,
            ),
        )


def restore_snapshot_attachments(snapshot: PublishedDeviceDeleteSnapshot) -> bool:
    if not snapshot.attachments:
        return False
    if snapshot.attachment_stash_id is None:
        raise HTTPException(status_code=400, detail="Invalid restore snapshot")
    try:
        restored = restore_staged_device_storage(snapshot.device.id, snapshot.attachment_stash_id)
    except OSError as exc:
        raise HTTPException(status_code=409, detail="Attachment restore source missing") from exc
    if not restored:
        raise HTTPException(status_code=409, detail="Attachment restore source missing")
    return True


def rollback_staged_attachments(
    device_id: uuid.UUID,
    attachment_stash_id: uuid.UUID | None,
) -> None:
    if attachment_stash_id is None:
        return
    try:
        restore_staged_device_storage(device_id, attachment_stash_id)
    except OSError:
        logger.warning(
            "Canvas delete attachment rollback failed for device={} stash={}",
            device_id,
            attachment_stash_id,
        )


def restage_restored_attachments(
    device_id: uuid.UUID,
    attachment_stash_id: uuid.UUID | None,
) -> None:
    if attachment_stash_id is None:
        return
    try:
        stage_device_storage(device_id, attachment_stash_id)
    except OSError:
        logger.warning(
            "Canvas restore attachment rollback failed for device={} stash={}",
            device_id,
            attachment_stash_id,
        )