"""Interdire les réservations qui se chevauchent (SC-27)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OCCUPYING = "('en_attente', 'confirmee')"


def upgrade() -> None:
    """Upgrade schema."""
    # Index GiST sur un entier (room_id WITH =) ; extension de confiance, créée par le propriétaire de la base
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Un doublon créé pendant les essais de SC-25 empêcherait de poser la contrainte :
    # la réservation la plus récente des deux est annulée
    op.execute(
        f"""
        UPDATE bookings AS b SET status = 'annulee'
        WHERE b.status IN {OCCUPYING} AND EXISTS (
            SELECT 1 FROM bookings AS o
            WHERE o.room_id = b.room_id AND o.id < b.id AND o.status IN {OCCUPYING}
              AND o.start_at < b.end_at AND o.end_at > b.start_at
        )
        """
    )
    # Même salle (=) et périodes [début, fin) qui se chevauchent (&&) : refusé, pour les statuts qui occupent la salle
    op.execute(
        f"""
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_no_overlap
        EXCLUDE USING gist (room_id WITH =, tstzrange(start_at, end_at) WITH &&)
        WHERE (status IN {OCCUPYING})
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ex_bookings_no_overlap", "bookings")
