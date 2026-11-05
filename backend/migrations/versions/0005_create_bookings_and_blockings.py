"""Créer les tables des réservations et des blocages (SC-22)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOOKING_STATUSES = ("en_attente", "confirmee", "refusee", "annulee", "non_honoree", "terminee")


def upgrade() -> None:
    
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("holder_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=False),
        sa.Column("participants", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*BOOKING_STATUSES, name="booking_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_bookings_end_after_start"),
        sa.CheckConstraint("participants > 0", name="ck_bookings_participants_positive"),
    )
    op.create_index("ix_bookings_room_start", "bookings", ["room_id", "start_at"])

    op.create_table(
        "blockings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_blockings_end_after_start"),
    )
    op.create_index("ix_blockings_room_start", "blockings", ["room_id", "start_at"])


def downgrade() -> None:
   
    op.drop_index("ix_blockings_room_start", table_name="blockings")
    op.drop_table("blockings")
    op.drop_index("ix_bookings_room_start", table_name="bookings")
    op.drop_table("bookings")
