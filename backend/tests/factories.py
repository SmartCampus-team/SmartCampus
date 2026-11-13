"""Outils de test partagés des tickets des Sprints 2 et 3."""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.blocking import Blocking
from src.models.booking import Booking, BookingStatus
from src.models.room import Room, RoomStatus, RoomType
from src.models.setting import Setting
from src.models.user import Role, User
from src.services import campus_clock
from tests.helpers import auth_header, login


# Mêmes valeurs que la migration 0009 (horizon RG-04, quotas RG-07) ; les tests les lisent en base (SC-26)
DEFAULT_SETTINGS = {
    "booking_horizon_days_student": "7",
    "booking_horizon_days_teacher": "30",
    "max_upcoming_bookings_student": "4",
    "max_weekly_hours_student": "8",
    "cancellation_notice_hours": "2",  # migration 0010 (RG-05, SC-29)
}


def set_setting(db: Session, key: str, value: int) -> None:
    """Change une règle de gestion, comme le fera l'écran de SC-59."""
    setting = db.get(Setting, key)
    assert setting is not None
    setting.value = str(value)
    db.commit()


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


def make_booking_at(
    db: Session,
    room: Room,
    holder: User,
    start_at: datetime,
    end_at: datetime,
    status: BookingStatus = BookingStatus.CONFIRMEE,
    purpose: str = "Cours",
) -> Booking:
    """Réservation à une date et heure précises, par exemple déjà commencée (SC-28)."""
    booking = Booking(
        room_id=room.id,
        holder_id=holder.id,
        start_at=start_at,
        end_at=end_at,
        status=status,
        purpose=purpose,
        participants=4,
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


def booking_body(
    room: Room,
    day: date,
    start: str,
    end: str,
    purpose: str = "Révision en groupe",
    participants: int = 4,
) -> dict:
    """Corps de POST /api/bookings (SC-25)."""
    return {
        "room_id": room.id,
        "date": day.isoformat(),
        "start": start,
        "end": end,
        "purpose": purpose,
        "participants": participants,
    }
