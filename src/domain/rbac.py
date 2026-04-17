"""RBAC domain logic.

Pure Python — no I/O, no database, no network.
"""
from src.models.types import Role

ROLE_HIERARCHY: dict[Role, int] = {
    Role.Admin: 3,
    Role.Contributor: 2,
    Role.Reader: 1,
}


def can_perform(user_role: Role, required_role: Role) -> bool:
    """Return True when *user_role* has at least the level of *required_role*."""
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]
