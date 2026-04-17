"""Unit tests for src/services/system_service.py.

Tests all 4 service functions with mocked SQLModel sessions.
"""
from unittest.mock import MagicMock, call, patch

import pytest


class TestGetEntityCounts:
    """get_entity_counts returns a dict with 6 entity counts."""

    def test_returns_all_six_keys(self) -> None:
        from src.services.system_service import get_entity_counts

        session = MagicMock()
        session.exec.return_value.one.return_value = 0

        result = get_entity_counts(session)

        assert set(result.keys()) == {
            "devices",
            "connections",
            "locations",
            "tags",
            "custom_fields",
            "diagrams",
        }

    def test_returns_correct_counts(self) -> None:
        from src.services.system_service import get_entity_counts

        session = MagicMock()
        counts = [5, 3, 2, 4, 1, 6]
        session.exec.return_value.one.side_effect = counts

        result = get_entity_counts(session)

        assert result["devices"] == 5
        assert result["connections"] == 3
        assert result["locations"] == 2
        assert result["tags"] == 4
        assert result["custom_fields"] == 1
        assert result["diagrams"] == 6

    def test_calls_session_exec_six_times(self) -> None:
        from src.services.system_service import get_entity_counts

        session = MagicMock()
        session.exec.return_value.one.return_value = 0

        get_entity_counts(session)

        assert session.exec.call_count == 6

    def test_counts_are_integers(self) -> None:
        from src.services.system_service import get_entity_counts

        session = MagicMock()
        session.exec.return_value.one.return_value = 42

        result = get_entity_counts(session)

        for value in result.values():
            assert isinstance(value, int)


class TestGetUserCount:
    """get_user_count returns total user count as int."""

    def test_returns_integer(self) -> None:
        from src.services.system_service import get_user_count

        session = MagicMock()
        session.exec.return_value.one.return_value = 7

        result = get_user_count(session)

        assert result == 7
        assert isinstance(result, int)

    def test_returns_zero_when_no_users(self) -> None:
        from src.services.system_service import get_user_count

        session = MagicMock()
        session.exec.return_value.one.return_value = 0

        result = get_user_count(session)

        assert result == 0


class TestGetDbDiagnostics:
    """get_db_diagnostics returns (version_str, size_bytes) tuple."""

    def test_returns_version_and_size(self) -> None:
        from src.services.system_service import get_db_diagnostics

        session = MagicMock()
        version_row = MagicMock()
        version_row.__getitem__ = lambda self, idx: "PostgreSQL 16.2"
        size_row = MagicMock()
        size_row.__getitem__ = lambda self, idx: 12345678

        session.execute.return_value.fetchone.side_effect = [version_row, size_row]

        version, size = get_db_diagnostics(session)

        assert version == "PostgreSQL 16.2"
        assert size == 12345678

    def test_returns_none_on_exception(self) -> None:
        from src.services.system_service import get_db_diagnostics

        session = MagicMock()
        session.execute.side_effect = Exception("not PG")

        version, size = get_db_diagnostics(session)

        assert version is None
        assert size is None

    def test_returns_none_when_fetchone_is_none(self) -> None:
        from src.services.system_service import get_db_diagnostics

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None

        version, size = get_db_diagnostics(session)

        assert version is None
        assert size is None


class TestCheckDbConnectivity:
    """check_db_connectivity returns bool based on SELECT 1 success."""

    def test_returns_true_on_success(self) -> None:
        from src.services.system_service import check_db_connectivity

        session = MagicMock()

        assert check_db_connectivity(session) is True

    def test_returns_false_on_exception(self) -> None:
        from src.services.system_service import check_db_connectivity

        session = MagicMock()
        session.exec.side_effect = Exception("connection refused")

        assert check_db_connectivity(session) is False

    def test_executes_select_1(self) -> None:
        from src.services.system_service import check_db_connectivity

        session = MagicMock()

        check_db_connectivity(session)

        session.exec.assert_called_once()
