"""Unit tests for src/services/workspace_service.py."""
import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.models.workspace import Workspace, WorkspaceCreate, WorkspaceUpdate
from src.services import workspace_service
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


class TestWorkspaceServiceCreate:
    def test_creates_workspace(self, session: Session) -> None:
        user = _make_user(session)
        ws = workspace_service.create(user.id, WorkspaceCreate(name="Lab"), session)
        assert ws.name == "Lab"
        assert ws.owner_id == user.id

    def test_duplicate_name_raises_409(self, session: Session) -> None:
        user = _make_user(session)
        workspace_service.create(user.id, WorkspaceCreate(name="Dup"), session)
        with pytest.raises(HTTPException) as exc_info:
            workspace_service.create(user.id, WorkspaceCreate(name="Dup"), session)
        assert exc_info.value.status_code == 409

    def test_strips_whitespace(self, session: Session) -> None:
        user = _make_user(session)
        ws = workspace_service.create(user.id, WorkspaceCreate(name="  Padded  "), session)
        assert ws.name == "Padded"


class TestWorkspaceServiceGetOrCreateDefault:
    def test_creates_default_workspace(self, session: Session) -> None:
        user = _make_user(session)
        ws = workspace_service.get_or_create_default(user.id, session)
        assert ws.name == "Default Workspace"

    def test_returns_existing_default(self, session: Session) -> None:
        user = _make_user(session)
        ws1 = workspace_service.get_or_create_default(user.id, session)
        ws2 = workspace_service.get_or_create_default(user.id, session)
        assert ws1.id == ws2.id


class TestWorkspaceServiceGetById:
    def test_returns_owned_workspace(self, session: Session) -> None:
        user = _make_user(session)
        ws = workspace_service.create(user.id, WorkspaceCreate(name="Mine"), session)
        result = workspace_service.get_by_id(ws.id, user.id, session)
        assert result.id == ws.id

    def test_raises_404_for_other_owner(self, session: Session) -> None:
        user_a = _make_user(session)
        user_b = _make_user(session)
        ws = workspace_service.create(user_a.id, WorkspaceCreate(name="Private"), session)
        with pytest.raises(HTTPException) as exc_info:
            workspace_service.get_by_id(ws.id, user_b.id, session)
        assert exc_info.value.status_code == 404


class TestWorkspaceServiceGetAll:
    def test_returns_paginated_list(self, session: Session) -> None:
        user = _make_user(session)
        workspace_service.create(user.id, WorkspaceCreate(name="A"), session)
        workspace_service.create(user.id, WorkspaceCreate(name="B"), session)
        items, total = workspace_service.get_all(user.id, session)
        assert total == 2
        assert len(items) == 2


class TestWorkspaceServiceRename:
    def test_renames_workspace(self, session: Session) -> None:
        user = _make_user(session)
        ws = workspace_service.create(user.id, WorkspaceCreate(name="Old"), session)
        result = workspace_service.rename(ws.id, user.id, WorkspaceUpdate(name="New"), session)
        assert result.name == "New"

    def test_rename_to_duplicate_raises_409(self, session: Session) -> None:
        user = _make_user(session)
        workspace_service.create(user.id, WorkspaceCreate(name="Existing"), session)
        ws = workspace_service.create(user.id, WorkspaceCreate(name="ToRename"), session)
        with pytest.raises(HTTPException) as exc_info:
            workspace_service.rename(ws.id, user.id, WorkspaceUpdate(name="Existing"), session)
        assert exc_info.value.status_code == 409


class TestWorkspaceServiceDelete:
    def test_deletes_workspace(self, session: Session) -> None:
        user = _make_user(session)
        ws = workspace_service.create(user.id, WorkspaceCreate(name="Del"), session)
        workspace_service.delete(ws.id, user.id, session)
        with pytest.raises(HTTPException) as exc_info:
            workspace_service.get_by_id(ws.id, user.id, session)
        assert exc_info.value.status_code == 404
