"""Table blockings : salles bloquées sur une période (examen, maintenance, événement) (SC-22).

Le Sprint 2 lit les blocages pour la recherche et le planning ; SC-32 (Sprint 3) ajoutera
leur création par le gestionnaire. Une salle bloquée ne peut pas être réservée (RG-10).
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.room import Room


class Blocking(Base):
    __tablename__ = "blockings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_blockings_end_after_start"),
        Index("ix_blockings_room_start", "room_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Motif affiché dans le planning : « Examen de mi-semestre », « Maintenance »
    reason: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped[Room] = relationship()
