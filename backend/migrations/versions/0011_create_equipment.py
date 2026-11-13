"""Créer le catalogue des équipements et leur affectation aux salles (SC-31)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("audiovisuel", "informatique", "mobilier", "confort", "accessibilite")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=80), nullable=False, unique=True),
        sa.Column(
            "category",
            sa.Enum(*CATEGORIES, name="equipment_category", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "room_equipment",
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("room_equipment")
    op.drop_table("equipment")
