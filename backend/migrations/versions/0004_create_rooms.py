"""Créer la table des salles (SC-20)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROOM_TYPES = ("amphitheatre", "salle_cours", "salle_td", "salle_tp", "salle_travail")
ROOM_STATUSES = ("active", "hors_service", "archivee")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("building", sa.String(length=80), nullable=False),
        sa.Column(
            "room_type",
            sa.Enum(*ROOM_TYPES, name="room_type", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*ROOM_STATUSES, name="room_status", native_enum=False, length=20),
            server_default="active",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),
    )
    op.create_index("ix_rooms_code", "rooms", ["code"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rooms_code", table_name="rooms")
    op.drop_table("rooms")
