"""Custom field service — orchestrates custom field domain logic and repository (HT-007)."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain.inventory import normalize_custom_field_key
from src.models.custom_field import CustomField, CustomFieldCreate, CustomFieldUpdate
from src.repositories import custom_field_repository, device_repository
from src.utils.logger import logger


def _raise_custom_field_conflict(exc: IntegrityError, session: Session) -> None:
    """Rollback failed transaction and map uniqueness conflicts to HTTP 409."""
    session.rollback()
    raise HTTPException(
        status_code=409,
        detail="Custom field key already exists for this device",
    ) from exc


def _assert_device_exists(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    """Raise HTTP 404 if the given device_id does not exist."""
    if device_repository.get_by_id(session, device_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")


def create(
    device_id: uuid.UUID,
    data: CustomFieldCreate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> CustomField:
    """Normalize key, check per-device uniqueness (409), persist."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    normalized = normalize_custom_field_key(data.key)
    existing = custom_field_repository.get_by_device_and_key_normalized(
        session, device_id, normalized
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Custom field key already exists for this device",
        )
    cf = CustomField(device_id=device_id, key=data.key, value=data.value)
    try:
        result = custom_field_repository.create(session, cf)
        session.commit()
    except IntegrityError as exc:
        _raise_custom_field_conflict(exc, session)
    logger.info(
        "CustomField created: id={} device_id={} key={}", result.id, device_id, result.key
    )
    return result


def get_by_device(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[CustomField]:
    """Return all custom fields for a device. HTTP 404 if device not found."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    return custom_field_repository.get_by_device(session, device_id)


def update(
    device_id: uuid.UUID,
    cf_id: uuid.UUID,
    data: CustomFieldUpdate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> CustomField:
    """Partial update; re-check key uniqueness if key changes.

    HTTP 404 if cf not found or doesn't belong to device_id.
    HTTP 409 if new key collides with existing key on same device.
    """
    _assert_device_exists(device_id, session, owner_id=owner_id)
    cf = custom_field_repository.get_by_id(session, cf_id)
    if cf is None or cf.device_id != device_id:
        raise HTTPException(status_code=404, detail="Custom field not found")

    update_data = data.model_dump(exclude_unset=True)

    if "key" in update_data:
        normalized = normalize_custom_field_key(update_data["key"])
        existing = custom_field_repository.get_by_device_and_key_normalized(
            session, device_id, normalized
        )
        if existing is not None and existing.id != cf_id:
            raise HTTPException(
                status_code=409,
                detail="Custom field key already exists for this device",
            )

    for field, value in update_data.items():
        setattr(cf, field, value)

    try:
        result = custom_field_repository.update(session, cf)
        session.commit()
    except IntegrityError as exc:
        _raise_custom_field_conflict(exc, session)
    logger.info("CustomField updated: id={} device_id={}", result.id, device_id)
    return result


def delete(
    device_id: uuid.UUID,
    cf_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    """Delete custom field. HTTP 404 if not found or wrong device."""
    _assert_device_exists(device_id, session, owner_id=owner_id)
    cf = custom_field_repository.get_by_id(session, cf_id)
    if cf is None or cf.device_id != device_id:
        raise HTTPException(status_code=404, detail="Custom field not found")
    custom_field_repository.delete(session, cf)
    session.commit()
    logger.info("CustomField deleted: id={} device_id={}", cf_id, device_id)
