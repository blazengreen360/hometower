"""Attachment service — validation, storage, and DB orchestration (HT-042)."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.attachment import DeviceAttachment, DeviceAttachmentResponse
from src.repositories import attachment_repository, device_repository
from src.services.attachment_service_storage import (
    build_thumbnail_path as _build_thumbnail_path_for_path,
    cleanup_device_storage,
    delete_path as _delete_path,
    relative_path as _relative_path,
    remove_device_dir_if_empty as _remove_device_dir_if_empty,
    resolve_original_path,
    resolve_thumbnail_path,
    storage_root as _storage_root,
    write_file as _write_file,
)
from src.services.attachment_service_validation import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS_PER_DEVICE,
    build_thumbnail_bytes as _build_thumbnail_bytes,
    extension_for_filename as _extension_for_filename,
    is_image_content_type as _is_image_content_type,
    normalize_filename as _normalize_filename,
    validate_content_type as _validate_content_type,
)
from src.utils.logger import logger


def _assert_device_exists(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    if device_repository.get_by_id(session, device_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")


def _to_response(attachment: DeviceAttachment) -> DeviceAttachmentResponse:
    has_thumbnail = _is_image_content_type(attachment.content_type) and resolve_thumbnail_path(
        attachment
    ).is_file()
    return DeviceAttachmentResponse(
        id=attachment.id,
        device_id=attachment.device_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        created_at=attachment.created_at,
        is_image=_is_image_content_type(attachment.content_type),
        has_thumbnail=has_thumbnail,
    )


def list_for_device(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[DeviceAttachmentResponse]:
    """List all attachments for a device."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    attachments = attachment_repository.list_by_device(session, device_id)
    return [_to_response(attachment) for attachment in attachments]


def upload(
    device_id: uuid.UUID,
    filename: str,
    raw: bytes,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> DeviceAttachmentResponse:
    """Validate, store, and persist an uploaded attachment."""
    _assert_device_exists(device_id, session, owner_id=owner_id)

    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    if attachment_repository.count_by_device(session, device_id) >= MAX_ATTACHMENTS_PER_DEVICE:
        raise HTTPException(status_code=422, detail="Maximum 20 attachments per device")

    safe_filename = _normalize_filename(filename)
    ext = _extension_for_filename(safe_filename)
    content_type = _validate_content_type(safe_filename, raw)
    thumbnail_bytes = _build_thumbnail_bytes(raw, ext)

    storage_id = uuid.uuid4()
    stored_name = f"{storage_id}.{ext}"
    stored_path = _relative_path(device_id, stored_name)
    absolute_path = _storage_root() / stored_path
    thumbnail_path = _build_thumbnail_path_for_path(absolute_path)

    try:
        _write_file(absolute_path, raw)
        if thumbnail_bytes is not None:
            _write_file(thumbnail_path, thumbnail_bytes)
    except OSError as exc:
        logger.error("Attachment storage write failed for device {}: {}", device_id, str(exc))
        raise HTTPException(status_code=500, detail="Could not store attachment") from exc

    attachment = DeviceAttachment(
        device_id=device_id,
        filename=safe_filename,
        stored_path=stored_path,
        content_type=content_type,
        size_bytes=len(raw),
    )
    try:
        created = attachment_repository.create(session, attachment)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _delete_path(absolute_path)
        if thumbnail_bytes is not None:
            _delete_path(thumbnail_path)
        raise HTTPException(status_code=409, detail="Attachment create conflict") from exc

    logger.info(
        "Attachment uploaded: device_id={} attachment_id={} filename={}",
        device_id,
        created.id,
        safe_filename,
    )
    return _to_response(created)


def get_attachment(
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> DeviceAttachment:
    """Return one attachment scoped to a device or raise 404."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    attachment = attachment_repository.get_by_id(session, device_id, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


def delete(
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    """Delete one attachment, its files, and its DB row."""
    attachment = get_attachment(
        device_id,
        attachment_id,
        session,
        owner_id=owner_id,
    )
    original_path = resolve_original_path(attachment)
    thumbnail_path = resolve_thumbnail_path(attachment)

    attachment_repository.delete(session, attachment)
    session.commit()
    _delete_path(original_path)
    _delete_path(thumbnail_path)
    _remove_device_dir_if_empty(device_id)
    logger.info(
        "Attachment deleted: device_id={} attachment_id={}",
        device_id,
        attachment_id,
    )


def delete_all_for_device(
    device_id: uuid.UUID,
    session: Session,
    *,
    commit: bool = True,
) -> int:
    """Delete all attachments and files for a device."""
    deleted_count = attachment_repository.delete_by_device(session, device_id)
    if commit:
        session.commit()
        cleanup_device_storage(device_id)
    return deleted_count


def is_image_attachment(attachment: DeviceAttachment) -> bool:
    """Return True when the attachment can be displayed inline as an image."""
    return _is_image_content_type(attachment.content_type)