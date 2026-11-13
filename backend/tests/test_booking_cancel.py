"""Annuler sa réservation (SC-29 : EF-BOOK-04, RG-05, RG-12, ENF-18)."""

from datetime import time, timedelta

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.booking import Booking, BookingStatus
from src.models.user import Role
from src.services import campus_clock
from tests.factories import headers_for, make_booking, make_booking_at, make_room, open_day, set_setting
from tests.helpers import reload_user

TOO_LATE = "Annulation impossible moins de 2 h avant le début : contactez le gestionnaire des salles."


@pytest.fixture
def room(db):
    return make_room(db, code="A-101", capacity=30)


@pytest.fixture
def teacher(client, make_user):
    return headers_for(client, make_user, Role.ENSEIGNANT)


@pytest.fixture
def me(db, teacher):
    return reload_user(db, "enseignant@usms.ac.ma")


@pytest.fixture
def manager(client, make_user):
    return headers_for(client, make_user, Role.GESTIONNAIRE)


def cancel(client, headers, booking_id, reason=None):
    body = {"reason": reason} if reason is not None else None
    return client.post(f"/api/bookings/{booking_id}/cancel", json=body, headers=headers)


def soon(db, room, holder, minutes: int = 60) -> Booking:
    """Réservation qui commence dans `minutes` minutes."""
    now = campus_clock.now()
    start = now + timedelta(minutes=minutes)
    return make_booking_at(db, room, holder, start, start + timedelta(hours=1))


def test_cancel_requires_a_token(client):
    assert client.post("/api/bookings/1/cancel").status_code == 401


def test_holder_cancels_more_than_two_hours_before(client, db, room, teacher, me):
    day = open_day()
    booking = make_booking(db, room, me, day, time(10), time(12))

    response = cancel(client, teacher, booking.id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "annulee"
    assert body["cancelled_at"] is not None
    assert (body["can_cancel"], body["cancel_refusal"]) == (False, "Cette réservation est déjà annulée.")

    # Jamais supprimée : la ligne reste, avec son nouveau statut
    db.expire_all()
    assert db.get(Booking, booking.id).status == BookingStatus.ANNULEE

    entry = db.scalar(select(AuditLog).where(AuditLog.action == "BOOKING_CANCELLED"))
    assert entry.actor_email == "enseignant@usms.ac.ma"
    assert entry.target == f"réservation {booking.id} : A-101 {day:%d/%m/%Y} 10:00–12:00"


def test_cancelled_slot_is_free_again(client, db, room, teacher, me):
    day = open_day()
    booking = make_booking(db, room, me, day, time(10), time(12))
    cancel(client, teacher, booking.id)

    params = {"date": day.isoformat(), "start": "10:00", "end": "12:00"}
    rooms = client.get("/api/rooms/available", params=params, headers=teacher).json()["rooms"]
    assert [r["code"] for r in rooms] == ["A-101"]


def test_cancelled_booking_moves_to_the_cancelled_tab(client, db, room, teacher, me):
    booking = make_booking(db, room, me, open_day(), time(10), time(12))
    cancel(client, teacher, booking.id)
    body = client.get("/api/bookings/me", headers=teacher).json()
    assert body["upcoming"] == []
    assert [line["id"] for line in body["cancelled"]] == [booking.id]


def test_less_than_two_hours_before_is_refused(client, db, room, teacher, me):
    booking = soon(db, room, me, minutes=60)
    response = cancel(client, teacher, booking.id)
    assert response.status_code == 409
    assert response.json()["detail"] == TOO_LATE
    db.expire_all()
    assert db.get(Booking, booking.id).status == BookingStatus.CONFIRMEE


def test_cancel_button_state_and_reason_are_given_by_the_api(client, db, room, teacher, me):
    later = make_booking(db, room, me, open_day(), time(10), time(12))
    near = soon(db, room, me, minutes=60)
    lines = {line["id"]: line for line in client.get("/api/bookings/me", headers=teacher).json()["upcoming"]}
    assert (lines[later.id]["can_cancel"], lines[later.id]["cancel_refusal"]) == (True, None)
    assert (lines[near.id]["can_cancel"], lines[near.id]["cancel_refusal"]) == (False, TOO_LATE)


def test_notice_is_read_in_the_settings_table(client, db, room, teacher, me):
    set_setting(db, "cancellation_notice_hours", 1)
    booking = soon(db, room, me, minutes=90)
    assert cancel(client, teacher, booking.id).status_code == 200


def test_started_booking_cannot_be_cancelled_by_its_holder(client, db, room, teacher, me):
    now = campus_clock.now()
    booking = make_booking_at(db, room, me, now - timedelta(minutes=30), now + timedelta(minutes=30))
    response = cancel(client, teacher, booking.id)
    assert response.status_code == 409
    assert response.json()["detail"].startswith("Cette réservation a déjà commencé")


# Gestionnaire : à tout moment


def test_manager_cancels_at_any_time_with_a_reason(client, db, room, manager, me):
    booking = soon(db, room, me, minutes=30)
    response = cancel(client, manager, booking.id, reason="Salle réquisitionnée pour un jury")
    assert response.status_code == 200
    assert response.json()["cancel_reason"] == "Salle réquisitionnée pour un jury"

    entry = db.scalar(select(AuditLog).where(AuditLog.action == "BOOKING_CANCELLED"))
    assert entry.actor_email == "gestionnaire@usms.ac.ma"
    assert entry.target.endswith("(par le gestionnaire)")


def test_manager_cancels_a_booking_in_progress(client, db, room, manager, me):
    now = campus_clock.now()
    booking = make_booking_at(db, room, me, now - timedelta(minutes=30), now + timedelta(minutes=30))
    assert cancel(client, manager, booking.id).status_code == 200


def test_finished_booking_cannot_be_cancelled(client, db, room, manager, me):
    yesterday = campus_clock.today() - timedelta(days=1)
    booking = make_booking(db, room, me, yesterday, time(10), time(11))
    response = cancel(client, manager, booking.id)
    assert response.status_code == 409
    assert response.json()["detail"] == "Cette réservation est terminée : elle ne peut plus être annulée."


# Refus


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (BookingStatus.ANNULEE, "Cette réservation est déjà annulée."),
        (BookingStatus.REFUSEE, "Cette réservation ne peut plus être annulée."),
    ],
)
def test_booking_that_no_longer_occupies_the_room_cannot_be_cancelled(client, db, room, teacher, me, status, message):
    booking = make_booking(db, room, me, open_day(), time(10), time(12), status=status)
    response = cancel(client, teacher, booking.id)
    assert response.status_code == 409
    assert response.json()["detail"] == message


def test_someone_elses_booking_is_not_found(client, db, make_user, room, teacher):
    other = make_user(email="autre@usms.ac.ma")
    booking = make_booking(db, room, other, open_day(), time(10), time(12))
    for booking_id in (booking.id, booking.id + 100):
        response = cancel(client, teacher, booking_id)
        assert response.status_code == 404
        assert response.json()["detail"] == "Réservation introuvable."


@pytest.mark.parametrize("role", [Role.SCOLARITE, Role.ADMINISTRATEUR])
def test_other_roles_cannot_cancel(client, db, make_user, room, me, role):
    booking = make_booking(db, room, me, open_day(), time(10), time(12))
    assert cancel(client, headers_for(client, make_user, role), booking.id).status_code == 403
