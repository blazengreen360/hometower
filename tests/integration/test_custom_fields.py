"""Integration tests for the Custom Fields system (HT-007).

Covers: CRUD, 409 on duplicate key per device, 404 on wrong device,
key stripping, GET /api/devices/{id}?include=custom_fields enriched response,
GET /api/devices/{id}/connections.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password

_DEVICE = {"name": "cf-test-node", "type": "Server"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role = Role.Reader) -> tuple[User, str]:
    user = User(
        username=f"custom_fields_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@custom-fields.local",
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


def _create_device(client: TestClient, token: str) -> dict:
    resp = client.post(
        "/api/devices/",
        json=_DEVICE,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_cf(
    client: TestClient,
    token: str,
    device_id: str,
    key: str = "serial",
    value: str = "XYZ-123",
) -> dict:
    resp = client.post(
        f"/api/devices/{device_id}/custom-fields",
        json={"key": key, "value": value},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCustomFieldCreate:
    def test_create_success(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "Wattage", "value": "45W"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "Wattage"
        assert data["value"] == "45W"
        assert data["device_id"] == device["id"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_strips_key_whitespace(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "  serial  ", "value": "ABC"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["key"] == "serial"

    def test_create_empty_value_allowed(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "notes", "value": ""},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["value"] == ""

    def test_create_duplicate_key_same_device_returns_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device["id"], key="serial")
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "serial", "value": "duplicate"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Custom field key already exists for this device"

    def test_create_duplicate_key_case_insensitive_returns_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device["id"], key="serial")
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "SERIAL", "value": "duplicate"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409

    def test_create_same_key_different_devices_ok(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device1 = _create_device(client, contributor_token)
        device2 = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device1["id"], key="serial")
        resp = client.post(
            f"/api/devices/{device2['id']}/custom-fields",
            json={"key": "serial", "value": "other"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_create_device_not_found_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/devices/{fake_id}/custom-fields",
            json={"key": "serial", "value": "x"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_create_requires_contributor(
        self, client: TestClient, reader_token: str, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "serial", "value": "x"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_create_returns_404_for_device_owned_by_another_contributor(
        self, client: TestClient, session: Session
    ) -> None:
        _, owner_token = _make_user(session, role=Role.Contributor)
        _, other_contributor_token = _make_user(session, role=Role.Contributor)
        device = _create_device(client, owner_token)

        response = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "serial", "value": "x"},
            headers=_auth(other_contributor_token),
        )

        assert response.status_code == 404

    def test_create_whitespace_only_key_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/custom-fields",
            json={"key": "   ", "value": "x"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_create_integrity_error_translated_to_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        with patch(
            "src.services.custom_field_service.custom_field_repository.create",
            side_effect=IntegrityError(
                "INSERT INTO custom_fields ...",
                {},
                Exception(
                    "duplicate key value violates unique constraint "
                    "ix_custom_fields_device_key_lower"
                ),
            ),
        ):
            resp = client.post(
                f"/api/devices/{device['id']}/custom-fields",
                json={"key": "serial", "value": "XYZ"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Custom field key already exists for this device"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestCustomFieldList:
    def test_list_returns_all_for_device(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device["id"], key="serial", value="S1")
        _create_cf(client, contributor_token, device["id"], key="wattage", value="45W")

        resp = client.get(
            f"/api/devices/{device['id']}/custom-fields",
            headers=_auth(contributor_token),
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        keys = {cf["key"] for cf in items}
        assert keys == {"serial", "wattage"}

    def test_list_empty_device_returns_empty_list(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.get(
            f"/api/devices/{device['id']}/custom-fields",
            headers=_auth(contributor_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_404_for_device_owned_by_another_reader(
        self, client: TestClient, session: Session
    ) -> None:
        _, owner_token = _make_user(session, role=Role.Contributor)
        _, other_reader_token = _make_user(session, role=Role.Reader)
        device = _create_device(client, owner_token)
        _create_cf(client, owner_token, device["id"], key="serial", value="S1")

        response = client.get(
            f"/api/devices/{device['id']}/custom-fields",
            headers=_auth(other_reader_token),
        )

        assert response.status_code == 404

    def test_list_device_not_found_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        fake_id = str(uuid.uuid4())
        resp = client.get(
            f"/api/devices/{fake_id}/custom-fields",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestCustomFieldUpdate:
    def test_update_value(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        cf = _create_cf(client, contributor_token, device["id"], key="serial", value="old")

        resp = client.patch(
            f"/api/devices/{device['id']}/custom-fields/{cf['id']}",
            json={"value": "new"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "new"
        assert resp.json()["key"] == "serial"

    def test_update_key(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        cf = _create_cf(client, contributor_token, device["id"], key="old-key", value="v")

        resp = client.patch(
            f"/api/devices/{device['id']}/custom-fields/{cf['id']}",
            json={"key": "new-key"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["key"] == "new-key"

    def test_update_key_collision_returns_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device["id"], key="existing")
        cf2 = _create_cf(client, contributor_token, device["id"], key="other")

        resp = client.patch(
            f"/api/devices/{device['id']}/custom-fields/{cf2['id']}",
            json={"key": "existing"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409

    def test_update_wrong_device_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device1 = _create_device(client, contributor_token)
        device2 = _create_device(client, contributor_token)
        cf = _create_cf(client, contributor_token, device1["id"], key="serial")

        resp = client.patch(
            f"/api/devices/{device2['id']}/custom-fields/{cf['id']}",
            json={"value": "x"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_update_nonexistent_cf_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.patch(
            f"/api/devices/{device['id']}/custom-fields/{uuid.uuid4()}",
            json={"value": "x"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_update_integrity_error_translated_to_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        cf = _create_cf(client, contributor_token, device["id"], key="serial", value="old")
        with patch(
            "src.services.custom_field_service.custom_field_repository.update",
            side_effect=IntegrityError(
                "UPDATE custom_fields ...",
                {},
                Exception(
                    "duplicate key value violates unique constraint "
                    "ix_custom_fields_device_key_lower"
                ),
            ),
        ):
            resp = client.patch(
                f"/api/devices/{device['id']}/custom-fields/{cf['id']}",
                json={"key": "renamed"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Custom field key already exists for this device"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestCustomFieldDelete:
    def test_delete_success(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        cf = _create_cf(client, contributor_token, device["id"], key="to-delete")

        resp = client.delete(
            f"/api/devices/{device['id']}/custom-fields/{cf['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

        # Confirm it's gone
        list_resp = client.get(
            f"/api/devices/{device['id']}/custom-fields",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert list_resp.json() == []

    def test_delete_wrong_device_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device1 = _create_device(client, contributor_token)
        device2 = _create_device(client, contributor_token)
        cf = _create_cf(client, contributor_token, device1["id"], key="serial")

        resp = client.delete(
            f"/api/devices/{device2['id']}/custom-fields/{cf['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.delete(
            f"/api/devices/{device['id']}/custom-fields/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# include=custom_fields enriched response
# ---------------------------------------------------------------------------


class TestDeviceEnrichedWithCustomFields:
    def test_include_custom_fields_returns_enriched(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device["id"], key="Serial", value="XYZ")

        resp = client.get(
            f"/api/devices/{device['id']}?include=custom_fields",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "custom_fields" in data
        assert len(data["custom_fields"]) == 1
        assert data["custom_fields"][0]["key"] == "Serial"
        assert data["custom_fields"][0]["value"] == "XYZ"

    def test_include_custom_fields_empty_list(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.get(
            f"/api/devices/{device['id']}?include=custom_fields",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["custom_fields"] == []

    def test_include_tags_and_custom_fields_combined(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        _create_cf(client, contributor_token, device["id"], key="wattage", value="45W")

        resp = client.get(
            f"/api/devices/{device['id']}?include=tags,custom_fields",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert "custom_fields" in data
        assert data["custom_fields"][0]["key"] == "wattage"


# ---------------------------------------------------------------------------
# GET /api/devices/{id}/connections
# ---------------------------------------------------------------------------


class TestDeviceConnections:
    def test_list_connections_empty(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token)
        resp = client.get(
            f"/api/devices/{device['id']}/connections",
            headers=_auth(contributor_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_connections_device_not_found(
        self, client: TestClient, reader_token: str
    ) -> None:
        fake_id = str(uuid.uuid4())
        resp = client.get(
            f"/api/devices/{fake_id}/connections",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404

    def test_list_connections_as_source(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev1 = _create_device(client, contributor_token)
        dev2 = _create_device(client, contributor_token)
        conn_resp = client.post(
            "/api/connections/",
            json={
                "source_id": dev1["id"],
                "target_id": dev2["id"],
                "type": "Ethernet",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert conn_resp.status_code == 201

        resp = client.get(
            f"/api/devices/{dev1['id']}/connections",
            headers=_auth(contributor_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["source_id"] == dev1["id"]
        assert data[0]["target_id"] == dev2["id"]

    def test_list_connections_returns_404_for_device_owned_by_another_reader(
        self, client: TestClient, session: Session
    ) -> None:
        _, owner_token = _make_user(session, role=Role.Contributor)
        _, other_reader_token = _make_user(session, role=Role.Reader)
        dev1 = _create_device(client, owner_token)
        dev2 = _create_device(client, owner_token)

        conn_resp = client.post(
            "/api/connections/",
            json={
                "source_id": dev1["id"],
                "target_id": dev2["id"],
                "type": "Ethernet",
            },
            headers=_auth(owner_token),
        )
        assert conn_resp.status_code == 201

        response = client.get(
            f"/api/devices/{dev1['id']}/connections",
            headers=_auth(other_reader_token),
        )

        assert response.status_code == 404

    def test_list_connections_as_target(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev1 = _create_device(client, contributor_token)
        dev2 = _create_device(client, contributor_token)
        client.post(
            "/api/connections/",
            json={
                "source_id": dev1["id"],
                "target_id": dev2["id"],
                "type": "Ethernet",
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        resp = client.get(
            f"/api/devices/{dev2['id']}/connections",
            headers=_auth(contributor_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
