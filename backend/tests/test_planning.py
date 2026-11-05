"""Planning d'une salle en vue jour et semaine (SC-23 : EF-ROOM-03, RG-03)."""

from datetime import date, time, timedelta

import pytest

from src.models.blocking import Blocking
from src.models.booking import BookingStatus
from src.models.room import RoomStatus
from src.models.user import Role
from src.services import campus_clock
from src.services.planning_service import PlanningView, period
from tests.factories import headers_for, make_blocking, make_booking, make_room, open_day
from tests.helpers import reload_user

MONDAY = date(2026, 11, 2) + timedelta(weeks=52)  # un lundi d'une semaine à venir


def planning(client, headers, room_id, **params):
    return client.get(f"/api/rooms/{room_id}/planning", params=params, headers=headers)


def slots(response) -> list[tuple[str, str, str, str]]:
    return [(e["day"], e["start"], e["end"], e["label"]) for e in response.json()["entries"]]


@pytest.fixture
def room(db):
    return make_room(db, code="A-101")


@pytest.fixture
def teacher(make_user):
    return make_user(email="prof@usms.ac.ma", role=Role.ENSEIGNANT)


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


def test_planning_requires_a_token(client, room):
    assert client.get(f"/api/rooms/{room.id}/planning").status_code == 401


def test_day_view_is_the_default_with_30_minute_steps_from_8_to_20(client, db, room, teacher, student):
    day = open_day()
    make_booking(db, room, teacher, day, time(14), time(16))
    make_booking(db, room, teacher, day, time(10), time(12))
    make_booking(db, room, teacher, campus_clock.next_open_day(day + timedelta(days=1)), time(10), time(12))

    response = planning(client, student, room.id, date=day.isoformat())
    assert response.status_code == 200
    body = response.json()
    assert body["view"] == "day"
    assert body["days"] == [day.isoformat()]
    assert (body["opening"], body["closing"], body["slot_minutes"]) == ("08:00:00", "20:00:00", 30)
    assert body["room"]["code"] == "A-101"
    assert slots(response) == [
        (day.isoformat(), "10:00:00", "12:00:00", "Réservé"),
        (day.isoformat(), "14:00:00", "16:00:00", "Réservé"),
    ]


def test_planning_defaults_to_today(client, room, student):
    assert planning(client, student, room.id).json()["days"] == [campus_clock.today().isoformat()]


def test_week_view_shows_monday_to_saturday(client, db, room, teacher, student):
    saturday = MONDAY + timedelta(days=5)
    make_booking(db, room, teacher, MONDAY, time(8), time(9))
    make_booking(db, room, teacher, saturday, time(18), time(20))
    make_booking(db, room, teacher, MONDAY + timedelta(days=7), time(8), time(9))  # semaine suivante

    body = planning(client, student, room.id, date=(MONDAY + timedelta(days=2)).isoformat(), view="week").json()
    assert body["view"] == "week"
    assert body["days"] == [(MONDAY + timedelta(days=i)).isoformat() for i in range(6)]
    assert [e["day"] for e in body["entries"]] == [MONDAY.isoformat(), saturday.isoformat()]


def test_week_period_helper():
    wednesday = date(2026, 11, 4)
    assert period(wednesday, PlanningView.WEEK)[0] == date(2026, 11, 2)
    assert period(wednesday, PlanningView.WEEK)[-1] == date(2026, 11, 7)
    assert period(wednesday, PlanningView.DAY) == [wednesday]


def test_booked_and_blocked_slots_carry_a_label(client, db, room, teacher, student):
    day = open_day()
    make_booking(db, room, teacher, day, time(8), time(9), status=BookingStatus.EN_ATTENTE)
    make_booking(db, room, teacher, day, time(10), time(11), status=BookingStatus.CONFIRMEE)
    make_blocking(db, room, day, time(14), time(18), reason="Examen de mi-semestre")
    response = planning(client, student, room.id, date=day.isoformat())
    entries = response.json()["entries"]
    assert [(e["kind"], e["label"], e["status"], e["detail"]) for e in entries] == [
        ("reservation", "En attente de validation", "en_attente", None),
        ("reservation", "Réservé", "confirmee", None),
        ("blocage", "Bloqué", None, "Examen de mi-semestre"),
    ]


def test_cancelled_and_refused_bookings_are_not_shown(client, db, room, teacher, student):
    day = open_day()
    make_booking(db, room, teacher, day, time(8), time(9), status=BookingStatus.ANNULEE)
    make_booking(db, room, teacher, day, time(9), time(10), status=BookingStatus.REFUSEE)
    assert planning(client, student, room.id, date=day.isoformat()).json()["entries"] == []


def test_blocking_over_several_days_is_cut_per_day_within_opening_hours(client, db, room, student):
    blocking_start = campus_clock.at(MONDAY, time(18))
    blocking_end = campus_clock.at(MONDAY + timedelta(days=2), time(9))
    db.add(Blocking(room_id=room.id, start_at=blocking_start, end_at=blocking_end, reason="Travaux"))
    db.commit()
    response = planning(client, student, room.id, date=MONDAY.isoformat(), view="week")
    assert slots(response) == [
        (MONDAY.isoformat(), "18:00:00", "20:00:00", "Bloqué"),
        ((MONDAY + timedelta(days=1)).isoformat(), "08:00:00", "20:00:00", "Bloqué"),
        ((MONDAY + timedelta(days=2)).isoformat(), "08:00:00", "09:00:00", "Bloqué"),
    ]


def test_other_users_do_not_see_purpose_or_holder(client, db, room, teacher, student):
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12), purpose="Réunion privée")
    entry = planning(client, student, room.id, date=day.isoformat()).json()["entries"][0]
    assert (entry["mine"], entry["detail"], entry["holder_name"]) == (False, None, None)
    assert entry["label"] == "Réservé"


def test_holder_sees_their_own_purpose(client, db, room, student):
    me = reload_user(db, "etudiant@usms.ac.ma")
    day = open_day()
    make_booking(db, room, me, day, time(10), time(12), purpose="Révision")
    entry = planning(client, student, room.id, date=day.isoformat()).json()["entries"][0]
    assert (entry["mine"], entry["detail"], entry["holder_name"]) == (True, "Révision", "Étudiant Test")


def test_room_manager_sees_every_purpose(client, db, make_user, room, teacher):
    manager = headers_for(client, make_user, Role.GESTIONNAIRE)
    day = open_day()
    make_booking(db, room, teacher, day, time(10), time(12), purpose="Cours")
    entry = planning(client, manager, room.id, date=day.isoformat()).json()["entries"][0]
    assert (entry["mine"], entry["detail"]) == (False, "Cours")


def test_archived_room_planning_is_open_to_the_manager_only(client, db, make_user, teacher, student):
    archived = make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    past_day = campus_clock.today() - timedelta(days=7)
    make_booking(db, archived, teacher, past_day, time(10), time(12), status=BookingStatus.TERMINEE)
    assert planning(client, student, archived.id).status_code == 404
    manager = headers_for(client, make_user, Role.GESTIONNAIRE)
    response = planning(client, manager, archived.id, date=past_day.isoformat())
    assert response.status_code == 200
    assert [e["label"] for e in response.json()["entries"]] == ["Terminé"]


def test_out_of_service_room_still_has_a_planning(client, db, student):
    room = make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    assert planning(client, student, room.id).json()["room"]["status"] == "hors_service"


def test_unknown_room_or_invalid_parameters(client, room, student):
    assert planning(client, student, 9999).status_code == 404
    assert planning(client, student, room.id, view="mois").status_code == 422
    assert planning(client, student, room.id, date="02/11/2026").status_code == 422
