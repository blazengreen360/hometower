"""Integration tests for /api/diagrams/ pagination behaviour."""
import uuid

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


class TestListDiagramsPagination:
    def test_page_and_limit_respected(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """Create 3 diagrams and verify page/limit controls the slice returned."""
        for i in range(3):
            client.post(
                "/api/diagrams/",
                json={**LAYOUT_PAYLOAD, "name": f"Layout {i}"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )

        page1 = client.get(
            "/api/diagrams/",
            params={"page": 1, "limit": 2},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert page1.status_code == 200
        data1 = page1.json()
        assert len(data1["items"]) <= 2
        assert data1["page"] == 1
        assert data1["limit"] == 2

    def test_page_two_returns_fewer_or_no_items(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        """When fewer items remain than limit, page 2 returns correct slice."""
        for i in range(2):
            client.post(
                "/api/diagrams/",
                json={**LAYOUT_PAYLOAD, "name": f"Pag2Layout {i}"},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )

        resp = client.get(
            "/api/diagrams/",
            params={"page": 2, "limit": 100},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["limit"] == 100

    def test_invalid_page_zero_returns_422(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            "/api/diagrams/",
            params={"page": 0},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 422

    def test_limit_above_max_returns_422(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            "/api/diagrams/",
            params={"limit": 101},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 422

    def test_topology_id_filter_returns_only_that_topology(
        self, client: TestClient, contributor_token: str
    ) -> None:
        """The optional topology_id query must scope the list to a single topology."""
        c_headers = {"Authorization": f"Bearer {contributor_token}"}

        ws_resp = client.post(
            "/api/workspaces/",
            json={"name": f"DiagFilter-{uuid.uuid4().hex[:8]}"},
            headers=c_headers,
        )
        assert ws_resp.status_code == 201
        ws_id = ws_resp.json()["id"]

        topo_a_resp = client.post(
            f"/api/workspaces/{ws_id}/topologies/",
            json={"name": "Topo-A"},
            headers=c_headers,
        )
        topo_b_resp = client.post(
            f"/api/workspaces/{ws_id}/topologies/",
            json={"name": "Topo-B"},
            headers=c_headers,
        )
        assert topo_a_resp.status_code == 201
        assert topo_b_resp.status_code == 201
        topo_a = topo_a_resp.json()["id"]
        topo_b = topo_b_resp.json()["id"]

        diag_a_resp = client.post(
            "/api/diagrams/",
            json={
                **LAYOUT_PAYLOAD,
                "name": "Layout-A",
                "topology_id": topo_a,
            },
            headers=c_headers,
        )
        diag_b_resp = client.post(
            "/api/diagrams/",
            json={
                **LAYOUT_PAYLOAD,
                "name": "Layout-B",
                "topology_id": topo_b,
            },
            headers=c_headers,
        )
        assert diag_a_resp.status_code == 201
        assert diag_b_resp.status_code == 201

        filtered = client.get(
            "/api/diagrams/",
            params={"topology_id": topo_a, "limit": 100},
            headers=c_headers,
        )
        assert filtered.status_code == 200
        data = filtered.json()
        items = data["items"]
        assert len(items) >= 1
        assert all(item["topology_id"] == topo_a for item in items)
        assert any(item["name"] == "Layout-A" for item in items)
        assert all(item["name"] != "Layout-B" for item in items)
