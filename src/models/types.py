"""Domain enum types — the only module that src/domain/ may import from models/."""
from enum import Enum


class DeviceType(str, Enum):
    Server = "Server"
    Switch = "Switch"
    Router = "Router"
    NAS = "NAS"
    UPS = "UPS"
    SBC = "SBC"
    Workstation = "Workstation"
    VM = "VM"
    LXC = "LXC"
    Docker = "Docker"
    Application = "Application"
    VLAN = "VLAN"
    Subnet = "Subnet"


class ConnectionType(str, Enum):
    Ethernet = "Ethernet"
    WiFi = "WiFi"
    Fibre = "Fibre"
    iSCSI = "iSCSI"
    NFS = "NFS"
    VM = "VM"
    Other = "Other"


class Role(str, Enum):
    Admin = "Admin"
    Contributor = "Contributor"
    Reader = "Reader"


class LocationType(str, Enum):
    rack = "rack"
    geo = "geo"


class DeviceStatus(str, Enum):
    Active = "Active"
    Offline = "Offline"
    Maintenance = "Maintenance"
    Planned = "Planned"
    Decommissioned = "Decommissioned"


class ServiceProtocol(str, Enum):
    http = "http"
    https = "https"
    tcp = "tcp"
    udp = "udp"
    other = "other"


class ServiceStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    unknown = "unknown"


class IpamAddressFamily(str, Enum):
    ipv4 = "ipv4"
    ipv6 = "ipv6"


class IpamRenderMode(str, Enum):
    grid = "grid"
    block_summary = "block_summary"
    unsupported = "unsupported"


class IpamCellStatus(str, Enum):
    free = "free"
    used = "used"
    gateway = "gateway"
    conflict = "conflict"
    reserved = "reserved"
