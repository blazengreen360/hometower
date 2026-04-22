"""Integration tests for the /api/connections/ endpoints — core CRUD behaviour."""
from uuid import uuid4

from fastapi.testclient import TestClient

CONNECTION_TYPE = "Ethernet"


class TestCreateConnection:
    def test_contributor_can_create_returns_201(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
    ) -> None:
        src, tgt = two_devices
        resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_id"] == src
        assert data["target_id"] == tgt
        assert data["type"] == CONNECTION_TYPE
        assert "id" in data
        assert "created_at" in data


class TestListConnections:
    def test_owner_can_list_returns_200(
        self,
        client: TestClient,
        contributor_token: str,
        two_devices: tuple[int, int],
    ) -> None:
        src, tgt = two_devices
        client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            "/api/connections/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] == 1

    def test_filter_by_source_id(
        self,
        client: TestClient,
        contributor_token: str,
        two_devices: tuple[int, int],
    ) -> None:
        src, tgt = two_devices
        client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            f"/api/connections/?source_id={src}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(item["source_id"] == src for item in items)

    def test_pagination_params(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            "/api/connections/?page=2&limit=5",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["limit"] == 5


class TestGetConnection:
    def test_owner_can_get_by_id_returns_200(
        self,
        client: TestClient,
        contributor_token: str,
        two_devices: tuple[int, int],
    ) -> None:
        src, tgt = two_devices
        create_resp = client.post(
            "/api/connections/",
            json={"source_id": src, "target_id": tgt, "type": CONNECTION_TYPE},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        conn_id = create_resp.json()["id"]
        resp = client.get(
            f"/api/connections/{conn_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == conn_id

    def test_nonexistent_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            f"/api/connections/{uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 404


class TestUpdateConnection:
    def test_contributor_can_update_returns_200(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
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
            json={"label": "uplink"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "uplink"


class TestDeleteConnection:
    def test_contributor_can_delete_returns_204(
        self, client: TestClient, contributor_token: str, two_devices: tuple[int, int]
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
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

    def test_nonexistent_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.delete(
            f"/api/connections/{uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404
