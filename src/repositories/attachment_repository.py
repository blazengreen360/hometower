"""Attachment repository — DB operations for device attachments."""
import uuid

from sqlmodel import Session, col, select

from src.models.attachment import DeviceAttachment


def create(session: Session, attachment: DeviceAttachment) -> DeviceAttachment:
    """Persist an attachment and return the refreshed instance."""
    session.add(attachment)
    session.flush()
    session.refresh(attachment)
    return attachment


def list_by_device(session: Session, device_id: uuid.UUID) -> list[DeviceAttachment]:
    """Return all attachments for a device ordered newest-first."""
    statement = (
        select(DeviceAttachment)
        .where(col(DeviceAttachment.device_id) == device_id)
        .order_by(col(DeviceAttachment.created_at).desc())
    )
    return list(session.exec(statement).all())


def count_by_device(session: Session, device_id: uuid.UUID) -> int:
    """Return the attachment count for a device."""
    return len(list_by_device(session, device_id))


def get_by_id(
    session: Session,
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> DeviceAttachment | None:
    """Return one attachment scoped to a device, or None."""
    statement = select(DeviceAttachment).where(
        col(DeviceAttachment.device_id) == device_id,
        col(DeviceAttachment.id) == attachment_id,
    )
    return session.exec(statement).first()


def delete(session: Session, attachment: DeviceAttachment) -> None:
    """Delete one attachment row."""
    session.delete(attachment)
    session.flush()


def delete_by_device(session: Session, device_id: uuid.UUID) -> int:
    """Delete all attachments for a device and return the row count."""
    attachments = list_by_device(session, device_id)
    for attachment in attachments:
        session.delete(attachment)
    session.flush()
    return len(attachments)