"""Réservations des salles (SC-25 : EF-BOOK-01), « Mes réservations » (SC-28 : EF-BOOK-03),
annulation (SC-29 : EF-BOOK-04, RG-05) et modification (SC-30 : EF-BOOK-05)."""

from datetime import date as Date
from datetime import datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.api.routes.rooms import client_ip
from src.database import get_db
from src.models.booking import Booking, BookingStatus
from src.models.room import RoomType
from src.models.user import Role, User
from src.services import booking_service, campus_clock
from src.services.booking_service import BOOKING_ROLES, BookingChanges, CancelRules

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

Booker = Annotated[User, Depends(require_roles(*BOOKING_ROLES))]
# Le titulaire annule sa réservation ; le gestionnaire annule n'importe laquelle (SC-29)
Canceller = Annotated[User, Depends(require_roles(*BOOKING_ROLES, Role.GESTIONNAIRE))]
Db = Annotated[Session, Depends(get_db)]

Purpose = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class BookingCreate(BaseModel):
    room_id: int
    date: Date = Field(description="Jour, AAAA-MM-JJ")
    start: time = Field(description="Début, HH:MM")
    end: time = Field(description="Fin, HH:MM")
    purpose: Purpose = Field(examples=["Révision en groupe"])
    participants: int = Field(ge=1, le=1000)


class BookingUpdate(BaseModel):
    """Seuls les champs envoyés changent (SC-30)."""

    room_id: int | None = None
    date: Date | None = None
    start: time | None = None
    end: time | None = None
    purpose: Purpose | None = None
    participants: int | None = Field(default=None, ge=1, le=1000)


class BookingRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    building: str
    room_type: RoomType
    capacity: int


class BookingOut(BaseModel):
    """Une réservation, avec ses horaires à l'heure du campus."""

    id: int
    room: BookingRoomOut
    date: Date
    start: time
    end: time
    purpose: str
    participants: int
    status: BookingStatus
    created_at: datetime
    # Annulation (SC-29) : bouton actif ou non, et pourquoi ; date et motif une fois annulée
    can_cancel: bool
    cancel_refusal: str | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    # Modification (SC-30) : réservation non commencée, par son titulaire
    can_edit: bool


class BookingCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=200, description="Motif, facultatif")


def booking_out(booking: Booking, rules: CancelRules) -> BookingOut:
    start, end = campus_clock.local(booking.start_at), campus_clock.local(booking.end_at)
    refusal = rules.refusal(booking)
    return BookingOut(
        id=booking.id,
        room=BookingRoomOut.model_validate(booking.room),
        date=start.date(),
        start=start.time(),
        end=end.time(),
        purpose=booking.purpose,
        participants=booking.participants,
        status=booking.status,
        created_at=booking.created_at,
        can_cancel=refusal is None,
        cancel_refusal=refusal.message if refusal else None,
        cancelled_at=booking.cancelled_at,
        cancel_reason=booking.cancel_reason,
        can_edit=booking_service.can_edit(booking, rules.user, rules.now),
    )


class MyBookingsOut(BaseModel):
    """Les trois onglets de « Mes réservations »."""

    upcoming: list[BookingOut]
    past: list[BookingOut]
    cancelled: list[BookingOut]


@router.get("/me", response_model=MyBookingsOut)
def my_bookings(user: Booker, db: Db) -> MyBookingsOut:
    """Mes réservations à venir (la plus proche d'abord), passées et annulées (les plus récentes d'abord).

    Seules les réservations de l'utilisateur connecté sont renvoyées (RG-12).
    """
    rules = booking_service.cancel_rules(db, user)
    mine = booking_service.list_mine(db, user, rules.now)
    return MyBookingsOut(
        upcoming=[booking_out(booking, rules) for booking in mine.upcoming],
        past=[booking_out(booking, rules) for booking in mine.past],
        cancelled=[booking_out(booking, rules) for booking in mine.cancelled],
    )


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(body: BookingCreate, request: Request, user: Booker, db: Db) -> BookingOut:
    """Réserve une salle sur un créneau : la réservation est créée « Confirmée ».

    400 : créneau hors grille ou déjà commencé, trop long pour le rôle (2 h étudiant, 4 h enseignant),
    trop de participants pour la salle, amphithéâtre ; 404 : salle inconnue ou archivée ;
    409 : salle hors service ; 403 : rôle qui ne réserve pas.
    """
    booking = booking_service.create_booking(
        db, user, body.room_id, body.date, body.start, body.end, body.purpose, body.participants, client_ip(request)
    )
    return booking_out(booking, booking_service.cancel_rules(db, user))


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int, request: Request, user: Canceller, db: Db, body: BookingCancel | None = None
) -> BookingOut:
    """Annule une réservation : elle passe « Annulée » et le créneau redevient libre ; jamais supprimée.

    Le titulaire annule jusqu'à 2 h avant le début (RG-05) ; le gestionnaire à tout moment.
    404 : réservation inconnue ou d'un autre utilisateur ; 409 : déjà annulée, terminée ou trop tard.
    """
    reason = body.reason if body else None
    booking = booking_service.cancel_booking(db, user, booking_id, reason, client_ip(request))
    return booking_out(booking, booking_service.cancel_rules(db, user))


@router.patch("/{booking_id}", response_model=BookingOut)
def update_booking(booking_id: int, body: BookingUpdate, request: Request, user: Booker, db: Db) -> BookingOut:
    """Modifie une réservation non commencée : autre créneau, autre salle, motif ou participants.

    Mêmes contrôles qu'à la création (grille, durée, horizon, quotas, capacité, chevauchements) ;
    si l'un refuse, la réservation d'origine reste intacte. L'ancien et le nouveau créneau sont journalisés.
    409 : réservation commencée, annulée ou créneau pris ; 404 : réservation d'un autre utilisateur.
    """
    changes = BookingChanges(
        room_id=body.room_id,
        day=body.date,
        start=body.start,
        end=body.end,
        purpose=body.purpose,
        participants=body.participants,
    )
    booking = booking_service.update_booking(db, user, booking_id, changes, client_ip(request))
    return booking_out(booking, booking_service.cancel_rules(db, user))
