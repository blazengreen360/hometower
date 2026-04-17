"""Network repository — SQLModel session access for networks and memberships."""
import uuid

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from src.models.device import Device
from src.models.device_network import DeviceNetwork
from src.models.network import Network


def create(session: Session, network: Network) -> Network:
    """Persist a new network and return the refreshed instance."""
    session.add(network)
    session.flush()
    session.refresh(network)
    return network


def get_by_id(session: Session, network_id: uuid.UUID) -> Network | None:
    """Return a network by id or None."""
    return session.get(Network, network_id)


def get_by_name_normalized(session: Session, normalized_name: str) -> Network | None:
    """Return a network whose lower(name) matches normalized_name."""
    stmt = select(Network).where(func.lower(Network.name) == normalized_name)
    return session.exec(stmt).first()


def get_all_with_counts(session: Session) -> list[tuple[Network, int]]:
    """Return (Network, member_count) pairs ordered by VLAN then name."""
    vlan_column = col(Network.vlan_id)
    stmt = (
        sa_select(Network, func.count(DeviceNetwork.device_id).label("device_count"))  # type: ignore[call-overload, arg-type]
        .outerjoin(DeviceNetwork, col(Network.id) == col(DeviceNetwork.network_id))
        .group_by(col(Network.id))
        .order_by(vlan_column.is_(None), vlan_column, col(Network.name))
    )
    rows = list(session.execute(stmt).all())
    return [(row[0], row[1]) for row in rows]


def update(session: Session, network: Network) -> Network:
    """Persist changes to a fetched network and return refreshed instance."""
    session.add(network)
    session.flush()
    session.refresh(network)
    return network


def delete(session: Session, network: Network) -> None:
    """Delete a network row."""
    session.delete(network)
    session.flush()


def get_by_device(session: Session, device_id: uuid.UUID) -> list[tuple[Network, str]]:
    """Return networks and membership IPs for one device."""
    stmt = (
        sa_select(Network, DeviceNetwork.ip_address)  # type: ignore[call-overload]
        .join(DeviceNetwork, Network.id == DeviceNetwork.network_id)
        .where(DeviceNetwork.device_id == device_id)
        .order_by(Network.name)
    )
    rows = list(session.execute(stmt).all())
    return [(row[0], row[1]) for row in rows]


def get_by_device_ids(
    session: Session, device_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[Network, str]]]:
    """Return grouped network memberships for provided device ids."""
    if not device_ids:
        return {}
    grouped: dict[uuid.UUID, list[tuple[Network, str]]] = {
        device_id: [] for device_id in device_ids
    }
    stmt = (
        sa_select(DeviceNetwork.device_id, Network, DeviceNetwork.ip_address)  # type: ignore[call-overload]
        .join(Network, Network.id == DeviceNetwork.network_id)
        .where(col(DeviceNetwork.device_id).in_(device_ids))
        .order_by(Network.name)
    )
    rows = list(session.execute(stmt).all())
    for row in rows:
        grouped[row[0]].append((row[1], row[2]))
    return grouped


def get_device_refs(session: Session, network_id: uuid.UUID) -> list[tuple[Device, str]]:
    """Return devices and membership IPs for one network."""
    stmt = (
        sa_select(Device, DeviceNetwork.ip_address)  # type: ignore[call-overload]
        .join(DeviceNetwork, Device.id == DeviceNetwork.device_id)
        .where(DeviceNetwork.network_id == network_id)
        .order_by(Device.name)
    )
    rows = list(session.execute(stmt).all())
    return [(row[0], row[1]) for row in rows]


def get_memberships_for_network(
    session: Session, network_id: uuid.UUID
) -> list[DeviceNetwork]:
    """Return all device-network rows for a network."""
    stmt = select(DeviceNetwork).where(DeviceNetwork.network_id == network_id)
    return list(session.exec(stmt).all())


def get_memberships_for_network_ids(
    session: Session,
    network_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[DeviceNetwork]]:
    """Return grouped membership rows for the provided network ids."""
    if not network_ids:
        return {}

    grouped: dict[uuid.UUID, list[DeviceNetwork]] = {
        network_id: [] for network_id in network_ids
    }
    stmt = (
        select(DeviceNetwork)
        .where(col(DeviceNetwork.network_id).in_(network_ids))
        .order_by(col(DeviceNetwork.network_id), col(DeviceNetwork.ip_address))
    )
    for membership in session.exec(stmt).all():
        grouped[membership.network_id].append(membership)
    return grouped


def get_membership(
    session: Session,
    device_id: uuid.UUID,
    network_id: uuid.UUID,
) -> DeviceNetwork | None:
    """Return one membership row by composite key."""
    return session.get(DeviceNetwork, (device_id, network_id))


def attach_to_device(session: Session, membership: DeviceNetwork) -> DeviceNetwork:
    """Persist membership row and return refreshed row."""
    session.add(membership)
    session.flush()
    session.refresh(membership)
    return membership


def detach_from_device(
    session: Session,
    device_id: uuid.UUID,
    network_id: uuid.UUID,
) -> None:
    """Delete membership if present."""
    membership = get_membership(session, device_id, network_id)
    if membership is not None:
        session.delete(membership)
        session.flush()


def count_devices(session: Session, network_id: uuid.UUID) -> int:
    """Count devices currently attached to network_id."""
    result = session.exec(
        select(func.count())
        .select_from(DeviceNetwork)
        .where(DeviceNetwork.network_id == network_id)
    ).one()
    return int(result)


def get_all_for_export(session: Session) -> list[Network]:
    """Return all networks for export sorted by created_at."""
    stmt = select(Network).order_by(col(Network.created_at))
    return list(session.exec(stmt).all())


def get_all_device_networks(session: Session) -> list[DeviceNetwork]:
    """Return all device-network rows for export sorted by created_at."""
    stmt = select(DeviceNetwork).order_by(col(DeviceNetwork.created_at))
    return list(session.exec(stmt).all())
