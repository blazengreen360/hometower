"""026 - add device power and typed power settings singleton (HT-044).

Revision ID: 026
Revises: 025
Create Date: 2026-04-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("power_watts", sa.Integer(), nullable=True),
    )

    op.create_table(
        "power_settings",
        sa.Column("scope", sa.String(length=16), primary_key=True, nullable=False),
        sa.Column("cost_per_kwh", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_check_constraint(
        "ck_power_settings_scope_global",
        "power_settings",
        "scope = 'global'",
    )
    op.create_check_constraint(
        "ck_power_settings_rate_currency_pair",
        "power_settings",
        "(cost_per_kwh IS NULL AND currency IS NULL) OR "
        "(cost_per_kwh IS NOT NULL AND currency IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_power_settings_rate_non_negative",
        "power_settings",
        "cost_per_kwh IS NULL OR cost_per_kwh >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_power_settings_rate_non_negative",
        "power_settings",
        type_="check",
    )
    op.drop_constraint(
        "ck_power_settings_rate_currency_pair",
        "power_settings",
        type_="check",
    )
    op.drop_constraint(
        "ck_power_settings_scope_global",
        "power_settings",
        type_="check",
    )
    op.drop_table("power_settings")

    op.drop_column("devices", "power_watts")