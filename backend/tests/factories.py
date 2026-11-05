"""Outils de test partagés des tickets du Sprint 2."""

from collections.abc import Callable
from datetime import date, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.blocking import Blocking
from src.models.booking import Booking, BookingStatus
from src.models.room import Room, RoomStatus, RoomType
from src.models.user import Role, User
from src.services import campus_clock
from tests.helpers import auth_header, login


def headers_for(
    client: TestClient, make_user: Callable[..., User], role: Role = Role.ETUDIANT
) -> dict[str, str]:
    """Crée un compte du rôle demandé, le connecte et renvoie l'en-tête Authorization (SC-17)."""
    email = f"{role.value}@usms.ac.ma"
    make_user(email=email, role=role)
    token = login(client, email=email).json()["access_token"]
    return auth_header(token)


def make_room(
    db: Session,
    code: str = "A-101",
    building: str = "Bâtiment A",
    room_type: RoomType = RoomType.SALLE_COURS,
    capacity: int = 30,
    status: RoomStatus = RoomStatus.ACTIVE,
    description: str | None = None,
) -> Room:
    """Salle enregistrée directement en base (SC-20)."""
    room = Room(
        code=code,
        building=building,
        room_type=room_type,
        capacity=capacity,
        status=status,
        description=description,
    )
    db.add(room)
    db.commit()
    return room


def open_day(offset: int = 1) -> date:
    """Un jour ouvré (lundi à samedi) situé au moins `offset` jours après aujourd'hui (SC-22)."""
    return campus_clock.next_open_day(campus_clock.today() + timedelta(days=offset))


def make_booking(
    db: Session,
    room: Room,
    holder: User,
    day: date,
    start: time,
    end: time,
    status: BookingStatus = BookingStatus.CONFIRMEE,
    purpose: str = "Cours",
    participants: int = 10,
) -> Booking:
    """Réservation enregistrée directement en base : les routes arrivent avec SC-25 (SC-22)."""
    booking = Booking(
        room_id=room.id,
        holder_id=holder.id,
        start_at=campus_clock.at(day, start),
        end_at=campus_clock.at(day, end),
        status=status,
        purpose=purpose,
        participants=participants,
    )
    db.add(booking)
    db.commit()
    return booking


def make_blocking(db: Session, room: Room, day: date, start: time, end: time, reason: str = "Examen") -> Blocking:
    """Blocage enregistré directement en base : les routes arrivent avec SC-32 (SC-22)."""
    blocking = Blocking(
        room_id=room.id,
        start_at=campus_clock.at(day, start),
        end_at=campus_clock.at(day, end),
        reason=reason,
    )
    db.add(blocking)
    db.commit()
    return blocking
