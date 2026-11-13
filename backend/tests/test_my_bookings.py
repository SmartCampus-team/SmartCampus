"""Consulter « Mes réservations » (SC-28 : EF-BOOK-03, RG-12)."""

from datetime import time, timedelta

import pytest

from src.models.booking import BookingStatus
from src.models.user import Role
from src.services import campus_clock
from tests.factories import headers_for, make_booking, make_booking_at, make_room, open_day
from tests.helpers import reload_user

URL = "/api/bookings/me"


@pytest.fixture
def room(db):
    return make_room(db, code="A-101", capacity=30)


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def me(db, student):
    return reload_user(db, "etudiant@usms.ac.ma")


def purposes(bookings: list[dict]) -> list[str]:
    return [booking["purpose"] for booking in bookings]


def test_my_bookings_requires_a_token(client):
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize("role", [Role.GESTIONNAIRE, Role.SCOLARITE, Role.ADMINISTRATEUR])
def test_only_students_and_teachers_have_bookings(client, make_user, role):
    assert client.get(URL, headers=headers_for(client, make_user, role)).status_code == 403


def test_no_booking_gives_three_empty_tabs(client, student):
    response = client.get(URL, headers=student)
    assert response.status_code == 200
    assert response.json() == {"upcoming": [], "past": [], "cancelled": []}


def test_bookings_are_split_into_upcoming_past_and_cancelled(client, db, room, student, me):
    day = open_day()
    yesterday = campus_clock.today() - timedelta(days=1)
    now = campus_clock.now()
    make_booking(db, room, me, day + timedelta(days=1), time(10), time(11), purpose="Plus tard")
    make_booking(db, room, me, day, time(10), time(11), purpose="Bientôt", status=BookingStatus.EN_ATTENTE)
    make_booking_at(db, room, me, now - timedelta(minutes=30), now + timedelta(minutes=30), purpose="En cours")
    make_booking(db, room, me, yesterday, time(8), time(9), purpose="Hier")
    make_booking(db, room, me, yesterday - timedelta(days=1), time(8), time(9), purpose="Avant-hier",
                 status=BookingStatus.TERMINEE)
    make_booking(db, room, me, day, time(14), time(15), purpose="Annulée", status=BookingStatus.ANNULEE)
    make_booking(db, room, me, day + timedelta(days=1), time(14), time(15), purpose="Refusée",
                 status=BookingStatus.REFUSEE)

    body = client.get(URL, headers=student).json()
    assert purposes(body["upcoming"]) == ["En cours", "Bientôt", "Plus tard"]  # la plus proche d'abord
    assert purposes(body["past"]) == ["Hier", "Avant-hier"]  # la plus récente d'abord
    assert purposes(body["cancelled"]) == ["Refusée", "Annulée"]


def test_each_line_shows_room_date_times_purpose_and_status(client, db, room, student, me):
    day = open_day()
    make_booking(db, room, me, day, time(10), time(12), purpose="Révision", participants=6)
    [line] = client.get(URL, headers=student).json()["upcoming"]
    assert line["room"]["code"] == "A-101"
    assert (line["date"], line["start"], line["end"]) == (day.isoformat(), "10:00:00", "12:00:00")
    assert (line["purpose"], line["participants"], line["status"]) == ("Révision", 6, "confirmee")


def test_i_only_see_my_own_bookings(client, db, make_user, room, student, me):
    other = make_user(email="autre@usms.ac.ma")
    make_booking(db, room, other, open_day(), time(8), time(9), purpose="Pas à moi")
    make_booking(db, room, me, open_day(), time(10), time(11), purpose="À moi")
    body = client.get(URL, headers=student).json()
    assert purposes(body["upcoming"] + body["past"] + body["cancelled"]) == ["À moi"]
