"""Consultation des salles (SC-20, SC-21 : EF-ROOM-01) et recherche d'une salle libre
(SC-22 : EF-ROOM-02, RG-03, RG-08, RG-10)."""

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import Select, and_, exists, or_, select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.blocking import Blocking
from src.models.booking import OCCUPYING_STATUSES, Booking
from src.models.room import Room, RoomStatus, RoomType
from src.services import campus_clock
from src.services.common import ServiceError

ROOM_NOT_FOUND = "Salle introuvable."
CLOSED_DAY = "Le campus est fermé le dimanche : choisissez un jour du lundi au samedi."
SLOT_STEP = "Les créneaux vont par pas de {step} min (par exemple 10:00 ou 10:30)."
OPENING_HOURS = "Les créneaux vont de {opening:%H:%M} à {closing:%H:%M}."
END_BEFORE_START = "L'heure de fin doit être après l'heure de début."
SLOT_PASSED = "Ce créneau est déjà passé : choisissez un créneau à venir."


@dataclass
class RoomFilters:
    """Critères de la liste des salles (SC-21)."""

    query: str | None = None  # code ou bâtiment, sans tenir compte des majuscules
    building: str | None = None
    room_type: RoomType | None = None
    min_capacity: int | None = None  # nombre de participants (RG-08)


def apply_filters(statement: Select[tuple[Room]], filters: RoomFilters) -> Select[tuple[Room]]:
    if filters.query and filters.query.strip():
        pattern = f"%{filters.query.strip()}%"
        statement = statement.where(or_(Room.code.ilike(pattern), Room.building.ilike(pattern)))
    if filters.building:
        statement = statement.where(Room.building == filters.building)
    if filters.room_type:
        statement = statement.where(Room.room_type == filters.room_type)
    if filters.min_capacity:
        statement = statement.where(Room.capacity >= filters.min_capacity)
    return statement


def list_rooms(db: Session, include_archived: bool = False, filters: RoomFilters | None = None) -> list[Room]:
    """Salles triées par bâtiment puis code ; les archivées seulement sur demande."""
    statement = select(Room)
    if not include_archived:
        statement = statement.where(Room.status != RoomStatus.ARCHIVEE)
    if filters is not None:
        statement = apply_filters(statement, filters)
    return list(db.scalars(statement.order_by(Room.building, Room.code)))


def get_room(db: Session, room_id: int, include_archived: bool = False) -> Room:
    """Une salle ; 404 si elle n'existe pas, ou si elle est archivée et que ce n'est pas demandé."""
    room = db.get(Room, room_id)
    if room is None or (room.status == RoomStatus.ARCHIVEE and not include_archived):
        raise ServiceError(404, ROOM_NOT_FOUND)
    return room


def check_slot(day: date, start: time, end: time, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Vérifie un créneau (RG-03) et le renvoie en dates du campus ; 400 avec un message clair sinon."""
    if not campus_clock.is_open_day(day):
        raise ServiceError(400, CLOSED_DAY)
    for moment in (start, end):
        if moment.second or moment.microsecond or moment.minute % settings.slot_minutes:
            raise ServiceError(400, SLOT_STEP.format(step=settings.slot_minutes))
    opening, closing = campus_clock.opening_time(), campus_clock.closing_time()
    if start < opening or end > closing:
        raise ServiceError(400, OPENING_HOURS.format(opening=opening, closing=closing))
    if end <= start:
        raise ServiceError(400, END_BEFORE_START)

    start_at, end_at = campus_clock.at(day, start), campus_clock.at(day, end)
    if end_at <= (now or campus_clock.now()):
        raise ServiceError(400, SLOT_PASSED)
    return start_at, end_at


def find_available(db: Session, day: date, start: time, end: time, filters: RoomFilters) -> list[Room]:
    """Salles actives, assez grandes, sans réservation ni blocage sur le créneau (EF-ROOM-02).

    Deux périodes se chevauchent si chacune commence avant la fin de l'autre :
    10:00-12:00 et 11:30-13:00 se chevauchent ; 10:00-12:00 et 12:00-13:00 non.
    Une réservation confirmée ou en attente de validation occupe la salle (RG-01) ;
    une salle hors service, archivée ou bloquée n'est jamais proposée (RG-10).
    La plus petite salle qui convient vient en premier.
    """
    start_at, end_at = check_slot(day, start, end)
    booked = exists().where(
        and_(
            Booking.room_id == Room.id,
            Booking.status.in_(OCCUPYING_STATUSES),
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        )
    )
    blocked = exists().where(
        and_(Blocking.room_id == Room.id, Blocking.start_at < end_at, Blocking.end_at > start_at)
    )
    statement = select(Room).where(Room.status == RoomStatus.ACTIVE, ~booked, ~blocked)
    statement = apply_filters(statement, filters).order_by(Room.capacity, Room.code)
    return list(db.scalars(statement))
