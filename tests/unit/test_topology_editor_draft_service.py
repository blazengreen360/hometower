"""Unit tests for personal-draft selection semantics in topology_editor_draft_service."""
import uuid

from sqlmodel import Session

from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.topology_personal_draft import TopologyPersonalDraft
from src.models.types import Role
from src.models.user import User
from src.models.workspace import Workspace
from src.services import topology_editor_draft_service
from src.utils.auth import hash_password


def _make_user(session: Session, role: Role = Role.Contributor) -> User:
    user = User(
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_workspace(session: Session, owner: User, name: str = "WS") -> Workspace:
    workspace = Workspace(name=name, owner_id=owner.id)
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def _make_topology(session: Session, workspace: Workspace, name: str = "Topology") -> Topology:
    topology = Topology(name=name, workspace_id=workspace.id, tags=[])
    session.add(topology)
    session.commit()
    session.refresh(topology)
    return topology


def _attach_current_snapshot(
    session: Session,
    topology: Topology,
    cytoscape_json: dict[str, object],
) -> DiagramLayout:
    diagram = DiagramLayout(
        name="Current",
        topology_id=topology.id,
        cytoscape_json=cytoscape_json,
        version=1,
    )
    session.add(diagram)
    session.commit()
    session.refresh(diagram)

    topology.current_diagram_id = diagram.id
    session.add(topology)
    session.commit()
    session.refresh(topology)
    return diagram


def _make_draft(
    session: Session,
    topology: Topology,
    user: User,
    cytoscape_json: dict[str, object],
) -> TopologyPersonalDraft:
    draft = TopologyPersonalDraft(
        topology_id=topology.id,
        user_id=user.id,
        cytoscape_json=cytoscape_json,
        version=1,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


class TestTopologyEditorDraftService:
    def test_get_editor_state_is_private_per_user(self, session: Session) -> None:
        owner = _make_user(session, Role.Contributor)
        colleague = _make_user(session, Role.Contributor)
        workspace = _make_workspace(session, owner, "WS-Private-Draft")
        topology = _make_topology(session, workspace, "Topo-Private-Draft")

        saved_canvas = {
            "elements": {"nodes": [{"data": {"id": "saved-node"}}], "edges": []},
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
        _attach_current_snapshot(session, topology, saved_canvas)

        owner_draft_canvas = {
            "elements": {"nodes": [{"data": {"id": "owner-draft"}}], "edges": []},
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
        colleague_draft_canvas = saved_canvas

        _make_draft(session, topology, owner, owner_draft_canvas)
        _make_draft(session, topology, colleague, colleague_draft_canvas)

        owner_state = topology_editor_draft_service.get_editor_state(
            topology_id=topology.id,
            owner_id=owner.id,
            user_id=owner.id,
            session=session,
        )
        colleague_state = topology_editor_draft_service.get_editor_state(
            topology_id=topology.id,
            owner_id=owner.id,
            user_id=colleague.id,
            session=session,
        )

        owner_nodes = owner_state.cytoscape_json["elements"]["nodes"]
        colleague_nodes = colleague_state.cytoscape_json["elements"]["nodes"]

        assert owner_state.source == "draft"
        assert owner_state.has_unsaved_changes is True
        assert owner_nodes[0]["data"]["id"] == "owner-draft"

        assert colleague_state.source == "draft"
        assert colleague_state.has_unsaved_changes is False
        assert colleague_nodes[0]["data"]["id"] == "saved-node"

    def test_get_editor_state_falls_back_to_saved_history_when_user_has_no_draft(
        self,
        session: Session,
    ) -> None:
        owner = _make_user(session, Role.Contributor)
        colleague = _make_user(session, Role.Contributor)
        workspace = _make_workspace(session, owner, "WS-History-Fallback")
        topology = _make_topology(session, workspace, "Topo-History-Fallback")

        saved_canvas = {
            "elements": {"nodes": [{"data": {"id": "saved-node"}}], "edges": []},
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
        diagram = _attach_current_snapshot(session, topology, saved_canvas)

        _make_draft(
            session,
            topology,
            owner,
            {
                "elements": {"nodes": [{"data": {"id": "owner-only-draft"}}], "edges": []},
                "zoom": 1,
                "pan": {"x": 0, "y": 0},
                "collapsedNodes": [],
            },
        )

        colleague_state = topology_editor_draft_service.get_editor_state(
            topology_id=topology.id,
            owner_id=owner.id,
            user_id=colleague.id,
            session=session,
        )

        assert colleague_state.source == "history"
        assert colleague_state.has_unsaved_changes is False
        assert colleague_state.current_diagram_id == diagram.id
        assert colleague_state.current_diagram_version == 1
        nodes = colleague_state.cytoscape_json["elements"]["nodes"]
        assert nodes[0]["data"]["id"] == "saved-node"
