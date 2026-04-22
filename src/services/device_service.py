import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import devices as device_domain
from src.models.device import Device, DeviceCreate, DevicePlacement, DeviceResponseEnriched, DeviceUpdate
from src.repositories import (
    connection_repository,
    device_repository,
    diagram_repository,
    topology_history_repository,
    topology_repository,
    workspace_repository,
)
from src.services import attachment_service
from src.services.device_enrichment_service import get_all_enriched as _get_all_enriched
from src.services.device_enrichment_service import get_by_id_enriched as _get_by_id_enriched
from src.services.device_layout_service_support import _current_layouts
from src.services.device_layout_service_support import get_device_placements as _get_device_placements
from src.services.device_layout_service_support import get_placed_device_ids as _get_placed_device_ids
from src.services.device_update_service_support import assert_location_exists
from src.services.device_update_service_support import assert_parent_exists
from src.services.device_update_service_support import prepare_device_update_data
from src.services.device_update_service_support import raise_device_conflict
from src.utils.logger import logger


def _assert_workspace_owned(workspace_id: uuid.UUID | None, owner_id: uuid.UUID | None, session: Session) -> None:
    if workspace_id is None:
        return
    workspace = workspace_repository.get_by_id(session, workspace_id)
    if workspace is None or owner_id is None or workspace.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Workspace not found")

def create(data: DeviceCreate, owner_id: uuid.UUID, session: Session) -> Device:
    validated_ip = device_domain.validate_ip(data.ip)
    if data.location_id is not None:
        assert_location_exists(data.location_id, session)
    if data.parent_id is not None:
        assert_parent_exists(data.parent_id, session, owner_id=owner_id)
    device = Device(
        name=data.name,
        type=data.type,
        status=data.status,
        ip=validated_ip,
        mac=device_domain.validate_mac(data.mac),
        os=data.os,
        notes=data.notes,
        power_watts=data.power_watts,
        location_id=data.location_id,
        parent_id=data.parent_id,
        owner_id=owner_id,
    )
    try:
        result = device_repository.create(session, device)
        session.commit()
    except IntegrityError as exc:
        raise_device_conflict(exc, session, "Device create conflict")
    logger.info("Device created: id={} name={}", result.id, result.name)
    return result

def get_by_id(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
    enforce_owner_scope: bool = True,
) -> Device:
    device = device_repository.get_by_id(
        session,
        device_id,
        owner_id=owner_id,
        enforce_owner_scope=enforce_owner_scope,
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

def get_all(
    session: Session,
    page: int,
    limit: int,
    sort: str | None = None,
    workspace_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[Device], int]:
    _assert_workspace_owned(workspace_id, owner_id, session)
    return device_repository.get_all(
        session,
        page,
        limit,
        sort=sort,
        workspace_id=workspace_id,
        owner_id=owner_id,
    )

def get_all_enriched(
    session: Session,
    page: int,
    limit: int,
    include: set[str],
    q: str | None = None,
    sort: str | None = None,
    workspace_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[DeviceResponseEnriched], int]:
    _assert_workspace_owned(workspace_id, owner_id, session)
    return _get_all_enriched(
        session,
        page,
        limit,
        include,
        q=q,
        sort=sort,
        workspace_id=workspace_id,
        owner_id=owner_id,
    )

def get_by_id_enriched(
    device_id: uuid.UUID,
    session: Session,
    include: set[str],
    owner_id: uuid.UUID | None = None,
) -> DeviceResponseEnriched:
    return _get_by_id_enriched(device_id, session, include, owner_id=owner_id)

def update(
    device_id: uuid.UUID,
    data: DeviceUpdate,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> Device:
    device = device_repository.get_by_id(session, device_id, owner_id=owner_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    update_data = prepare_device_update_data(
        device_id,
        device,
        data,
        session,
        owner_id=owner_id,
    )
    for field, value in update_data.items():
        setattr(device, field, value)

    device.version += 1
    device.updated_at = datetime.now(timezone.utc)
    try:
        result = device_repository.update(session, device)
        session.commit()
    except IntegrityError as exc:
        raise_device_conflict(exc, session, "Device update conflict")
    logger.info("Device updated: id={} name={}", result.id, result.name)
    return result

def get_device_placements(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[DevicePlacement]:
    return _get_device_placements(device_id, session, owner_id=owner_id)

def get_placed_device_ids(
    session: Session,
    owner_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    _assert_workspace_owned(workspace_id, owner_id, session)
    return _get_placed_device_ids(session, owner_id=owner_id, workspace_id=workspace_id)

def _clean_device_from_views(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> int:
    device_id_str = str(device_id)
    layouts = _current_layouts(session, owner_id=owner_id)
    immutable_diagram_ids = topology_history_repository.get_immutable_diagram_ids(
        session,
        {layout.id for layout in layouts},
    )
    modified = 0
    for layout in layouts:
        if layout.id in immutable_diagram_ids:
            continue
        cj = layout.cytoscape_json
        if not isinstance(cj, dict):
            continue
        new_cj, changed = device_domain.filter_device_from_cytoscape_json(
            cj, device_id_str
        )
        if changed:
            layout.cytoscape_json = new_cj  # type: ignore[assignment]
            layout.updated_at = datetime.now(timezone.utc)
            diagram_repository.update(session, layout)
            modified += 1
    return modified

def delete(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    device = device_repository.get_by_id(session, device_id, owner_id=owner_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    child_count = device_repository.count_children(session, device_id, owner_id=owner_id)
    try:
        device_domain.validate_device_no_children(child_count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    conn_count = connection_repository.delete_by_device(session, device_id)
    if conn_count:
        logger.info("Cascade-deleted {} connection(s) for device={}", conn_count, device_id)
    attachment_count = attachment_service.delete_all_for_device(device_id, session, commit=False)
    if attachment_count:
        logger.info("Cascade-deleted {} attachment(s) for device={}", attachment_count, device_id)
    view_count = _clean_device_from_views(device_id, session, owner_id=owner_id)
    if view_count:
        logger.info("Cleaned device={} from {} view(s)", device_id, view_count)
    device_repository.delete(session, device)
    session.commit()
    if attachment_count:
        attachment_service.cleanup_device_storage(device_id)
    logger.info("Device deleted: id={}", device_id)
