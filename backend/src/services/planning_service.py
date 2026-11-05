"""Planning d'occupation d'une salle en vue jour ou semaine (SC-23 : EF-ROOM-03, RG-03).

Chaque créneau occupé porte un libellé, pas seulement une couleur : « Réservé »,
« En attente de validation », « Terminé » ou « Bloqué ». Le motif d'une réservation et
son titulaire ne sont visibles que par le titulaire et par le gestionnaire ; le motif
d'un blocage (examen, maintenance) est visible par tous.
"""

import enum
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.blocking import Blocking
from src.models.booking import PLANNING_STATUSES, Booking, BookingStatus
from src.models.room import Room
from src.models.user import Role, User
from src.services import campus_clock


class PlanningView(enum.StrEnum):
    DAY = "day"
    WEEK = "week"


class EntryKind(enum.StrEnum):
    BOOKING = "reservation"
    BLOCKING = "blocage"


BOOKING_LABELS = {
    BookingStatus.CONFIRMEE: "Réservé",
    BookingStatus.EN_ATTENTE: "En attente de validation",
    BookingStatus.TERMINEE: "Terminé",
}
BLOCKING_LABEL = "Bloqué"


@dataclass
class PlanningEntry:
    kind: EntryKind
    id: int
    day: date
    start: time
    end: time
    label: str
    status: BookingStatus | None  # statut de la réservation ; None pour un blocage
    detail: str | None  # motif de la réservation (si visible) ou du blocage
    holder_name: str | None  # titulaire, si visible
    mine: bool


@dataclass
class Planning:
    room: Room
    view: PlanningView
    days: list[date]
    entries: list[PlanningEntry]


def period(day: date, view: PlanningView) -> list[date]:
    """Jours affichés : le jour demandé, ou du lundi au samedi de sa semaine."""
    if view == PlanningView.DAY:
        return [day]
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=offset) for offset in range(6)]


def _slices(start_at: datetime, end_at: datetime, days: list[date]) -> list[tuple[date, time, time]]:
    """Découpe une période par jour affiché, dans les heures d'ouverture du campus."""
    start, end = campus_clock.local(start_at), campus_clock.local(end_at)
    pieces = []
    for day in days:
        opening = campus_clock.at(day, campus_clock.opening_time())
        closing = campus_clock.at(day, campus_clock.closing_time())
        piece_start, piece_end = max(start, opening), min(end, closing)
        if piece_start < piece_end:
            pieces.append((day, piece_start.time(), piece_end.time()))
    return pieces


def build_planning(db: Session, room: Room, day: date, view: PlanningView, viewer: User) -> Planning:
    days = period(day, view)
    start_at = campus_clock.at(days[0], time(0))
    end_at = campus_clock.at(days[-1] + timedelta(days=1), time(0))
    full_view = viewer.role == Role.GESTIONNAIRE
    entries: list[PlanningEntry] = []

    bookings = db.scalars(
        select(Booking)
        .where(
            Booking.room_id == room.id,
            Booking.status.in_(PLANNING_STATUSES),
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        )
        .order_by(Booking.start_at)
    )
    for booking in bookings:
        mine = booking.holder_id == viewer.id
        visible = mine or full_view
        for piece_day, start, end in _slices(booking.start_at, booking.end_at, days):
            entries.append(
                PlanningEntry(
                    kind=EntryKind.BOOKING,
                    id=booking.id,
                    day=piece_day,
                    start=start,
                    end=end,
                    label=BOOKING_LABELS[booking.status],
                    status=booking.status,
                    detail=booking.purpose if visible else None,
                    holder_name=booking.holder.full_name if visible else None,
                    mine=mine,
                )
            )

    blockings = db.scalars(
        select(Blocking)
        .where(Blocking.room_id == room.id, Blocking.start_at < end_at, Blocking.end_at > start_at)
        .order_by(Blocking.start_at)
    )
    for blocking in blockings:
        for piece_day, start, end in _slices(blocking.start_at, blocking.end_at, days):
            entries.append(
                PlanningEntry(
                    kind=EntryKind.BLOCKING,
                    id=blocking.id,
                    day=piece_day,
                    start=start,
                    end=end,
                    label=BLOCKING_LABEL,
                    status=None,
                    detail=blocking.reason,
                    holder_name=None,
                    mine=False,
                )
            )

    entries.sort(key=lambda entry: (entry.day, entry.start))
    return Planning(room=room, view=view, days=days, entries=entries)
