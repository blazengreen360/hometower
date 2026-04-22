"""Integration tests for /api/devices/ CRUD endpoints and access control."""
import uuid
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.device import Device
from src.models.types import DeviceType, Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password

DEVICE_PAYLOAD: dict[str, str] = {"name": "test-server", "type": "Server"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role = Role.Reader) -> tuple[User, str]:
    user = User(
        username=f"devices_get_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@devices-get.local",
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


def _make_owned_device(session: Session, owner: User, name: str) -> Device:
    device = Device(name=name, type=DeviceType.Server, owner_id=owner.id)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


class TestCreateDevice:
    def test_create_device_as_contributor_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json=DEVICE_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-server"
        assert data["type"] == "Server"
        assert "id" in data
        assert "created_at" in data

    def test_create_device_as_reader_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json=DEVICE_PAYLOAD,
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403


class TestGetDevice:
    def test_get_device_by_id_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "get-me", "type": "Router"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.get(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "get-me"

    def test_get_nonexistent_device_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            f"/api/devices/{uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 404

    def test_get_device_by_id_hides_device_owned_by_another_reader(
        self, client: TestClient, session: Session
    ) -> None:
        owner, _ = _make_user(session, role=Role.Reader)
        _, other_reader_token = _make_user(session, role=Role.Reader)
        device = _make_owned_device(session, owner, "private-reader-device")

        response = client.get(
            f"/api/devices/{device.id}",
            headers=_auth(other_reader_token),
        )

        assert response.status_code == 404


class TestListDevices:
    def test_list_devices_returns_paginated_response(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        client.post(
            "/api/devices/",
            json={"name": "list-me", "type": "Switch"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        response = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["items"], list)

    def test_list_devices_pagination_params(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            "/api/devices/?page=2&limit=10",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10


class TestUpdateDevice:
    def test_update_device_as_contributor_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "update-me", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]
        created_at = created["created_at"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "updated-name", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-name"
        assert data["type"] == "NAS"
        assert data["updated_at"] >= created_at

    def test_update_nonexistent_device_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.patch(
            f"/api/devices/{uuid4()}",
            json={"name": "ghost", "version": 1},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 404

    def test_update_without_version_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "must-have-version", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "missing-version"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_device_update_rejects_stale_version(
        self, client: TestClient, admin_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {admin_token}"}
        create_resp = client.post(
            "/api/devices/",
            json={"name": "versioned-device", "type": "Server"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]
        current_version = created["version"]

        first_update = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "updated-once", "version": current_version},
            headers=headers,
        )
        assert first_update.status_code == 200

        stale_update = client.patch(
            f"/api/devices/{device_id}",
            json={"ip": "10.0.0.2", "version": 1},
            headers=headers,
        )
        assert stale_update.status_code == 409
        assert stale_update.json()["detail"] == (
            "Conflict: device was modified by another request"
        )

    def test_patch_parent_id_reparents_device_via_device_endpoint(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        parent = client.post(
            "/api/devices/",
            json={"name": "parent-device", "type": "Server"},
            headers=headers,
        )
        child = client.post(
            "/api/devices/",
            json={"name": "child-device", "type": "VM"},
            headers=headers,
        )
        assert parent.status_code == 201
        assert child.status_code == 201

        child_payload = child.json()
        parent_id = parent.json()["id"]

        response = client.patch(
            f"/api/devices/{child_payload['id']}",
            json={"parent_id": parent_id, "version": child_payload["version"]},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["parent_id"] == parent_id
        assert response.json()["version"] == child_payload["version"] + 1


class TestDeleteDevice:
    def test_delete_device_as_contributor_returns_204(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "delete-me", "type": "VM"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 204

    def test_delete_nonexistent_device_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.delete(
            f"/api/devices/{uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 404

    def test_delete_device_as_reader_returns_403(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "no-delete", "type": "Docker"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403

    def test_delete_device_cascades_connections(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        d1 = client.post("/api/devices/", json={"name": "src-dev", "type": "Server"}, headers=headers)
        d2 = client.post("/api/devices/", json={"name": "tgt-dev", "type": "Switch"}, headers=headers)
        assert d1.status_code == 201
        assert d2.status_code == 201
        d1_id = d1.json()["id"]
        d2_id = d2.json()["id"]

        conn = client.post(
            "/api/connections/",
            json={"source_id": d1_id, "target_id": d2_id, "type": "Ethernet"},
            headers=headers,
        )
        assert conn.status_code == 201

        # Delete d1 — connection should cascade
        resp = client.delete(f"/api/devices/{d1_id}", headers=headers)
        assert resp.status_code == 204

        # Verify connection is gone
        conns = client.get("/api/connections/", headers=headers)
        assert conns.status_code == 200
        conn_ids = [c["id"] for c in conns.json()["items"]]
        assert conn.json()["id"] not in conn_ids


class TestUnauthenticated:
    def test_unauthenticated_request_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/devices/")
        assert response.status_code == 401
