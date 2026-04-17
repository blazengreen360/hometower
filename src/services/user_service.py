"""User management service — orchestrates user_repository + business validation.

Hides the decision of how user mutations are validated (self-delete, last-admin,
email uniqueness). If business rules change, only this file changes.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from src.domain.auth import validate_password_strength
from src.models.types import Role
from src.models.user import User, UserCreate, UserResponse, UserUpdate
from src.repositories import user_repository
from src.utils.auth import hash_password
from src.utils.logger import logger


def list_users(session: Session) -> list[UserResponse]:
    """Return all users ordered by creation time."""
    users = user_repository.get_all(session)
    return [UserResponse.model_validate(u.model_dump()) for u in users]


def get_user(user_id: uuid.UUID, session: Session) -> UserResponse:
    """Return the user with the given ID.

    Raises:
        HTTPException(404): when the user does not exist.
    """
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user.model_dump())


def create_user(data: UserCreate, session: Session) -> UserResponse:
    """Create a new user.

    Raises:
        HTTPException(422): when the password is shorter than 8 characters.
        HTTPException(409): when the email is already registered.
    """
    try:
        validate_password_strength(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if user_repository.get_by_email(session, data.email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=data.is_active,
    )
    created = user_repository.create(session, user)
    session.commit()
    session.refresh(created)
    logger.info("User created: id={}", created.id)
    return UserResponse.model_validate(created.model_dump())


def reset_password_by_email(
    email: str, new_password: str, session: Session
) -> None:
    """Reset a user's password by email for administrative tooling.

    Raises:
        ValueError: when the password is weak or the user does not exist.
    """
    validate_password_strength(new_password)

    user = user_repository.get_by_email(session, email)
    if user is None:
        raise ValueError(f"User not found: {email}")

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    user_repository.update(session, user)
    session.commit()
    logger.info("Password reset via service: user_id={}", user.id)


def update_user(
    user_id: uuid.UUID, data: UserUpdate, session: Session
) -> UserResponse:
    """Partially update a user.

    Raises:
        HTTPException(404): when the user does not exist.
        HTTPException(409): when the new email is already taken by another user.
        HTTPException(422): when a new password is shorter than 8 characters.
    """
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if data.email is not None and data.email != user.email:
        if user_repository.get_by_email(session, data.email) is not None:
            raise HTTPException(status_code=409, detail="Email already registered")
    if data.password is not None:
        try:
            validate_password_strength(data.password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    role_changed = data.role is not None and data.role != user.role
    is_active_changed = data.is_active is not None and data.is_active != user.is_active
    if data.username is not None:
        user.username = data.username
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    user.updated_at = datetime.now(timezone.utc)
    updated = user_repository.update(session, user)
    if role_changed or is_active_changed:
        user_repository.increment_token_version(session, user_id)
    session.commit()
    session.refresh(updated)
    logger.info("User updated: user_id={}", user_id)
    return UserResponse.model_validate(updated.model_dump())


def delete_user(
    user_id: uuid.UUID, requesting_user_id: str, session: Session
) -> None:
    """Delete the user with the given ID.

    Raises:
        HTTPException(404): when the user does not exist.
        HTTPException(400): when the requesting user tries to delete themselves.
        HTTPException(400): when deleting the last Admin user.
    """
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.id) == requesting_user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if (
        user.role == Role.Admin
        and user_repository.count_by_role_for_update(session, Role.Admin) <= 1
    ):
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    user_repository.delete(session, user)
    session.commit()
    logger.info("User deleted: user_id={}", user_id)
