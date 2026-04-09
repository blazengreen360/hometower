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
