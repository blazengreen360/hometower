"""Unit tests for src/domain/workspaces.py pure functions."""
import pytest

from src.domain.workspaces import (
    validate_topology_name,
    validate_view_name,
    validate_workspace_name,
)


class TestValidateWorkspaceName:
    def test_valid_name_returned(self) -> None:
        assert validate_workspace_name("My Lab") == "My Lab"

    def test_strips_whitespace(self) -> None:
        assert validate_workspace_name("  padded  ") == "padded"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_workspace_name("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_workspace_name("   ")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="must not exceed 255"):
            validate_workspace_name("x" * 256)

    def test_exact_max_length_ok(self) -> None:
        name = "a" * 255
        assert validate_workspace_name(name) == name


class TestValidateTopologyName:
    def test_valid_name_returned(self) -> None:
        assert validate_topology_name("Home Lab") == "Home Lab"

    def test_strips_whitespace(self) -> None:
        assert validate_topology_name("  padded  ") == "padded"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_topology_name("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_topology_name("   ")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="must not exceed 255"):
            validate_topology_name("x" * 256)


class TestValidateViewName:
    def test_valid_name_returned(self) -> None:
        assert validate_view_name("Rack Overview") == "Rack Overview"

    def test_strips_whitespace(self) -> None:
        assert validate_view_name("  padded  ") == "padded"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_view_name("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_view_name("   ")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="must not exceed 255"):
            validate_view_name("x" * 256)
