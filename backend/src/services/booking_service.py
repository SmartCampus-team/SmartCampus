"""Réservation des salles (SC-25 : EF-BOOK-01, RG-03, RG-08, RG-12).

Une réservation est créée « Confirmée » sur un créneau de la grille du campus (RG-03),
dans une salle active assez grande pour ses participants (RG-08, RG-10). Elle n'est jamais
supprimée : elle change de statut (RG-12). Un amphithéâtre ne se réserve pas directement :
la demande validée par le gestionnaire arrive avec SC-50 (RG-09).

Les dates sont stockées en UTC (timestamptz) et affichées à l'heure du campus (Africa/Casablanca).

SC-26 (RG-04, RG-07) : horizon et quotas, lus dans la table settings (quota_service.py).

SC-27 (EF-BOOK-02, RG-01, ENF-06) : une salle n'est jamais attribuée deux fois sur le même créneau.
La salle est verrouillée (SELECT … FOR UPDATE) le temps de vérifier blocages et réservations puis
d'enregistrer : deux demandes simultanées passent l'une après l'autre. La contrainte d'exclusion de
la table bookings reste le dernier filet : si elle refuse, l'API répond aussi 409.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import settings
from src.models.blocking import Blocking
from src.models.booking import OCCUPYING_STATUSES, Booking, BookingStatus
from src.models.room import Room, RoomStatus, RoomType
from src.models.user import Role, User
from src.services import audit_service, campus_clock, quota_service, room_service
from src.services.common import ServiceError

# Rôles qui réservent pour eux-mêmes ; le gestionnaire gère les salles sans réserver
BOOKING_ROLES = (Role.ETUDIANT, Role.ENSEIGNANT)

SLOT_STARTED = "Ce créneau a déjà commencé : choisissez un créneau à venir."
TOO_LONG = "Une réservation dure au plus {duration} pour {who}."
ROOM_OUT_OF_SERVICE = "La salle {code} est hors service : elle ne peut pas être réservée."
AMPHITHEATRE = (
    "Un amphithéâtre ne se réserve pas directement : la demande doit être validée "
    "par le gestionnaire des salles."
)
TOO_MANY_PARTICIPANTS = (
    "La salle {code} compte {capacity} places pour {participants} participants : choisissez une salle plus grande."
)
SLOT_TAKEN = "Créneau déjà réservé : choisissez un autre créneau ou une autre salle."
ROOM_BLOCKED = "Salle bloquée sur ce créneau : {reason}."

# Code d'erreur PostgreSQL d'une contrainte d'exclusion (ex_bookings_no_overlap)
EXCLUSION_VIOLATION = "23P01"

WHO = {Role.ETUDIANT: "un étudiant", Role.ENSEIGNANT: "un enseignant"}


def format_duration(minutes: int) -> str:
    """120 → « 2 h », 90 → « 1 h 30 », 30 → « 30 min »."""
    hours, rest = divmod(minutes, 60)
    if hours == 0:
        return f"{rest} min"
    return f"{hours} h {rest:02d}" if rest else f"{hours} h"


def max_minutes(role: Role) -> int:
    """Durée maximale d'une réservation selon le rôle (RG-03)."""
    if role == Role.ENSEIGNANT:
        return settings.max_booking_minutes_teacher
    return settings.max_booking_minutes_student


def describe(booking: Booking) -> str:
    """« A-101 02/11/2026 10:00–12:00 » : la réservation telle qu'écrite dans AuditLog."""
    start, end = campus_clock.local(booking.start_at), campus_clock.local(booking.end_at)
    return f"{booking.room.code} {start:%d/%m/%Y %H:%M}–{end:%H:%M}"


def check_slot(user: User, day: date, start: time, end: time, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Créneau de la grille (RG-03), pas encore commencé, et pas plus long que permis au rôle."""
    now = now or campus_clock.now()
    start_at, end_at = room_service.check_slot(day, start, end, now)
    if start_at <= now:
        raise ServiceError(400, SLOT_STARTED)
    limit = max_minutes(user.role)
    if end_at - start_at > timedelta(minutes=limit):
        raise ServiceError(400, TOO_LONG.format(duration=format_duration(limit), who=WHO[user.role]))
    return start_at, end_at


def check_room(room: Room, participants: int) -> None:
    """Salle réservable (RG-10, RG-09) et assez grande (RG-08)."""
    if room.status != RoomStatus.ACTIVE:
        raise ServiceError(409, ROOM_OUT_OF_SERVICE.format(code=room.code))
    if room.room_type == RoomType.AMPHITHEATRE:
        raise ServiceError(400, AMPHITHEATRE)
    if participants > room.capacity:
        raise ServiceError(
            400, TOO_MANY_PARTICIPANTS.format(code=room.code, capacity=room.capacity, participants=participants)
        )


def lock_room(db: Session, room_id: int) -> Room:
    """Verrouille la salle jusqu'à la fin de la transaction (RG-01) ; 404 si inconnue ou archivée.

    Une autre réservation ou un blocage de la même salle attend que celle-ci soit enregistrée.
    """
    db.execute(select(Room.id).where(Room.id == room_id).with_for_update())
    return room_service.get_room(db, room_id)


def check_free(db: Session, room: Room, start_at: datetime, end_at: datetime) -> None:
    """409 si un blocage ou une réservation qui occupe la salle (en attente ou confirmée) chevauche le créneau."""
    blocking = db.scalar(
        select(Blocking)
        .where(Blocking.room_id == room.id, Blocking.start_at < end_at, Blocking.end_at > start_at)
        .order_by(Blocking.start_at)
        .limit(1)
    )
    if blocking is not None:
        raise ServiceError(409, ROOM_BLOCKED.format(reason=blocking.reason))

    overlapping = select(Booking.id).where(
        Booking.room_id == room.id,
        Booking.status.in_(OCCUPYING_STATUSES),
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )
    if db.scalar(overlapping.limit(1)) is not None:
        raise ServiceError(409, SLOT_TAKEN)


def save(db: Session) -> None:
    """Écrit en base ; un chevauchement refusé par la contrainte d'exclusion devient une erreur 409 lisible."""
    try:
        db.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) != EXCLUSION_VIOLATION:
            raise
        db.rollback()
        raise ServiceError(409, SLOT_TAKEN) from None


def create_booking(
    db: Session,
    user: User,
    room_id: int,
    day: date,
    start: time,
    end: time,
    purpose: str,
    participants: int,
    ip: str | None,
) -> Booking:
    """Crée une réservation « Confirmée » et l'écrit dans AuditLog ; 400, 404 ou 409 sinon."""
    start_at, end_at = check_slot(user, day, start, end)
    quota_service.check_horizon(db, user, start_at)
    quota_service.check_quotas(db, user, start_at, end_at)
    room = lock_room(db, room_id)  # 404 si inconnue ou archivée
    check_room(room, participants)
    check_free(db, room, start_at, end_at)

    booking = Booking(
        room=room,
        holder=user,
        start_at=start_at,
        end_at=end_at,
        purpose=purpose.strip(),
        participants=participants,
        status=BookingStatus.CONFIRMEE,
    )
    db.add(booking)
    save(db)  # attribue l'identifiant, écrit dans le journal
    target = f"réservation {booking.id} : {describe(booking)}"
    audit_service.record(db, "BOOKING_CREATED", actor=user, target=target, ip=ip)
    db.commit()
    return booking
