"""Unit tests for src/models/location.py validators."""

import pytest
from pydantic import ValidationError

from src.models.location import LocationCreate
from src.models.types import LocationType


class TestLocationRowValidation:
    def test_rejects_negative_numeric_row_for_rack(self) -> None:
        with pytest.raises(ValidationError, match="row must be non-negative"):
            LocationCreate(name="R", type=LocationType.rack, row="-1")

    def test_rejects_empty_row_string(self) -> None:
        with pytest.raises(ValidationError, match="row must not be empty"):
            LocationCreate(name="R", type=LocationType.rack, row="   ")
