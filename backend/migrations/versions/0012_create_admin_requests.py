"""Créer les demandes administratives, leur historique et la séquence des numéros (SC-34)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES = ("attestation_scolarite", "releve_notes", "certificat_reussite", "demande_stage", "reclamation", "autre")
STATUSES = ("en_attente", "en_cours", "infos_demandees", "acceptee", "refusee", "terminee")


def status(name: str, nullable: bool) -> sa.Column:
    return sa.Column(name, sa.Enum(*STATUSES, name="request_status", native_enum=False, length=30), nullable=nullable)


def upgrade() -> None:
    """Upgrade schema."""
    # NNNNN du numéro DA-AAAA-NNNNN : PostgreSQL ne donne jamais deux fois la même valeur
    op.execute("CREATE SEQUENCE request_number_seq")
    op.create_table(
        "admin_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=20), nullable=False, unique=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "request_type", sa.Enum(*TYPES, name="request_type", native_enum=False, length=30), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=False),
        status("status", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_requests_student", "admin_requests", ["student_id"])
    op.create_index("ix_admin_requests_status_created", "admin_requests", ["status", "created_at"])
    op.create_table(
        "request_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id", sa.Integer(), sa.ForeignKey("admin_requests.id", ondelete="CASCADE"), nullable=False
        ),
        status("from_status", nullable=True),
        status("to_status", nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_request_history_request", "request_history", ["request_id", "created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("request_history")
    op.drop_table("admin_requests")
    op.execute("DROP SEQUENCE request_number_seq")
