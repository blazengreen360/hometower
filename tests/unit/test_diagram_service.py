"""Unit tests for diagram_service locking and rollback behavior."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from src.models.diagram import DiagramLayout, DiagramLayoutCreate, DiagramLayoutUpdate
from src.models.topology import Topology
from src.models.types import Role
from src.models.user import User
from src.models.workspace import Workspace
from src.repositories import diagram_repository
from src.services import diagram_service
from src.utils.auth import hash_password


@pytest.fixture
def owner_id(session: Session):
    user = User(
        username=f"owner_{uuid4().hex[:8]}",
        email=f"owner_{uuid4().hex[:8]}@test.local",
        password_hash=hash_password("x"),
        role=Role.Contributor,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user.id


def _layout_create(name: str = "Autosave", version: int | None = None) -> DiagramLayoutCreate:
    return DiagramLayoutCreate(
        name=name,
        cytoscape_json={
            "elements": [{"data": {"id": "n1", "label": "Node 1"}, "position": {"x": 0, "y": 0}}],
            "zoom": 1.0,
            "pan": {"x": 0, "y": 0},
        },
        version=version,
    )


class TestDiagramServiceUpdateTimestamp:
    def test_update_timestamp_uses_update_path_not_create(
        self, session: Session, monkeypatch, owner_id
    ) -> None:
        layout = diagram_service.create(_layout_create(), owner_id, session)
        called: dict[str, bool] = {"update": False}

        def fail_create(*_args: object, **_kwargs: object) -> DiagramLayout:
            raise AssertionError("create() must not be used when touching updated_at")

        def repo_update(current_session: Session, current_layout: DiagramLayout) -> DiagramLayout:
            called["update"] = True
            current_session.add(current_layout)
            current_session.commit()
            current_session.refresh(current_layout)
            return current_layout

        monkeypatch.setattr(diagram_repository, "create", fail_create)
        monkeypatch.setattr(diagram_repository, "update", repo_update, raising=False)

        result = diagram_service.update_timestamp(layout.id, session)

        assert called["update"] is True
        assert result.id == layout.id

    def test_update_timestamp_keeps_single_layout_and_changes_updated_at(
        self, session: Session, owner_id
    ) -> None:
        name = f"Autosave-{uuid4()}"
        layout = diagram_service.create(_layout_create(name=name), owner_id, session)
        layout.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        session.add(layout)
        session.commit()
        session.refresh(layout)

        before = layout.updated_at
        result = diagram_service.update_timestamp(layout.id, session)
        matching_layouts = list(
            session.exec(
                select(DiagramLayout).where(col(DiagramLayout.name) == name)
            ).all()
        )

        assert len(matching_layouts) == 1
        assert result.updated_at > before


class TestDiagramServiceVersionConflicts:
    def test_update_uses_locked_read_and_rejects_stale_version(
        self, session: Session, monkeypatch, owner_id
    ) -> None:
        layout = diagram_service.create(_layout_create(), owner_id, session)
        layout.version = 2
        session.add(layout)
        session.commit()
        session.refresh(layout)

        called: dict[str, bool] = {"locked_read": False}

        def fail_get_by_id(*_args: object, **_kwargs: object) -> DiagramLayout | None:
            raise AssertionError("update() must use get_by_id_for_update()")

        def get_by_id_for_update(
            _current_session: Session, _layout_id: object
        ) -> DiagramLayout:
            called["locked_read"] = True
            return layout

        monkeypatch.setattr(diagram_repository, "get_by_id", fail_get_by_id)
        monkeypatch.setattr(diagram_repository, "get_by_id_for_update", get_by_id_for_update)

        with pytest.raises(HTTPException) as exc_info:
            diagram_service.update(
                layout.id,
                _layout_create(name="Stale", version=1),
                owner_id,
                session,
            )

        assert called["locked_read"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Conflict: diagram was modified by another request"

    def test_partial_update_uses_locked_read_and_rejects_stale_version(
        self, session: Session, monkeypatch, owner_id
    ) -> None:
        layout = diagram_service.create(_layout_create(), owner_id, session)
        layout.version = 2
        session.add(layout)
        session.commit()
        session.refresh(layout)

        called: dict[str, bool] = {"locked_read": False}

        def fail_get_by_id(*_args: object, **_kwargs: object) -> DiagramLayout | None:
            raise AssertionError("partial_update() must use get_by_id_for_update()")

        def get_by_id_for_update(
            _current_session: Session, _layout_id: object
        ) -> DiagramLayout:
            called["locked_read"] = True
            return layout

        monkeypatch.setattr(diagram_repository, "get_by_id", fail_get_by_id)
        monkeypatch.setattr(diagram_repository, "get_by_id_for_update", get_by_id_for_update)

        with pytest.raises(HTTPException) as exc_info:
            diagram_service.partial_update(
                layout.id,
                DiagramLayoutUpdate(name="Stale Patch", version=1),
                owner_id,
                session,
            )

        assert called["locked_read"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Conflict: diagram was modified by another request"


class TestDiagramServiceRollbackHandling:
    def test_create_integrity_error_rolls_back_and_returns_409(
        self, session: Session, monkeypatch, owner_id
    ) -> None:
        called: dict[str, bool] = {"rollback": False}

        def fail_commit() -> None:
            raise IntegrityError("COMMIT", {}, Exception("simulated duplicate"))

        original_rollback = session.rollback

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "commit", fail_commit)
        monkeypatch.setattr(session, "rollback", rollback_spy)

        with pytest.raises(HTTPException) as exc_info:
            diagram_service.create(_layout_create(), owner_id, session)

        assert called["rollback"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Diagram layout conflict"

    def test_update_integrity_error_rolls_back_and_returns_409(
        self, session: Session, monkeypatch, owner_id
    ) -> None:
        layout = diagram_service.create(_layout_create(), owner_id, session)
        called: dict[str, bool] = {"rollback": False}

        def fail_commit() -> None:
            raise IntegrityError("COMMIT", {}, Exception("simulated duplicate"))

        original_rollback = session.rollback

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "commit", fail_commit)
        monkeypatch.setattr(session, "rollback", rollback_spy)

        with pytest.raises(HTTPException) as exc_info:
            diagram_service.update(
                layout.id,
                _layout_create(name="Updated", version=layout.version),
                owner_id,
                session,
            )

        assert called["rollback"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Diagram layout conflict"


class TestDiagramServiceDefaultTopologyBinding:
    def test_create_without_topology_id_binds_to_default_owner_topology(
        self, session: Session, owner_id
    ) -> None:
        layout = diagram_service.create(_layout_create(name="AutoBound"), owner_id, session)

        assert layout.topology_id is not None
        topology = session.get(Topology, layout.topology_id)
        assert topology is not None
        assert topology.name == "Default Topology"

        workspace = session.get(Workspace, topology.workspace_id)
        assert workspace is not None
        assert workspace.owner_id == owner_id
        assert workspace.name == "Default Workspace"

    def test_owner_scoped_read_hides_legacy_null_topology_layout(
        self, session: Session, owner_id
    ) -> None:
        legacy_layout = DiagramLayout(
            name=f"Legacy-{uuid4().hex[:8]}",
            cytoscape_json={"elements": []},
            topology_id=None,
        )
        session.add(legacy_layout)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            diagram_service.get_by_id(legacy_layout.id, session, owner_id=owner_id)

        assert exc_info.value.status_code == 404
