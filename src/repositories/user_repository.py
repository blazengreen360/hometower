"""User repository — sole layer that holds a SQLModel Session for User operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.types import Role
from src.models.user import User


def create(session: Session, user: User) -> User:
    """Persist a new user and return the refreshed instance."""
    session.add(user)
    session.flush()
    session.refresh(user)
    return user


def get_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    """Return the user with the given primary key, or None."""
    return session.get(User, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    """Return the user matching *email* (case-sensitive), or None."""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def get_all(session: Session) -> list[User]:
    """Return all users ordered by creation time."""
    statement = select(User).order_by(col(User.created_at))
    return list(session.exec(statement).all())


def update(session: Session, user: User) -> User:
    """Persist changes to an already-fetched user and return it."""
    session.add(user)
    session.flush()
    session.refresh(user)
    return user


def delete(session: Session, user: User) -> None:
    """Hard-delete a user record."""
    session.delete(user)
    session.flush()


def count(session: Session) -> int:
    """Return the total number of users in the database."""
    result = session.exec(select(func.count()).select_from(User)).one()
    return int(result)


def count_by_role(session: Session, role: Role) -> int:
    """Return the number of users with the given role."""
    result = session.exec(
        select(func.count()).select_from(User).where(User.role == role)
    ).one()
    return int(result)


def count_by_role_for_update(session: Session, role: Role) -> int:
    """Return role count while locking matching rows for the active transaction."""
    rows = session.exec(
        select(User.id).where(User.role == role).with_for_update()
    ).all()
    return len(rows)


def increment_token_version(session: Session, user_id: uuid.UUID) -> None:
    """Atomically increment token_version, invalidating all issued tokens for this user.

    No-op when the user does not exist. Caller must commit after calling.
    """
    user = session.get(User, user_id)
    if user is not None:
        user.token_version += 1
        session.add(user)
