"""Rechercher une salle libre : chevauchements et bornes (SC-22 : EF-ROOM-02, RG-01, RG-03, RG-08, RG-10)."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.models.booking import OCCUPYING_STATUSES, PLANNING_STATUSES, Booking, BookingStatus
from src.models.room import RoomStatus, RoomType
from src.models.user import Role
from src.services import campus_clock, room_service
from src.services.common import ServiceError
from tests.factories import headers_for, make_blocking, make_booking, make_room, open_day

URL = "/api/rooms/available"


@pytest.fixture
def headers(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def teacher(make_user):
    return make_user(email="prof@usms.ac.ma", role=Role.ENSEIGNANT)


def search(client, headers, day: date, start: str, end: str, **filters):
    params = {"date": day.isoformat(), "start": start, "end": end, **filters}
    return client.get(URL, params=params, headers=headers)


def codes(response) -> list[str]:
    return [room["code"] for room in response.json()["rooms"]]


def test_search_requires_a_token(client):
    assert client.get(URL, params={"date": "2026-11-02", "start": "10:00", "end": "12:00"}).status_code == 401


def test_free_room_is_found(client, db, headers):
    make_room(db, code="A-101")
    day = open_day()
    response = search(client, headers, day, "10:00", "12:00")
    assert response.status_code == 200
    body = response.json()
    assert (body["date"], body["start"], body["end"]) == (day.isoformat(), "10:00:00", "12:00:00")
    assert codes(response) == ["A-101"]


# Chevauchements (RG-01)


@pytest.mark.parametrize(
    ("start", "end"),
    [("11:30", "13:00"), ("08:00", "10:30"), ("09:00", "13:00"), ("10:30", "11:30"), ("10:00", "12:00")],
)
def test_overlapping_booking_makes_the_room_unavailable(client, db, headers, teacher, start, end):
    room = make_room(db, code="A-101")
    make_room(db, code="A-102")
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12))
    assert codes(search(client, headers, day, start, end)) == ["A-102"]


@pytest.mark.parametrize(("start", "end"), [("12:00", "13:00"), ("08:00", "10:00")])
def test_back_to_back_slots_do_not_overlap(client, db, headers, teacher, start, end):
    room = make_room(db, code="A-101")
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12))
    assert codes(search(client, headers, day, start, end)) == ["A-101"]


def test_pending_booking_occupies_the_room(client, db, headers, teacher):
    room = make_room(db, code="A-101")
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12), status=BookingStatus.EN_ATTENTE)
    assert codes(search(client, headers, day, "10:00", "12:00")) == []


@pytest.mark.parametrize("status", [BookingStatus.ANNULEE, BookingStatus.REFUSEE, BookingStatus.NON_HONOREE])
def test_cancelled_refused_or_no_show_booking_frees_the_room(client, db, headers, teacher, status):
    room = make_room(db, code="A-101")
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12), status=status)
    assert codes(search(client, headers, day, "10:00", "12:00")) == ["A-101"]


def test_blocking_makes_the_room_unavailable(client, db, headers):
    room = make_room(db, code="A-101")
    make_room(db, code="A-102")
    day = open_day()
    make_blocking(db, room, day, time(8), time(12), reason="Examen")
    assert codes(search(client, headers, day, "11:00", "12:00")) == ["A-102"]
    assert codes(search(client, headers, day, "12:00", "13:00")) == ["A-101", "A-102"]


def test_booking_or_blocking_on_another_day_does_not_matter(client, db, headers, teacher):
    room = make_room(db, code="A-101")
    day = open_day(1)
    other_day = campus_clock.next_open_day(day + timedelta(days=1))
    make_booking(db, room, teacher, day, time(10), time(12))
    make_blocking(db, room, day, time(8), time(20))
    assert codes(search(client, headers, other_day, "10:00", "12:00")) == ["A-101"]


def test_out_of_service_and_archived_rooms_are_never_proposed(client, db, headers):
    make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    assert codes(search(client, headers, open_day(), "10:00", "12:00")) == []


# Capacité et filtres (RG-08)


def test_capacity_and_type_filters(client, db, headers):
    make_room(db, code="A-101", capacity=40)
    make_room(db, code="A-102", room_type=RoomType.SALLE_TD, capacity=30)
    make_room(db, code="C-001", building="Bâtiment C", room_type=RoomType.SALLE_TRAVAIL, capacity=8)
    day = open_day()
    # La plus petite salle qui convient vient en premier
    assert codes(search(client, headers, day, "10:00", "12:00", min_capacity=8)) == ["C-001", "A-102", "A-101"]
    assert codes(search(client, headers, day, "10:00", "12:00", min_capacity=31)) == ["A-101"]
    assert codes(search(client, headers, day, "10:00", "12:00", min_capacity=41)) == []
    assert codes(search(client, headers, day, "10:00", "12:00", room_type="salle_td")) == ["A-102"]
    assert codes(search(client, headers, day, "10:00", "12:00", building="Bâtiment C")) == ["C-001"]


# Bornes du créneau (RG-03)


def next_sunday() -> date:
    day = campus_clock.today() + timedelta(days=1)
    while day.weekday() != 6:
        day += timedelta(days=1)
    return day


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("10:15", "11:00", "pas de 30 min"),
        ("10:00", "11:45", "pas de 30 min"),
        ("07:30", "09:00", "de 08:00 à 20:00"),
        ("19:00", "20:30", "de 08:00 à 20:00"),
        ("12:00", "10:00", "après l'heure de début"),
        ("10:00", "10:00", "après l'heure de début"),
    ],
)
def test_invalid_slots_are_refused_with_a_clear_message(client, db, headers, start, end, message):
    make_room(db)
    response = search(client, headers, open_day(), start, end)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_whole_day_08_to_20_is_accepted(client, db, headers):
    make_room(db)
    assert search(client, headers, open_day(), "08:00", "20:00").status_code == 200


def test_sunday_is_refused(client, headers):
    response = search(client, headers, next_sunday(), "10:00", "12:00")
    assert response.status_code == 400
    assert response.json()["detail"] == room_service.CLOSED_DAY


def test_past_slot_is_refused(client, headers):
    day = campus_clock.today() - timedelta(days=1)
    if not campus_clock.is_open_day(day):
        day -= timedelta(days=1)
    response = search(client, headers, day, "10:00", "12:00")
    assert response.status_code == 400
    assert response.json()["detail"] == room_service.SLOT_PASSED


def test_slot_ending_now_is_already_passed():
    monday = date(2026, 11, 2)
    now = campus_clock.at(monday, time(12))
    with pytest.raises(ServiceError):
        room_service.check_slot(monday, time(10), time(12), now=now)
    start_at, end_at = room_service.check_slot(monday, time(11, 30), time(13), now=now)
    assert end_at - start_at == timedelta(minutes=90)


def test_seconds_are_refused():
    with pytest.raises(ServiceError):
        room_service.check_slot(open_day(), time(10, 0, 30), time(11))


def test_missing_criteria_are_rejected(client, headers):
    assert client.get(URL, params={"date": "2026-11-02"}, headers=headers).status_code == 422
    assert client.get(URL, params={"date": "02/11/2026", "start": "10:00", "end": "12:00"}, headers=headers).status_code == 422


# Modèles et heure du campus


def test_booking_must_end_after_it_starts(db, teacher):
    room = make_room(db)
    with pytest.raises(IntegrityError):
        make_booking(db, room, teacher, open_day(), time(12), time(10))


def test_blocking_must_end_after_it_starts(db):
    room = make_room(db)
    with pytest.raises(IntegrityError):
        make_blocking(db, room, open_day(), time(12), time(10))


def test_booking_is_stored_with_its_time_zone(db, teacher):
    room = make_room(db)
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12))
    db.expire_all()
    booking = db.scalar(select(Booking))
    assert campus_clock.local(booking.start_at) == campus_clock.at(day, time(10))
    assert (booking.room.code, booking.holder.email) == ("A-101", "prof@usms.ac.ma")


def test_only_confirmed_and_pending_bookings_occupy_a_room():
    assert set(OCCUPYING_STATUSES) == {BookingStatus.CONFIRMEE, BookingStatus.EN_ATTENTE}
    assert BookingStatus.ANNULEE not in PLANNING_STATUSES
    assert BookingStatus.TERMINEE in PLANNING_STATUSES


def test_campus_opens_monday_to_saturday():
    monday, saturday, sunday = date(2026, 11, 2), date(2026, 11, 7), date(2026, 11, 8)
    assert campus_clock.is_open_day(monday) and campus_clock.is_open_day(saturday)
    assert not campus_clock.is_open_day(sunday)
    assert campus_clock.next_open_day(sunday) == date(2026, 11, 9)
    assert campus_clock.next_open_day(monday) == monday


def test_campus_clock_uses_the_campus_time_zone():
    moment = campus_clock.at(date(2026, 11, 2), time(10))
    assert moment.tzinfo is not None
    assert campus_clock.local(moment.astimezone(UTC)) == moment
    assert (campus_clock.opening_time(), campus_clock.closing_time()) == (time(8), time(20))
    assert abs((campus_clock.now() - datetime.now(UTC)).total_seconds()) < 5
    assert campus_clock.today() == campus_clock.now().date()
