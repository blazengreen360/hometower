"""Device enrichment service — enriched reads with tags, fields, services, hierarchy."""
import uuid

from fastapi import HTTPException
from sqlmodel import Session

from src.models.device_network import DeviceNetworkNetworkRef
from src.models.custom_field import CustomFieldResponse
from src.models.device import DeviceResponseEnriched
from src.models.service import ServiceResponse
from src.models.tag import TagResponse
from src.repositories import (
    custom_field_repository,
    device_repository,
    location_repository,
    network_repository,
    service_repository,
    tag_repository,
)


def _load_parent_chain(
    device_id: uuid.UUID, session: Session
) -> list["DeviceResponse"]:  # type: ignore[name-defined]
    """Walk device.parent_id upward and return ancestors nearest→root.

    Depth-capped at 50 hops as a defensive guard against pre-existing
    corruption; legitimate hierarchies are 3-5 levels deep.
    """
    from src.models.device import DeviceResponse

    chain: list[DeviceResponse] = []
    current = device_repository.get_by_id(session, device_id)
    if current is None:
        return chain

    depth = 0
    parent_id = current.parent_id
    while parent_id is not None:
        if depth >= 50:
            break
        parent = device_repository.get_by_id(session, parent_id)
        if parent is None:
            break
        chain.append(DeviceResponse.model_validate(parent.model_dump()))
        parent_id = parent.parent_id
        depth += 1
    return chain


def _apply_collection_enrichment(
    session: Session,
    items: list[DeviceResponseEnriched],
    include: set[str],
) -> None:
    """Attach include=tags/custom_fields/services/networks using batched repository reads."""
    if not items:
        return

    device_ids = [item.id for item in items]

    if "tags" in include:
        tags_by_device = tag_repository.get_by_device_ids(session, device_ids)
        for item in items:
            raw_tags = tags_by_device.get(item.id, [])
            item.tags = [TagResponse.model_validate(t.model_dump()) for t in raw_tags]

    if "custom_fields" in include:
        cfs_by_device = custom_field_repository.get_by_device_ids(session, device_ids)
        for item in items:
            raw_cfs = cfs_by_device.get(item.id, [])
            item.custom_fields = [
                CustomFieldResponse.model_validate(cf.model_dump()) for cf in raw_cfs
            ]

    if "services" in include:
        svcs_by_device = service_repository.get_by_device_ids(session, device_ids)
        for item in items:
            raw_svcs = svcs_by_device.get(item.id, [])
            item.services = [
                ServiceResponse.model_validate(s.model_dump()) for s in raw_svcs
            ]

    if "networks" in include:
        nets_by_device = network_repository.get_by_device_ids(session, device_ids)
        for item in items:
            raw_nets = nets_by_device.get(item.id, [])
            item.networks = [
                DeviceNetworkNetworkRef(
                    network_id=network.id,
                    name=network.name,
                    vlan_id=network.vlan_id,
                    cidr=network.cidr,
                    gateway=network.gateway,
                    color=network.color,
                    ip_address=ip_address,
                )
                for network, ip_address in raw_nets
            ]


def get_all_enriched(
    session: Session, page: int, limit: int, include: set[str],
    q: str | None = None, sort: str | None = None,
) -> tuple[list[DeviceResponseEnriched], int]:
    """Return enriched device list. Supports include={'location', 'tags', 'custom_fields', 'services', 'networks'}."""
    if q:
        from src.domain.search import parse_query
        parsed = parse_query(q)
        if not parsed.is_empty():
            pairs, total = device_repository.search(session, parsed, page, limit)
            items = [
                DeviceResponseEnriched.model_validate(
                    {**device.model_dump(), "location_name": loc_name}
                )
                for device, loc_name in pairs
            ]
            _apply_collection_enrichment(session, items, include)
            return items, total

    if "location" in include:
        pairs, total = device_repository.get_all_with_location(session, page, limit, sort=sort)
        items = [
            DeviceResponseEnriched.model_validate(
                {**device.model_dump(), "location_name": loc_name}
            )
            for device, loc_name in pairs
        ]
    else:
        devices, total = device_repository.get_all(session, page, limit, sort=sort)
        items = [
            DeviceResponseEnriched.model_validate(device.model_dump())
            for device in devices
        ]

    _apply_collection_enrichment(session, items, include)
    return items, total


def get_by_id_enriched(
    device_id: uuid.UUID, session: Session, include: set[str]
) -> DeviceResponseEnriched:
    """Return a single device enriched with requested fields. HTTP 404 if not found."""
    device = device_repository.get_by_id(session, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    loc_name: str | None = None
    if "location" in include and device.location_id is not None:
        loc = location_repository.get_by_id(session, device.location_id)
        loc_name = loc.name if loc is not None else None

    enriched = DeviceResponseEnriched.model_validate(
        {**device.model_dump(), "location_name": loc_name}
    )
    if "tags" in include:
        raw_tags = tag_repository.get_by_device(session, device_id)
        enriched.tags = [TagResponse.model_validate(t.model_dump()) for t in raw_tags]
    if "custom_fields" in include:
        raw_cfs = custom_field_repository.get_by_device(session, device_id)
        enriched.custom_fields = [
            CustomFieldResponse.model_validate(cf.model_dump()) for cf in raw_cfs
        ]
    if "services" in include:
        svcs = service_repository.get_by_device(session, device_id)
        enriched.services = [ServiceResponse.model_validate(s.model_dump()) for s in svcs]
    if "networks" in include:
        raw_nets = network_repository.get_by_device(session, device_id)
        enriched.networks = [
            DeviceNetworkNetworkRef(
                network_id=network.id,
                name=network.name,
                vlan_id=network.vlan_id,
                cidr=network.cidr,
                gateway=network.gateway,
                color=network.color,
                ip_address=ip_address,
            )
            for network, ip_address in raw_nets
        ]
    if "children" in include:
        from src.models.device import DeviceResponse
        children = device_repository.get_children(session, device_id)
        enriched.children = [DeviceResponse.model_validate(c.model_dump()) for c in children]
    if "ancestors" in include:
        enriched.parent_chain = _load_parent_chain(device_id, session)
    return enriched
