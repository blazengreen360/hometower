"""Device domain logic — pure functions, no I/O.

Only imports re and standard library. No SQLModel, FastAPI, or network calls.
"""
import re
from typing import Optional

_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
_IPV4_RE = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')


def validate_mac(mac: Optional[str]) -> Optional[str]:
    """Return normalized (uppercase) MAC or None. Raise ValueError if invalid format."""
    if mac is None:
        return None
    if not _MAC_RE.match(mac):
        raise ValueError("Invalid MAC address format")
    return mac.upper()


def validate_ip(ip: Optional[str]) -> Optional[str]:
    """Return ip or None. Raise ValueError if invalid format."""
    if ip is None:
        return None
    if not _IPV4_RE.match(ip):
        raise ValueError("Invalid IPv4 address format")
    octets = ip.split(".")
    if any(int(o) > 255 for o in octets):
        raise ValueError("Invalid IPv4 address: octet out of range")
    if any(str(int(o)) != o for o in octets):
        raise ValueError("Invalid IPv4 address: leading zeros not allowed")
    return ip


def validate_device_deletable(connection_count: int) -> None:
    """Raise ValueError if device has active connections."""
    if connection_count > 0:
        raise ValueError("Cannot delete device with active connections")
