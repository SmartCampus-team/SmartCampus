"""Ajouter la date et le motif d'annulation des réservations, et le délai d'annulation (SC-29)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTICE_KEY = "cancellation_notice_hours"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("bookings", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("cancel_reason", sa.String(length=200), nullable=True))
    # Délai d'annulation (RG-05), modifiable comme les autres règles de gestion (SC-59)
    settings = sa.table("settings", sa.column("key"), sa.column("value"), sa.column("description"))
    op.bulk_insert(
        settings,
        [{"key": NOTICE_KEY, "value": "2", "description": "Annulation possible jusqu'à N heures avant le début (RG-05)"}],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DELETE FROM settings WHERE key = '{NOTICE_KEY}'")
    op.drop_column("bookings", "cancel_reason")
    op.drop_column("bookings", "cancelled_at")
