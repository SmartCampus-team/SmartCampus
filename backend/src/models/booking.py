"""Table bookings : réservations des salles (SC-22).

Le Sprint 2 lit les réservations pour la recherche et le planning ; SC-25 les crée.
SC-27 : une contrainte d'exclusion PostgreSQL interdit deux réservations qui occupent la même
salle sur des créneaux qui se chevauchent (RG-01), même si les deux demandes arrivent en même temps.
"""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
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
        # RG-01 (SC-27) : même salle et périodes [début, fin) qui se chevauchent → refusé par PostgreSQL.
        # 10:00-12:00 et 12:00-13:00 ne se chevauchent pas. Seuls les statuts qui occupent la salle comptent.
        # L'index GiST sur room_id demande l'extension btree_gist (migration 0008).
        ExcludeConstraint(
            ("room_id", "="),
            (text("tstzrange(start_at, end_at)"), "&&"),
            name="ex_bookings_no_overlap",
            using="gist",
            where=text("status IN ('en_attente', 'confirmee')"),
        ),
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
