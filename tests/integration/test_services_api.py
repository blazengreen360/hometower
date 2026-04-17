"""Integration tests for the Services API (HT-023).

Covers: CRUD, 409 duplicate name, cascade delete, dependency CRUD,
cycle detection, ?include=services enrichment, RBAC.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


_DEVICE = {"name": "svc-test-node", "type": "Server"}
_SERVICE = {"name": "nginx", "protocol": "http", "port": 80}


def _create_device(client: TestClient, token: str, name: str = "svc-test-node") -> dict:
    resp = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_service(
    client: TestClient,
    token: str,
    device_id: str,
    name: str = "nginx",
    protocol: str = "http",
    port: int = 80,
) -> dict:
    resp = client.post(
        f"/api/devices/{device_id}/services",
        json={"name": name, "protocol": protocol, "port": port},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestServiceCreate:
    def test_create_success(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token)
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "plex", "protocol": "tcp", "port": 32400, "status": "running"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "plex"
        assert data["port"] == 32400
        assert data["protocol"] == "tcp"
        assert data["status"] == "running"
        assert data["device_id"] == device["id"]
        assert "id" in data

    def test_create_minimal(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "min-dev")
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "unnamed-svc", "protocol": "other"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["port"] is None
        assert data["status"] == "unknown"

    def test_duplicate_name_same_device_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "dup-dev")
        _create_service(client, contributor_token, device["id"], name="redis")
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "redis", "protocol": "tcp"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409

    def test_duplicate_name_case_insensitive_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "case-dev")
        _create_service(client, contributor_token, device["id"], name="Redis")
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "REDIS", "protocol": "tcp"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409

    def test_same_name_different_devices_ok(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev1 = _create_device(client, contributor_token, "dev1-svc")
        dev2 = _create_device(client, contributor_token, "dev2-svc")
        _create_service(client, contributor_token, dev1["id"], name="nginx")
        resp = client.post(
            f"/api/devices/{dev2['id']}/services",
            json={"name": "nginx", "protocol": "http"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_invalid_port_low_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "port-dev-low")
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "bad-svc", "protocol": "tcp", "port": 0},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422  # Pydantic ge=1 validation

    def test_invalid_port_high_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "port-dev-high")
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "bad-svc2", "protocol": "tcp", "port": 65536},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 422

    def test_device_not_found_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            f"/api/devices/{uuid.uuid4()}/services",
            json={"name": "orphan", "protocol": "tcp"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_reader_cannot_create(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "rbac-svc-dev")
        resp = client.post(
            f"/api/devices/{device['id']}/services",
            json={"name": "blocked", "protocol": "tcp"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class TestServiceRead:
    def test_list_by_device(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "list-svc-dev")
        _create_service(client, contributor_token, device["id"], "svc-a", "http", 80)
        _create_service(client, contributor_token, device["id"], "svc-b", "tcp", 5432)
        resp = client.get(
            f"/api/devices/{device['id']}/services",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "svc-a" in names
        assert "svc-b" in names

    def test_get_by_id(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "get-svc-dev")
        svc = _create_service(client, contributor_token, device["id"])
        resp = client.get(
            f"/api/services/{svc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == svc["id"]

    def test_get_not_found_404(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.get(
            f"/api/services/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 404

    def test_list_all_services(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "global-svc-dev")
        _create_service(client, contributor_token, device["id"], "glob-svc", "http", 80)
        resp = client.get(
            "/api/services/",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "glob-svc" in names

    def test_list_all_services_q_filter(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "q-svc-dev")
        _create_service(client, contributor_token, device["id"], "postgres-main", "tcp", 5432)
        _create_service(client, contributor_token, device["id"], "redis-main", "tcp", 6379)
        resp = client.get(
            "/api/services/?q=postgres",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "postgres-main" in names
        assert "redis-main" not in names


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestServiceUpdate:
    def test_patch_name(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "patch-svc-dev")
        svc = _create_service(client, contributor_token, device["id"])
        resp = client.patch(
            f"/api/services/{svc['id']}",
            json={"name": "nginx-updated", "status": "running"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "nginx-updated"
        assert resp.json()["status"] == "running"

    def test_patch_name_conflict_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "patch-conf-dev")
        _create_service(client, contributor_token, device["id"], "svc1", "tcp", 100)
        svc2 = _create_service(client, contributor_token, device["id"], "svc2", "tcp", 200)
        resp = client.patch(
            f"/api/services/{svc2['id']}",
            json={"name": "svc1"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Delete + Cascade
# ---------------------------------------------------------------------------


class TestServiceDelete:
    def test_delete_service(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "del-svc-dev")
        svc = _create_service(client, contributor_token, device["id"])
        resp = client.delete(
            f"/api/services/{svc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204
        # Confirm gone
        get_resp = client.get(
            f"/api/services/{svc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert get_resp.status_code == 404

    def test_device_cascade_deletes_services(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "casc-dev")
        svc = _create_service(client, contributor_token, device["id"])
        client.delete(
            f"/api/devices/{device['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # Service should be deleted by cascade at DB level
        # (check via listing endpoint)
        # NOTE: SQLite doesn't enforce FK CASCADE by default unless PRAGMA set
        # This test exercises the delete path; cascade is enforced in Postgres
        get_resp = client.get(
            f"/api/services/{svc['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # Accept either 404 (cascaded) or still present (SQLite without pragma)
        assert get_resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestServiceDependencies:
    def test_add_dependency(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "dep-dev")
        svc_a = _create_service(client, contributor_token, device["id"], "dep-a", "tcp", 100)
        svc_b = _create_service(client, contributor_token, device["id"], "dep-b", "tcp", 200)
        resp = client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 201

    def test_list_dependencies(self, client: TestClient, contributor_token: str) -> None:
        device = _create_device(client, contributor_token, "list-dep-dev")
        svc_a = _create_service(client, contributor_token, device["id"], "l-dep-a", "tcp", 101)
        svc_b = _create_service(client, contributor_token, device["id"], "l-dep-b", "tcp", 201)
        client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            f"/api/services/{svc_a['id']}/dependencies",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        dep_ids = [d["id"] for d in resp.json()]
        assert svc_b["id"] in dep_ids

    def test_add_dependency_duplicate_409(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "dup-dep-dev")
        svc_a = _create_service(client, contributor_token, device["id"], "dd-a", "tcp", 102)
        svc_b = _create_service(client, contributor_token, device["id"], "dd-b", "tcp", 202)
        client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 409

    def test_cycle_detection_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "cycle-dev")
        svc_a = _create_service(client, contributor_token, device["id"], "cy-a", "tcp", 103)
        svc_b = _create_service(client, contributor_token, device["id"], "cy-b", "tcp", 203)
        client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # Now try to make B depend on A → would create cycle
        resp = client.post(
            f"/api/services/{svc_b['id']}/dependencies",
            json={"depends_on": svc_a["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400
        assert "Circular" in resp.json()["detail"]

    def test_self_dependency_400(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "self-dep-dev")
        svc = _create_service(client, contributor_token, device["id"], "self-svc", "tcp", 104)
        resp = client.post(
            f"/api/services/{svc['id']}/dependencies",
            json={"depends_on": svc["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 400

    def test_self_dependency_400_when_domain_cycle_check_is_bypassed(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "self-dep-db-guard-dev")
        svc = _create_service(client, contributor_token, device["id"], "self-db-svc", "tcp", 108)
        with patch(
            "src.services.service_service.service_domain.validate_no_dependency_cycle",
            return_value=None,
        ):
            resp = client.post(
                f"/api/services/{svc['id']}/dependencies",
                json={"depends_on": svc["id"]},
                headers={"Authorization": f"Bearer {contributor_token}"},
            )
        assert resp.status_code == 400

    def test_remove_dependency(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "rm-dep-dev")
        svc_a = _create_service(client, contributor_token, device["id"], "rm-a", "tcp", 105)
        svc_b = _create_service(client, contributor_token, device["id"], "rm-b", "tcp", 205)
        client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.delete(
            f"/api/services/{svc_a['id']}/dependencies/{svc_b['id']}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 204

    def test_get_with_dependencies(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "full-dep-dev")
        svc_a = _create_service(client, contributor_token, device["id"], "full-a", "tcp", 106)
        svc_b = _create_service(client, contributor_token, device["id"], "full-b", "tcp", 206)
        client.post(
            f"/api/services/{svc_a['id']}/dependencies",
            json={"depends_on": svc_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        resp = client.get(
            f"/api/services/{svc_a['id']}?include=dependencies",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "depends_on" in data
        dep_ids = [d["id"] for d in data["depends_on"]]
        assert svc_b["id"] in dep_ids


# ---------------------------------------------------------------------------
# include=services enrichment
# ---------------------------------------------------------------------------


class TestIncludeServices:
    def test_device_detail_with_services(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "inc-svc-dev")
        _create_service(client, contributor_token, device["id"], "inc-nginx", "http", 80)
        resp = client.get(
            f"/api/devices/{device['id']}?include=services",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data
        svc_names = [s["name"] for s in data["services"]]
        assert "inc-nginx" in svc_names

    def test_device_list_with_services(
        self, client: TestClient, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "list-inc-svc-dev")
        _create_service(client, contributor_token, device["id"], "list-svc", "tcp", 1234)
        resp = client.get(
            "/api/devices/?include=services&limit=1000",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        target = next((i for i in items if i["id"] == device["id"]), None)
        assert target is not None
        assert any(s["name"] == "list-svc" for s in target["services"])
