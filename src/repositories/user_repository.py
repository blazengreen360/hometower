"""User repository — sole layer that holds a SQLModel Session for User operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.user import User


def create(session: Session, user: User) -> User:
    """Persist a new user and return the refreshed instance."""
    session.add(user)
    session.commit()
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
    session.commit()
    session.refresh(user)
    return user


def delete(session: Session, user: User) -> None:
    """Hard-delete a user record."""
    session.delete(user)
    session.commit()


def count(session: Session) -> int:
    """Return the total number of users in the database."""
    result = session.exec(select(func.count()).select_from(User)).one()
    return int(result)
