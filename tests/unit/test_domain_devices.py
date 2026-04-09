"""Unit tests for src/domain/devices.py pure functions."""
import pytest

from src.domain.devices import validate_device_deletable, validate_ip, validate_mac


class TestValidateMac:
    def test_validate_mac_valid(self) -> None:
        assert validate_mac("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"

    def test_validate_mac_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_mac("not-a-mac")

    def test_validate_mac_none_returns_none(self) -> None:
        assert validate_mac(None) is None

    def test_validate_mac_normalizes_to_uppercase(self) -> None:
        assert validate_mac("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"

    def test_validate_mac_mixed_case_normalizes(self) -> None:
        assert validate_mac("aA:bB:cC:dD:eE:fF") == "AA:BB:CC:DD:EE:FF"

    def test_validate_mac_invalid_separator_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_mac("AA-BB-CC-DD-EE-FF")

    def test_validate_mac_short_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_mac("AA:BB:CC:DD:EE")


class TestValidateIp:
    def test_validate_ip_valid(self) -> None:
        assert validate_ip("192.168.1.1") == "192.168.1.1"

    def test_validate_ip_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("not-an-ip")

    def test_validate_ip_none_returns_none(self) -> None:
        assert validate_ip(None) is None

    def test_validate_ip_octet_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("192.168.1.256")

    def test_validate_ip_loopback(self) -> None:
        assert validate_ip("127.0.0.1") == "127.0.0.1"

    def test_validate_ip_broadcast(self) -> None:
        assert validate_ip("255.255.255.255") == "255.255.255.255"

    def test_validate_ip_all_octets_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_ip("999.999.999.999")


class TestValidateDeviceDeletable:
    def test_validate_device_deletable_zero_connections_passes(self) -> None:
        validate_device_deletable(0)  # must not raise

    def test_validate_device_deletable_with_connections_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_device_deletable(1)

    def test_validate_device_deletable_many_connections_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_device_deletable(10)
