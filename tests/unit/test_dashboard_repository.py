"""Unit tests for dashboard repository and service HT-082 follow-up behavior."""
import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.topology_history_entry import TopologyHistoryEntry
from src.models.types import DeviceStatus, DeviceType, Role
from src.models.user import User
from src.models.workspace import Workspace
from src.repositories import dashboard_repository
from src.repositories import dashboard_device_scope_support
from src.repositories import device_layout_repository_support
from src.repositories import dashboard_repository_support
from src.services import dashboard_service


def _create_user(session: Session) -> User:
    user = User(
        username=f"dashboard_repo_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@dashboard-repo.local",
        password_hash="hash",
        role=Role.Contributor,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_workspace(session: Session, owner_id: uuid.UUID, name: str) -> Workspace:
    workspace = Workspace(name=name, owner_id=owner_id)
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def _create_topology(session: Session, workspace_id: uuid.UUID, name: str) -> Topology:
    topology = Topology(name=name, workspace_id=workspace_id, tags=[])
    session.add(topology)
    session.commit()
    session.refresh(topology)
    return topology


def _create_device(
    session: Session,
    owner_id: uuid.UUID,
    name: str,
    power_watts: int,
    status: DeviceStatus = DeviceStatus.Active,
) -> Device:
    device = Device(
        name=name,
        type=DeviceType.Server,
        status=status,
        power_watts=power_watts,
        owner_id=owner_id,
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def _cytoscape_json(*device_ids: uuid.UUID) -> dict[str, object]:
    return {
        "elements": {
            "nodes": [
                {
                    "data": {
                        "id": f"node-{index}",
                        "device_id": str(device_id),
                    }
                }
                for index, device_id in enumerate(device_ids, start=1)
            ],
            "edges": [],
        }
    }


def _create_diagram(
    session: Session,
    topology_id: uuid.UUID,
    name: str,
    *device_ids: uuid.UUID,
) -> DiagramLayout:
    diagram = DiagramLayout(
        name=name,
        topology_id=topology_id,
        cytoscape_json=_cytoscape_json(*device_ids),
    )
    session.add(diagram)
    session.commit()
    session.refresh(diagram)
    return diagram


def _create_history_entry(
    session: Session,
    topology_id: uuid.UUID,
    diagram_id: uuid.UUID,
    snapshot_name: str,
) -> TopologyHistoryEntry:
    entry = TopologyHistoryEntry(
        topology_id=topology_id,
        diagram_id=diagram_id,
        snapshot_name=snapshot_name,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def _recent_activity_route(summary, title: str) -> str | None:
    for item in summary.recent_activity:
        if item.title == title:
            return item.route
    return None


def test_extract_device_ids_flat_elements_ignore_edge_ids() -> None:
    node_id = uuid.uuid4()
    edge_id = uuid.uuid4()
    payload = {
        "elements": [
            {"data": {"id": str(node_id)}},
            {
                "data": {
                    "id": str(edge_id),
                    "source": str(node_id),
                    "target": str(uuid.uuid4()),
                }
            },
        ]
    }

    assert dashboard_repository_support._extract_device_ids(payload) == {node_id}


def test_dashboard_repository_all_workspaces_include_unplaced_devices_but_workspace_scope_uses_current_membership(
    session: Session,
) -> None:
    owner = _create_user(session)
    workspace = _create_workspace(session, owner.id, "Repo Scope WS")
    topology = _create_topology(session, workspace.id, "Repo Scope Topology")
    placed_device = _create_device(session, owner.id, "Placed Node", 120)
    removed_device = _create_device(session, owner.id, "Removed Node", 70)
    orphan_device = _create_device(
        session,
        owner.id,
        "Orphan Node",
        40,
        status=DeviceStatus.Offline,
    )

    previous_diagram = _create_diagram(
        session,
        topology.id,
        "Previous Snapshot",
        removed_device.id,
    )
    current_diagram = _create_diagram(
        session,
        topology.id,
        "Current Snapshot",
        placed_device.id,
    )
    _create_history_entry(session, topology.id, previous_diagram.id, "Previous Snapshot")
    _create_history_entry(session, topology.id, current_diagram.id, "Current Snapshot")

    topology.current_diagram_id = current_diagram.id
    session.add(topology)
    session.commit()

    all_summary = dashboard_repository.get_summary(session, owner_id=owner.id)
    workspace_summary = dashboard_repository.get_summary(
        session,
        selected_workspace_id=workspace.id,
        owner_id=owner.id,
    )

    assert all_summary.devices == 3
    assert all_summary.offline_devices == 1
    assert all_summary.recent_edits == 5
    assert all_summary.power.total_watts == 230
    assert _recent_activity_route(all_summary, "Placed Node") == (
        f"/topology?workspace_id={workspace.id}&topology_id={topology.id}&device_id={placed_device.id}"
    )
    assert _recent_activity_route(all_summary, "Removed Node") == (
        f"/inventory/edit/{removed_device.id}"
    )
    assert _recent_activity_route(all_summary, "Orphan Node") == (
        f"/inventory/edit/{orphan_device.id}"
    )

    assert workspace_summary.devices == 1
    assert workspace_summary.offline_devices == 0
    assert workspace_summary.recent_edits == 3
    assert workspace_summary.power.total_watts == 120
    assert _recent_activity_route(workspace_summary, "Placed Node") == (
        f"/topology?workspace_id={workspace.id}&topology_id={topology.id}&device_id={placed_device.id}"
    )
    assert _recent_activity_route(workspace_summary, "Removed Node") is None
    assert _recent_activity_route(workspace_summary, "Orphan Node") is None


def test_dashboard_service_invalid_workspace_raises_404(session: Session) -> None:
    owner = _create_user(session)

    with pytest.raises(HTTPException) as exc_info:
        dashboard_service.get_summary(owner.id, session, workspace_id=uuid.uuid4())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Workspace not found"


def test_dashboard_service_foreign_workspace_raises_404(session: Session) -> None:
    owner = _create_user(session)
    foreign_owner = _create_user(session)
    foreign_workspace = _create_workspace(session, foreign_owner.id, "Foreign Workspace")

    with pytest.raises(HTTPException) as exc_info:
        dashboard_service.get_summary(owner.id, session, workspace_id=foreign_workspace.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Workspace not found"


def test_dashboard_repository_recent_device_routes_stay_scoped_without_device_owner_column(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _create_user(session)
    workspace = _create_workspace(session, owner.id, "Legacy Schema WS")
    topology = _create_topology(session, workspace.id, "Legacy Schema Topology")
    placed_device = _create_device(session, owner.id, "Legacy Schema Device", 90)
    current_diagram = _create_diagram(
        session,
        topology.id,
        "Current Snapshot",
        placed_device.id,
    )
    _create_history_entry(session, topology.id, current_diagram.id, "Current Snapshot")

    topology.current_diagram_id = current_diagram.id
    session.add(topology)
    session.commit()

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

    summary = dashboard_repository.get_summary(
        session,
        selected_workspace_id=workspace.id,
        owner_id=owner.id,
    )

    assert summary.devices == 1
    assert summary.power.total_watts == 90
    assert {item.title for item in summary.recent_activity} == {
        "Legacy Schema Device",
        "Legacy Schema Topology",
    }
    assert _recent_activity_route(summary, "Legacy Schema Device") == (
        f"/topology?workspace_id={workspace.id}&topology_id={topology.id}&device_id={placed_device.id}"
    )


def test_dashboard_repository_legacy_all_scope_fails_closed_to_owned_visible_devices(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _create_user(session)
    foreign_owner = _create_user(session)

    workspace = _create_workspace(session, owner.id, "Legacy Repo WS")
    topology = _create_topology(session, workspace.id, "Legacy Repo Topology")
    placed_device = _create_device(session, owner.id, "Legacy Repo Device", 55)
    current_diagram = _create_diagram(
        session,
        topology.id,
        "Legacy Repo Snapshot",
        placed_device.id,
    )
    _create_history_entry(session, topology.id, current_diagram.id, "Legacy Repo Snapshot")

    foreign_workspace = _create_workspace(session, foreign_owner.id, "Foreign Repo WS")
    foreign_topology = _create_topology(session, foreign_workspace.id, "Foreign Repo Topology")
    foreign_device = _create_device(
        session,
        foreign_owner.id,
        "Foreign Repo Device",
        90,
        status=DeviceStatus.Offline,
    )
    foreign_diagram = _create_diagram(
        session,
        foreign_topology.id,
        "Foreign Repo Snapshot",
        foreign_device.id,
    )
    _create_history_entry(
        session,
        foreign_topology.id,
        foreign_diagram.id,
        "Foreign Repo Snapshot",
    )

    topology.current_diagram_id = current_diagram.id
    foreign_topology.current_diagram_id = foreign_diagram.id
    session.add(topology)
    session.add(foreign_topology)
    session.commit()

    monkeypatch.setattr(
        dashboard_device_scope_support,
        "_device_owner_scope_available",
        lambda _session: False,
    )

    summary = dashboard_repository.get_summary(session, owner_id=owner.id)

    assert summary.devices == 1
    assert summary.workspaces == 1
    assert summary.topologies == 1
    assert summary.offline_devices == 0
    assert summary.recent_edits == 2
    assert summary.power.total_watts == 55
    assert {item.title for item in summary.recent_activity} == {
        "Legacy Repo Device",
        "Legacy Repo Topology",
    }
    assert _recent_activity_route(summary, "Legacy Repo Device") == (
        f"/topology?workspace_id={workspace.id}&topology_id={topology.id}&device_id={placed_device.id}"
    )
    assert _recent_activity_route(summary, "Foreign Repo Device") is None


def test_dashboard_repository_legacy_all_scope_excludes_foreign_device_ids_in_same_owned_workspace(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _create_user(session)
    foreign_owner = _create_user(session)

    workspace = _create_workspace(session, owner.id, "Mixed Legacy Repo WS")
    topology = _create_topology(session, workspace.id, "Mixed Legacy Repo Topology")
    owned_device = _create_device(session, owner.id, "Owned Repo Device", 55)
    foreign_device = _create_device(
        session,
        foreign_owner.id,
        "Foreign Same Workspace Device",
        90,
        status=DeviceStatus.Offline,
    )
    current_diagram = _create_diagram(
        session,
        topology.id,
        "Mixed Legacy Repo Snapshot",
        owned_device.id,
        foreign_device.id,
    )
    _create_history_entry(
        session,
        topology.id,
        current_diagram.id,
        "Mixed Legacy Repo Snapshot",
    )

    topology.current_diagram_id = current_diagram.id
    session.add(topology)
    session.commit()

    monkeypatch.setattr(
        dashboard_device_scope_support,
        "_device_owner_scope_available",
        lambda _session: False,
    )

    summary = dashboard_repository.get_summary(session, owner_id=owner.id)

    assert summary.devices == 1
    assert summary.workspaces == 1
    assert summary.topologies == 1
    assert summary.offline_devices == 0
    assert summary.recent_edits == 2
    assert summary.power.total_watts == 55
    assert {item.title for item in summary.recent_activity} == {
        "Owned Repo Device",
        "Mixed Legacy Repo Topology",
    }
    assert _recent_activity_route(summary, "Owned Repo Device") == (
        f"/topology?workspace_id={workspace.id}&topology_id={topology.id}&device_id={owned_device.id}"
    )
    assert _recent_activity_route(summary, "Foreign Same Workspace Device") is None