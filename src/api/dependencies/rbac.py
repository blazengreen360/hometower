"""FastAPI RBAC dependency — require_role() factory.

Separated from ``src.domain.rbac`` to keep the domain layer free of
FastAPI / logging / I-O imports.
"""
from fastapi import HTTPException, Request

from src.domain.rbac import can_perform
from src.models.types import Role
from src.utils.logger import logger


def require_role(required: Role):  # type: ignore[return]
    """FastAPI dependency factory. Raises 403 if the caller lacks *required* role.

    Usage::

        @router.delete("/resource", dependencies=[Depends(require_role(Role.Admin))])
        async def delete_resource(): ...
    """
    def dependency(request: Request) -> None:
        role_claim = getattr(request.state, "role", None)
        try:
            user_role = Role(role_claim)
        except ValueError:
            user_id = getattr(request.state, "user_id", None)
            logger.warning(
                "Invalid JWT role claim denied: role={} user_id={}",
                role_claim,
                user_id,
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions") from None
        if not can_perform(user_role, required):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    dependency._rbac_protected = True  # type: ignore[attr-defined]  # machine-readable marker for coverage test
    return dependency
