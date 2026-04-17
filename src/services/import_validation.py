"""Import payload validation — pure functions, no I/O."""
from src.domain import networks as network_domain
from src.models.export_schema import ExportSchema


class ImportPayloadValidationError(ValueError):
    """Raised when payload cross-references are invalid before DB writes."""


def validate_device_location_refs(payload: ExportSchema) -> None:
    """Ensure each device.location_id exists in payload.locations (or is None)."""
    location_ids = {loc.id for loc in payload.locations}
    dangling = [
        str(device.id)
        for device in payload.devices
        if device.location_id is not None and device.location_id not in location_ids
    ]
    if dangling:
        raise ImportPayloadValidationError(
            "devices.location_id must reference ids present in payload.locations; "
            f"invalid device ids: {', '.join(sorted(dangling))}"
        )


def validate_device_parent_refs(payload: ExportSchema) -> None:
    """Ensure each device.parent_id exists in payload.devices (or is None)."""
    device_ids = {d.id for d in payload.devices}
    dangling = [
        str(d.id)
        for d in payload.devices
        if d.parent_id is not None and d.parent_id not in device_ids
    ]
    if dangling:
        raise ImportPayloadValidationError(
            "devices.parent_id must reference ids present in payload.devices; "
            f"invalid device ids: {', '.join(sorted(dangling))}"
        )


def validate_device_network_refs(payload: ExportSchema) -> None:
    """Ensure membership rows reference known device and network ids."""
    device_ids = {device.id for device in payload.devices}
    network_ids = {network.id for network in payload.networks}

    dangling_devices = [
        f"{row.device_id}->{row.network_id}"
        for row in payload.device_networks
        if row.device_id not in device_ids
    ]
    if dangling_devices:
        raise ImportPayloadValidationError(
            "device_networks.device_id must reference ids present in payload.devices; "
            f"invalid memberships: {', '.join(sorted(dangling_devices))}"
        )

    dangling_networks = [
        f"{row.device_id}->{row.network_id}"
        for row in payload.device_networks
        if row.network_id not in network_ids
    ]
    if dangling_networks:
        raise ImportPayloadValidationError(
            "device_networks.network_id must reference ids present in payload.networks; "
            f"invalid memberships: {', '.join(sorted(dangling_networks))}"
        )


def validate_network_rows(payload: ExportSchema) -> None:
    """Validate name/color/VLAN/CIDR/gateway semantics for standalone network rows."""
    invalid: list[str] = []
    for row in payload.networks:
        try:
            network_domain.validate_network_name(row.name)
            network_domain.validate_network_color(row.color)
            network_domain.validate_vlan_id(row.vlan_id)
            cidr = network_domain.validate_cidr(row.cidr)
            network_domain.validate_gateway(row.gateway, cidr)
        except ValueError as exc:
            invalid.append(f"{row.id}: {exc}")

    if invalid:
        raise ImportPayloadValidationError(
            "payload.networks rows must contain valid name/color/vlan_id/cidr/gateway combinations; "
            f"invalid networks: {', '.join(sorted(invalid))}"
        )


def validate_device_network_subnets(payload: ExportSchema) -> None:
    """Ensure each membership IP is inside its referenced network CIDR."""
    cidr_by_network_id = {network.id: network.cidr for network in payload.networks}
    invalid: list[str] = []
    for row in payload.device_networks:
        cidr = cidr_by_network_id.get(row.network_id)
        if cidr is None:
            continue
        try:
            network_domain.validate_ip_in_subnet(row.ip_address, cidr)
        except ValueError:
            invalid.append(f"{row.device_id}->{row.network_id}")
    if invalid:
        raise ImportPayloadValidationError(
            "device_networks.ip_address must be inside the referenced network cidr; "
            f"invalid memberships: {', '.join(sorted(invalid))}"
        )
