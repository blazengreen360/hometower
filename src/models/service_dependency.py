"""ServiceDependency SQLModel (HT-023) — join table for service-to-service dependencies."""
import uuid

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class ServiceDependency(SQLModel, table=True):
    __tablename__ = "service_dependencies"
    __table_args__ = (
        CheckConstraint(
            "service_id <> depends_on_id",
            name="ck_service_dep_no_self_ref",
        ),
    )

    service_id: uuid.UUID = Field(
        foreign_key="services.id", ondelete="CASCADE", primary_key=True
    )
    depends_on_id: uuid.UUID = Field(
        foreign_key="services.id", ondelete="CASCADE", primary_key=True
    )


class DependencyCreate(SQLModel):
    depends_on: uuid.UUID
