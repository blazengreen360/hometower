"""Integration tests for GET /api/export endpoint."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient


class TestExportRbac:
    def test_contributor_can_export(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200

    def test_admin_can_export(
        self, client: TestClient, admin_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_reader_cannot_export_returns_403(
        self, client: TestClient, reader_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_cannot_export_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/export")
        assert response.status_code == 401

    def test_contributor_cookie_auth_can_export(
        self, client: TestClient, contributor_token: str
    ) -> None:
        client.cookies.set("ht_access_token", contributor_token, path="/api")
        response = client.get("/api/export")
        assert response.status_code == 200


class TestExportResponse:
    def test_content_disposition_header_is_attachment(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.status_code == 200
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd

    def test_content_disposition_filename_pattern(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        cd = response.headers.get("content-disposition", "")
        assert "hometower-export-" in cd
        assert ".json" in cd

    def test_response_is_valid_json(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        parsed = json.loads(response.text)
        assert isinstance(parsed, dict)

    def test_response_contains_all_required_keys(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        data = response.json()
        required_keys = {
            "version", "exported_at", "devices", "connections", "locations",
            "tags", "device_tags", "networks", "device_networks",
            "custom_fields", "diagram_layouts", "users",
            "services", "service_dependencies", "workspaces", "topologies",
        }
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_export_version_is_1_0(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert response.json()["version"] == "1.0"

    def test_entity_arrays_are_lists(
        self, client: TestClient, contributor_token: str
    ) -> None:
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        data = response.json()
        assert isinstance(data["devices"], list)
        assert isinstance(data["connections"], list)
        assert isinstance(data["tags"], list)
        assert isinstance(data["locations"], list)
        assert isinstance(data["device_tags"], list)
        assert isinstance(data["networks"], list)
        assert isinstance(data["device_networks"], list)
        assert isinstance(data["custom_fields"], list)
        assert isinstance(data["diagram_layouts"], list)
        assert isinstance(data["users"], list)
        assert isinstance(data["services"], list)
        assert isinstance(data["service_dependencies"], list)
        assert isinstance(data["workspaces"], list)
        assert isinstance(data["topologies"], list)

    def test_export_is_rate_limited_after_three_requests_per_minute(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}

        for _ in range(3):
            response = client.get("/api/export", headers=headers)
            assert response.status_code == 200

        response = client.get("/api/export", headers=headers)
        assert response.status_code == 429


class TestExportDataIntegrity:
    def test_created_device_appears_in_export(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        client.post("/api/devices/", json={"name": "export-device", "type": "Server"}, headers=headers)

        response = client.get("/api/export", headers=headers)
        data = response.json()
        names = [d["name"] for d in data["devices"]]
        assert "export-device" in names

    def test_password_hash_never_appears_in_response_body(
        self, client: TestClient, contributor_token: str, admin_token: str
    ) -> None:
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        client.post(
            "/api/users/",
            json={"username": "noleak", "email": "noleak@test.local",
                  "password": "SecurePass123!", "role": "Contributor"},
            headers=admin_headers,
        )
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert "password_hash" not in response.text

    def test_exported_users_have_no_password_hash_field(
        self, client: TestClient, contributor_token: str, admin_token: str
    ) -> None:
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        client.post(
            "/api/users/",
            json={"username": "noleak2", "email": "noleak2@test.local",
                  "password": "SecurePass123!", "role": "Contributor"},
            headers=admin_headers,
        )
        response = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        data = response.json()
        for user in data["users"]:
            assert "password_hash" not in user

    def test_export_redact_masks_sensitive_device_fields(
        self, client: TestClient, contributor_token: str
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        client.post(
            "/api/devices/",
            json={
                "name": "redact-device",
                "type": "Server",
                "ip": "192.168.99.10",
                "mac": "aa:bb:cc:dd:ee:ff",
                "notes": "contains secret",
            },
            headers=headers,
        )

        response = client.get("/api/export?redact=true", headers=headers)
        assert response.status_code == 200
        data = response.json()
        target = next((d for d in data["devices"] if d["name"] == "redact-device"), None)
        assert target is not None
        assert target["ip"] == "[REDACTED]"
        assert target["mac"] == "[REDACTED]"
        assert target["notes"] == "[REDACTED]"

    def test_created_network_and_membership_appear_in_export(
        self,
        client: TestClient,
        contributor_token: str,
    ) -> None:
        headers = {"Authorization": f"Bearer {contributor_token}"}
        suffix = uuid.uuid4().hex[:8]

        dev_resp = client.post(
            "/api/devices/",
            json={"name": f"export-net-dev-{suffix}", "type": "Server"},
            headers=headers,
        )
        assert dev_resp.status_code == 201
        device_id = dev_resp.json()["id"]

        net_resp = client.post(
            "/api/networks/",
            json={
                "name": f"Management-{suffix}",
                "vlan_id": 10,
                "cidr": "10.0.10.0/24",
                "gateway": "10.0.10.1",
                "description": "Management",
                "color": "#3b82f6",
            },
            headers=headers,
        )
        assert net_resp.status_code == 201
        network_id = net_resp.json()["id"]

        attach_resp = client.post(
            f"/api/devices/{device_id}/networks",
            json={"network_id": network_id, "ip_address": "10.0.10.20"},
            headers=headers,
        )
        assert attach_resp.status_code == 201

        export_resp = client.get("/api/export", headers=headers)
        assert export_resp.status_code == 200
        payload = export_resp.json()

        assert any(row["id"] == network_id for row in payload["networks"])
        assert any(
            row["device_id"] == device_id
            and row["network_id"] == network_id
            and row["ip_address"] == "10.0.10.20"
            for row in payload["device_networks"]
        )
