"""Appliquer l'horizon et les quotas de réservation (SC-26 : EF-BOOK-01, RG-04, RG-07)."""

from datetime import date, time, timedelta

import pytest
from sqlalchemy import delete

from src.models.booking import BookingStatus
from src.models.setting import Setting
from src.models.user import Role
from src.services import campus_clock, setting_service
from src.services.setting_service import SettingKey
from tests.factories import booking_body, headers_for, make_booking, make_room, open_day, set_setting
from tests.helpers import reload_user

URL = "/api/bookings"
UPCOMING_QUOTA = (
    "Quota atteint : un étudiant a au plus 4 réservations à venir. Annulez-en une pour en créer une autre."
)
WEEKLY_QUOTA = "Quota atteint : un étudiant réserve au plus 8 h de salle par semaine (du lundi au samedi)."


@pytest.fixture
def room(db):
    return make_room(db, code="A-101", capacity=30)


@pytest.fixture
def other_room(db):
    return make_room(db, code="B-201", capacity=24)


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def student_user(db, student):
    return reload_user(db, "etudiant@usms.ac.ma")


def in_days(days: int, step: int = -1) -> date:
    """Le jour J + days ; s'il tombe un dimanche, le jour ouvré d'avant (step=-1) ou d'après (step=1)."""
    day = campus_clock.today() + timedelta(days=days)
    return day + timedelta(days=step) if day.weekday() == 6 else day


def book(client, headers, room, day, start="10:00", end="11:00"):
    return client.post(URL, json=booking_body(room, day, start, end), headers=headers)


# Horizon (RG-04)


def test_student_books_up_to_seven_days_ahead(client, room, student):
    assert book(client, student, room, in_days(7)).status_code == 201


def test_student_cannot_book_more_than_seven_days_ahead(client, room, student):
    day = in_days(8, step=1)
    response = book(client, student, room, day)
    assert response.status_code == 400
    last = campus_clock.today() + timedelta(days=7)
    assert response.json()["detail"] == (
        f"Réservation trop lointaine : un étudiant réserve au plus 7 jours à l'avance, soit jusqu'au {last:%d/%m/%Y}."
    )


def test_teacher_books_up_to_thirty_days_ahead(client, make_user, room):
    teacher = headers_for(client, make_user, Role.ENSEIGNANT)
    assert book(client, teacher, room, in_days(30)).status_code == 201
    response = book(client, teacher, room, in_days(31, step=1))
    assert response.status_code == 400
    assert "un enseignant réserve au plus 30 jours à l'avance" in response.json()["detail"]


def test_horizon_is_read_in_the_settings_table(client, db, room, student):
    set_setting(db, "booking_horizon_days_student", 14)
    assert book(client, student, room, in_days(10)).status_code == 201


# Réservations à venir (RG-07)


def test_fifth_upcoming_booking_is_refused_with_the_quota(client, db, room, other_room, student, student_user):
    day = open_day()
    for hour in (8, 9, 10, 11):
        make_booking(db, other_room, student_user, day, time(hour), time(hour + 1))
    response = book(client, student, room, day, "14:00", "15:00")
    assert response.status_code == 400
    assert response.json()["detail"] == UPCOMING_QUOTA


def test_cancelled_and_past_bookings_are_not_upcoming(client, db, room, other_room, student, student_user):
    day = open_day()
    for hour in (8, 9, 10):
        make_booking(db, other_room, student_user, day, time(hour), time(hour + 1))
    make_booking(db, other_room, student_user, day, time(11), time(12), status=BookingStatus.ANNULEE)
    make_booking(db, other_room, student_user, campus_clock.today() - timedelta(days=2), time(10), time(11))
    assert book(client, student, room, day, "14:00", "15:00").status_code == 201


def test_upcoming_quota_is_read_in_the_settings_table(client, db, room, other_room, student, student_user):
    set_setting(db, "max_upcoming_bookings_student", 5)
    day = open_day()
    for hour in (8, 9, 10, 11):
        make_booking(db, other_room, student_user, day, time(hour), time(hour + 1))
    assert book(client, student, room, day, "14:00", "15:00").status_code == 201


# Heures par semaine (RG-07)


@pytest.fixture
def eight_hours(db, other_room, student_user) -> date:
    """L'étudiant a déjà 8 h réservées le même jour (quota de réservations à venir relevé pour l'isoler)."""
    set_setting(db, "max_upcoming_bookings_student", 10)
    day = open_day()
    for hour in (8, 10, 12, 14):
        make_booking(db, other_room, student_user, day, time(hour), time(hour + 2))
    return day


def test_one_more_slot_after_eight_hours_in_the_week_is_refused(client, room, student, eight_hours):
    response = book(client, student, room, eight_hours, "16:00", "16:30")
    assert response.status_code == 400
    assert response.json()["detail"] == WEEKLY_QUOTA


def test_next_week_has_its_own_hours(client, db, room, student, eight_hours):
    set_setting(db, "booking_horizon_days_student", 30)
    next_week = eight_hours + timedelta(days=7)
    assert book(client, student, room, next_week, "16:00", "17:00").status_code == 201


def test_weekly_hours_are_read_in_the_settings_table(client, db, room, student, eight_hours):
    set_setting(db, "max_weekly_hours_student", 9)
    assert book(client, student, room, eight_hours, "16:00", "17:00").status_code == 201


def test_teacher_has_no_quota(client, db, make_user, room, other_room):
    headers = headers_for(client, make_user, Role.ENSEIGNANT)
    teacher = reload_user(db, "enseignant@usms.ac.ma")
    day = open_day()
    for hour in (8, 10, 12, 14, 16):
        make_booking(db, other_room, teacher, day, time(hour), time(hour + 2))
    assert book(client, headers, room, day, "18:00", "20:00").status_code == 201


# Paramètres


def test_missing_setting_gives_an_explicit_error(db):
    db.execute(delete(Setting).where(Setting.key == "max_weekly_hours_student"))
    db.commit()
    with pytest.raises(RuntimeError, match="max_weekly_hours_student"):
        setting_service.get_int(db, SettingKey.MAX_WEEKLY_HOURS_STUDENT)
