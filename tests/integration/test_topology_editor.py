"""Integration tests for HT-072 topology editor-state, history, and drafts endpoints."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from src.models.topology_personal_draft import TopologyPersonalDraft
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


def _empty_canvas() -> dict[str, object]:
    return {
        "elements": {
            "nodes": [],
            "edges": [],
        },
        "zoom": 1,
        "pan": {"x": 0, "y": 0},
        "collapsedNodes": [],
    }


def _canvas_with_inline_size(node_id: str, width: int, height: int) -> dict[str, object]:
    return {
        "elements": {
            "nodes": [
                {
                    "data": {"id": node_id},
                    "position": {"x": 180, "y": 140},
                    "style": {"width": width, "height": height},
                }
            ],
            "edges": [],
        },
        "zoom": 1,
        "pan": {"x": 0, "y": 0},
        "collapsedNodes": [],
    }


class TestTopologyEditorState:
    def test_editor_state_returns_empty_for_new_topology(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Empty")

        response = client.get(
            f"/api/topologies/{topology['id']}/editor-state",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "empty"
        assert payload["has_unsaved_changes"] is False
        assert payload["current_diagram_id"] is None
        assert payload["draft_version"] is None
        assert payload["cytoscape_json"]["elements"] == {"nodes": [], "edges": []}

    def test_personal_draft_is_preferred_for_editor_state(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Draft")

        save_payload = {
            "snapshot_name": "Base",
            "cytoscape_json": _empty_canvas(),
        }
        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json=save_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save_response.status_code == 200

        draft_payload = {
            "cytoscape_json": {
                "elements": {
                    "nodes": [{"data": {"id": "draft-1", "draft": True}}],
                    "edges": [],
                },
                "zoom": 1,
                "pan": {"x": 0, "y": 0},
                "collapsedNodes": [],
            }
        }
        draft_response = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json=draft_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert draft_response.status_code == 200
        assert draft_response.json()["has_unsaved_changes"] is True

        editor_state = client.get(
            f"/api/topologies/{topology['id']}/editor-state",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert editor_state.status_code == 200
        payload = editor_state.json()
        assert payload["source"] == "draft"
        assert payload["has_unsaved_changes"] is True
        assert payload["draft_version"] == 1
        nodes = payload["cytoscape_json"]["elements"]["nodes"]
        assert nodes[0]["data"]["id"] == "draft-1"

    def test_editor_state_draft_matching_saved_version_has_no_unsaved_changes(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Draft Match")

        base_canvas = {
            "elements": {
                "nodes": [{"data": {"id": "node-1"}, "position": {"x": 110, "y": 95}}],
                "edges": [],
            },
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }

        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Base", "cytoscape_json": base_canvas},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save_response.status_code == 200

        draft_response = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json={"cytoscape_json": base_canvas},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert draft_response.status_code == 200
        assert draft_response.json()["has_unsaved_changes"] is False

        editor_state = client.get(
            f"/api/topologies/{topology['id']}/editor-state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert editor_state.status_code == 200
        payload = editor_state.json()
        assert payload["source"] == "draft"
        assert payload["has_unsaved_changes"] is False

    def test_reader_editor_state_does_not_create_personal_draft_row(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        user, contributor_token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, contributor_token)
        topology = _create_topology(client, contributor_token, str(workspace["id"]), "Topology Reader View")

        # Downgrade the same owner to Reader to ensure topology access stays valid.
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
        topology_id = uuid.UUID(str(topology["id"]))

        before = session.exec(
            select(TopologyPersonalDraft).where(
                TopologyPersonalDraft.topology_id == topology_id,
                TopologyPersonalDraft.user_id == user.id,
            )
        ).all()
        assert before == []

        response = client.get(
            f"/api/topologies/{topology['id']}/editor-state",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

        assert response.status_code == 200
        assert response.json()["source"] in {"empty", "history"}

        after = session.exec(
            select(TopologyPersonalDraft).where(
                TopologyPersonalDraft.topology_id == topology_id,
                TopologyPersonalDraft.user_id == user.id,
            )
        ).all()
        assert after == []

    def test_discard_personal_draft_removes_only_callers_draft(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        owner, owner_token = _make_user(session, Role.Contributor)
        other_user, _ = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, owner_token)
        topology = _create_topology(client, owner_token, str(workspace["id"]), "Topology Discard")
        topology_id = uuid.UUID(str(topology["id"]))

        owner_draft = TopologyPersonalDraft(
            topology_id=topology_id,
            user_id=owner.id,
            cytoscape_json=_empty_canvas(),
            version=2,
        )
        other_draft = TopologyPersonalDraft(
            topology_id=topology_id,
            user_id=other_user.id,
            cytoscape_json=_empty_canvas(),
            version=1,
        )
        session.add(owner_draft)
        session.add(other_draft)
        session.commit()

        discard = client.delete(
            f"/api/topologies/{topology['id']}/personal-draft",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert discard.status_code == 200
        discard_payload = discard.json()
        assert discard_payload["topology_id"] == str(topology_id)
        assert discard_payload["discarded"] is True
        assert discard_payload["has_unsaved_changes"] is False

        session.expire_all()
        remaining = session.exec(
            select(TopologyPersonalDraft).where(
                TopologyPersonalDraft.topology_id == topology_id,
            )
        ).all()
        assert len(remaining) == 1
        assert remaining[0].user_id == other_user.id

        repeat_discard = client.delete(
            f"/api/topologies/{topology['id']}/personal-draft",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert repeat_discard.status_code == 200
        assert repeat_discard.json()["discarded"] is False


class TestTopologyHistoryAndRestore:
    def test_save_version_creates_history_entry_and_sets_current_pointer(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Save")

        save_payload = {
            "snapshot_name": "Version A",
            "cytoscape_json": {
                "elements": {
                    "nodes": [{"data": {"id": "node-a"}, "position": {"x": 100, "y": 100}}],
                    "edges": [],
                },
                "zoom": 1,
                "pan": {"x": 0, "y": 0},
                "collapsedNodes": [],
            },
        }

        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json=save_payload,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert save_response.status_code == 200
        saved = save_response.json()
        assert saved["current_diagram_id"] is not None
        assert saved["current_diagram_version"] == 1
        assert saved["action"] == "save_version"

        history_response = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["total"] >= 1
        assert history["items"][0]["is_current"] is True
        assert history["items"][0]["snapshot_name"] == "Version A"

    def test_save_version_without_name_uses_server_generated_snapshot(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Auto Name")

        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert save_response.status_code == 200
        payload = save_response.json()
        assert payload["snapshot_name"].startswith("Version ")

        history_response = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["items"][0]["snapshot_name"] == payload["snapshot_name"]
        assert history["items"][0]["is_current"] is True

    def test_save_version_without_cytoscape_payload_publishes_active_draft(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Publish Draft")

        draft_canvas = {
            "elements": {
                "nodes": [{"data": {"id": "draft-node"}, "position": {"x": 140, "y": 180}}],
                "edges": [],
            },
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
        draft_response = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json={"cytoscape_json": draft_canvas},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert draft_response.status_code == 200

        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Publish Active Draft"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert save_response.status_code == 200
        save_payload = save_response.json()
        assert save_payload["has_unsaved_changes"] is False
        nodes = save_payload["cytoscape_json"]["elements"]["nodes"]
        assert nodes[0]["data"]["id"] == "draft-node"

    def test_restore_history_is_append_only(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Restore")

        first = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Version 1", "cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )
        second = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "Version 2",
                "cytoscape_json": {
                    "elements": {"nodes": [{"data": {"id": "node-2"}}], "edges": []},
                    "zoom": 1,
                    "pan": {"x": 0, "y": 0},
                    "collapsedNodes": [],
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200
        assert second.status_code == 200

        history_before = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history_before.status_code == 200
        items_before = history_before.json()["items"]
        total_before = history_before.json()["total"]
        oldest_entry_id = items_before[-1]["id"]

        restore_response = client.post(
            f"/api/topologies/{topology['id']}/history/{oldest_entry_id}/restore",
            json={"base_diagram_version": second.json()["current_diagram_version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert restore_response.status_code == 200
        restored = restore_response.json()
        assert restored["action"] == "restore"
        assert restored["restored_from_history_entry_id"] == oldest_entry_id

        history_after = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history_after.status_code == 200
        payload_after = history_after.json()
        assert payload_after["total"] == total_before + 1
        assert payload_after["items"][0]["action"] == "restore"
        assert payload_after["items"][0]["is_current"] is True

    def test_restore_history_preserves_inline_node_dimensions(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Restore Size")

        v1_canvas = _canvas_with_inline_size("node-size", 120, 90)
        v2_canvas = _canvas_with_inline_size("node-size", 220, 150)

        first = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Version 1", "cytoscape_json": v1_canvas},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200

        second = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "Version 2",
                "cytoscape_json": v2_canvas,
                "base_diagram_version": first.json()["current_diagram_version"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 200

        history = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history.status_code == 200
        items = history.json()["items"]
        source_entry = next(item for item in items if item["snapshot_name"] == "Version 1")

        restore_response = client.post(
            f"/api/topologies/{topology['id']}/history/{source_entry['id']}/restore",
            json={"base_diagram_version": second.json()["current_diagram_version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert restore_response.status_code == 200
        restored_payload = restore_response.json()

        restored_nodes = restored_payload["cytoscape_json"]["elements"]["nodes"]
        assert len(restored_nodes) == 1
        assert restored_nodes[0]["style"]["width"] == 120
        assert restored_nodes[0]["style"]["height"] == 90

    def test_save_version_rejects_stale_base_after_successive_snapshots(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Save Stale")

        first = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Version 1", "cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200

        second_canvas = {
            "elements": {
                "nodes": [{"data": {"id": "node-2"}, "position": {"x": 180, "y": 140}}],
                "edges": [],
            },
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
        second = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "Version 2",
                "cytoscape_json": second_canvas,
                "base_diagram_version": first.json()["current_diagram_version"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 200

        stale = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "Version stale",
                "cytoscape_json": _empty_canvas(),
                "base_diagram_version": first.json()["current_diagram_version"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stale.status_code == 409

    def test_restore_history_rejects_stale_base_after_successive_snapshots(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Restore Stale")

        first = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Version 1", "cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200

        second_canvas = {
            "elements": {
                "nodes": [{"data": {"id": "node-2"}, "position": {"x": 220, "y": 160}}],
                "edges": [],
            },
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
        second = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={
                "snapshot_name": "Version 2",
                "cytoscape_json": second_canvas,
                "base_diagram_version": first.json()["current_diagram_version"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 200

        history = client.get(
            f"/api/topologies/{topology['id']}/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert history.status_code == 200
        oldest_entry_id = history.json()["items"][-1]["id"]

        restore = client.post(
            f"/api/topologies/{topology['id']}/history/{oldest_entry_id}/restore",
            json={"base_diagram_version": second.json()["current_diagram_version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert restore.status_code == 200

        stale_restore = client.post(
            f"/api/topologies/{topology['id']}/history/{oldest_entry_id}/restore",
            json={"base_diagram_version": second.json()["current_diagram_version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stale_restore.status_code == 409

    def test_save_version_clears_existing_personal_draft(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Draft Clear")

        draft_response = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json={"cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert draft_response.status_code == 200

        save_response = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Saved", "cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert save_response.status_code == 200
        assert save_response.json()["has_unsaved_changes"] is False

        editor_state = client.get(
            f"/api/topologies/{topology['id']}/editor-state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert editor_state.status_code == 200
        assert editor_state.json()["source"] == "history"
        assert editor_state.json()["draft_version"] is None
        assert editor_state.json()["has_unsaved_changes"] is False


class TestTopologyEditorRbacAndConflicts:
    def test_personal_draft_conflict_returns_409(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, token = _make_user(session, Role.Contributor)
        workspace = _create_workspace(client, token)
        topology = _create_topology(client, token, str(workspace["id"]), "Topology Conflict")

        first = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json={"cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200

        conflict = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json={"cytoscape_json": _empty_canvas(), "base_version": 999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert conflict.status_code == 409

    def test_reader_cannot_write_personal_draft_or_save_version(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, contrib_token = _make_user(session, Role.Contributor)
        _, reader_token = _make_user(session, Role.Reader)
        workspace = _create_workspace(client, contrib_token)
        topology = _create_topology(client, contrib_token, str(workspace["id"]), "Topology RBAC")

        draft = client.put(
            f"/api/topologies/{topology['id']}/personal-draft",
            json={"cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        save = client.post(
            f"/api/topologies/{topology['id']}/save-version",
            json={"snapshot_name": "Reader Save", "cytoscape_json": _empty_canvas()},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        discard = client.delete(
            f"/api/topologies/{topology['id']}/personal-draft",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

        assert draft.status_code == 403
        assert save.status_code == 403
        assert discard.status_code == 403
