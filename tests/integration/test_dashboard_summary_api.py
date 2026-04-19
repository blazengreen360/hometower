"""Integration tests for the HT-082 dashboard summary endpoint."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import DeviceStatus, Role
from src.models.user import User
from src.repositories import dashboard_device_scope_support
from src.repositories import device_layout_repository_support
from src.repositories import dashboard_repository_support
from src.utils.auth import create_jwt, hash_password


def _make_user(session: Session, role: Role = Role.Contributor) -> tuple[User, str]:
    user = User(
        username=f"dashboard_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@dashboard.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt({"sub": str(user.id), "role": role.value, "version": user.token_version})
    return user, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_workspace(
    client: TestClient,
    token: str,
    name: str,
) -> dict[str, object]:
    response = client.post(
        "/api/workspaces/",
        json={"name": name},
        headers=_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def _create_topology(
    client: TestClient,
    token: str,
    workspace_id: str,
    name: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/workspaces/{workspace_id}/topologies/",
        json={"name": name},
        headers=_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def _create_device(
    client: TestClient,
    token: str,
    name: str,
    power_watts: int,
    status: str = DeviceStatus.Active.value,
) -> dict[str, object]:
    response = client.post(
        "/api/devices/",
        json={
            "name": name,
            "type": "Server",
            "status": status,
            "power_watts": power_watts,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def _save_topology_version(
    client: TestClient,
    token: str,
    topology_id: str,
    snapshot_name: str,
    device_ids: list[str],
) -> dict[str, object]:
    nodes = [
        {
            "data": {
                "id": f"node-{index}",
                "device_id": device_id,
            },
            "position": {"x": index * 120, "y": 100},
        }
        for index, device_id in enumerate(device_ids, start=1)
    ]
    response = client.post(
        f"/api/topologies/{topology_id}/save-version",
        json={
            "snapshot_name": snapshot_name,
            "cytoscape_json": {
                "elements": {"nodes": nodes, "edges": []},
                "zoom": 1,
                "pan": {"x": 0, "y": 0},
                "collapsedNodes": [],
            },
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    return response.json()


def _breakdown_count(items: list[dict[str, object]], key: str) -> int:
    for item in items:
        if item["key"] == key:
            return int(item["count"])
    return 0


def _breakdown_route(items: list[dict[str, object]], key: str) -> str | None:
    for item in items:
        if item["key"] == key:
            route = item["route"]
            return str(route) if route is not None else None
    return None


def _recent_activity_route(items: list[dict[str, object]], title: str) -> str | None:
    for item in items:
        if item["title"] == title:
            route = item["route"]
            return str(route) if route is not None else None
    return None


def test_dashboard_summary_reader_access_returns_aggregate_payload(
    client: TestClient,
    session: Session,
) -> None:
    user, contributor_token = _make_user(session, Role.Contributor)
    baseline_response = client.get(
        "/api/dashboard/summary",
        headers=_headers(contributor_token),
    )
    assert baseline_response.status_code == 200
    baseline = baseline_response.json()
    workspace = _create_workspace(client, contributor_token, "Lab Alpha")
    topology = _create_topology(client, contributor_token, str(workspace["id"]), "Rack A")
    device = _create_device(client, contributor_token, "Alpha Node", 90)
    offline_device = _create_device(
        client,
        contributor_token,
        "Offline Node",
        40,
        status=DeviceStatus.Offline.value,
    )
    _save_topology_version(
        client,
        contributor_token,
        str(topology["id"]),
        "Initial Snapshot",
        [str(device["id"]), str(offline_device["id"])],
    )

    user.role = Role.Reader
    session.add(user)
    session.commit()
    session.refresh(user)
    reader_token = create_jwt(
        {"sub": str(user.id), "role": Role.Reader.value, "version": user.token_version}
    )

    response = client.get("/api/dashboard/summary", headers=_headers(reader_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["devices"] == baseline["devices"] + 2
    assert payload["workspaces"] == baseline["workspaces"] + 1
    assert payload["topologies"] == baseline["topologies"] + 1
    assert payload["offline_devices"] == baseline["offline_devices"] + 1
    assert payload["power"]["selected_workspace_name"] == "All Workspaces"
    assert payload["power"]["selected_workspace_id"] is None
    assert payload["power"]["workspace_options"][0] == {"id": None, "name": "All Workspaces"}
    assert payload["power"]["workspace_options"][1]["id"] == str(workspace["id"])
    assert payload["power"]["workspace_options"][1]["name"] == "Lab Alpha"
    assert payload["power"]["total_watts"] == baseline["power"]["total_watts"] + 130
    assert any(
        item["key"] == DeviceStatus.Offline.value and item["route"] == "/inventory?status=Offline"
        for item in payload["inventory_breakdown"]["status_counts"]
    )
    assert isinstance(payload["recent_activity"], list)


def test_dashboard_summary_workspace_filter_changes_power_totals(
    client: TestClient,
    session: Session,
) -> None:
    _, contributor_token = _make_user(session, Role.Contributor)
    baseline_response = client.get(
        "/api/dashboard/summary",
        headers=_headers(contributor_token),
    )
    assert baseline_response.status_code == 200
    baseline = baseline_response.json()
    workspace_one = _create_workspace(client, contributor_token, "Lab One")
    workspace_two = _create_workspace(client, contributor_token, "Lab Two")
    topology_one = _create_topology(client, contributor_token, str(workspace_one["id"]), "Topo One")
    topology_two = _create_topology(client, contributor_token, str(workspace_two["id"]), "Topo Two")
    device_one = _create_device(client, contributor_token, "Node One", 120)
    device_two = _create_device(client, contributor_token, "Node Two", 45)

    _save_topology_version(
        client,
        contributor_token,
        str(topology_one["id"]),
        "Snapshot One",
        [str(device_one["id"])],
    )
    _save_topology_version(
        client,
        contributor_token,
        str(topology_two["id"]),
        "Snapshot Two",
        [str(device_two["id"])],
    )

    all_response = client.get(
        "/api/dashboard/summary",
        headers=_headers(contributor_token),
    )
    filtered_response = client.get(
        f"/api/dashboard/summary?workspace_id={workspace_two['id']}",
        headers=_headers(contributor_token),
    )

    assert all_response.status_code == 200
    assert filtered_response.status_code == 200

    all_payload = all_response.json()
    filtered_payload = filtered_response.json()

    assert all_payload["devices"] == baseline["devices"] + 2
    assert all_payload["topologies"] == baseline["topologies"] + 2
    assert all_payload["recent_edits"] == baseline["recent_edits"] + 4
    assert all_payload["power"]["selected_workspace_name"] == "All Workspaces"
    assert all_payload["power"]["total_watts"] == baseline["power"]["total_watts"] + 165
    assert filtered_payload["devices"] == 1
    assert filtered_payload["power"]["selected_workspace_id"] == str(workspace_two["id"])
    assert filtered_payload["power"]["selected_workspace_name"] == "Lab Two"
    assert filtered_payload["power"]["total_watts"] == 45
    assert filtered_payload["topologies"] == 1
    assert filtered_payload["recent_edits"] == 2
    assert filtered_payload["inventory_breakdown"]["status_counts"] == [
        {
            "key": DeviceStatus.Active.value,
            "count": 1,
            "route": f"/inventory?workspace_id={workspace_two['id']}&status=Active",
        }
    ]
    assert filtered_payload["inventory_breakdown"]["type_counts"] == [
        {
            "key": device_two["type"],
            "count": 1,
            "route": f"/inventory?workspace_id={workspace_two['id']}&type={device_two['type']}",
        }
    ]
    assert {item["title"] for item in filtered_payload["recent_activity"]} == {
        "Node Two",
        "Topo Two",
    }
    assert _recent_activity_route(
        filtered_payload["recent_activity"],
        "Node Two",
    ) == (
        f"/topology?workspace_id={workspace_two['id']}&topology_id={topology_two['id']}&device_id={device_two['id']}"
    )


def test_dashboard_summary_recent_activity_includes_normalized_device_and_topology_items(
    client: TestClient,
    session: Session,
) -> None:
    _, contributor_token = _make_user(session, Role.Contributor)
    workspace = _create_workspace(client, contributor_token, "Recent WS")
    topology = _create_topology(client, contributor_token, str(workspace["id"]), "Recent Topology")
    device = _create_device(client, contributor_token, "Recent Device", 75)
    _save_topology_version(
        client,
        contributor_token,
        str(topology["id"]),
        "Recent Version",
        [str(device["id"])],
    )

    response = client.get(
        "/api/dashboard/summary",
        headers=_headers(contributor_token),
    )

    assert response.status_code == 200
    payload = response.json()
    activity = payload["recent_activity"]

    device_item = next(item for item in activity if item["kind"].startswith("device_"))
    topology_item = next(item for item in activity if item["kind"].startswith("topology_"))

    assert device_item["kind"] == "device_created"
    assert device_item["title"] == "Recent Device"
    assert device_item["subtitle"] == "Device added"
    assert device_item["route"] == (
        f"/topology?workspace_id={workspace['id']}&topology_id={topology['id']}&device_id={device['id']}"
    )

    assert topology_item["kind"] == "topology_save_version"
    assert topology_item["title"] == "Recent Topology"
    assert topology_item["subtitle"] == "Recent WS: Recent Version"
    assert topology_item["route"] == (
        f"/topology?workspace_id={workspace['id']}&topology_id={topology['id']}"
    )


def test_dashboard_summary_all_workspaces_includes_unplaced_devices_but_workspace_scope_uses_current_published_membership(
    client: TestClient,
    session: Session,
) -> None:
    _, contributor_token = _make_user(session, Role.Contributor)
    baseline_response = client.get(
        "/api/dashboard/summary",
        headers=_headers(contributor_token),
    )
    assert baseline_response.status_code == 200
    baseline = baseline_response.json()
    workspace = _create_workspace(client, contributor_token, "Aggregate WS")
    topology = _create_topology(client, contributor_token, str(workspace["id"]), "Aggregate Topology")
    placed_device = _create_device(client, contributor_token, "Placed Node", 120)
    removed_device = _create_device(client, contributor_token, "Removed Node", 70)
    orphan_device = _create_device(
        client,
        contributor_token,
        "Orphan Node",
        40,
        status=DeviceStatus.Offline.value,
    )
    _save_topology_version(
        client,
        contributor_token,
        str(topology["id"]),
        "Previous Snapshot",
        [str(removed_device["id"])],
    )
    _save_topology_version(
        client,
        contributor_token,
        str(topology["id"]),
        "Placed Snapshot",
        [str(placed_device["id"])],
    )

    all_response = client.get("/api/dashboard/summary", headers=_headers(contributor_token))
    filtered_response = client.get(
        f"/api/dashboard/summary?workspace_id={workspace['id']}",
        headers=_headers(contributor_token),
    )

    assert all_response.status_code == 200
    assert filtered_response.status_code == 200

    all_payload = all_response.json()
    filtered_payload = filtered_response.json()

    baseline_status_counts = baseline["inventory_breakdown"]["status_counts"]
    baseline_type_counts = baseline["inventory_breakdown"]["type_counts"]

    assert all_payload["devices"] == baseline["devices"] + 3
    assert all_payload["offline_devices"] == baseline["offline_devices"] + 1
    assert all_payload["recent_edits"] == baseline["recent_edits"] + 5
    assert all_payload["power"]["total_watts"] == baseline["power"]["total_watts"] + 230
    assert (
        _breakdown_count(
            all_payload["inventory_breakdown"]["status_counts"],
            DeviceStatus.Active.value,
        )
        == _breakdown_count(baseline_status_counts, DeviceStatus.Active.value) + 2
    )
    assert (
        _breakdown_count(
            all_payload["inventory_breakdown"]["status_counts"],
            DeviceStatus.Offline.value,
        )
        == _breakdown_count(baseline_status_counts, DeviceStatus.Offline.value) + 1
    )
    assert (
        _breakdown_count(
            all_payload["inventory_breakdown"]["type_counts"],
            str(placed_device["type"]),
        )
        == _breakdown_count(baseline_type_counts, str(placed_device["type"])) + 3
    )
    assert (
        _breakdown_route(
            all_payload["inventory_breakdown"]["type_counts"],
            str(placed_device["type"]),
        )
        == f"/inventory?type={placed_device['type']}"
    )
    assert _recent_activity_route(all_payload["recent_activity"], "Placed Node") == (
        f"/topology?workspace_id={workspace['id']}&topology_id={topology['id']}&device_id={placed_device['id']}"
    )
    assert _recent_activity_route(all_payload["recent_activity"], "Removed Node") == (
        f"/inventory/edit/{removed_device['id']}"
    )
    assert _recent_activity_route(all_payload["recent_activity"], "Orphan Node") == (
        f"/inventory/edit/{orphan_device['id']}"
    )

    assert filtered_payload["devices"] == 1
    assert filtered_payload["offline_devices"] == 0
    assert filtered_payload["recent_edits"] == 3
    assert filtered_payload["power"]["total_watts"] == 120
    assert _recent_activity_route(filtered_payload["recent_activity"], "Placed Node") == (
        f"/topology?workspace_id={workspace['id']}&topology_id={topology['id']}&device_id={placed_device['id']}"
    )
    assert all(item["title"] != "Removed Node" for item in filtered_payload["recent_activity"])
    assert all(item["title"] != "Orphan Node" for item in filtered_payload["recent_activity"])


def test_dashboard_summary_owner_all_scope_excludes_cross_owner_orphan_devices(
    client: TestClient,
    session: Session,
) -> None:
    _, owner_one_token = _make_user(session, Role.Contributor)
    _, owner_two_token = _make_user(session, Role.Contributor)
    baseline_response = client.get("/api/dashboard/summary", headers=_headers(owner_one_token))
    assert baseline_response.status_code == 200
    baseline = baseline_response.json()

    workspace_one = _create_workspace(client, owner_one_token, "Owner One")
    topology_one = _create_topology(client, owner_one_token, str(workspace_one["id"]), "Topo One")
    device_one = _create_device(client, owner_one_token, "Scoped Device", 55)
    hidden_orphan = _create_device(
        client,
        owner_two_token,
        "Hidden Orphan",
        90,
        status=DeviceStatus.Offline.value,
    )
    _save_topology_version(
        client,
        owner_one_token,
        str(topology_one["id"]),
        "Owner One Snapshot",
        [str(device_one["id"])],
    )

    response = client.get("/api/dashboard/summary", headers=_headers(owner_one_token))
    filtered_response = client.get(
        f"/api/dashboard/summary?workspace_id={workspace_one['id']}",
        headers=_headers(owner_one_token),
    )

    assert response.status_code == 200
    assert filtered_response.status_code == 200

    payload = response.json()
    filtered_payload = filtered_response.json()

    assert payload["devices"] == baseline["devices"] + 1
    assert payload["offline_devices"] == baseline["offline_devices"]
    assert payload["recent_edits"] == baseline["recent_edits"] + 2
    assert payload["power"]["total_watts"] == baseline["power"]["total_watts"] + 55
    assert _recent_activity_route(payload["recent_activity"], "Scoped Device") == (
        f"/topology?workspace_id={workspace_one['id']}&topology_id={topology_one['id']}&device_id={device_one['id']}"
    )
    assert any(
        item["title"] == "Hidden Orphan"
        and item["route"] == f"/inventory/edit/{hidden_orphan['id']}"
        for item in payload["recent_activity"]
    ) is False

    assert filtered_payload["devices"] == 1
    assert filtered_payload["offline_devices"] == 0
    assert filtered_payload["recent_edits"] == 2
    assert filtered_payload["power"]["total_watts"] == 55
    assert all(item["title"] != "Hidden Orphan" for item in filtered_payload["recent_activity"])


def test_dashboard_summary_all_scope_uses_visible_devices_but_keeps_workspace_filter(
    client: TestClient,
    session: Session,
) -> None:
    _, owner_one_token = _make_user(session, Role.Contributor)
    _, owner_two_token = _make_user(session, Role.Contributor)
    baseline_response = client.get("/api/dashboard/summary", headers=_headers(owner_one_token))
    assert baseline_response.status_code == 200
    baseline = baseline_response.json()

    workspace_one = _create_workspace(client, owner_one_token, "Owner One")
    topology_one = _create_topology(client, owner_one_token, str(workspace_one["id"]), "Topo One")
    device_one = _create_device(client, owner_one_token, "Scoped Device", 55)
    _save_topology_version(
        client,
        owner_one_token,
        str(topology_one["id"]),
        "Owner One Snapshot",
        [str(device_one["id"])],
    )

    workspace_two = _create_workspace(client, owner_two_token, "Owner Two")
    topology_two = _create_topology(client, owner_two_token, str(workspace_two["id"]), "Topo Two")
    device_two = _create_device(
        client,
        owner_two_token,
        "Leaked Device",
        90,
        status=DeviceStatus.Offline.value,
    )
    _save_topology_version(
        client,
        owner_two_token,
        str(topology_two["id"]),
        "Owner Two Snapshot",
        [str(device_two["id"])],
    )

    response = client.get("/api/dashboard/summary", headers=_headers(owner_one_token))
    filtered_response = client.get(
        f"/api/dashboard/summary?workspace_id={workspace_one['id']}",
        headers=_headers(owner_one_token),
    )

    assert response.status_code == 200
    assert filtered_response.status_code == 200

    payload = response.json()
    filtered_payload = filtered_response.json()

    baseline_status_counts = baseline["inventory_breakdown"]["status_counts"]

    assert payload["devices"] == baseline["devices"] + 1
    assert payload["workspaces"] == baseline["workspaces"] + 1
    assert payload["topologies"] == baseline["topologies"] + 1
    assert payload["offline_devices"] == baseline["offline_devices"]
    assert payload["recent_edits"] == baseline["recent_edits"] + 2
    assert payload["power"]["total_watts"] == baseline["power"]["total_watts"] + 55
    assert (
        _breakdown_count(
            payload["inventory_breakdown"]["status_counts"],
            DeviceStatus.Active.value,
        )
        == _breakdown_count(baseline_status_counts, DeviceStatus.Active.value) + 1
    )
    assert (
        _breakdown_count(
            payload["inventory_breakdown"]["status_counts"],
            DeviceStatus.Offline.value,
        )
        == _breakdown_count(baseline_status_counts, DeviceStatus.Offline.value)
    )
    activity_titles = {item["title"] for item in payload["recent_activity"]}
    assert activity_titles >= {
        "Scoped Device",
        "Topo One",
    }
    assert "Leaked Device" not in activity_titles

    assert filtered_payload["devices"] == 1
    assert filtered_payload["offline_devices"] == 0
    assert filtered_payload["recent_edits"] == 2
    assert filtered_payload["power"]["total_watts"] == 55
    assert {item["title"] for item in filtered_payload["recent_activity"]} == {
        "Scoped Device",
        "Topo One",
    }


def test_dashboard_summary_invalid_workspace_filter_returns_404(
    client: TestClient,
    session: Session,
) -> None:
    _, contributor_token = _make_user(session, Role.Contributor)

    response = client.get(
        f"/api/dashboard/summary?workspace_id={uuid.uuid4()}",
        headers=_headers(contributor_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}


def test_dashboard_summary_foreign_workspace_filter_returns_404(
    client: TestClient,
    session: Session,
) -> None:
    _, owner_one_token = _make_user(session, Role.Contributor)
    _, owner_two_token = _make_user(session, Role.Contributor)
    workspace = _create_workspace(client, owner_two_token, "Foreign Workspace")

    response = client.get(
        f"/api/dashboard/summary?workspace_id={workspace['id']}",
        headers=_headers(owner_one_token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found"}


def test_dashboard_summary_recent_device_route_stays_scoped_without_device_owner_column(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    _, contributor_token = _make_user(session, Role.Contributor)
    workspace = _create_workspace(client, contributor_token, "Legacy API WS")
    topology = _create_topology(client, contributor_token, str(workspace["id"]), "Legacy API Topology")
    device = _create_device(client, contributor_token, "Legacy API Device", 65)
    _save_topology_version(
        client,
        contributor_token,
        str(topology["id"]),
        "Legacy API Snapshot",
        [str(device["id"])],
    )

    class _LegacyDeviceInspector:
        def get_columns(self, _table_name: str) -> list[dict[str, str]]:
            return [{"name": "id"}]

    monkeypatch.setattr(
        dashboard_device_scope_support,
        "sa_inspect",
        lambda _bind: _LegacyDeviceInspector(),
    )
    monkeypatch.setattr(
        device_layout_repository_support,
        "sa_inspect",
        lambda _bind: _LegacyDeviceInspector(),
    )

    response = client.get(
        f"/api/dashboard/summary?workspace_id={workspace['id']}",
        headers=_headers(contributor_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["devices"] == 1
    assert payload["power"]["total_watts"] == 65
    assert {item["title"] for item in payload["recent_activity"]} == {
        "Legacy API Device",
        "Legacy API Topology",
    }
    assert _recent_activity_route(payload["recent_activity"], "Legacy API Device") == (
        f"/topology?workspace_id={workspace['id']}&topology_id={topology['id']}&device_id={device['id']}"
    )


def test_dashboard_summary_legacy_all_scope_fails_closed_to_owned_visible_devices(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    _, owner_one_token = _make_user(session, Role.Contributor)
    _, owner_two_token = _make_user(session, Role.Contributor)

    workspace_one = _create_workspace(client, owner_one_token, "Legacy Owner One")
    topology_one = _create_topology(
        client,
        owner_one_token,
        str(workspace_one["id"]),
        "Legacy Topo One",
    )
    device_one = _create_device(client, owner_one_token, "Legacy Scoped Device", 55)
    _save_topology_version(
        client,
        owner_one_token,
        str(topology_one["id"]),
        "Legacy Owner One Snapshot",
        [str(device_one["id"])],
    )

    workspace_two = _create_workspace(client, owner_two_token, "Legacy Owner Two")
    topology_two = _create_topology(
        client,
        owner_two_token,
        str(workspace_two["id"]),
        "Legacy Topo Two",
    )
    leaked_device = _create_device(
        client,
        owner_two_token,
        "Legacy Leaked Device",
        90,
        status=DeviceStatus.Offline.value,
    )
    _save_topology_version(
        client,
        owner_two_token,
        str(topology_two["id"]),
        "Legacy Owner Two Snapshot",
        [str(leaked_device["id"])],
    )

    monkeypatch.setattr(
        dashboard_device_scope_support,
        "_device_owner_scope_available",
        lambda _session: False,
    )

    response = client.get("/api/dashboard/summary", headers=_headers(owner_one_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["devices"] == 1
    assert payload["workspaces"] == 1
    assert payload["topologies"] == 1
    assert payload["offline_devices"] == 0
    assert payload["recent_edits"] == 2
    assert payload["power"]["total_watts"] == 55
    assert {item["title"] for item in payload["recent_activity"]} == {
        "Legacy Scoped Device",
        "Legacy Topo One",
    }
    assert _recent_activity_route(payload["recent_activity"], "Legacy Scoped Device") == (
        f"/topology?workspace_id={workspace_one['id']}&topology_id={topology_one['id']}&device_id={device_one['id']}"
    )
    assert all(item["title"] != "Legacy Leaked Device" for item in payload["recent_activity"])


def test_dashboard_summary_legacy_all_scope_excludes_foreign_same_workspace_devices(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    _, owner_one_token = _make_user(session, Role.Contributor)
    _, owner_two_token = _make_user(session, Role.Contributor)

    workspace = _create_workspace(client, owner_one_token, "Legacy Mixed Owner WS")
    topology = _create_topology(
        client,
        owner_one_token,
        str(workspace["id"]),
        "Legacy Mixed Owner Topology",
    )
    owned_device = _create_device(client, owner_one_token, "Legacy Mixed Owned Device", 55)
    leaked_device = _create_device(
        client,
        owner_two_token,
        "Legacy Mixed Foreign Device",
        90,
        status=DeviceStatus.Offline.value,
    )
    _save_topology_version(
        client,
        owner_one_token,
        str(topology["id"]),
        "Legacy Mixed Snapshot",
        [str(owned_device["id"]), str(leaked_device["id"])],
    )

    monkeypatch.setattr(
        dashboard_device_scope_support,
        "_device_owner_scope_available",
        lambda _session: False,
    )

    response = client.get("/api/dashboard/summary", headers=_headers(owner_one_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["devices"] == 1
    assert payload["workspaces"] == 1
    assert payload["topologies"] == 1
    assert payload["offline_devices"] == 0
    assert payload["recent_edits"] == 2
    assert payload["power"]["total_watts"] == 55
    assert {item["title"] for item in payload["recent_activity"]} == {
        "Legacy Mixed Owned Device",
        "Legacy Mixed Owner Topology",
    }
    assert _recent_activity_route(payload["recent_activity"], "Legacy Mixed Owned Device") == (
        f"/topology?workspace_id={workspace['id']}&topology_id={topology['id']}&device_id={owned_device['id']}"
    )
    assert all(item["title"] != "Legacy Mixed Foreign Device" for item in payload["recent_activity"])
