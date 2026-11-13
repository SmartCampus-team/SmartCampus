"""Interdire les réservations qui se chevauchent (SC-27 : EF-BOOK-02, RG-01, ENF-06)."""

import threading
from datetime import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.database import SessionLocal
from src.models.booking import OCCUPYING_STATUSES, Booking, BookingStatus
from src.models.user import Role, User
from src.services import booking_service
from src.services.common import ServiceError
from tests.factories import booking_body, headers_for, make_blocking, make_booking, make_room, open_day

URL = "/api/bookings"
SLOT_TAKEN = "Créneau déjà réservé : choisissez un autre créneau ou une autre salle."


@pytest.fixture
def room(db):
    return make_room(db, code="A-101", capacity=30)


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def teacher(make_user):
    return make_user(email="prof@usms.ac.ma", role=Role.ENSEIGNANT)


def book(client, headers, room, start, end, day=None):
    return client.post(URL, json=booking_body(room, day or open_day(), start, end), headers=headers)


# Chevauchements refusés par l'API, avec un message lisible


def test_overlapping_booking_is_refused(client, db, room, student, teacher):
    make_booking(db, room, teacher, open_day(), time(10), time(12))
    response = book(client, student, room, "11:00", "11:30")
    assert response.status_code == 409
    assert response.json()["detail"] == SLOT_TAKEN


@pytest.mark.parametrize(("start", "end"), [("12:00", "13:00"), ("08:00", "10:00")])
def test_back_to_back_booking_is_accepted(client, db, room, student, teacher, start, end):
    make_booking(db, room, teacher, open_day(), time(10), time(12))
    assert book(client, student, room, start, end).status_code == 201


def test_pending_booking_also_occupies_the_slot(client, db, room, student, teacher):
    make_booking(db, room, teacher, open_day(), time(10), time(12), status=BookingStatus.EN_ATTENTE)
    response = book(client, student, room, "10:00", "11:00")
    assert response.status_code == 409
    assert response.json()["detail"] == SLOT_TAKEN


@pytest.mark.parametrize("status", [BookingStatus.ANNULEE, BookingStatus.REFUSEE])
def test_cancelled_or_refused_booking_frees_the_slot(client, db, room, student, teacher, status):
    make_booking(db, room, teacher, open_day(), time(10), time(12), status=status)
    assert book(client, student, room, "10:00", "12:00").status_code == 201


def test_blocking_on_the_slot_is_refused_with_its_reason(client, db, room, student):
    make_blocking(db, room, open_day(), time(8), time(12), reason="Examen de mi-semestre")
    response = book(client, student, room, "11:30", "12:30")
    assert response.status_code == 409
    assert response.json()["detail"] == "Salle bloquée sur ce créneau : Examen de mi-semestre."


def test_same_slot_in_another_room_is_free(client, db, room, student, teacher):
    other = make_room(db, code="A-102")
    make_booking(db, room, teacher, open_day(), time(10), time(12))
    assert book(client, student, other, "10:00", "12:00").status_code == 201


# Contrainte d'exclusion : PostgreSQL refuse même une écriture qui ne passe pas par l'API


def test_database_refuses_two_overlapping_bookings(db, room, teacher):
    make_booking(db, room, teacher, open_day(), time(10), time(12))
    with pytest.raises(IntegrityError) as error:
        make_booking(db, room, teacher, open_day(), time(11), time(13), status=BookingStatus.EN_ATTENTE)
    assert "ex_bookings_no_overlap" in str(error.value)
    db.rollback()


def test_database_accepts_overlap_with_a_cancelled_booking(db, room, teacher):
    make_booking(db, room, teacher, open_day(), time(10), time(12), status=BookingStatus.ANNULEE)
    make_booking(db, room, teacher, open_day(), time(10), time(12))
    assert db.scalar(select(func.count()).select_from(Booking)) == 2


def test_constraint_violation_becomes_a_readable_409(client, db, room, student, teacher, monkeypatch):
    """Si deux écritures échappent au contrôle de l'API, la contrainte refuse et l'API répond 409."""
    make_booking(db, room, teacher, open_day(), time(10), time(12))
    monkeypatch.setattr(booking_service, "check_free", lambda *args, **kwargs: None)
    response = book(client, student, room, "10:30", "11:30")
    assert response.status_code == 409
    assert response.json()["detail"] == SLOT_TAKEN


def test_other_integrity_errors_are_not_hidden(db, room, make_user):
    """Seul le chevauchement devient un 409 : une autre erreur de base reste une erreur."""
    student = make_user()
    with pytest.raises(IntegrityError):
        booking_service.create_booking(db, student, room.id, open_day(), time(10), time(11), "Révision", 0, None)
    db.rollback()


# Deux demandes simultanées : une seule aboutit


def test_two_simultaneous_requests_only_one_succeeds(db, room, make_user):
    users = [make_user(email=f"etudiant{n}@usms.ac.ma") for n in (1, 2)]
    day = open_day()
    barrier = threading.Barrier(2)
    results: list[str] = []

    def request(user_id: int) -> None:
        with SessionLocal() as session:
            user = session.get(User, user_id)
            barrier.wait()  # les deux demandes partent ensemble
            try:
                booking_service.create_booking(session, user, room.id, day, time(10), time(12), "Révision", 4, None)
                results.append("créée")
            except ServiceError as error:
                results.append(f"{error.status} {error.message}")

    threads = [threading.Thread(target=request, args=(user.id,)) for user in users]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(results) == [f"409 {SLOT_TAKEN}", "créée"]
    db.expire_all()
    occupying = select(func.count()).select_from(Booking).where(Booking.status.in_(OCCUPYING_STATUSES))
    assert db.scalar(occupying) == 1
