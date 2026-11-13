"""Table rooms : référentiel des salles (SC-20 : EF-ROOM-04).

Les équipements arrivent avec le catalogue de SC-31 (Sprint 3).
"""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class RoomType(enum.StrEnum):
    AMPHITHEATRE = "amphitheatre"
    SALLE_COURS = "salle_cours"
    SALLE_TD = "salle_td"
    SALLE_TP = "salle_tp"
    SALLE_TRAVAIL = "salle_travail"


class RoomStatus(enum.StrEnum):
    ACTIVE = "active"
    # Panne ou travaux : la salle reste visible mais ne se réserve pas (RG-10, SC-53 au Sprint 5)
    HORS_SERVICE = "hors_service"
    # Retirée du référentiel ; jamais supprimée, pour garder ses réservations passées
    ARCHIVEE = "archivee"


def _values(items: type[enum.StrEnum]) -> list[str]:
    return [item.value for item in items]


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Code affiché sur la porte, unique : A-101, AMPHI-A
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    building: Mapped[str] = mapped_column(String(80))
    room_type: Mapped[RoomType] = mapped_column(
        Enum(RoomType, name="room_type", native_enum=False, length=20, values_callable=_values)
    )
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status", native_enum=False, length=20, values_callable=_values),
        default=RoomStatus.ACTIVE,
        server_default=RoomStatus.ACTIVE.value,
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
