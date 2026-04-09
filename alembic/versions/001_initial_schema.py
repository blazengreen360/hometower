"""Initial schema — users table, enum type, index, and updated_at trigger.

Revision ID: 001
Revises:
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL native enum type for user roles (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM ('Admin', 'Contributor', 'Reader');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        "users",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            PG_ENUM("Admin", "Contributor", "Reader", name="user_role", create_type=False),
            nullable=False,
            server_default="Contributor",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="TRUE"),
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
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_index("idx_users_email", "users", ["email"])

    # Trigger function to keep updated_at in sync
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE 'plpgsql';
        """
    )

    op.execute(
        """
        CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")
