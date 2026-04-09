"""Unit tests for src/domain/connections.py."""
import uuid

import pytest

from src.domain.connections import validate_no_self_loop


class TestValidateNoSelfLoop:
    def test_same_uuid_raises_value_error(self) -> None:
        device_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Cannot connect a device to itself"):
            validate_no_self_loop(device_id, device_id)

    def test_different_uuids_does_not_raise(self) -> None:
        validate_no_self_loop(uuid.uuid4(), uuid.uuid4())
