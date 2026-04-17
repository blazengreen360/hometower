"""Unit tests for service domain functions (HT-023)."""
import uuid

import pytest

from src.domain.services import validate_no_dependency_cycle, validate_port


class TestValidatePort:
    def test_none_returns_none(self) -> None:
        assert validate_port(None) is None

    def test_valid_low_boundary(self) -> None:
        assert validate_port(1) == 1

    def test_valid_high_boundary(self) -> None:
        assert validate_port(65535) == 65535

    def test_valid_common_port(self) -> None:
        assert validate_port(8080) == 8080

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            validate_port(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_port(-1)

    def test_over_max_raises(self) -> None:
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            validate_port(65536)

    def test_large_number_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_port(99999)


class TestValidateNoDependencyCycle:
    def test_no_existing_edges_no_cycle(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        validate_no_dependency_cycle(a, b, [])  # should not raise

    def test_self_dependency_raises(self) -> None:
        a = uuid.uuid4()
        with pytest.raises(ValueError, match="Circular dependency detected"):
            validate_no_dependency_cycle(a, a, [])

    def test_direct_cycle_raises(self) -> None:
        # Existing: B → A. Proposed: A → B → would create A → B → A
        a, b = uuid.uuid4(), uuid.uuid4()
        existing = [(b, a)]  # B depends on A
        with pytest.raises(ValueError, match="Circular dependency detected"):
            validate_no_dependency_cycle(a, b, existing)

    def test_transitive_cycle_raises(self) -> None:
        # Existing: B → C → A. Proposed: A → B → would create A → B → C → A
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(b, c), (c, a)]
        with pytest.raises(ValueError, match="Circular dependency detected"):
            validate_no_dependency_cycle(a, b, existing)

    def test_no_cycle_fan_out(self) -> None:
        # A → B, A → C is fine
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b)]
        validate_no_dependency_cycle(a, c, existing)  # should not raise

    def test_no_cycle_chain(self) -> None:
        # Existing: A → B → C. Proposed: D → A is fine (D is new root)
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b), (b, c)]
        validate_no_dependency_cycle(d, a, existing)  # should not raise

    def test_cycle_through_longer_path(self) -> None:
        # Existing: B → C → D → A. Proposed: A → B
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(b, c), (c, d), (d, a)]
        with pytest.raises(ValueError, match="Circular dependency detected"):
            validate_no_dependency_cycle(a, b, existing)

    def test_unrelated_existing_edges_no_cycle(self) -> None:
        a, b, x, y = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(x, y)]  # unrelated edge
        validate_no_dependency_cycle(a, b, existing)  # should not raise
