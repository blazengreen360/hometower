"""017 — add explicit unique constraints for services/custom_fields/tags.

Revision ID: 017
Revises: 016
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_service_device_name",
        "services",
        ["device_id", "name"],
    )
    op.create_unique_constraint(
        "uq_custom_field_device_key",
        "custom_fields",
        ["device_id", "key"],
    )
    op.create_unique_constraint(
        "uq_tag_name",
        "tags",
        ["name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tag_name", "tags", type_="unique")
    op.drop_constraint("uq_custom_field_device_key", "custom_fields", type_="unique")
    op.drop_constraint("uq_service_device_name", "services", type_="unique")
