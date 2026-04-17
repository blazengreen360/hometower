"""Unit tests for generate_copy_name in src.domain.devices (HT-041)."""
import pytest

from src.domain.devices import generate_copy_name


class TestGenerateCopyName:
    def test_basic_copy_name_no_collision(self) -> None:
        assert generate_copy_name("My Server", []) == "My Server (copy)"

    def test_collision_with_copy_appends_2(self) -> None:
        assert generate_copy_name("My Server", ["My Server (copy)"]) == "My Server (copy 2)"

    def test_collision_with_copy_and_copy2_appends_3(self) -> None:
        result = generate_copy_name(
            "My Server", ["My Server (copy)", "My Server (copy 2)"]
        )
        assert result == "My Server (copy 3)"

    def test_no_collision_with_unrelated_names(self) -> None:
        assert generate_copy_name("Pi", ["raspberry", "pi-zero"]) == "Pi (copy)"

    def test_empty_existing_names(self) -> None:
        assert generate_copy_name("Router", []) == "Router (copy)"

    def test_original_name_in_existing_does_not_affect_copy(self) -> None:
        assert generate_copy_name("Switch", ["Switch"]) == "Switch (copy)"

    def test_long_chain_of_copies(self) -> None:
        existing = [
            "Device (copy)",
            "Device (copy 2)",
            "Device (copy 3)",
            "Device (copy 4)",
        ]
        assert generate_copy_name("Device", existing) == "Device (copy 5)"

    def test_spaces_and_special_chars_in_name(self) -> None:
        assert generate_copy_name("NAS #1 (prod)", []) == "NAS #1 (prod) (copy)"

    def test_large_name_set_more_than_1000_entries(self) -> None:
        existing = [f"device-{i}" for i in range(1000)] + ["Edge (copy)"]
        assert generate_copy_name("Edge", existing) == "Edge (copy 2)"
