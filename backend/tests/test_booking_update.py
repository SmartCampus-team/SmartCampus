"""Modifier une réservation non commencée (SC-30 : EF-BOOK-05, RG-01, RG-03, RG-04, RG-07, RG-08)."""

from datetime import time, timedelta

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.booking import Booking, BookingStatus
from src.models.room import RoomStatus, RoomType
from src.models.user import Role
from src.services import booking_service, campus_clock
from src.services.booking_service import BookingChanges
from src.services.common import ServiceError
from tests.factories import (
    headers_for,
    make_blocking,
    make_booking,
    make_booking_at,
    make_room,
    open_day,
    set_setting,
)
from tests.helpers import reload_user

SLOT_TAKEN = "Créneau déjà réservé : choisissez un autre créneau ou une autre salle."


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
def me(db, student):
    return reload_user(db, "etudiant@usms.ac.ma")


@pytest.fixture
def booking(db, room, me):
    return make_booking(db, room, me, open_day(), time(10), time(12), purpose="Révision", participants=4)


def patch(client, headers, booking_id, **changes):
    return client.patch(f"/api/bookings/{booking_id}", json=changes, headers=headers)


def unchanged(db, booking: Booking) -> bool:
    """La réservation d'origine est intacte en base."""
    db.expire_all()
    stored = db.get(Booking, booking.id)
    return (stored.room_id, stored.start_at, stored.end_at, stored.status) == (
        booking.room_id,
        campus_clock.at(open_day(), time(10)),
        campus_clock.at(open_day(), time(12)),
        BookingStatus.CONFIRMEE,
    )


def test_update_requires_a_token(client, booking):
    assert client.patch(f"/api/bookings/{booking.id}", json={}).status_code == 401


def test_another_free_slot_is_saved(client, db, student, booking):
    day = open_day() + timedelta(days=1)
    day = day + timedelta(days=1) if day.weekday() == 6 else day
    response = patch(client, student, booking.id, date=day.isoformat(), start="14:00", end="15:30")
    assert response.status_code == 200
    body = response.json()
    assert (body["date"], body["start"], body["end"]) == (day.isoformat(), "14:00:00", "15:30:00")
    assert body["status"] == "confirmee"
    db.expire_all()
    assert db.get(Booking, booking.id).start_at == campus_clock.at(day, time(14))


def test_another_free_room_is_saved(client, db, student, booking, other_room):
    response = patch(client, student, booking.id, room_id=other_room.id)
    assert response.status_code == 200
    assert response.json()["room"]["code"] == "B-201"


def test_new_slot_may_overlap_the_old_one(client, student, booking):
    """La réservation que l'on déplace ne se gêne pas elle-même."""
    assert patch(client, student, booking.id, start="11:00", end="13:00").status_code == 200


def test_purpose_and_participants_can_change_alone(client, student, booking):
    response = patch(client, student, booking.id, purpose="Préparation de soutenance", participants=6)
    assert response.status_code == 200
    assert (response.json()["purpose"], response.json()["participants"]) == ("Préparation de soutenance", 6)


def test_old_and_new_slots_are_written_in_the_audit_log(client, db, student, booking, other_room):
    day = open_day()
    patch(client, student, booking.id, room_id=other_room.id, start="14:00", end="15:00")
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "BOOKING_UPDATED"))
    assert entry.target == (
        f"réservation {booking.id} : A-101 {day:%d/%m/%Y} 10:00–12:00 → B-201 {day:%d/%m/%Y} 14:00–15:00"
    )


# Refus : la réservation d'origine reste intacte


def test_conflicting_slot_is_refused_and_original_kept(client, db, make_user, student, booking, room):
    other = make_user(email="autre@usms.ac.ma")
    make_booking(db, room, other, open_day(), time(14), time(16))
    response = patch(client, student, booking.id, start="15:00", end="16:00")
    assert response.status_code == 409
    assert response.json()["detail"] == SLOT_TAKEN
    assert unchanged(db, booking)


def test_blocked_room_is_refused_and_original_kept(client, db, student, booking, other_room):
    make_blocking(db, other_room, open_day(), time(8), time(20), reason="Maintenance")
    response = patch(client, student, booking.id, room_id=other_room.id)
    assert response.status_code == 409
    assert response.json()["detail"] == "Salle bloquée sur ce créneau : Maintenance."
    assert unchanged(db, booking)


@pytest.mark.parametrize(
    ("changes", "status"),
    [
        ({"start": "10:15"}, 400),  # hors grille (RG-03)
        ({"end": "13:00"}, 400),  # 3 h pour un étudiant (RG-03)
        ({"participants": 31}, 400),  # plus que la capacité (RG-08)
    ],
)
def test_change_breaking_a_rule_is_refused_and_original_kept(client, db, student, booking, changes, status):
    assert patch(client, student, booking.id, **changes).status_code == status
    assert unchanged(db, booking)


def test_room_out_of_service_or_amphitheatre_is_refused(client, db, student, booking):
    broken = make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    amphi = make_room(db, code="AMPHI-A", room_type=RoomType.AMPHITHEATRE, capacity=200)
    assert patch(client, student, booking.id, room_id=broken.id).status_code == 409
    assert patch(client, student, booking.id, room_id=amphi.id).status_code == 400
    assert unchanged(db, booking)


def test_slot_beyond_the_horizon_is_refused(client, db, student, booking):
    far = campus_clock.today() + timedelta(days=9)
    far = far + timedelta(days=1) if far.weekday() == 6 else far
    response = patch(client, student, booking.id, date=far.isoformat())
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Réservation trop lointaine")
    assert unchanged(db, booking)


# Quotas : la réservation modifiée ne compte pas deux fois


def test_student_at_quota_can_still_move_a_booking(client, db, student, me, booking, other_room):
    day = open_day()
    for hour in (14, 15, 16):
        make_booking(db, other_room, me, day, time(hour), time(hour + 1))
    assert patch(client, student, booking.id, start="08:00", end="10:00").status_code == 200


def test_student_with_eight_hours_can_move_one_of_them(client, db, student, me, booking, other_room):
    set_setting(db, "max_upcoming_bookings_student", 10)
    day = open_day()
    for hour in (12, 14, 16):
        make_booking(db, other_room, me, day, time(hour), time(hour + 2))
    assert patch(client, student, booking.id, start="08:00", end="10:00").status_code == 200


# Réservation commencée, passée ou annulée


def test_started_booking_can_no_longer_be_changed(client, db, student, me, room):
    now = campus_clock.now()
    started = make_booking_at(db, room, me, now - timedelta(minutes=30), now + timedelta(minutes=30))
    response = patch(client, student, started.id, purpose="Autre motif")
    assert response.status_code == 409
    assert response.json()["detail"] == "Cette réservation a déjà commencé : elle ne peut plus être modifiée."


def test_past_booking_can_no_longer_be_changed(client, db, student, me, room):
    past = make_booking(db, room, me, campus_clock.today() - timedelta(days=1), time(10), time(11))
    assert patch(client, student, past.id, purpose="Autre motif").status_code == 409


def test_cancelled_booking_can_no_longer_be_changed(client, db, student, me, room):
    cancelled = make_booking(db, room, me, open_day(), time(14), time(15), status=BookingStatus.ANNULEE)
    response = patch(client, student, cancelled.id, purpose="Autre motif")
    assert response.status_code == 409
    assert response.json()["detail"] == "Seule une réservation en attente ou confirmée peut être modifiée."


def test_edit_button_state_is_given_by_the_api(client, db, student, me, room, booking):
    now = campus_clock.now()
    started = make_booking_at(db, room, me, now - timedelta(minutes=30), now + timedelta(minutes=30))
    lines = {line["id"]: line for line in client.get("/api/bookings/me", headers=student).json()["upcoming"]}
    assert lines[booking.id]["can_edit"] is True
    assert lines[started.id]["can_edit"] is False


# Droits


def test_someone_elses_booking_is_not_found(client, db, make_user, room):
    owner = make_user(email="autre@usms.ac.ma")
    theirs = make_booking(db, room, owner, open_day(), time(10), time(12))
    headers = headers_for(client, make_user, Role.ETUDIANT)
    assert patch(client, headers, theirs.id, purpose="Autre motif").status_code == 404


def test_manager_does_not_edit_bookings(client, make_user, booking):
    manager = headers_for(client, make_user, Role.GESTIONNAIRE)
    assert patch(client, manager, booking.id, purpose="Autre motif").status_code == 403


def test_service_refuses_to_change_someone_elses_booking_even_for_a_manager(db, make_user, booking):
    """Le service lui-même protège la réservation, quel que soit le rôle de l'appelant."""
    manager = make_user(email="gestionnaire@usms.ac.ma", role=Role.GESTIONNAIRE)
    with pytest.raises(ServiceError) as error:
        booking_service.update_booking(db, manager, booking.id, BookingChanges(purpose="Autre"), None)
    assert error.value.status == 404
