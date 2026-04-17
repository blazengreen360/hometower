"""DB-level uniqueness regression tests for Service, CustomField, and Tag."""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.custom_field import CustomField
from src.models.device import Device
from src.models.service import Service
from src.models.tag import Tag
from src.models.types import DeviceType


def test_service_name_unique_per_device(session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    device = Device(name=f"svc-uniq-dev-{suffix}", type=DeviceType.Server)
    session.add(device)
    session.commit()
    session.refresh(device)

    session.add(Service(device_id=device.id, name=f"svc-{suffix}"))
    session.commit()

    session.add(Service(device_id=device.id, name=f"svc-{suffix}"))
    with pytest.raises(IntegrityError):
        session.commit()



def test_custom_field_key_unique_per_device(session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    device = Device(name=f"cf-uniq-dev-{suffix}", type=DeviceType.Server)
    session.add(device)
    session.commit()
    session.refresh(device)

    session.add(CustomField(device_id=device.id, key=f"owner-{suffix}", value="qa"))
    session.commit()

    session.add(CustomField(device_id=device.id, key=f"owner-{suffix}", value="ops"))
    with pytest.raises(IntegrityError):
        session.commit()



def test_tag_name_unique(session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    name = f"tag-uniq-{suffix}"
    session.add(Tag(name=name, color="#123abc"))
    session.commit()

    session.add(Tag(name=name, color="#abcdef"))
    with pytest.raises(IntegrityError):
        session.commit()
