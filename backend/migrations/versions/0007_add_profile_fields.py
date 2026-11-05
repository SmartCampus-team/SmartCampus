"""Ajouter le téléphone, la photo et le canal de notification aux comptes (SC-19)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHANNELS = ("les_deux", "email", "application")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "notification_channel",
            sa.Enum(*CHANNELS, name="notification_channel", native_enum=False, length=20),
            server_default="les_deux",
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("photo", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("photo_type", sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "photo_type")
    op.drop_column("users", "photo")
    op.drop_column("users", "notification_channel")
    op.drop_column("users", "phone")
