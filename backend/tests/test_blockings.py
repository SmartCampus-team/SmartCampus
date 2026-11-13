"""Bloquer une salle sur une période (SC-32 : EF-ROOM-06, RG-01, RG-10)."""

from datetime import time, timedelta

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.blocking import Blocking
from src.models.booking import Booking, BookingStatus
from src.models.room import RoomStatus
from src.models.user import Role
from src.services import blocking_service, campus_clock
from src.services.common import ServiceError
from tests.factories import booking_body, headers_for, make_blocking, make_booking, make_room, open_day
from tests.helpers import reload_user


@pytest.fixture
def room(db):
    return make_room(db, code="B-201", capacity=24)


@pytest.fixture
def manager(client, make_user):
    return headers_for(client, make_user, Role.GESTIONNAIRE)


@pytest.fixture
def manager_user(db, manager):
    return reload_user(db, "gestionnaire@usms.ac.ma")


@pytest.fixture
def teacher(make_user):
    return make_user(email="prof@usms.ac.ma", role=Role.ENSEIGNANT)


def period(day, start="08:00", end="20:00", end_day=None, reason="Examen de mi-semestre") -> dict:
    return {
        "start_date": day.isoformat(),
        "start_time": start,
        "end_date": (end_day or day).isoformat(),
        "end_time": end,
        "reason": reason,
    }


def block(client, headers, room, body):
    return client.post(f"/api/rooms/{room.id}/blockings", json=body, headers=headers)


def test_blocking_shows_in_the_planning_and_hides_the_room(client, db, room, manager):
    day = open_day()
    response = block(client, manager, room, period(day, "08:00", "12:00"))
    assert response.status_code == 201
    body = response.json()
    assert (body["start_date"], body["start_time"], body["end_time"]) == (day.isoformat(), "08:00:00", "12:00:00")
    assert (body["reason"], body["cancelled_bookings"]) == ("Examen de mi-semestre", 0)
    assert body["author_name"] == "Étudiant Test"  # nom donné par make_user au gestionnaire

    planning = client.get(f"/api/rooms/{room.id}/planning", params={"date": day.isoformat()}, headers=manager).json()
    assert [(e["label"], e["detail"], e["start"]) for e in planning["entries"]] == [
        ("Bloqué", "Examen de mi-semestre", "08:00:00")
    ]
    params = {"date": day.isoformat(), "start": "10:00", "end": "11:00"}
    assert client.get("/api/rooms/available", params=params, headers=manager).json()["rooms"] == []


def test_booking_a_blocked_room_is_refused(client, make_user, room, manager):
    day = open_day()
    block(client, manager, room, period(day))
    student = headers_for(client, make_user, Role.ETUDIANT)
    response = client.post("/api/bookings", json=booking_body(room, day, "14:00", "15:00"), headers=student)
    assert response.status_code == 409
    assert response.json()["detail"] == "Salle bloquée sur ce créneau : Examen de mi-semestre."


def test_future_bookings_of_the_period_are_cancelled_with_the_reason(client, db, room, manager, teacher):
    day = open_day()
    inside = make_booking(db, room, teacher, day, time(9), time(10))
    straddling = make_booking(db, room, teacher, day, time(11), time(13), status=BookingStatus.EN_ATTENTE)
    outside = make_booking(db, room, teacher, day, time(14), time(16))

    response = block(client, manager, room, period(day, "09:00", "12:00", reason="Maintenance du réseau"))
    assert response.json()["cancelled_bookings"] == 2

    db.expire_all()
    for booking in (inside, straddling):
        stored = db.get(Booking, booking.id)
        assert (stored.status, stored.cancel_reason) == (BookingStatus.ANNULEE, "Salle bloquée : Maintenance du réseau")
        assert stored.cancelled_at is not None
    assert db.get(Booking, outside.id).status == BookingStatus.CONFIRMEE


def test_finished_bookings_are_left_untouched(db, room, manager_user, teacher):
    """Une réservation déjà terminée garde son statut, même dans la période bloquée."""
    day = open_day()
    finished = make_booking(db, room, teacher, day, time(8), time(9))
    later = make_booking(db, room, teacher, day, time(11), time(12))
    now = campus_clock.at(day, time(10))  # pendant la journée bloquée
    result = blocking_service.create_blocking(
        db, room.id, day, time(8), day, time(20), "Maintenance", manager_user, None, now=now
    )
    assert [booking.id for booking in result.cancelled] == [later.id]
    db.expire_all()
    assert db.get(Booking, finished.id).status == BookingStatus.CONFIRMEE


def test_blocking_over_several_days(client, room, manager):
    day = open_day()
    last = day + timedelta(days=2)
    response = block(client, manager, room, period(day, "14:00", "10:00", end_day=last))
    assert response.status_code == 201
    week = client.get(
        f"/api/rooms/{room.id}/planning", params={"date": day.isoformat(), "view": "week"}, headers=manager
    ).json()
    shown = {(e["day"], e["start"], e["end"]) for e in week["entries"]}
    assert (day.isoformat(), "14:00:00", "20:00:00") in shown  # le premier jour, à partir de 14:00


def test_blocking_and_cancellations_are_written_in_the_audit_log(client, db, room, manager, teacher):
    day = open_day()
    booking = make_booking(db, room, teacher, day, time(10), time(12))
    block(client, manager, room, period(day, "08:00", "12:00"))
    rows = db.execute(select(AuditLog.action, AuditLog.target).order_by(AuditLog.id)).all()[-2:]
    assert rows == [
        ("BOOKING_CANCELLED", f"réservation {booking.id} : B-201 {day:%d/%m/%Y} 10:00–12:00 (blocage)"),
        (
            "BLOCKING_CREATED",
            f"B-201 {day:%d/%m/%Y} 08:00 → {day:%d/%m/%Y} 12:00 : Examen de mi-semestre ; 1 réservation annulée",
        ),
    ]


# Refus


def test_overlapping_blocking_is_refused(client, db, room, manager):
    day = open_day()
    make_blocking(db, room, day, time(8), time(12), reason="Examen")
    response = block(client, manager, room, period(day, "11:00", "14:00"))
    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"La salle est déjà bloquée du {day:%d/%m/%Y} 08:00 au {day:%d/%m/%Y} 12:00 : Examen."
    )


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("10:15", "12:00", "Les heures vont par pas de 30 min (par exemple 10:00 ou 10:30)."),
        ("07:00", "12:00", "Les heures vont de 08:00 à 20:00."),
        ("12:00", "10:00", "La fin du blocage doit être après son début."),
    ],
)
def test_period_off_the_grid_is_refused(client, room, manager, start, end, message):
    response = block(client, manager, room, period(open_day(), start, end))
    assert response.status_code == 400
    assert response.json()["detail"] == message


def test_past_period_is_refused(client, room, manager):
    yesterday = campus_clock.today() - timedelta(days=1)
    response = block(client, manager, room, period(yesterday))
    assert response.status_code == 400
    assert response.json()["detail"] == "Cette période est déjà passée : choisissez une période à venir."


def test_reason_is_required(client, room, manager):
    assert block(client, manager, room, period(open_day(), reason="  ")).status_code == 422


def test_archived_or_unknown_room_is_not_found(client, db, manager):
    archived = make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    assert block(client, manager, archived, period(open_day())).status_code == 404
    assert client.post("/api/rooms/9999/blockings", json=period(open_day()), headers=manager).status_code == 404


def test_room_out_of_service_can_still_be_blocked(client, db, manager):
    broken = make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    assert block(client, manager, broken, period(open_day())).status_code == 201


@pytest.mark.parametrize("role", [Role.ETUDIANT, Role.ENSEIGNANT, Role.ADMINISTRATEUR])
def test_only_the_manager_blocks_a_room(client, db, make_user, room, role):
    headers = headers_for(client, make_user, role)
    blocking = make_blocking(db, room, open_day(), time(8), time(10))
    assert block(client, headers, room, period(open_day(), "14:00", "16:00")).status_code == 403
    assert client.get(f"/api/rooms/{room.id}/blockings", headers=headers).status_code == 403
    assert client.delete(f"/api/rooms/{room.id}/blockings/{blocking.id}", headers=headers).status_code == 403


# Liste et levée d'un blocage


def test_manager_lists_current_and_upcoming_blockings(client, db, room, manager):
    day = open_day()
    make_blocking(db, room, campus_clock.today() - timedelta(days=2), time(8), time(10), reason="Passé")
    make_blocking(db, room, day + timedelta(days=1), time(8), time(10), reason="Plus tard")
    make_blocking(db, room, day, time(8), time(10), reason="Bientôt")
    listed = client.get(f"/api/rooms/{room.id}/blockings", headers=manager).json()
    assert [item["reason"] for item in listed] == ["Bientôt", "Plus tard"]


def test_lifting_a_blocking_frees_the_room(client, db, make_user, room, manager):
    day = open_day()
    blocking_id = block(client, manager, room, period(day)).json()["id"]
    assert client.delete(f"/api/rooms/{room.id}/blockings/{blocking_id}", headers=manager).status_code == 204
    assert db.scalar(select(Blocking)) is None
    assert db.scalar(select(AuditLog.action).order_by(AuditLog.id.desc()).limit(1)) == "BLOCKING_REMOVED"

    student = headers_for(client, make_user, Role.ETUDIANT)
    response = client.post("/api/bookings", json=booking_body(room, day, "10:00", "11:00"), headers=student)
    assert response.status_code == 201


def test_finished_or_unknown_blocking_cannot_be_lifted(client, db, room, manager):
    old = make_blocking(db, room, campus_clock.today() - timedelta(days=2), time(8), time(10))
    response = client.delete(f"/api/rooms/{room.id}/blockings/{old.id}", headers=manager)
    assert (response.status_code, response.json()["detail"]) == (
        409,
        "Ce blocage est terminé : il reste dans l'historique de la salle.",
    )
    other_room = make_room(db, code="B-202")
    assert client.delete(f"/api/rooms/{other_room.id}/blockings/{old.id}", headers=manager).status_code == 404


def test_period_check_rejects_a_slot_already_over(db):
    day = open_day()
    with pytest.raises(ServiceError):
        blocking_service.check_period(day, time(8), day, time(10), now=campus_clock.at(day, time(11)))
