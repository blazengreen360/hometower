"""Unit tests for src/domain/rbac.py.

No database, no mocks — pure function calls only.
"""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.domain.rbac import ROLE_HIERARCHY, can_perform, require_role
from src.models.types import Role


def _make_request(role: str) -> Request:
    """Build a minimal Starlette Request with role injected into state."""
    scope: dict[str, object] = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "query_string": b"",
        "headers": [],
    }
    req = Request(scope)
    req.state.role = role
    return req


# ---------------------------------------------------------------------------
# ROLE_HIERARCHY sanity
# ---------------------------------------------------------------------------

class TestRoleHierarchy:
    def test_admin_has_highest_level(self) -> None:
        assert ROLE_HIERARCHY[Role.Admin] > ROLE_HIERARCHY[Role.Contributor]

    def test_contributor_outranks_reader(self) -> None:
        assert ROLE_HIERARCHY[Role.Contributor] > ROLE_HIERARCHY[Role.Reader]

    def test_all_roles_are_present(self) -> None:
        assert set(ROLE_HIERARCHY.keys()) == {Role.Admin, Role.Contributor, Role.Reader}


# ---------------------------------------------------------------------------
# can_perform()
# ---------------------------------------------------------------------------

class TestCanPerform:
    def test_admin_can_perform_admin(self) -> None:
        assert can_perform(Role.Admin, Role.Admin) is True

    def test_admin_can_perform_contributor(self) -> None:
        assert can_perform(Role.Admin, Role.Contributor) is True

    def test_admin_can_perform_reader(self) -> None:
        assert can_perform(Role.Admin, Role.Reader) is True

    def test_contributor_cannot_perform_admin(self) -> None:
        assert can_perform(Role.Contributor, Role.Admin) is False

    def test_contributor_can_perform_contributor(self) -> None:
        assert can_perform(Role.Contributor, Role.Contributor) is True

    def test_contributor_can_perform_reader(self) -> None:
        assert can_perform(Role.Contributor, Role.Reader) is True

    def test_reader_cannot_perform_admin(self) -> None:
        assert can_perform(Role.Reader, Role.Admin) is False

    def test_reader_cannot_perform_contributor(self) -> None:
        assert can_perform(Role.Reader, Role.Contributor) is False

    def test_reader_can_perform_reader(self) -> None:
        assert can_perform(Role.Reader, Role.Reader) is True


# ---------------------------------------------------------------------------
# require_role()
# ---------------------------------------------------------------------------

class TestRequireRole:
    def test_admin_passes_admin_requirement(self) -> None:
        dep = require_role(Role.Admin)
        dep(_make_request("Admin"))  # must not raise

    def test_admin_passes_contributor_requirement(self) -> None:
        dep = require_role(Role.Contributor)
        dep(_make_request("Admin"))  # must not raise

    def test_admin_passes_reader_requirement(self) -> None:
        dep = require_role(Role.Reader)
        dep(_make_request("Admin"))  # must not raise

    def test_contributor_fails_admin_requirement(self) -> None:
        dep = require_role(Role.Admin)
        with pytest.raises(HTTPException) as exc_info:
            dep(_make_request("Contributor"))
        assert exc_info.value.status_code == 403
        assert "Insufficient" in exc_info.value.detail

    def test_contributor_passes_contributor_requirement(self) -> None:
        dep = require_role(Role.Contributor)
        dep(_make_request("Contributor"))  # must not raise

    def test_contributor_passes_reader_requirement(self) -> None:
        dep = require_role(Role.Reader)
        dep(_make_request("Contributor"))  # must not raise

    def test_reader_fails_admin_requirement(self) -> None:
        dep = require_role(Role.Admin)
        with pytest.raises(HTTPException) as exc_info:
            dep(_make_request("Reader"))
        assert exc_info.value.status_code == 403

    def test_reader_fails_contributor_requirement(self) -> None:
        dep = require_role(Role.Contributor)
        with pytest.raises(HTTPException) as exc_info:
            dep(_make_request("Reader"))
        assert exc_info.value.status_code == 403

    def test_reader_passes_reader_requirement(self) -> None:
        dep = require_role(Role.Reader)
        dep(_make_request("Reader"))  # must not raise

    def test_require_role_returns_403_detail(self) -> None:
        dep = require_role(Role.Admin)
        with pytest.raises(HTTPException) as exc_info:
            dep(_make_request("Reader"))
        assert exc_info.value.detail == "Insufficient permissions"
