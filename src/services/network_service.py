"""Network service — orchestrates domain rules and network repository operations."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import networks as network_domain
from src.models.device_network import (
    DeviceNetwork,
    DeviceNetworkCreate,
    DeviceNetworkDeviceRef,
    DeviceNetworkNetworkRef,
)
from src.models.network import (
    Network,
    NetworkCreate,
    NetworkListResponse,
    NetworkResponse,
    NetworkResponseEnriched,
    NetworkUpdate,
)
from src.repositories import network_repository
from src.services.network_service_helpers import (
    assert_device_exists,
    raise_network_integrity_error,
    reject_null_required_patch_fields,
)
from src.utils.logger import logger

def create(data: NetworkCreate, session: Session) -> Network:
    """Create a network after validating business constraints."""
    normalized_name = network_domain.normalize_network_name(data.name)
    if network_repository.get_by_name_normalized(session, normalized_name) is not None:
        raise HTTPException(status_code=409, detail="Network name already exists")

    try:
        vlan_id = network_domain.validate_vlan_id(data.vlan_id)
        cidr = network_domain.validate_cidr(data.cidr)
        gateway = network_domain.validate_gateway(data.gateway, cidr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    network = Network(
        name=data.name,
        vlan_id=vlan_id,
        cidr=cidr,
        gateway=gateway,
        description=data.description,
        color=data.color,
    )
    try:
        result = network_repository.create(session, network)
        session.commit()
    except IntegrityError as exc:
        raise_network_integrity_error(
            exc,
            session,
            conflict_detail="Network name already exists",
            fallback_detail="Invalid network payload",
        )
    logger.info("Network created: id={} name={}", result.id, result.name)
    return result


def get_all(session: Session) -> list[NetworkListResponse]:
    """Return all networks with member counts."""
    pairs = network_repository.get_all_with_counts(session)
    return [
        NetworkListResponse(
            **network.model_dump(),
            device_count=count,
        )
        for network, count in pairs
    ]


def get_by_id(network_id: uuid.UUID, session: Session) -> Network:
    """Return one network or raise 404."""
    network = network_repository.get_by_id(session, network_id)
    if network is None:
        raise HTTPException(status_code=404, detail="Network not found")
    return network


def get_by_id_enriched(
    network_id: uuid.UUID,
    include: set[str],
    session: Session,
) -> NetworkResponse | NetworkResponseEnriched:
    """Return network response, optionally including attached devices."""
    network = get_by_id(network_id, session)
    if "devices" not in include:
        return NetworkResponse.model_validate(network.model_dump())

    refs = network_repository.get_device_refs(session, network_id)
    return NetworkResponseEnriched(
        **network.model_dump(),
        devices=[
            DeviceNetworkDeviceRef(
                device_id=device.id,
                name=device.name,
                type=device.type,
                status=device.status,
                ip_address=ip_address,
            )
            for device, ip_address in refs
        ],
    )


def update(network_id: uuid.UUID, data: NetworkUpdate, session: Session) -> Network:
    """Partially update network fields with CIDR/membership invariants."""
    network = get_by_id(network_id, session)
    update_data = data.model_dump(exclude_unset=True)
    reject_null_required_patch_fields(update_data)

    if "name" in update_data and update_data["name"] is not None:
        normalized = network_domain.normalize_network_name(update_data["name"])
        existing = network_repository.get_by_name_normalized(session, normalized)
        if existing is not None and existing.id != network_id:
            raise HTTPException(status_code=409, detail="Network name already exists")

    if "vlan_id" in update_data:
        try:
            update_data["vlan_id"] = network_domain.validate_vlan_id(update_data["vlan_id"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    effective_cidr = network.cidr
    try:
        if "cidr" in update_data and update_data["cidr"] is not None:
            effective_cidr = network_domain.validate_cidr(update_data["cidr"])
            update_data["cidr"] = effective_cidr

        if "gateway" in update_data:
            update_data["gateway"] = network_domain.validate_gateway(
                update_data["gateway"],
                effective_cidr,
            )
        else:
            network_domain.validate_gateway(network.gateway, effective_cidr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if effective_cidr != network.cidr:
        memberships = network_repository.get_memberships_for_network(session, network_id)
        for membership in memberships:
            try:
                network_domain.validate_ip_in_subnet(membership.ip_address, effective_cidr)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    for field, value in update_data.items():
        setattr(network, field, value)
    network.updated_at = datetime.now(timezone.utc)

    try:
        result = network_repository.update(session, network)
        session.commit()
    except IntegrityError as exc:
        raise_network_integrity_error(
            exc,
            session,
            conflict_detail="Network name already exists",
            fallback_detail="Invalid network update payload",
        )
    logger.info("Network updated: id={} name={}", result.id, result.name)
    return result


def delete(network_id: uuid.UUID, session: Session) -> None:
    """Delete a network if no memberships exist."""
    network = get_by_id(network_id, session)
    if network_repository.count_devices(session, network_id) > 0:
        raise HTTPException(
            status_code=400,
            detail="Network has devices assigned - remove them first",
        )
    network_repository.delete(session, network)
    session.commit()
    logger.info("Network deleted: id={}", network_id)


def get_by_device(device_id: uuid.UUID, session: Session) -> list[DeviceNetworkNetworkRef]:
    """Return network refs for one device."""
    assert_device_exists(device_id, session)
    rows = network_repository.get_by_device(session, device_id)
    return [
        DeviceNetworkNetworkRef(
            network_id=network.id,
            name=network.name,
            vlan_id=network.vlan_id,
            cidr=network.cidr,
            gateway=network.gateway,
            color=network.color,
            ip_address=ip_address,
        )
        for network, ip_address in rows
    ]


def attach_to_device(
    device_id: uuid.UUID,
    data: DeviceNetworkCreate,
    session: Session,
) -> DeviceNetwork:
    """Attach a device to a network with subnet validation."""
    assert_device_exists(device_id, session)
    network = get_by_id(data.network_id, session)
    try:
        ip_address = network_domain.validate_ip_address(data.ip_address)
        network_domain.validate_ip_in_subnet(ip_address, network.cidr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if network_repository.get_membership(session, device_id, data.network_id) is not None:
        raise HTTPException(status_code=409, detail="Device is already on this network")

    membership = DeviceNetwork(
        device_id=device_id,
        network_id=data.network_id,
        ip_address=ip_address,
    )
    try:
        result = network_repository.attach_to_device(session, membership)
        session.commit()
    except IntegrityError as exc:
        raise_network_integrity_error(
            exc,
            session,
            conflict_detail="Device is already on this network",
            fallback_detail="Invalid device-network payload",
        )
    logger.info("Device attached to network: device_id={} network_id={}", device_id, data.network_id)
    return result


def detach_from_device(
    device_id: uuid.UUID,
    network_id: uuid.UUID,
    session: Session,
) -> None:
    """Detach a device from a network. No-op when membership is absent."""
    assert_device_exists(device_id, session)
    get_by_id(network_id, session)
    network_repository.detach_from_device(session, device_id, network_id)
    session.commit()
    logger.info("Device detached from network: device_id={} network_id={}", device_id, network_id)
