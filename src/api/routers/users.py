"""Admin-only CRUD endpoints for user management.

Hides the HTTP shape of user management — if the API contract is versioned
or restructured, only this file changes.
"""
import uuid

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.types import Role
from src.models.user import UserCreate, UserResponse, UserUpdate
from src.services import user_service
from src.utils.db import get_session

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    response_model=list[UserResponse],
    dependencies=[Depends(require_role(Role.Admin))],
)
def list_users(session: Session = Depends(get_session)) -> list[UserResponse]:
    """List all users. Requires Admin role."""
    return user_service.list_users(session)


@router.post(
    "/",
    status_code=201,
    response_model=UserResponse,
    dependencies=[Depends(require_role(Role.Admin))],
)
def create_user(
    data: UserCreate,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Create a new user. Requires Admin role."""
    return user_service.create_user(data, session)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_role(Role.Admin))],
)
def get_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Get a user by ID. Requires Admin role."""
    return user_service.get_user(user_id, session)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_role(Role.Admin))],
)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Partially update a user. Requires Admin role."""
    return user_service.update_user(user_id, data, session)


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Admin))],
)
def delete_user(
    user_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Delete a user. Cannot delete self or last admin. Requires Admin role."""
    user_service.delete_user(user_id, request.state.user_id, session)
