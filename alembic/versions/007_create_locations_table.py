"""007 — create locations table and location_type enum.

Revision ID: 007
Revises: 006
Create Date: 2026-04-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, UUID as PG_UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL native enum type for location types (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE location_type AS ENUM ('rack', 'geo');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        "locations",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            PG_ENUM("rack", "geo", name="location_type", create_type=False),
            nullable=False,
        ),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("rack", sa.String(64), nullable=True),
        sa.Column("row", sa.String(64), nullable=True),
        sa.Column(
            "parent_id",
            PG_UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["locations.id"],
            ondelete="RESTRICT",
        ),
    )

    op.create_index("ix_locations_type", "locations", ["type"])

    op.execute(
        """
        CREATE TRIGGER update_locations_updated_at
        BEFORE UPDATE ON locations
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_locations_updated_at ON locations")
    op.drop_index("ix_locations_type", table_name="locations")
    op.drop_table("locations")
    op.execute("DROP TYPE IF EXISTS location_type")
