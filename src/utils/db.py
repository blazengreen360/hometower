"""SQLModel engine, session factory, and FastAPI session dependency."""
from sqlmodel import Session, create_engine

from src.utils.settings import settings

engine = create_engine(settings.database_url)


def get_session():  # type: ignore[return]
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session
