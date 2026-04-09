"""Integration tests for /api/connections/ — validation and permission rules."""
from uuid import uuid4

from fastapi.testclient import TestClient

CONNECTION_TYPE = "Ethernet"


class TestCreateConnectionValidation:
    def test_reader_cannot_create_returns_403(
        self, client: TestClient, reader_token: str, two_devices: tuple[int, int]
    ) -> None:
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(
        self, client: TestClient, two_devices: tuple[int, int]
    ) -> None:
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
        )
        assert resp.status_code == 401

    def test_self_loop_returns_400(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
    ) -> None:
        src, _ = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": src, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "itself" in resp.json()["detail"]

    def test_nonexistent_source_returns_400(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
    ) -> None:
        _, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": str(uuid4()), "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "Source" in resp.json()["detail"]

    def test_nonexistent_target_returns_400(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
    ) -> None:
        src, _ = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": str(uuid4()), "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "Target" in resp.json()["detail"]


class TestUpdateConnectionPermissions:
    def test_reader_cannot_update_returns_403(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        two_devices: tuple[int, int],
    ) -> None:
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]
        resp = client.patch(
            f"/api/connections/{conn_id}",
            json={"label": "blocked"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403


class TestDeleteConnectionPermissions:
    def test_reader_cannot_delete_returns_403(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
        two_devices: tuple[int, int],
    ) -> None:
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403

    def test_delete_device_with_connections_returns_400(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
    ) -> None:
        """Deleting a device that has active connections must be blocked."""
        src, tgt = two_devices
        headers = {"Authorization": f"Bearer {contributor_token}"}
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers=headers,
        )
        assert create_resp.status_code == 201

        resp = client.delete(f"/api/devices/{src}", headers=headers)
        assert resp.status_code == 400
        assert "connection" in resp.json()["detail"].lower()
