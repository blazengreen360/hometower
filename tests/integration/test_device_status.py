"""Integration tests for device status field via API (HT-039)."""
import pytest
from fastapi.testclient import TestClient


class TestDeviceStatusCreate:
    def test_create_device_default_status_is_active(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/devices/",
            json={"name": "default-status", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "Active"

    def test_create_device_with_explicit_status(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/devices/",
            json={"name": "maint-device", "type": "Switch", "status": "Maintenance"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "Maintenance"

    def test_create_device_with_planned_status(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/devices/",
            json={"name": "planned-srv", "type": "Server", "status": "Planned"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "Planned"

    def test_create_device_invalid_status_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/devices/",
            json={"name": "bad-status", "type": "Server", "status": "Broken"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_all_valid_status_values_accepted(
        self, client: TestClient, contributor_token: str
    ) -> None:
        for status in ("Active", "Offline", "Maintenance", "Planned", "Decommissioned"):
            resp = client.post(
                "/api/devices/",
                json={"name": f"dev-{status}", "type": "Server", "status": status},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
            assert resp.status_code == 201, f"Expected 201 for status={status}"
            assert resp.json()["status"] == status


class TestDeviceStatusPatch:
    def test_patch_device_status(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/devices/",
            json={"name": "patch-me", "type": "Router"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create.status_code == 201
        created = create.json()
        device_id = created["id"]

        patch = client.patch(
            f"/api/devices/{device_id}",
            json={"status": "Decommissioned", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 200
        assert patch.json()["status"] == "Decommissioned"

    def test_patch_invalid_status_returns_422(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/devices/",
            json={"name": "patch-invalid", "type": "Router"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        created = create.json()
        device_id = created["id"]

        patch = client.patch(
            f"/api/devices/{device_id}",
            json={"status": "Unknown", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert patch.status_code == 422

    def test_get_device_response_includes_status(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create = client.post(
            "/api/devices/",
            json={"name": "status-check", "type": "NAS", "status": "Offline"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        device_id = create.json()["id"]

        resp = client.get(
            f"/api/devices/{device_id}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Offline"
