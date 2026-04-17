"""Unit tests for ConnectionUpdate validators (self-loop and label length)."""
import uuid

import pytest
from pydantic import ValidationError

from src.models.connection import ConnectionUpdate


class TestConnectionUpdateValidators:
    def test_self_loop_raises_value_error(self) -> None:
        same_id = uuid.uuid4()
        with pytest.raises(ValueError):
            ConnectionUpdate(source_id=same_id, target_id=same_id)

    def test_different_source_and_target_succeeds(self) -> None:
        s = uuid.uuid4()
        t = uuid.uuid4()
        cu = ConnectionUpdate(source_id=s, target_id=t)
        assert cu.source_id == s
        assert cu.target_id == t

    def test_partial_update_with_source_only_succeeds(self) -> None:
        s = uuid.uuid4()
        cu = ConnectionUpdate(source_id=s)
        assert cu.source_id == s
        assert cu.target_id is None

    def test_label_exceeds_max_length_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionUpdate(label="x" * 256)

    def test_label_at_max_length_succeeds(self) -> None:
        label = "x" * 255
        cu = ConnectionUpdate(label=label)
        assert cu.label == label
