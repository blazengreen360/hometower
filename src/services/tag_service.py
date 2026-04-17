"""Tag service — orchestrates tag domain logic and tag repository (HT-006)."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain.inventory import normalize_tag_name
from src.models.tag import Tag, TagCreate, TagUpdate, TagWithCountResponse
from src.repositories import device_repository, tag_repository
from src.utils.logger import logger


def _raise_tag_conflict(exc: IntegrityError, session: Session) -> None:
    """Rollback failed transaction and surface duplicate-name conflicts as HTTP 409."""
    session.rollback()
    raise HTTPException(status_code=409, detail="Tag name already exists") from exc


def create(data: TagCreate, session: Session) -> Tag:
    """Normalize name, check for case-insensitive duplicate, then persist."""
    normalized = normalize_tag_name(data.name)
    if tag_repository.get_by_name_normalized(session, normalized) is not None:
        raise HTTPException(status_code=409, detail="Tag name already exists")
    tag = Tag(name=data.name, color=data.color)
    try:
        result = tag_repository.create(session, tag)
        session.commit()
    except IntegrityError as exc:
        _raise_tag_conflict(exc, session)
    logger.info("Tag created: id={} name={}", result.id, result.name)
    return result


def get_all(session: Session) -> list[TagWithCountResponse]:
    """Return all tags with device counts."""
    pairs = tag_repository.get_all_with_counts(session)
    return [
        TagWithCountResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            created_at=tag.created_at,
            device_count=count,
        )
        for tag, count in pairs
    ]


def get_by_id(tag_id: uuid.UUID, session: Session) -> Tag:
    """Return tag or raise HTTP 404."""
    tag = tag_repository.get_by_id(session, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


def update(tag_id: uuid.UUID, data: TagUpdate, session: Session) -> Tag:
    """Partially update a tag; re-check name uniqueness if name changes."""
    tag = tag_repository.get_by_id(session, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data:
        normalized = normalize_tag_name(update_data["name"])
        existing = tag_repository.get_by_name_normalized(session, normalized)
        if existing is not None and existing.id != tag_id:
            raise HTTPException(status_code=409, detail="Tag name already exists")

    for field, value in update_data.items():
        setattr(tag, field, value)

    try:
        result = tag_repository.update(session, tag)
        session.commit()
    except IntegrityError as exc:
        _raise_tag_conflict(exc, session)
    logger.info("Tag updated: id={} name={}", result.id, result.name)
    return result


def delete(tag_id: uuid.UUID, session: Session) -> None:
    """Delete tag; DB CASCADE removes device_tags rows."""
    tag = tag_repository.get_by_id(session, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_repository.delete(session, tag)
    session.commit()
    logger.info("Tag deleted: id={}", tag_id)


def attach_to_device(
    device_id: uuid.UUID, tag_id: uuid.UUID, session: Session
) -> None:
    """Idempotent attach: verify device exists (404), verify tag exists (404), then attach."""
    if device_repository.get_by_id(session, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if tag_repository.get_by_id(session, tag_id) is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_repository.attach_to_device(session, device_id, tag_id)
    session.commit()
    logger.info("Tag attached: device_id={} tag_id={}", device_id, tag_id)


def detach_from_device(
    device_id: uuid.UUID, tag_id: uuid.UUID, session: Session
) -> None:
    """Detach tag from device. No-op if association does not exist."""
    tag_repository.detach_from_device(session, device_id, tag_id)
    session.commit()
    logger.info("Tag detached: device_id={} tag_id={}", device_id, tag_id)


def get_by_device(device_id: uuid.UUID, session: Session) -> list[Tag]:
    """Return tags for a device. Raises HTTP 404 if device not found."""
    if device_repository.get_by_id(session, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return tag_repository.get_by_device(session, device_id)
