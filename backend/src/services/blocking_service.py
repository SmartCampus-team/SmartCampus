"""Bloquer une salle sur une période (SC-32 : EF-ROOM-06, RG-01, RG-10).

Le gestionnaire bloque une salle pour un examen, une maintenance ou un événement. Le blocage
apparaît dans le planning, la recherche exclut la salle et toute réservation y est refusée (SC-27).
Les réservations qui occupaient la période et ne sont pas terminées passent « Annulée » avec le
motif du blocage ; leurs titulaires seront prévenus par SC-54 (Sprint 5).

La salle est verrouillée comme pour une réservation (booking_service.lock_room) : un blocage et
une réservation sur la même salle ne peuvent pas se croiser.
"""

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.blocking import Blocking
from src.models.booking import OCCUPYING_STATUSES, Booking, BookingStatus
from src.models.user import User
from src.services import audit_service, booking_service, campus_clock, room_service
from src.services.common import ServiceError

SLOT_STEP = "Les heures vont par pas de {step} min (par exemple 10:00 ou 10:30)."
OPENING_HOURS = "Les heures vont de {opening:%H:%M} à {closing:%H:%M}."
END_BEFORE_START = "La fin du blocage doit être après son début."
PERIOD_PASSED = "Cette période est déjà passée : choisissez une période à venir."
ALREADY_BLOCKED = "La salle est déjà bloquée du {start:%d/%m/%Y %H:%M} au {end:%d/%m/%Y %H:%M} : {reason}."
BLOCKING_NOT_FOUND = "Blocage introuvable."
BLOCKING_FINISHED = "Ce blocage est terminé : il reste dans l'historique de la salle."


@dataclass
class BlockingResult:
    blocking: Blocking
    cancelled: list[Booking]  # réservations annulées par le blocage


def describe(blocking: Blocking) -> str:
    """« B-201 12/11/2026 08:00 → 13/11/2026 20:00 : Examen »."""
    start, end = campus_clock.local(blocking.start_at), campus_clock.local(blocking.end_at)
    return f"{blocking.room.code} {start:%d/%m/%Y %H:%M} → {end:%d/%m/%Y %H:%M} : {blocking.reason}"


def check_period(
    start_day: date, start: time, end_day: date, end: time, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Début et fin sur la grille du campus (pas de 30 min, 08:00–20:00), fin après début et à venir."""
    for moment in (start, end):
        if moment.second or moment.microsecond or moment.minute % settings.slot_minutes:
            raise ServiceError(400, SLOT_STEP.format(step=settings.slot_minutes))
        if not campus_clock.opening_time() <= moment <= campus_clock.closing_time():
            opening, closing = campus_clock.opening_time(), campus_clock.closing_time()
            raise ServiceError(400, OPENING_HOURS.format(opening=opening, closing=closing))
    start_at, end_at = campus_clock.at(start_day, start), campus_clock.at(end_day, end)
    if end_at <= start_at:
        raise ServiceError(400, END_BEFORE_START)
    if end_at <= (now or campus_clock.now()):
        raise ServiceError(400, PERIOD_PASSED)
    return start_at, end_at


def list_blockings(db: Session, room_id: int, now: datetime | None = None) -> list[Blocking]:
    """Blocages en cours ou à venir de la salle, le plus proche d'abord."""
    room = room_service.get_room(db, room_id, include_archived=True)
    return list(
        db.scalars(
            select(Blocking)
            .where(Blocking.room_id == room.id, Blocking.end_at > (now or campus_clock.now()))
            .order_by(Blocking.start_at)
        )
    )


def create_blocking(
    db: Session,
    room_id: int,
    start_day: date,
    start: time,
    end_day: date,
    end: time,
    reason: str,
    actor: User,
    ip: str | None,
    now: datetime | None = None,
) -> BlockingResult:
    """Bloque la salle et annule les réservations non terminées de la période ; tout est journalisé."""
    now = now or campus_clock.now()
    start_at, end_at = check_period(start_day, start, end_day, end, now)
    room = booking_service.lock_room(db, room_id)  # 404 si inconnue ou archivée

    existing = db.scalar(
        select(Blocking)
        .where(Blocking.room_id == room.id, Blocking.start_at < end_at, Blocking.end_at > start_at)
        .order_by(Blocking.start_at)
        .limit(1)
    )
    if existing is not None:
        start_local, end_local = campus_clock.local(existing.start_at), campus_clock.local(existing.end_at)
        raise ServiceError(409, ALREADY_BLOCKED.format(start=start_local, end=end_local, reason=existing.reason))

    reason = reason.strip()
    blocking = Blocking(room=room, start_at=start_at, end_at=end_at, reason=reason, author_id=actor.id)
    db.add(blocking)

    # Réservations de la période qui ne sont pas encore terminées : annulées avec le motif (RG-10)
    cancelled = list(
        db.scalars(
            select(Booking)
            .where(
                Booking.room_id == room.id,
                Booking.status.in_(OCCUPYING_STATUSES),
                Booking.start_at < end_at,
                Booking.end_at > start_at,
                Booking.end_at > now,
            )
            .order_by(Booking.start_at)
        )
    )
    for booking in cancelled:
        booking.status = BookingStatus.ANNULEE
        booking.cancelled_at = now
        booking.cancel_reason = f"Salle bloquée : {reason}"[:200]
        target = f"réservation {booking.id} : {booking_service.describe(booking)} (blocage)"
        audit_service.record(db, "BOOKING_CANCELLED", actor=actor, target=target, ip=ip)

    db.flush()
    plural = "s" if len(cancelled) > 1 else ""
    target = f"{describe(blocking)} ; {len(cancelled)} réservation{plural} annulée{plural}"
    audit_service.record(db, "BLOCKING_CREATED", actor=actor, target=target[:255], ip=ip)
    db.commit()
    return BlockingResult(blocking=blocking, cancelled=cancelled)


def remove_blocking(db: Session, room_id: int, blocking_id: int, actor: User, ip: str | None) -> None:
    """Lève un blocage en cours ou à venir ; les réservations annulées ne sont pas rétablies."""
    blocking = db.get(Blocking, blocking_id)
    if blocking is None or blocking.room_id != room_id:
        raise ServiceError(404, BLOCKING_NOT_FOUND)
    if blocking.end_at <= campus_clock.now():
        raise ServiceError(409, BLOCKING_FINISHED)
    audit_service.record(db, "BLOCKING_REMOVED", actor=actor, target=describe(blocking)[:255], ip=ip)
    db.delete(blocking)
    db.commit()
