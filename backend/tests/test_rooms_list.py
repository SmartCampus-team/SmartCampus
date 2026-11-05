"""Consulter la liste des salles (SC-21 : EF-ROOM-01)."""

import pytest

from src.models.room import RoomStatus, RoomType
from src.models.user import Role
from tests.factories import headers_for, make_room

URL = "/api/rooms"


@pytest.fixture
def headers(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


def codes(client, headers, **params) -> list[str]:
    return [room["code"] for room in client.get(URL, params=params, headers=headers).json()]


def test_each_room_shows_building_type_capacity_and_status(client, db, headers):
    make_room(db, code="A-101", capacity=40, description="Près du hall")
    response = client.get(URL, headers=headers)
    assert response.status_code == 200
    room = response.json()[0]
    assert room == {
        "id": room["id"],
        "code": "A-101",
        "building": "Bâtiment A",
        "room_type": "salle_cours",
        "capacity": 40,
        "status": "active",
        "description": "Près du hall",
    }


@pytest.mark.parametrize("role", list(Role))
def test_every_role_can_read_the_list(client, db, make_user, role):
    headers = headers_for(client, make_user, role)
    make_room(db)
    assert client.get(URL, headers=headers).status_code == 200


def test_archived_rooms_are_hidden_out_of_service_rooms_are_shown(client, db, headers):
    make_room(db, code="A-101")
    make_room(db, code="A-103", status=RoomStatus.HORS_SERVICE)
    make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    response = client.get(URL, headers=headers).json()
    assert [(room["code"], room["status"]) for room in response] == [("A-101", "active"), ("A-103", "hors_service")]


def test_no_room_gives_an_empty_list(client, headers):
    response = client.get(URL, headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_filters(client, db, headers):
    make_room(db, code="A-101", capacity=40)
    make_room(db, code="B-201", building="Bâtiment B", room_type=RoomType.SALLE_TP, capacity=24)
    make_room(db, code="C-001", building="Bâtiment C", room_type=RoomType.SALLE_TRAVAIL, capacity=8)
    assert codes(client, headers, q="b-2") == ["B-201"]
    assert codes(client, headers, q="bâtiment c") == ["C-001"]
    assert codes(client, headers, q="  ") == ["A-101", "B-201", "C-001"]
    assert codes(client, headers, building="Bâtiment A") == ["A-101"]
    assert codes(client, headers, room_type="salle_tp") == ["B-201"]
    assert codes(client, headers, min_capacity=20) == ["A-101", "B-201"]
    assert codes(client, headers, q="Z-999") == []


def test_invalid_filters_are_rejected(client, headers):
    assert client.get(URL, params={"room_type": "bureau"}, headers=headers).status_code == 422
    assert client.get(URL, params={"min_capacity": 0}, headers=headers).status_code == 422
