"""Integration tests for the /api/diagrams/ endpoints.

All tests run against the full FastAPI stack with an SQLite in-memory database.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

LAYOUT_PAYLOAD: dict[str, object] = {
    "name": "My Homelab",
    "cytoscape_json": {
        "elements": [
            {"data": {"id": "n1", "label": "Server-1"}, "position": {"x": 100, "y": 200}},
        ],
        "zoom": 1.0,
        "pan": {"x": 0, "y": 0},
    },
}


class TestCreateDiagram:
    def test_contributor_can_save_layout_returns_201(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Homelab"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "cytoscape_json" in data
        assert data["cytoscape_json"]["zoom"] == 1.0

    def test_reader_cannot_save_layout_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_post_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/diagrams/", json=LAYOUT_PAYLOAD)
        assert response.status_code == 401


class TestListDiagrams:
    def test_reader_can_list_diagrams_returns_200(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        response = client.get(
            "/api/diagrams/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["total"] >= 1
        assert data["page"] == 1
        assert data["limit"] == 50

    def test_list_returns_summaries_without_cytoscape_json(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        response = client.get(
            "/api/diagrams/",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 1
        for item in items:
            assert "cytoscape_json" not in item
            assert "name" in item
            assert "id" in item
            assert "created_at" in item
            assert "updated_at" in item

    def test_unauthenticated_list_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/diagrams/")
        assert response.status_code == 401


class TestGetDiagram:
    def test_reader_can_get_diagram_by_id_with_full_json(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        response = client.get(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Homelab"
        assert "cytoscape_json" in data
        assert data["cytoscape_json"]["zoom"] == 1.0

    def test_get_nonexistent_diagram_returns_404(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            f"/api/diagrams/{uuid4()}",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 404

    def test_unauthenticated_get_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.get(f"/api/diagrams/{uuid4()}")
        assert response.status_code == 401


class TestDeleteDiagram:
    def test_admin_can_delete_diagram_returns_204(
        self, client: TestClient, contributor_token: str, admin_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        diagram_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_resp = client.get(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404

    def test_contributor_cannot_delete_diagram_returns_403(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        diagram_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/diagrams/{diagram_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 403

    def test_delete_nonexistent_diagram_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        response = client.delete(
            f"/api/diagrams/{uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    def test_unauthenticated_delete_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.delete(f"/api/diagrams/{uuid4()}")
        assert response.status_code == 401


class TestCytoscapeJsonValidation:
    def test_create_with_empty_cytoscape_json_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json={"name": "test", "cytoscape_json": {}},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_create_with_non_object_cytoscape_json_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json={"name": "test", "cytoscape_json": "not-an-object"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_create_with_array_cytoscape_json_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/diagrams/",
            json={"name": "test", "cytoscape_json": [{"data": {"id": "n1"}}]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422
