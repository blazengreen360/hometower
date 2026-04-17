"""Regression tests for location parent/name uniqueness."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.location import Location
from src.models.types import LocationType
from src.repositories import location_repository


def test_duplicate_location_name_under_same_parent_rejected(session: Session) -> None:
    parent = Location(name="Parent-Rack", type=LocationType.rack)
    location_repository.create(session, parent)

    first = Location(name="Child-Rack", type=LocationType.rack, parent_id=parent.id)
    second = Location(name="Child-Rack", type=LocationType.rack, parent_id=parent.id)

    location_repository.create(session, first)
    with pytest.raises(IntegrityError):
        location_repository.create(session, second)
