"""Réservations des salles (SC-25 : EF-BOOK-01) et « Mes réservations » (SC-28 : EF-BOOK-03)."""

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
from src.models.user import User
from src.services import booking_service, campus_clock
from src.services.booking_service import BOOKING_ROLES

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

Booker = Annotated[User, Depends(require_roles(*BOOKING_ROLES))]
Db = Annotated[Session, Depends(get_db)]

Purpose = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class BookingCreate(BaseModel):
    room_id: int
    date: Date = Field(description="Jour, AAAA-MM-JJ")
    start: time = Field(description="Début, HH:MM")
    end: time = Field(description="Fin, HH:MM")
    purpose: Purpose = Field(examples=["Révision en groupe"])
    participants: int = Field(ge=1, le=1000)


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


def booking_out(booking: Booking) -> BookingOut:
    start, end = campus_clock.local(booking.start_at), campus_clock.local(booking.end_at)
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
    mine = booking_service.list_mine(db, user)
    return MyBookingsOut(
        upcoming=[booking_out(booking) for booking in mine.upcoming],
        past=[booking_out(booking) for booking in mine.past],
        cancelled=[booking_out(booking) for booking in mine.cancelled],
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
    return booking_out(booking)
