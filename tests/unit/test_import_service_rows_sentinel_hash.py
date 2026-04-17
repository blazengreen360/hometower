"""Unit tests for import row insertion sentinel hashing behavior (BUG-003)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, select

from src.models.export_schema import ExportSchema, ExportedUser
from src.models.types import Role
from src.models.user import User
from src.services import import_service_rows


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_with_users(user_count: int) -> ExportSchema:
    now = _now()
    users = [
        ExportedUser(
            id=uuid.uuid4(),
            username=f"import_user_{index}",
            email=f"import_user_{index}@test.local",
            role=Role.Reader,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for index in range(user_count)
    ]

    return ExportSchema(
        version="1.0",
        exported_at=now,
        devices=[],
        connections=[],
        locations=[],
        tags=[],
        device_tags=[],
        custom_fields=[],
        diagram_layouts=[],
        users=users,
    )


def test_insert_snapshot_rows_hashes_user_sentinel_once_per_import(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload_with_users(8)
    calls: dict[str, int] = {"token": 0, "hash": 0}

    def fake_token_hex(size: int) -> str:
        calls["token"] += 1
        assert size == 32
        return "fixed_sentinel_seed"

    def fake_hash_password(raw: str) -> str:
        calls["hash"] += 1
        assert raw == "fixed_sentinel_seed"
        return "hashed::fixed_sentinel_seed"

    monkeypatch.setattr(import_service_rows.secrets, "token_hex", fake_token_hex)
    monkeypatch.setattr(import_service_rows, "hash_password", fake_hash_password)

    import_service_rows.insert_snapshot_rows(session, payload)

    inserted = list(session.exec(select(User)).all())
    assert len(inserted) == 8
    assert calls["token"] == 1
    assert calls["hash"] == 1
    assert {user.password_hash for user in inserted} == {"hashed::fixed_sentinel_seed"}