"""Integration tests for HT-075 ghost restore and reconciliation APIs."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt({"sub": str(user.id), "role": role.value, "version": user.token_version})
    return user, token


def _create_workspace(client: TestClient, token: str, name: str = "WS") -> dict[str, object]:
    response = client.post(
        "/api/workspaces/",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_topology(client: TestClient, token: str, workspace_id: str, name: str) -> dict[str, object]:
    response = client.post(
        f"/api/workspaces/{workspace_id}/topologies/",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_device(client: TestClient, token: str, name: str, device_type: str = "Server") -> dict[str, object]:
    response = client.post(
        "/api/devices/",
        json={"name": name, "type": device_type},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def _single_device_canvas(device_id: str, name: str, device_type: str) -> dict[str, object]:
    return {
        "elements": {
            "nodes": [
                {
                    "data": {
                        "id": device_id,
                        "label": name,
                        "raw_name": name,
                        "device_type": device_type,
                        "raw_device_type": device_type,
                        "status": "Active",
                    },
                    "position": {"x": 120, "y": 180},
                }
            ],
            "edges": [],
        },
        "zoom": 1,
        "pan": {"x": 0, "y": 0},
        "collapsedNodes": [],
    }


def _restore_after_device_deletion(
    client: TestClient,
    token: str,
    topology_id: str,
    deleted_device_id: str,
) -> dict[str, object]:
    history = client.get(
        f"/api/topologies/{topology_id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    history_items = history.json()["items"]
    target_entry_id = history_items[-1]["id"]

    restore = client.post(
        f"/api/topologies/{topology_id}/history/{target_entry_id}/restore",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert restore.status_code == 200

    # Device deletion remains authoritative for inventory.
    deleted_read = client.get(
        f"/api/devices/{deleted_device_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted_read.status_code == 404

    return restore.json()


class TestTopologyGhostRestore:
    def test_restore_preserves_deleted_device_as_ghost_without_inventory_resurrection(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token, "WS Ghost Restore")
        topology = _create_topology(client, token, str(workspace["id"]), "Topo Ghost Restore")

        historical_device = _create_device(client, token, "historical-device", "Router")
        historical_device_id = str(historical_device["id"])

        save = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "before-delete",
                "cytoscape_json": _single_device_canvas(
                    device_id=historical_device_id,
                    name="historical-device",
                    device_type="Router",
                ),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save.status_code == 200

        delete = client.delete(
            f"/api/devices/{historical_device_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete.status_code == 204

        restored = _restore_after_device_deletion(
            client,
            token,
            str(topology["id"]),
            historical_device_id,
        )

        nodes = restored["cytoscape_json"]["elements"]["nodes"]
        ghost_node = next(node for node in nodes if node["data"]["id"] == historical_device_id)
        ghost_data = ghost_node["data"]

        assert ghost_data["ghost"] is True
        assert ghost_data["ghost_reason"] == "deleted_from_inventory"
        assert ghost_data["ghost_status"] == "Deleted from inventory"
        assert ghost_data["ghost_original_name"] == "historical-device"
        assert ghost_data["ghost_original_type"] == "Router"
        assert "Deleted from inventory" in ghost_data["label"]

        restore_summary = restored["cytoscape_json"]["restore_summary"]
        assert restore_summary["ghost_count"] == 1
        assert historical_device_id in restore_summary["ghost_device_ids"]
        assert "preserved as ghost placeholders" in restore_summary["message"]
        assert restore_summary["ghost_recovery"]["can_reconcile"] is True
        assert set(restore_summary["ghost_recovery"]["allowed_actions"]) == {
            "recreate_as_new_device",
            "map_to_existing_device",
        }

    def test_reader_editor_state_keeps_ghosts_visible_but_hides_recovery_actions(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        user, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token, "WS Ghost Reader")
        topology = _create_topology(client, token, str(workspace["id"]), "Topo Ghost Reader")

        historical_device = _create_device(client, token, "reader-ghost", "NAS")
        historical_device_id = str(historical_device["id"])
        save = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "reader-before-delete",
                "cytoscape_json": _single_device_canvas(
                    device_id=historical_device_id,
                    name="reader-ghost",
                    device_type="NAS",
                ),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save.status_code == 200

        delete = client.delete(
            f"/api/devices/{historical_device_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete.status_code == 204

        _ = _restore_after_device_deletion(
            client,
            token,
            str(topology["id"]),
            historical_device_id,
        )

        # Downgrade owner role to Reader while preserving topology ownership.
        user.role = Role.Reader
        session.add(user)
        session.commit()
        session.refresh(user)

        reader_token = create_jwt(
            {
                "sub": str(user.id),
                "role": Role.Reader.value,
                "version": user.token_version,
            }
        )

        editor_state = client.get(
            f"/api/topologies/{topology['id']}/editor-state",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert editor_state.status_code == 200

        payload = editor_state.json()
        nodes = payload["cytoscape_json"]["elements"]["nodes"]
        ghost_node = next(node for node in nodes if node["data"]["id"] == historical_device_id)
        assert ghost_node["data"]["ghost"] is True

        restore_summary = payload["cytoscape_json"]["restore_summary"]
        assert restore_summary["ghost_count"] == 1
        assert restore_summary["ghost_recovery"]["can_reconcile"] is False
        assert restore_summary["ghost_recovery"]["allowed_actions"] == []

        blocked_recreate = client.post(
            f"/api/topologies/{topology['id']}/ghosts/{historical_device_id}/recreate",
            json={},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        blocked_map = client.post(
            f"/api/topologies/{topology['id']}/ghosts/{historical_device_id}/map",
            json={"live_device_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert blocked_recreate.status_code == 403
        assert blocked_map.status_code == 403

    def test_recreate_ghost_as_new_device_replaces_placeholder(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token, "WS Ghost Recreate")
        topology = _create_topology(client, token, str(workspace["id"]), "Topo Ghost Recreate")

        historical_device = _create_device(client, token, "recreate-ghost", "Server")
        historical_device_id = str(historical_device["id"])

        save = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "recreate-before-delete",
                "cytoscape_json": _single_device_canvas(
                    device_id=historical_device_id,
                    name="recreate-ghost",
                    device_type="Server",
                ),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save.status_code == 200

        delete = client.delete(
            f"/api/devices/{historical_device_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete.status_code == 204

        _ = _restore_after_device_deletion(
            client,
            token,
            str(topology["id"]),
            historical_device_id,
        )

        recreated = client.post(
            f"/api/topologies/{topology['id']}/ghosts/{historical_device_id}/recreate",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert recreated.status_code == 200

        payload = recreated.json()
        nodes = payload["cytoscape_json"]["elements"]["nodes"]
        assert all(node["data"].get("ghost") is not True for node in nodes)
        assert all(node["data"]["id"] != historical_device_id for node in nodes)

        replacement_ids = [node["data"]["id"] for node in nodes if node["data"]["id"] != historical_device_id]
        assert len(replacement_ids) == 1

        recreated_device = client.get(
            f"/api/devices/{replacement_ids[0]}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert recreated_device.status_code == 200
        assert recreated_device.json()["name"] == "recreate-ghost"
        assert recreated_device.json()["status"] == "Planned"

    def test_map_ghost_to_existing_device_replaces_placeholder_without_new_inventory_row(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token, "WS Ghost Map")
        topology = _create_topology(client, token, str(workspace["id"]), "Topo Ghost Map")

        historical_device = _create_device(client, token, "map-ghost-source", "Switch")
        historical_device_id = str(historical_device["id"])
        target_device = _create_device(client, token, "map-ghost-target", "Switch")
        target_device_id = str(target_device["id"])

        save = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "map-before-delete",
                "cytoscape_json": _single_device_canvas(
                    device_id=historical_device_id,
                    name="map-ghost-source",
                    device_type="Switch",
                ),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save.status_code == 200

        delete = client.delete(
            f"/api/devices/{historical_device_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete.status_code == 204

        _ = _restore_after_device_deletion(
            client,
            token,
            str(topology["id"]),
            historical_device_id,
        )

        before_devices = client.get(
            "/api/devices/?page=1&limit=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert before_devices.status_code == 200
        before_total = before_devices.json()["total"]

        mapped = client.post(
            f"/api/topologies/{topology['id']}/ghosts/{historical_device_id}/map",
            json={"live_device_id": target_device_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert mapped.status_code == 200

        payload = mapped.json()
        nodes = payload["cytoscape_json"]["elements"]["nodes"]
        assert all(node["data"].get("ghost") is not True for node in nodes)
        assert any(node["data"]["id"] == target_device_id for node in nodes)
        assert all(node["data"]["id"] != historical_device_id for node in nodes)

        after_devices = client.get(
            "/api/devices/?page=1&limit=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert after_devices.status_code == 200
        assert after_devices.json()["total"] == before_total
