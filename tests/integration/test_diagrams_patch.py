"""Integration tests for PATCH /api/diagrams/{id} endpoint (HT-029)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

LAYOUT_PAYLOAD: dict[str, object] = {
    "name": "Initial Layout",
    "cytoscape_json": {
        "elements": [],
        "zoom": 1.0,
        "pan": {"x": 0, "y": 0},
    },
}


class TestPatchDiagram:
    def test_patch_name_only_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create.status_code == 201
        created = create.json()
        layout_id = created["id"]
        version = created["version"]

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "Renamed Layout", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 200
        data = patch.json()
        assert data["name"] == "Renamed Layout"
        assert data["version"] == version + 1
        # cytoscape_json should be unchanged
        assert data["cytoscape_json"]["zoom"] == 1.0

    def test_patch_cytoscape_json_only_returns_200(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        created = create.json()
        layout_id = created["id"]
        version = created["version"]
        new_json = {"elements": [{"data": {"id": "n1"}}], "zoom": 2.0, "pan": {"x": 10, "y": 20}}

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"cytoscape_json": new_json, "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 200
        data = patch.json()
        # name should be unchanged
        assert data["name"] == "Initial Layout"
        assert data["cytoscape_json"]["zoom"] == 2.0

    def test_patch_both_name_and_json(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        created = create.json()
        layout_id = created["id"]
        version = created["version"]

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={
                "name": "New Name",
                "cytoscape_json": {"elements": [], "zoom": 3.0},
                "version": version,
            },
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 200
        data = patch.json()
        assert data["name"] == "New Name"
        assert data["cytoscape_json"]["zoom"] == 3.0

    def test_patch_missing_version_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create.status_code == 201
        layout_id = create.json()["id"]

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "missing-version"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 422

    def test_patch_oversized_cytoscape_json_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create.status_code == 201
        created = create.json()
        layout_id = created["id"]
        version = created["version"]

        oversized_json: dict[str, object] = {
            "elements": [],
            "blob": "x" * 5_000_001,
        }
        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"cytoscape_json": oversized_json, "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 422

    def test_patch_nonexistent_layout_returns_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        patch = client.patch(
            f"/api/diagrams/{uuid4()}",
            json={"name": "Missing", "version": 1},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 404

    def test_patch_requires_contributor_role(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        created = create.json()
        layout_id = created["id"]
        version = created["version"]

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "Should Fail", "version": version},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert patch.status_code == 403

    def test_patch_empty_name_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        created = create.json()
        layout_id = created["id"]
        version = created["version"]

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 422

    def test_patch_updates_updated_at(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        created = create.json()
        orig_updated_at = created["updated_at"]
        layout_id = created["id"]
        version = created["version"]

        patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "Updated", "version": version},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 200
        assert patch.json()["id"] == layout_id
        assert "updated_at" in patch.json()
        assert patch.json()["updated_at"] != orig_updated_at

    def test_patch_rejects_stale_version(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers=headers,
        )
        assert create.status_code == 201
        layout_id = create.json()["id"]

        first_patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "v1", "version": 1},
            headers=headers,
        )
        assert first_patch.status_code == 200

        stale_patch = client.patch(
            f"/api/diagrams/{layout_id}",
            json={"name": "stale", "version": 1},
            headers=headers,
        )
        assert stale_patch.status_code == 409
        assert stale_patch.json()["detail"] == (
            "Conflict: diagram was modified by another request"
        )

    def test_patch_pruned_cytoscape_json_increments_version_once(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        create = client.post(
            "/api/diagrams/",
            json=LAYOUT_PAYLOAD,
            headers=headers,
        )
        assert create.status_code == 201
        created = create.json()

        pruned_json = {
            "elements": {
                "nodes": [{"data": {"id": "container-1"}}],
                "edges": [],
            },
            "zoom": 1.25,
            "pan": {"x": 4, "y": 5},
            "collapsedNodes": [],
        }

        patch = client.patch(
            f"/api/diagrams/{created['id']}",
            json={"cytoscape_json": pruned_json, "version": created["version"]},
            headers=headers,
        )

        assert patch.status_code == 200
        data = patch.json()
        assert data["version"] == created["version"] + 1
        assert data["cytoscape_json"] == pruned_json
