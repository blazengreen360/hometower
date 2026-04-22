"""Unit tests for src/services/import_service.py."""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.export_schema import ExportSchema, ExportedLocation
from src.models.types import LocationType
from src.services.import_service import _is_postgres, import_full_snapshot, _clear_all_tables


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payload(locations: list[ExportedLocation]) -> ExportSchema:
    now = _now()
    return ExportSchema(
        version="1.0",
        exported_at=now,
        devices=[],
        connections=[],
        locations=locations,
        tags=[],
        device_tags=[],
        custom_fields=[],
        diagram_layouts=[],
        users=[],
    )


def _exported_location(
    *,
    location_type: LocationType,
    lat: float | None = None,
    lng: float | None = None,
    row: str | None = None,
) -> ExportedLocation:
    now = _now()
    return ExportedLocation(
        id=uuid.uuid4(),
        name="loc",
        type=location_type,
        lat=lat,
        lng=lng,
        rack=None,
        row=row,
        parent_id=None,
        created_at=now,
        updated_at=now,
    )


class TestIsPostgres:
    def test_runtime_error_from_get_bind_is_not_swallowed(self) -> None:
        class BrokenSession:
            def get_bind(self) -> object:
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            _is_postgres(BrokenSession())  # type: ignore[arg-type]


class TestImportLocationValidation:
    def test_import_rejects_out_of_bounds_location_lat(self, session: Session) -> None:
        payload = _payload(
            [
                _exported_location(
                    location_type=LocationType.geo,
                    lat=100.0,
                    lng=0.0,
                )
            ]
        )

        with pytest.raises((ValidationError, ValueError), match="lat must be between -90 and 90"):
            import_full_snapshot(session, payload)


class TestImportTransactionOwnership:
    def test_import_commits_after_successful_replace(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = _payload([])
        called = {"commit": False}
        original_commit = session.commit

        def commit_spy() -> None:
            called["commit"] = True
            original_commit()

        monkeypatch.setattr("src.services.import_service._clear_all_tables", lambda current_session: None)
        monkeypatch.setattr(
            "src.services.import_service.insert_snapshot_rows",
            lambda current_session, current_payload: None,
        )
        monkeypatch.setattr(session, "commit", commit_spy)

        counts = import_full_snapshot(session, payload)

        assert called["commit"] is True
        assert counts["devices"] == 0

    def test_import_rolls_back_when_insert_fails(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = _payload([])
        called = {"rollback": False}
        original_rollback = session.rollback

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        def fail_insert(current_session: Session, current_payload: ExportSchema) -> None:
            raise IntegrityError("INSERT ...", {}, Exception("simulated duplicate"))

        monkeypatch.setattr("src.services.import_service._clear_all_tables", lambda current_session: None)
        monkeypatch.setattr("src.services.import_service.insert_snapshot_rows", fail_insert)
        monkeypatch.setattr(session, "rollback", rollback_spy)

        with pytest.raises(IntegrityError):
            import_full_snapshot(session, payload)

        assert called["rollback"] is True


def test_clear_all_tables_uses_delete_not_truncate_for_postgres() -> None:
    """Ensure we do not use TRUNCATE on Postgres (BUG-001 mitigation).

    This unit test constructs a fake session whose bind reports a
    Postgres dialect and captures executed SQL. The import service must
    issue `DELETE FROM <table>` statements (no TRUNCATE) to avoid taking
    ACCESS EXCLUSIVE locks on busy databases.
    """

    executed: list[str] = []

    class FakeBind:
        dialect = type("D", (), {"name": "postgresql"})()

    class FakeSession:
        def get_bind(self) -> object:  # type: ignore[override]
            return FakeBind()

        def exec(self, clause: object) -> None:  # type: ignore[override]
            # Extract text if SQLAlchemy TextClause, else str()
            try:
                executed.append(clause.text)  # type: ignore[attr-defined]
            except Exception:
                executed.append(str(clause))

    _clear_all_tables(FakeSession())

    # No TRUNCATE statements should be present
    assert not any("TRUNCATE" in q.upper() for q in executed)
    # At least one DELETE should be present
    assert any("DELETE FROM" in q.upper() for q in executed)

    deleted_tables = [
        query.split()[-1]
        for query in executed
        if query.upper().startswith("DELETE FROM")
    ]

    for table in [
        "service_dependencies",
        "services",
        "custom_fields",
        "device_attachments",
        "device_networks",
        "device_tags",
        "connections",
        "topology_personal_drafts",
        "topology_history_entries",
        "diagram_layouts",
        "devices",
        "networks",
        "topologies",
        "locations",
        "tags",
        "power_settings",
        "workspaces",
        "users",
    ]:
        assert table in deleted_tables

    # Dependency-sensitive ordering guarantees: child tables must clear first.
    assert deleted_tables.index("device_attachments") < deleted_tables.index("devices")
    assert deleted_tables.index("topology_personal_drafts") < deleted_tables.index("topologies")
    assert deleted_tables.index("topology_history_entries") < deleted_tables.index("topologies")
    assert deleted_tables.index("workspaces") < deleted_tables.index("users")
