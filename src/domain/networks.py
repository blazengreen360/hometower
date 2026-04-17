"""Network domain logic — pure functions for CIDR/IP/VLAN validation."""
import ipaddress
import re

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_network_name(name: str) -> str:
    """Return canonical network name for duplicate checks."""
    return name.strip().lower()


def validate_network_name(name: str) -> str:
    """Return normalized display name or raise ValueError."""
    normalized = name.strip()
    if not normalized:
        raise ValueError("name cannot be empty or whitespace-only")
    return normalized


def validate_network_color(color: str) -> str:
    """Return normalized hex color string or raise ValueError."""
    normalized = color.strip()
    if not _HEX_COLOR_PATTERN.match(normalized):
        raise ValueError("color must be a 6-digit hex color, e.g. #3b82f6")
    return normalized


def validate_vlan_id(vlan_id: int | None) -> int | None:
    """Return VLAN id when valid, else raise ValueError."""
    if vlan_id is None:
        return None
    if 1 <= vlan_id <= 4094:
        return vlan_id
    raise ValueError("VLAN ID must be between 1 and 4094")


def validate_cidr(cidr: str) -> str:
    """Return canonical CIDR string, enforcing network notation (strict=True)."""
    raw = cidr.strip()
    if "/" not in raw:
        raise ValueError("Invalid CIDR notation")
    try:
        network = ipaddress.ip_network(raw, strict=True)
    except ValueError as exc:
        raise ValueError("Invalid CIDR notation") from exc
    return str(network)


def validate_ip_address(ip_address: str) -> str:
    """Return canonical IP string or raise ValueError for invalid syntax."""
    try:
        ip = ipaddress.ip_address(ip_address.strip())
    except ValueError as exc:
        raise ValueError("Invalid IP address format") from exc
    return str(ip)


def validate_gateway(gateway: str | None, cidr: str) -> str | None:
    """Validate gateway syntax and subnet membership against cidr."""
    if gateway is None:
        return None
    gateway_ip = validate_ip_address(gateway)
    network = ipaddress.ip_network(cidr, strict=True)
    ip_obj = ipaddress.ip_address(gateway_ip)
    if ip_obj not in network:
        raise ValueError(f"Gateway {gateway_ip} is not within subnet {cidr}")
    return gateway_ip


def validate_ip_in_subnet(ip_address: str, cidr: str) -> None:
    """Raise ValueError when ip_address is outside the provided subnet."""
    ip_text = validate_ip_address(ip_address)
    network = ipaddress.ip_network(cidr, strict=True)
    ip_obj = ipaddress.ip_address(ip_text)
    if ip_obj not in network:
        raise ValueError(f"IP {ip_text} is not within subnet {cidr}")
