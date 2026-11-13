"""Réserver un créneau libre (SC-25 : EF-BOOK-01, RG-03, RG-08, RG-12)."""

from datetime import time, timedelta

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.booking import Booking, BookingStatus
from src.models.room import RoomStatus, RoomType
from src.models.user import Role
from src.services import booking_service, campus_clock
from src.services.common import ServiceError
from tests.factories import booking_body, headers_for, make_room, open_day

URL = "/api/bookings"


@pytest.fixture
def room(db):
    return make_room(db, code="A-101", capacity=30)


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def teacher(client, make_user):
    return headers_for(client, make_user, Role.ENSEIGNANT)


def test_booking_requires_a_token(client, room):
    assert client.post(URL, json=booking_body(room, open_day(), "10:00", "12:00")).status_code == 401


def test_free_slot_is_booked_and_confirmed(client, db, room, student):
    day = open_day()
    response = client.post(URL, json=booking_body(room, day, "10:00", "12:00", participants=6), headers=student)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "confirmee"
    assert (body["date"], body["start"], body["end"]) == (day.isoformat(), "10:00:00", "12:00:00")
    assert (body["purpose"], body["participants"]) == ("Révision en groupe", 6)
    assert body["room"] == {
        "id": room.id, "code": "A-101", "building": "Bâtiment A", "room_type": "salle_cours", "capacity": 30,
    }

    # Stockée en UTC avec son fuseau, à l'heure du campus une fois relue
    booking = db.get(Booking, body["id"])
    assert booking.start_at == campus_clock.at(day, time(10))
    assert booking.end_at == campus_clock.at(day, time(12))
    assert booking.status == BookingStatus.CONFIRMEE


def test_new_booking_appears_in_the_planning(client, room, student):
    day = open_day()
    client.post(URL, json=booking_body(room, day, "14:00", "15:30"), headers=student)

    planning = client.get(f"/api/rooms/{room.id}/planning", params={"date": day.isoformat()}, headers=student)
    [entry] = planning.json()["entries"]
    assert (entry["start"], entry["end"], entry["label"], entry["mine"]) == ("14:00:00", "15:30:00", "Réservé", True)


def test_new_booking_takes_the_room_out_of_the_search(client, room, student):
    day = open_day()
    client.post(URL, json=booking_body(room, day, "10:00", "12:00"), headers=student)

    params = {"date": day.isoformat(), "start": "11:00", "end": "11:30"}
    assert client.get("/api/rooms/available", params=params, headers=student).json()["rooms"] == []


def test_each_booking_is_written_in_the_audit_log(client, db, room, student):
    day = open_day()
    booking_id = client.post(URL, json=booking_body(room, day, "10:00", "12:00"), headers=student).json()["id"]

    entry = db.scalar(select(AuditLog).where(AuditLog.action == "BOOKING_CREATED"))
    assert entry.actor_email == "etudiant@usms.ac.ma"
    assert entry.target == f"réservation {booking_id} : A-101 {day:%d/%m/%Y} 10:00–12:00"


# Durée selon le rôle (RG-03)


def test_teacher_can_book_four_hours(client, room, teacher):
    response = client.post(URL, json=booking_body(room, open_day(), "08:00", "12:00"), headers=teacher)
    assert response.status_code == 201


@pytest.mark.parametrize(
    ("role", "end", "message"),
    [
        (Role.ETUDIANT, "12:30", "Une réservation dure au plus 2 h pour un étudiant."),
        (Role.ENSEIGNANT, "14:30", "Une réservation dure au plus 4 h pour un enseignant."),
    ],
)
def test_too_long_booking_is_refused(client, make_user, room, role, end, message):
    headers = headers_for(client, make_user, role)
    response = client.post(URL, json=booking_body(room, open_day(), "10:00", end), headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == message


# Grille horaire (RG-03)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("10:15", "11:00", "Les créneaux vont par pas de 30 min (par exemple 10:00 ou 10:30)."),
        ("07:30", "09:00", "Les créneaux vont de 08:00 à 20:00."),
        ("19:30", "20:30", "Les créneaux vont de 08:00 à 20:00."),
        ("12:00", "10:00", "L'heure de fin doit être après l'heure de début."),
    ],
)
def test_slot_off_the_grid_is_refused(client, room, student, start, end, message):
    response = client.post(URL, json=booking_body(room, open_day(), start, end), headers=student)
    assert response.status_code == 400
    assert response.json()["detail"] == message


def test_sunday_is_refused(client, room, student):
    day = open_day()
    sunday = day + timedelta(days=6 - day.weekday())
    response = client.post(URL, json=booking_body(room, sunday, "10:00", "12:00"), headers=student)
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Le campus est fermé le dimanche")


def test_past_slot_is_refused(client, room, student):
    yesterday = campus_clock.today() - timedelta(days=1)
    response = client.post(URL, json=booking_body(room, yesterday, "10:00", "11:00"), headers=student)
    assert response.status_code == 400


def test_slot_already_started_is_refused(make_user):
    day = open_day()
    user = make_user()
    with pytest.raises(ServiceError) as error:
        booking_service.check_slot(user, day, time(10), time(11), now=campus_clock.at(day, time(10, 15)))
    assert error.value.message == "Ce créneau a déjà commencé : choisissez un créneau à venir."


# Salle (RG-08, RG-09, RG-10)


def test_room_capacity_is_enough(client, room, student):
    response = client.post(URL, json=booking_body(room, open_day(), "10:00", "11:00", participants=30), headers=student)
    assert response.status_code == 201


def test_more_participants_than_capacity_is_refused(client, room, student):
    response = client.post(URL, json=booking_body(room, open_day(), "10:00", "11:00", participants=31), headers=student)
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "La salle A-101 compte 30 places pour 31 participants : choisissez une salle plus grande."
    )


def test_amphitheatre_is_not_booked_directly(client, db, teacher):
    amphi = make_room(db, code="AMPHI-A", room_type=RoomType.AMPHITHEATRE, capacity=200)
    response = client.post(URL, json=booking_body(amphi, open_day(), "10:00", "12:00", participants=80), headers=teacher)
    assert response.status_code == 400
    assert "amphithéâtre" in response.json()["detail"]


def test_room_out_of_service_is_refused(client, db, student):
    room = make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    response = client.post(URL, json=booking_body(room, open_day(), "10:00", "11:00"), headers=student)
    assert response.status_code == 409
    assert response.json()["detail"] == "La salle A-103 est hors service : elle ne peut pas être réservée."


def test_archived_or_unknown_room_is_not_found(client, db, student):
    archived = make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    for room_id in (archived.id, archived.id + 100):
        body = {**booking_body(archived, open_day(), "10:00", "11:00"), "room_id": room_id}
        assert client.post(URL, json=body, headers=student).status_code == 404


# Rôles et saisie


@pytest.mark.parametrize("role", [Role.GESTIONNAIRE, Role.SCOLARITE, Role.ADMINISTRATEUR])
def test_other_roles_cannot_book(client, make_user, room, role):
    headers = headers_for(client, make_user, role)
    assert client.post(URL, json=booking_body(room, open_day(), "10:00", "11:00"), headers=headers).status_code == 403


@pytest.mark.parametrize(("purpose", "participants"), [("   ", 4), ("Révision", 0)])
def test_purpose_and_participants_are_required(client, db, room, student, purpose, participants):
    body = booking_body(room, open_day(), "10:00", "11:00", purpose=purpose, participants=participants)
    assert client.post(URL, json=body, headers=student).status_code == 422
    assert db.scalar(select(Booking)) is None


@pytest.mark.parametrize(("minutes", "text"), [(120, "2 h"), (90, "1 h 30"), (240, "4 h"), (30, "30 min")])
def test_format_duration(minutes, text):
    assert booking_service.format_duration(minutes) == text
