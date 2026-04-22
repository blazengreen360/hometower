"""Integration tests for /api/devices/ validation edge cases."""
from fastapi.testclient import TestClient


class TestCreateDeviceValidation:
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

    def test_create_device_rejects_notes_over_5000_chars(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json={"name": "long-notes", "type": "Server", "notes": "x" * 5001},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_create_device_accepts_ipv6_address(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.post(
            "/api/devices/",
            json={"name": "ipv6-node", "type": "Router", "ip": "2001:db8::1"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 201
        assert response.json()["ip"] == "2001:db8::1"


class TestUpdateDeviceValidation:
    def test_update_device_rejects_empty_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "edit-empty", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_update_device_rejects_whitespace_only_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "edit-whitespace", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": "   ", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_update_device_rejects_null_name(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "edit-null", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"name": None, "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_update_device_rejects_notes_over_5000_chars(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "notes-me", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"notes": "y" * 5001, "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_update_device_validates_mac_format(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "edit-mac", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"mac": "bad:mac", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422

    def test_update_device_rejects_invalid_ip_format(
        self, client: TestClient, contributor_token: str
    ) -> None:
        create_resp = client.post(
            "/api/devices/",
            json={"name": "edit-ip", "type": "NAS"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        device_id = created["id"]

        response = client.patch(
            f"/api/devices/{device_id}",
            json={"ip": "not-an-ip", "version": created["version"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 422
