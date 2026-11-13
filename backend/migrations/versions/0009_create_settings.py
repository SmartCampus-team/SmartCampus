"""Créer la table settings et les valeurs par défaut de l'horizon et des quotas (SC-26)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Valeurs par défaut des règles de gestion (cahier des charges) ; SC-59 permettra de les modifier
DEFAULT_SETTINGS = [
    ("booking_horizon_days_student", "7", "Un étudiant réserve au plus N jours à l'avance (RG-04)"),
    ("booking_horizon_days_teacher", "30", "Un enseignant réserve au plus N jours à l'avance (RG-04)"),
    ("max_upcoming_bookings_student", "4", "Réservations à venir au plus pour un étudiant (RG-07)"),
    ("max_weekly_hours_student", "8", "Heures de réservation par semaine au plus pour un étudiant (RG-07)"),
]


def upgrade() -> None:
    """Upgrade schema."""
    settings = op.create_table(
        "settings",
        sa.Column("key", sa.String(length=60), primary_key=True),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.bulk_insert(
        settings,
        [{"key": key, "value": value, "description": description} for key, value, description in DEFAULT_SETTINGS],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("settings")
