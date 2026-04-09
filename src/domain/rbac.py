"""RBAC domain logic.

Pure Python — no I/O, no database, no network.
Only imports from src/models/types.py.
"""
from fastapi import HTTPException, Request

from src.models.types import Role

ROLE_HIERARCHY: dict[Role, int] = {
    Role.Admin: 3,
    Role.Contributor: 2,
    Role.Reader: 1,
}


def can_perform(user_role: Role, required_role: Role) -> bool:
    """Return True when *user_role* has at least the level of *required_role*."""
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]


def require_role(required: Role):  # type: ignore[return]
    """FastAPI dependency factory. Raises 403 if the caller lacks *required* role.

    Usage::

        @router.delete("/resource", dependencies=[Depends(require_role(Role.Admin))])
        async def delete_resource(): ...
    """
    def dependency(request: Request) -> None:
        user_role = Role(request.state.role)
        if not can_perform(user_role, required):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return dependency
