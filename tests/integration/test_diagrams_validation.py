"""Integration tests for /api/diagrams/ validation and edge cases."""
from uuid import uuid4

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


class TestDiagramAuthValidation:
    def test_unauthenticated_post_returns_401(self, client: TestClient) -> None:
        response = client.post("/api/diagrams/", json=LAYOUT_PAYLOAD)
        assert response.status_code == 401

    def test_unauthenticated_list_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/diagrams/")
        assert response.status_code == 401

    def test_unauthenticated_get_returns_401(self, client: TestClient) -> None:
        response = client.get(f"/api/diagrams/{uuid4()}")
        assert response.status_code == 401

    def test_unauthenticated_delete_returns_401(self, client: TestClient) -> None:
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

    def test_create_with_oversized_cytoscape_json_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        oversized_json: dict[str, object] = {
            "elements": [],
            "blob": "x" * 5_000_001,
        }
        response = client.post(
            "/api/diagrams/",
            json={"name": "oversized", "cytoscape_json": oversized_json},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422
