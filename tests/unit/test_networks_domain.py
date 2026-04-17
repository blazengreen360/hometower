"""Unit tests for src/domain/networks.py pure validation helpers (HT-022)."""

import pytest

from src.domain.networks import (
    normalize_network_name,
    validate_cidr,
    validate_gateway,
    validate_ip_address,
    validate_ip_in_subnet,
    validate_network_color,
    validate_network_name,
    validate_vlan_id,
)


class TestNormalizeNetworkName:
    def test_normalizes_with_strip_and_lower(self) -> None:
        assert normalize_network_name("  Mgmt VLAN  ") == "mgmt vlan"


class TestNetworkNameAndColorValidation:
    def test_validate_network_name_trims_whitespace(self) -> None:
        assert validate_network_name("  Management  ") == "Management"

    def test_validate_network_name_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="name cannot be empty or whitespace-only"):
            validate_network_name("   ")

    def test_validate_network_color_accepts_hex(self) -> None:
        assert validate_network_color("#3b82f6") == "#3b82f6"

    def test_validate_network_color_rejects_non_hex(self) -> None:
        with pytest.raises(ValueError, match="color must be a 6-digit hex color"):
            validate_network_color("blue")


class TestValidateVlanId:
    def test_none_allowed(self) -> None:
        assert validate_vlan_id(None) is None

    def test_lower_bound_allowed(self) -> None:
        assert validate_vlan_id(1) == 1

    def test_upper_bound_allowed(self) -> None:
        assert validate_vlan_id(4094) == 4094

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="VLAN ID must be between 1 and 4094"):
            validate_vlan_id(0)

    def test_above_upper_bound_rejected(self) -> None:
        with pytest.raises(ValueError, match="VLAN ID must be between 1 and 4094"):
            validate_vlan_id(4095)


class TestValidateCidr:
    def test_ipv4_cidr_is_canonicalized(self) -> None:
        assert validate_cidr("10.0.10.0/24") == "10.0.10.0/24"

    def test_ipv6_cidr_is_canonicalized(self) -> None:
        assert validate_cidr("2001:db8::/64") == "2001:db8::/64"

    def test_invalid_cidr_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid CIDR notation"):
            validate_cidr("10.0.10.0")

    def test_host_address_cidr_rejected_in_strict_mode(self) -> None:
        with pytest.raises(ValueError, match="Invalid CIDR notation"):
            validate_cidr("10.0.10.5/24")


class TestValidateIpAddress:
    def test_valid_ip_returns_canonical_value(self) -> None:
        assert validate_ip_address("10.0.10.5") == "10.0.10.5"

    def test_invalid_ip_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("10.0.10.500")


class TestGatewayAndSubnetValidation:
    def test_gateway_none_is_allowed(self) -> None:
        assert validate_gateway(None, "10.0.10.0/24") is None

    def test_gateway_within_subnet_is_allowed(self) -> None:
        assert validate_gateway("10.0.10.1", "10.0.10.0/24") == "10.0.10.1"

    def test_gateway_outside_subnet_rejected(self) -> None:
        with pytest.raises(ValueError, match="Gateway 10.0.20.1 is not within subnet 10.0.10.0/24"):
            validate_gateway("10.0.20.1", "10.0.10.0/24")

    def test_gateway_family_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="Gateway 10.0.10.1 is not within subnet 2001:db8::/64"):
            validate_gateway("10.0.10.1", "2001:db8::/64")

    def test_ip_in_subnet_accepts_valid_ip(self) -> None:
        validate_ip_in_subnet("10.0.10.5", "10.0.10.0/24")

    def test_ip_in_subnet_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="IP 10.0.20.5 is not within subnet 10.0.10.0/24"):
            validate_ip_in_subnet("10.0.20.5", "10.0.10.0/24")
