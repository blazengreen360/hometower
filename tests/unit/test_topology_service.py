"""Unit tests for src/services/topology_service.py."""
import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.models.topology import TopologyCreate, TopologyUpdate
from src.models.types import Role
from src.models.user import User
from src.models.workspace import WorkspaceCreate
from src.services import topology_service, workspace_service
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


def _make_workspace(session: Session, user: User, name: str = "WS") -> uuid.UUID:
    ws = workspace_service.create(user.id, WorkspaceCreate(name=name), session)
    return ws.id


class TestTopologyServiceCreate:
    def test_creates_topology(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        t = topology_service.create(ws_id, user.id, TopologyCreate(name="Home Lab"), session)
        assert t.name == "Home Lab"
        assert t.workspace_id == ws_id

    def test_creates_topology_with_tags(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        t = topology_service.create(
            ws_id, user.id, TopologyCreate(name="Tagged", tags=["prod"]), session,
        )
        assert t.tags == ["prod"]

    def test_duplicate_name_raises_409(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        topology_service.create(ws_id, user.id, TopologyCreate(name="Dup"), session)
        with pytest.raises(HTTPException) as exc_info:
            topology_service.create(ws_id, user.id, TopologyCreate(name="Dup"), session)
        assert exc_info.value.status_code == 409

    def test_wrong_workspace_raises_404(self, session: Session) -> None:
        user = _make_user(session)
        with pytest.raises(HTTPException) as exc_info:
            topology_service.create(uuid.uuid4(), user.id, TopologyCreate(name="X"), session)
        assert exc_info.value.status_code == 404


class TestTopologyServiceGetById:
    def test_returns_owned_topology(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        t = topology_service.create(ws_id, user.id, TopologyCreate(name="Get"), session)
        result = topology_service.get_by_id(t.id, user.id, session)
        assert result.id == t.id

    def test_raises_404_for_other_owner(self, session: Session) -> None:
        user_a = _make_user(session)
        user_b = _make_user(session)
        ws_id = _make_workspace(session, user_a)
        t = topology_service.create(ws_id, user_a.id, TopologyCreate(name="Private"), session)
        with pytest.raises(HTTPException) as exc_info:
            topology_service.get_by_id(t.id, user_b.id, session)
        assert exc_info.value.status_code == 404


class TestTopologyServiceGetByWorkspace:
    def test_returns_paginated_list(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        topology_service.create(ws_id, user.id, TopologyCreate(name="A"), session)
        topology_service.create(ws_id, user.id, TopologyCreate(name="B"), session)
        items, total = topology_service.get_by_workspace(ws_id, user.id, session)
        assert total == 2
        assert len(items) == 2


class TestTopologyServiceRename:
    def test_renames_topology(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        t = topology_service.create(ws_id, user.id, TopologyCreate(name="Old"), session)
        result = topology_service.rename(t.id, user.id, TopologyUpdate(name="New"), session)
        assert result.name == "New"

    def test_rename_to_duplicate_raises_409(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        topology_service.create(ws_id, user.id, TopologyCreate(name="Existing"), session)
        t = topology_service.create(ws_id, user.id, TopologyCreate(name="ToRename"), session)
        with pytest.raises(HTTPException) as exc_info:
            topology_service.rename(t.id, user.id, TopologyUpdate(name="Existing"), session)
        assert exc_info.value.status_code == 409


class TestTopologyServiceUpdateTags:
    def test_updates_tags(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        t = topology_service.create(ws_id, user.id, TopologyCreate(name="T"), session)
        result = topology_service.update_tags(t.id, user.id, ["a", "b"], session)
        assert result.tags == ["a", "b"]


class TestTopologyServiceDelete:
    def test_deletes_topology(self, session: Session) -> None:
        user = _make_user(session)
        ws_id = _make_workspace(session, user)
        t = topology_service.create(ws_id, user.id, TopologyCreate(name="Del"), session)
        topology_service.delete(t.id, user.id, session)
        with pytest.raises(HTTPException) as exc_info:
            topology_service.get_by_id(t.id, user.id, session)
        assert exc_info.value.status_code == 404
