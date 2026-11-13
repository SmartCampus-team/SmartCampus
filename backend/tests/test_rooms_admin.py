"""Créer, modifier et archiver une salle (SC-20 : EF-ROOM-04, ENF-03)."""

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.room import Room, RoomStatus
from src.models.user import Role
from src.services import room_admin_service
from src.services.room_service import ROOM_NOT_FOUND
from tests.factories import headers_for, make_room

URL = "/api/rooms"
NEW = {"code": " a-104 ", "building": "Bâtiment A", "room_type": "salle_td", "capacity": 30, "description": "Près de l'escalier"}


@pytest.fixture
def manager(client, make_user):
    return headers_for(client, make_user, Role.GESTIONNAIRE)


def codes(response) -> list[str]:
    return [room["code"] for room in response.json()]


def last_audit(db) -> tuple[str, str | None]:
    db.expire_all()
    entry = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()))
    return entry.action, entry.target


@pytest.mark.parametrize("role", [Role.ETUDIANT, Role.ENSEIGNANT, Role.SCOLARITE, Role.ADMINISTRATEUR])
def test_other_roles_get_403(client, db, make_user, role):
    headers = headers_for(client, make_user, role)
    room = make_room(db)
    assert client.post(URL, json=NEW, headers=headers).status_code == 403
    assert client.patch(f"{URL}/{room.id}", json={"capacity": 10}, headers=headers).status_code == 403
    assert client.post(f"{URL}/{room.id}/archive", headers=headers).status_code == 403
    assert client.get(URL, params={"include_archived": "true"}, headers=headers).status_code == 403


def test_rooms_require_a_token(client):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=NEW).status_code == 401


def test_manager_creates_an_active_room(client, db, manager):
    response = client.post(URL, json=NEW, headers=manager)
    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "code": "A-104",  # code normalisé
        "building": "Bâtiment A",
        "room_type": "salle_td",
        "capacity": 30,
        "status": "active",
        "description": "Près de l'escalier",
    }
    # Elle apparaît dans la liste avec le statut « active »
    assert codes(client.get(URL, headers=manager)) == ["A-104"]
    assert last_audit(db) == ("ROOM_CREATED", "A-104")


@pytest.mark.parametrize("room_type", ["amphitheatre", "salle_td", "salle_travail", "salle_cours", "salle_tp"])
def test_every_room_type_is_accepted(client, manager, room_type):
    assert client.post(URL, json={**NEW, "room_type": room_type}, headers=manager).status_code == 201


def test_code_already_used_is_refused(client, db, manager):
    make_room(db, code="A-104")
    response = client.post(URL, json=NEW, headers=manager)
    assert response.status_code == 409
    assert response.json() == {"detail": "Une salle porte déjà le code A-104."}


@pytest.mark.parametrize(
    "changes",
    [{"capacity": 0}, {"capacity": -5}, {"capacity": 501}, {"code": ""}, {"code": "A 104"}, {"building": "A"}, {"room_type": "bureau"}],
)
def test_invalid_room_is_refused(client, manager, changes):
    assert client.post(URL, json={**NEW, **changes}, headers=manager).status_code == 422


def test_manager_updates_a_room(client, db, manager):
    room = make_room(db, code="A-101", capacity=30, description="Ancienne description")
    response = client.patch(f"{URL}/{room.id}", json={"capacity": 45, "description": ""}, headers=manager)
    assert response.status_code == 200
    body = response.json()
    assert (body["code"], body["capacity"], body["description"]) == ("A-101", 45, None)
    assert last_audit(db) == ("ROOM_UPDATED", "A-101")


def test_update_can_rename_but_not_take_another_code(client, db, manager):
    make_room(db, code="A-101")
    other = make_room(db, code="A-102")
    assert client.patch(f"{URL}/{other.id}", json={"code": "a-101"}, headers=manager).status_code == 409
    response = client.patch(f"{URL}/{other.id}", json={"code": "A-105", "building": "Bâtiment B", "room_type": "salle_tp"}, headers=manager)
    assert response.status_code == 200
    assert (response.json()["code"], response.json()["building"]) == ("A-105", "Bâtiment B")


def test_update_refuses_a_null_capacity(client, db, manager):
    room = make_room(db)
    assert client.patch(f"{URL}/{room.id}", json={"capacity": 0}, headers=manager).status_code == 422


def test_archived_room_disappears_from_the_list_but_stays_in_database(client, db, manager):
    room = make_room(db, code="A-101")
    make_room(db, code="A-102")
    response = client.post(f"{URL}/{room.id}/archive", headers=manager)
    assert response.status_code == 200
    assert response.json()["status"] == "archivee"
    assert codes(client.get(URL, headers=manager)) == ["A-102"]
    db.expire_all()
    assert db.scalar(select(Room.status).where(Room.code == "A-101")) == RoomStatus.ARCHIVEE
    assert last_audit(db) == ("ROOM_ARCHIVED", "A-101")
    # Le gestionnaire la retrouve avec include_archived
    assert codes(client.get(URL, params={"include_archived": "true"}, headers=manager)) == ["A-101", "A-102"]


def test_archived_room_cannot_be_modified_or_archived_again(client, db, manager):
    room = make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    response = client.patch(f"{URL}/{room.id}", json={"capacity": 20}, headers=manager)
    assert response.status_code == 409
    assert response.json() == {"detail": room_admin_service.ROOM_ARCHIVED}
    assert client.post(f"{URL}/{room.id}/archive", headers=manager).status_code == 409


def test_unknown_room_is_404(client, manager):
    response = client.patch(f"{URL}/9999", json={"capacity": 20}, headers=manager)
    assert response.status_code == 404
    assert response.json() == {"detail": ROOM_NOT_FOUND}
    assert client.post(f"{URL}/9999/archive", headers=manager).status_code == 404


def test_list_is_sorted_by_building_then_code_for_every_role(client, db, make_user):
    headers = headers_for(client, make_user, Role.ETUDIANT)
    make_room(db, code="B-201", building="Bâtiment B")
    make_room(db, code="A-102")
    make_room(db, code="A-101")
    make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    assert codes(client.get(URL, headers=headers)) == ["A-101", "A-102", "A-103", "B-201"]
