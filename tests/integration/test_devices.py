"""Integration tests for the /api/devices/ endpoints.

All tests run against the full FastAPI stack with an SQLite in-memory database.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

DEVICE_PAYLOAD: dict[str, str] = {"name": "test-server", "type": "Server"}


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

    def test_create_device_validates_mac_format(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json={"name": "bad-mac-device", "type": "Server", "mac": "invalid-mac"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_create_device_with_valid_mac_normalizes_to_uppercase(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json={"name": "mac-device", "type": "Switch", "mac": "aa:bb:cc:dd:ee:ff"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        assert response.json()["mac"] == "AA:BB:CC:DD:EE:FF"


class TestGetDevice:
    def test_get_device_by_id_returns_200(
        self, client: TestClient, contributor_token: str, reader_token: str
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
            headers={"Authorization": f"Bearer {reader_token}"},
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
            json={"name": "updated-name"},
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
            json={"name": "ghost"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 404


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

    def test_delete_device_with_active_connections_returns_400(
        self, client: TestClient, contributor_token: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "connected-device", "type": "Switch"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        device_id = create_resp.json()["id"]

        import src.services.device_service as svc

        monkeypatch.setattr(svc, "_count_device_connections", lambda _id, _session: 2)

        response = client.delete(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 400
        assert "Cannot delete device with active connections" in response.json()["detail"]


class TestUnauthenticated:
    def test_unauthenticated_request_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/devices/")
        assert response.status_code == 401
