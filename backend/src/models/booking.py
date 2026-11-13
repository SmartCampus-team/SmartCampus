"""Table bookings : réservations des salles (SC-22).

Le Sprint 2 ne fait que lire les réservations, pour exclure les créneaux occupés de la
recherche et les afficher dans le planning. SC-25 (Sprint 3) ajoutera leur création,
SC-27 la contrainte d'exclusion qui interdit les chevauchements (RG-01).
"""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.room import Room
from src.models.user import User


class BookingStatus(enum.StrEnum):
    EN_ATTENTE = "en_attente"
    CONFIRMEE = "confirmee"
    REFUSEE = "refusee"
    ANNULEE = "annulee"
    NON_HONOREE = "non_honoree"
    TERMINEE = "terminee"


# RG-01 : une réservation confirmée ou en attente de validation occupe la salle
OCCUPYING_STATUSES = (BookingStatus.EN_ATTENTE, BookingStatus.CONFIRMEE)

# Statuts affichés dans le planning : une réservation annulée ou refusée libère la salle
PLANNING_STATUSES = (*OCCUPYING_STATUSES, BookingStatus.TERMINEE)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_bookings_end_after_start"),
        CheckConstraint("participants > 0", name="ck_bookings_participants_positive"),
        Index("ix_bookings_room_start", "room_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    holder_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Dates stockées en UTC (timestamptz), affichées dans le fuseau du campus
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    purpose: Mapped[str] = mapped_column(String(200))
    participants: Mapped[int] = mapped_column(Integer)
    # Une réservation n'est jamais supprimée : elle change de statut (RG-12)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            native_enum=False,
            length=20,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=BookingStatus.CONFIRMEE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped[Room] = relationship()
    holder: Mapped[User] = relationship()
