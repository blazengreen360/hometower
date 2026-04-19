"""Integration tests for GET /api/devices/?include=location enriched endpoint."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.device import Device
from src.models.location import Location
from src.models.tag import DeviceTag, Tag
from src.models.types import Role
from src.models.types import DeviceType, LocationType
from src.models.user import User
from src.utils.auth import create_jwt, hash_password

_DEVICE = {"name": "test-device", "type": "Server"}
_LOCATION = {"name": "Main Rack", "type": "rack", "rack": "A", "row": "1"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"devices_include_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@devices-include.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt(
        {"sub": str(user.id), "role": role.value, "version": user.token_version}
    )
    return user, token


def _make_owned_device(
    session: Session,
    owner: User,
    name: str,
    *,
    location_id: str | None = None,
) -> Device:
    device = Device(
        name=name,
        type=DeviceType.Server,
        owner_id=owner.id,
        location_id=uuid.UUID(location_id) if location_id is not None else None,
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def _make_location(session: Session, name: str = "Main Rack") -> Location:
    location = Location(name=name, type=LocationType.rack, rack="A", row="1")
    session.add(location)
    session.commit()
    session.refresh(location)
    return location


def _make_tag(session: Session, name: str, color: str = "#22aa66") -> Tag:
    tag = Tag(name=name, color=color)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def _attach_tag(session: Session, device: Device, tag: Tag) -> None:
    session.add(DeviceTag(device_id=device.id, tag_id=tag.id))
    session.commit()


class TestNoIncludeBackwardCompat:
    def test_list_without_include_returns_classic_format(
        self, client: TestClient, session: Session
    ) -> None:
        """GET /api/devices/ without include returns PaginatedDeviceResponse (no location_name)."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        _make_owned_device(session, owner, _DEVICE["name"])
        resp = client.get(
            "/api/devices/",
            headers=_auth(reader_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["items"]
        assert "location_name" not in data["items"][0]

    def test_include_empty_string_is_backward_compat(
        self, client: TestClient, session: Session
    ) -> None:
        """?include= (empty) behaves the same as omitting the param."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        _make_owned_device(session, owner, _DEVICE["name"])
        resp = client.get(
            "/api/devices/?include=",
            headers=_auth(reader_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"]
        assert "location_name" not in data["items"][0]


class TestIncludeLocation:
    def test_include_location_adds_location_name_field(
        self, client: TestClient, session: Session
    ) -> None:
        """?include=location returns items with location_name key in each item."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        _make_owned_device(session, owner, _DEVICE["name"])
        resp = client.get(
            "/api/devices/?include=location",
            headers=_auth(reader_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["items"]
        for item in data["items"]:
            assert "location_name" in item

    def test_include_location_with_actual_location(
        self, client: TestClient, session: Session
    ) -> None:
        """Device with location_id returns the correct location_name."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        location = _make_location(session, name=_LOCATION["name"])
        device = _make_owned_device(
            session,
            owner,
            "located-server",
            location_id=str(location.id),
        )
        list_resp = client.get(
            "/api/devices/?include=location&limit=1000",
            headers=_auth(reader_token),
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        payload = next((d for d in items if d["id"] == str(device.id)), None)
        assert payload is not None
        assert payload["location_name"] == "Main Rack"

    def test_include_location_device_without_location(
        self, client: TestClient, session: Session
    ) -> None:
        """Device with no location_id returns location_name=null in enriched response."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        device = _make_owned_device(session, owner, "no-loc-server")
        list_resp = client.get(
            "/api/devices/?include=location&limit=1000",
            headers=_auth(reader_token),
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        payload = next((d for d in items if d["id"] == str(device.id)), None)
        assert payload is not None
        assert payload["location_name"] is None

    def test_include_multiple_keys_returns_location_and_tags(
        self, client: TestClient, session: Session
    ) -> None:
        """?include=location,tags returns both enriched location_name and populated tags."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        location = _make_location(session, name=_LOCATION["name"])
        tag = _make_tag(session, name="prod")
        device = _make_owned_device(
            session,
            owner,
            "enriched-server",
            location_id=str(location.id),
        )
        _attach_tag(session, device, tag)
        resp = client.get(
            "/api/devices/?include=location,tags&limit=1000",
            headers=_auth(reader_token),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        payload = next((d for d in items if d["id"] == str(device.id)), None)
        assert payload is not None
        assert payload["location_name"] == "Main Rack"
        assert len(payload["tags"]) == 1
        assert payload["tags"][0]["id"] == str(tag.id)
        assert payload["tags"][0]["name"] == tag.name

    def test_include_unknown_key_returns_enriched_without_crash(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Unknown include key is silently ignored."""
        resp = client.get(
            "/api/devices/?include=unknown_key",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200


class TestLimitCap:
    def test_limit_1000_accepted(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Limit of 1000 is now valid (previously capped at 100)."""
        resp = client.get(
            "/api/devices/?limit=1000",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200

    def test_limit_above_1000_rejected(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Limit above 1000 is rejected with 422."""
        resp = client.get(
            "/api/devices/?limit=1001",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 422

    def test_pagination_structure_preserved_with_include(
        self, client: TestClient, reader_token: str
    ) -> None:
        """Enriched response has same pagination envelope as classic response."""
        resp = client.get(
            "/api/devices/?include=location&page=1&limit=10",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["limit"] == 10
        assert "total" in data
        assert "items" in data


class TestIncludeLocationWithSort:
    def test_include_location_sort_by_name_ascending(
        self, client: TestClient, session: Session
    ) -> None:
        """GET /api/devices/?include=location&sort=name orders by name ascending."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        _make_owned_device(session, owner, "Zebra-IncSort")
        _make_owned_device(session, owner, "Alpha-IncSort")
        resp = client.get(
            "/api/devices/?include=location&sort=name&limit=1000",
            headers=_auth(reader_token),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [d["name"] for d in items]
        assert names.index("Alpha-IncSort") < names.index("Zebra-IncSort")
        # Enriched fields must still be present
        for item in items:
            assert "location_name" in item

    def test_include_location_sort_by_name_descending(
        self, client: TestClient, session: Session
    ) -> None:
        """GET /api/devices/?include=location&sort=-name orders by name descending."""
        owner, reader_token = _make_user(session, role=Role.Reader)
        _make_owned_device(session, owner, "Zebra-IncSortD")
        _make_owned_device(session, owner, "Alpha-IncSortD")
        resp = client.get(
            "/api/devices/?include=location&sort=-name&limit=1000",
            headers=_auth(reader_token),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [d["name"] for d in items]
        assert names.index("Zebra-IncSortD") < names.index("Alpha-IncSortD")
        for item in items:
            assert "location_name" in item
