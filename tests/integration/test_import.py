"""Integration tests for POST /api/import endpoint (HT-013)."""
import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.domain.export import EXPORT_VERSION
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.user import User
from src.models.workspace import Workspace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_as_payload(user: User) -> dict:  # type: ignore[type-arg]
    """Convert a User ORM object to the ExportedUser dict shape."""
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else _now(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else _now(),
    }


def _valid_payload(**overrides) -> dict:  # type: ignore[type-arg]
    base: dict = {  # type: ignore[type-arg]
        "version": EXPORT_VERSION,
        "exported_at": _now(),
        "devices": [],
        "connections": [],
        "locations": [],
        "tags": [],
        "device_tags": [],
        "networks": [],
        "device_networks": [],
        "custom_fields": [],
        "diagram_layouts": [],
        "services": [],
        "service_dependencies": [],
        "workspaces": [],
        "topologies": [],
        "users": [],
    }
    base.update(overrides)
    return base


def _do_import(
    client: TestClient,
    payload: dict,  # type: ignore[type-arg]
    token: str,
    confirm: bool = True,
) -> object:
    content = json.dumps(payload).encode()
    qs = "?confirm=true" if confirm else ""
    return client.post(
        f"/api/import{qs}",
        files={"file": ("export.json", content, "application/json")},
        headers={"Authorization": f"Bearer {token}"},
    )


def _create_device(client: TestClient, token: str, name: str) -> dict:  # type: ignore[type-arg]
    response = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_service(client: TestClient, token: str, device_id: str, name: str) -> dict:  # type: ignore[type-arg]
    response = client.post(
        f"/api/devices/{device_id}/services",
        json={"name": name, "protocol": "tcp", "port": 1234},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


class TestImportRbac:
    def test_admin_can_import(self, client: TestClient, admin_token: str) -> None:
        resp = _do_import(client, _valid_payload(), admin_token)
        assert resp.status_code == 200

    def test_contributor_receives_403(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = _do_import(client, _valid_payload(), contributor_token)
        assert resp.status_code == 403

    def test_reader_receives_403(self, client: TestClient, reader_token: str) -> None:
        resp = _do_import(client, _valid_payload(), reader_token)
        assert resp.status_code == 403

    def test_unauthenticated_receives_401(self, client: TestClient) -> None:
        content = json.dumps(_valid_payload()).encode()
        resp = client.post(
            "/api/import?confirm=true",
            files={"file": ("export.json", content, "application/json")},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestImportValidation:
    def test_missing_confirm_flag_returns_400(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = _do_import(client, _valid_payload(), admin_token, confirm=False)
        assert resp.status_code == 400

    def test_malformed_json_returns_400(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.post(
            "/api/import?confirm=true",
            files={"file": ("export.json", b"not-json!!", "application/json")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_unknown_version_returns_400(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _valid_payload(version="99.0")
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 400

    def test_invalid_schema_missing_fields_returns_422(
        self, client: TestClient, admin_token: str
    ) -> None:
        bad: dict = {"version": EXPORT_VERSION, "exported_at": _now()}  # type: ignore[type-arg]
        resp = _do_import(client, bad, admin_token)
        assert resp.status_code == 422

    def test_file_over_50mb_returns_413(
        self, client: TestClient, admin_token: str
    ) -> None:
        big_content = b"x" * (51 * 1024 * 1024)
        resp = client.post(
            "/api/import?confirm=true",
            files={"file": ("export.json", big_content, "application/json")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 413

    def test_dangling_device_location_id_returns_422(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _valid_payload(
            devices=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "dangling-location-device",
                    "type": "Server",
                    "ip": None,
                    "mac": None,
                    "os": None,
                    "notes": None,
                    "location_id": str(uuid.uuid4()),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ]
        )
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 422

    def test_import_is_rate_limited_after_one_request_per_minute(
        self,
        client: TestClient,
        admin_token: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        counts = {"devices": 0}

        monkeypatch.setattr(
            "src.api.routers.data_transfer.import_full_snapshot",
            lambda session, payload: counts,
        )

        first = _do_import(client, _valid_payload(), admin_token)
        second = _do_import(client, _valid_payload(), admin_token)

        assert first.status_code == 200
        assert second.status_code == 429

    def test_import_accepts_legacy_payload_without_network_keys(
        self,
        client: TestClient,
        admin_token: str,
    ) -> None:
        payload = _valid_payload()
        payload.pop("networks")
        payload.pop("device_networks")
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 200

    def test_invalid_network_row_without_memberships_returns_422(
        self,
        client: TestClient,
        admin_token: str,
    ) -> None:
        payload = _valid_payload(
            networks=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "invalid-net",
                    "vlan_id": 10,
                    "cidr": "not-a-cidr",
                    "gateway": "10.0.10.1",
                    "description": "bad network row",
                    "color": "#3b82f6",
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ],
            device_networks=[],
        )

        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 422
        assert "payload.networks rows must contain valid" in resp.json()["detail"]

    def test_invalid_network_color_returns_422_before_insert(
        self,
        client: TestClient,
        admin_token: str,
        contributor_token: str,
    ) -> None:
        existing = _create_device(client, contributor_token, "existing-before-invalid-network-color")
        payload = _valid_payload(
            networks=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "invalid-color-net",
                    "vlan_id": 12,
                    "cidr": "10.12.0.0/24",
                    "gateway": "10.12.0.1",
                    "description": "bad color",
                    "color": "blue",
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ]
        )

        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 422
        assert "payload.networks rows must contain valid" in resp.json()["detail"]

        detail_resp = client.get(
            f"/api/devices/{existing['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["id"] == existing["id"]

    def test_invalid_network_name_returns_422(
        self,
        client: TestClient,
        admin_token: str,
    ) -> None:
        payload = _valid_payload(
            networks=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "   ",
                    "vlan_id": 13,
                    "cidr": "10.13.0.0/24",
                    "gateway": "10.13.0.1",
                    "description": "bad name",
                    "color": "#3b82f6",
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ]
        )

        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 422
        assert "payload.networks rows must contain valid" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Successful import
# ---------------------------------------------------------------------------


class TestImportSuccess:
    def test_returns_200_with_summary_dict(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = _do_import(client, _valid_payload(), admin_token)
        assert resp.status_code == 200
        body = resp.json()
        for key in [
            "users", "workspaces", "topologies", "locations", "tags", "devices",
            "connections", "device_tags", "networks", "device_networks",
            "custom_fields", "diagram_layouts",
            "services", "service_dependencies",
        ]:
            assert key in body, f"summary missing key: {key}"

    def test_returns_correct_counts(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _valid_payload(
            devices=[
                {
                    "id": str(uuid.uuid4()),
                    "name": "Server01",
                    "type": "Server",
                    "ip": None, "mac": None, "os": None, "notes": None,
                    "location_id": None,
                    "created_at": _now(), "updated_at": _now(),
                }
            ]
        )
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 200
        assert resp.json()["devices"] == 1

    def test_preserves_original_uuids(
        self, client: TestClient, admin_token: str, admin_user: "User"
    ) -> None:
        device_id = str(uuid.uuid4())
        payload = _valid_payload(
            devices=[
                {
                    "id": device_id,
                    "name": "MyDevice",
                    "type": "Server",
                    "ip": None, "mac": None, "os": None, "notes": None,
                    "location_id": None,
                    "created_at": _now(), "updated_at": _now(),
                }
            ],
            # Preserve admin_user so the token remains valid after truncation
            users=[_user_as_payload(admin_user)],
        )
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 200

        export_resp = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        exported = export_resp.json()
        device_ids = [d["id"] for d in exported["devices"]]
        assert device_id in device_ids

    def test_replaces_all_existing_data(
        self, client: TestClient, admin_token: str, admin_user: "User",
        contributor_token: str
    ) -> None:
        # Create some data first
        client.post(
            "/api/devices/",
            json={"name": "OldDevice", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        # Import an empty snapshot, but preserve admin_user so the token stays valid
        resp = _do_import(
            client,
            _valid_payload(users=[_user_as_payload(admin_user)]),
            admin_token,
        )
        assert resp.status_code == 200

        # The old device must be gone
        list_resp = client.get(
            "/api/devices/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert list_resp.status_code == 200
        devices = list_resp.json()["items"]
        assert not any(d["name"] == "OldDevice" for d in devices)

    def test_round_trip_preserves_ids(
        self, client: TestClient, admin_token: str, contributor_token: str
    ) -> None:
        """Export → import → export must preserve device UUIDs."""
        # Create a device
        create_resp = client.post(
            "/api/devices/",
            json={"name": "RoundTrip", "type": "Switch"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert create_resp.status_code == 201

        # Export
        export1 = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        original_ids = {d["id"] for d in export1["devices"]}

        # Import
        resp = _do_import(client, export1, admin_token)
        assert resp.status_code == 200

        # Export again
        export2 = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        restored_ids = {d["id"] for d in export2["devices"]}

        assert original_ids == restored_ids

    def test_round_trip_preserves_services_and_dependencies(
        self, client: TestClient, admin_token: str, contributor_token: str
    ) -> None:
        device = _create_device(client, contributor_token, "svc-round-trip-device")
        service_a = _create_service(client, contributor_token, device["id"], "svc-a")
        service_b = _create_service(client, contributor_token, device["id"], "svc-b")

        dep_resp = client.post(
            f"/api/services/{service_a['id']}/dependencies",
            json={"depends_on": service_b["id"]},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert dep_resp.status_code == 201

        export_1 = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        assert len(export_1["services"]) >= 2
        assert len(export_1["service_dependencies"]) >= 1

        import_resp = _do_import(client, export_1, admin_token)
        assert import_resp.status_code == 200

        export_2 = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()

        services_1 = {
            (
                row["id"],
                row["device_id"],
                row["name"],
                row["port"],
                row["protocol"],
                row["status"],
                row["notes"],
                row["url"],
            )
            for row in export_1["services"]
        }
        services_2 = {
            (
                row["id"],
                row["device_id"],
                row["name"],
                row["port"],
                row["protocol"],
                row["status"],
                row["notes"],
                row["url"],
            )
            for row in export_2["services"]
        }

        deps_1 = {
            (row["service_id"], row["depends_on_id"])
            for row in export_1["service_dependencies"]
        }
        deps_2 = {
            (row["service_id"], row["depends_on_id"])
            for row in export_2["service_dependencies"]
        }

        assert services_1 == services_2
        assert deps_1 == deps_2

    def test_round_trip_preserves_topology_scoped_diagram_layouts(
        self,
        client: TestClient,
        admin_token: str,
        admin_user: "User",
        session: Session,
    ) -> None:
        workspace_id = uuid.uuid4()
        topology_id = uuid.uuid4()
        layout_id = uuid.uuid4()

        workspace = Workspace(
            id=workspace_id,
            owner_id=admin_user.id,
            name=f"ws-{uuid.uuid4().hex[:8]}",
        )
        topology = Topology(
            id=topology_id,
            workspace_id=workspace_id,
            name=f"topo-{uuid.uuid4().hex[:8]}",
            tags=["edge", "prod"],
        )
        layout = DiagramLayout(
            id=layout_id,
            topology_id=topology_id,
            name=f"layout-{uuid.uuid4().hex[:8]}",
            version=7,
            cytoscape_json={"nodes": [], "edges": []},
        )
        session.add(workspace)
        session.flush()
        session.add(topology)
        session.flush()
        session.add(layout)
        session.commit()

        try:
            export_1 = client.get(
                "/api/export",
                headers={"Authorization": f"Bearer {admin_token}"},
            ).json()

            layout_row_1 = next(
                row for row in export_1["diagram_layouts"] if row["id"] == str(layout_id)
            )
            assert layout_row_1["topology_id"] == str(topology_id)
            assert layout_row_1["version"] == 7

            import_resp = _do_import(client, export_1, admin_token)
            assert import_resp.status_code == 200

            export_2 = client.get(
                "/api/export",
                headers={"Authorization": f"Bearer {admin_token}"},
            ).json()

            workspaces_1 = {
                (row["id"], row["owner_id"], row["name"])
                for row in export_1["workspaces"]
            }
            workspaces_2 = {
                (row["id"], row["owner_id"], row["name"])
                for row in export_2["workspaces"]
            }
            topologies_1 = {
                (row["id"], row["workspace_id"], row["name"], tuple(row["tags"]))
                for row in export_1["topologies"]
            }
            topologies_2 = {
                (row["id"], row["workspace_id"], row["name"], tuple(row["tags"]))
                for row in export_2["topologies"]
            }
            layouts_1 = {
                (row["id"], row.get("topology_id"), row.get("version"), row["name"])
                for row in export_1["diagram_layouts"]
            }
            layouts_2 = {
                (row["id"], row.get("topology_id"), row.get("version"), row["name"])
                for row in export_2["diagram_layouts"]
            }

            assert workspaces_1 == workspaces_2
            assert topologies_1 == topologies_2
            assert layouts_1 == layouts_2
        finally:
            restored_workspace = session.get(Workspace, workspace_id)
            if restored_workspace is not None:
                session.delete(restored_workspace)
                session.commit()

    def test_round_trip_preserves_device_status(
        self, client: TestClient, admin_token: str, admin_user: "User"
    ) -> None:
        """Export → import → export must preserve device status field."""
        device_id = str(uuid.uuid4())
        payload = _valid_payload(
            devices=[
                {
                    "id": device_id,
                    "name": "StatusDevice",
                    "type": "Server",
                    "status": "Maintenance",
                    "ip": None, "mac": None, "os": None, "notes": None,
                    "location_id": None, "parent_id": None,
                    "created_at": _now(), "updated_at": _now(),
                }
            ],
            users=[_user_as_payload(admin_user)],
        )
        resp = _do_import(client, payload, admin_token)
        assert resp.status_code == 200

        export_resp = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        exported = export_resp.json()
        device = next(d for d in exported["devices"] if d["id"] == device_id)
        assert device["status"] == "Maintenance"

    def test_round_trip_preserves_networks_and_memberships(
        self,
        client: TestClient,
        admin_token: str,
        admin_user: "User",
    ) -> None:
        # Reset to a known baseline so this round-trip snapshot is fully specified
        # and independent from prior tests in the same worker process.
        reset_resp = _do_import(
            client,
            _valid_payload(users=[_user_as_payload(admin_user)]),
            admin_token,
        )
        assert reset_resp.status_code == 200

        headers = {"Authorization": f"Bearer {admin_token}"}
        device_resp = client.post(
            "/api/devices/",
            json={"name": "rt-net-device", "type": "Server"},
            headers=headers,
        )
        assert device_resp.status_code == 201
        device_id = device_resp.json()["id"]

        network_resp = client.post(
            "/api/networks/",
            json={
                "name": "RT Management",
                "vlan_id": 55,
                "cidr": "10.55.0.0/24",
                "gateway": "10.55.0.1",
                "description": "Round trip",
                "color": "#3b82f6",
            },
            headers=headers,
        )
        assert network_resp.status_code == 201
        network_id = network_resp.json()["id"]

        attach_resp = client.post(
            f"/api/devices/{device_id}/networks",
            json={"network_id": network_id, "ip_address": "10.55.0.20"},
            headers=headers,
        )
        assert attach_resp.status_code == 201

        export_1 = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        assert any(row["id"] == network_id for row in export_1["networks"])
        assert any(
            row["device_id"] == device_id
            and row["network_id"] == network_id
            and row["ip_address"] == "10.55.0.20"
            for row in export_1["device_networks"]
        )

        from src.api.middleware.rate_limit import limiter

        if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
            limiter._storage.reset()

        import_resp = _do_import(client, export_1, admin_token)
        assert import_resp.status_code == 200

        export_2 = client.get(
            "/api/export",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()

        networks_1 = {
            (
                row["id"],
                row["name"],
                row.get("vlan_id"),
                row["cidr"],
                row.get("gateway"),
                row.get("description"),
                row["color"],
            )
            for row in export_1["networks"]
        }
        networks_2 = {
            (
                row["id"],
                row["name"],
                row.get("vlan_id"),
                row["cidr"],
                row.get("gateway"),
                row.get("description"),
                row["color"],
            )
            for row in export_2["networks"]
        }
        memberships_1 = {
            (row["device_id"], row["network_id"], row["ip_address"])
            for row in export_1["device_networks"]
        }
        memberships_2 = {
            (row["device_id"], row["network_id"], row["ip_address"])
            for row in export_2["device_networks"]
        }

        assert networks_1 == networks_2
        assert memberships_1 == memberships_2
