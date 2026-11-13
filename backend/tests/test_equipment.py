"""Gérer le catalogue d'équipements (SC-31 : EF-ROOM-05) et filtrer la recherche par équipement."""

from datetime import time

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.equipment import Equipment, EquipmentCategory
from src.models.room import Room, RoomStatus
from src.models.user import Role
from tests.factories import headers_for, make_booking, make_room, open_day

URL = "/api/equipment"


@pytest.fixture
def manager(client, make_user):
    return headers_for(client, make_user, Role.GESTIONNAIRE)


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


def make_equipment(db, label="Vidéoprojecteur", category=EquipmentCategory.AUDIOVISUEL) -> Equipment:
    equipment = Equipment(label=label, category=category)
    db.add(equipment)
    db.commit()
    return equipment


def equip(client, headers, room, *equipment):
    body = {"equipment_ids": [item.id for item in equipment]}
    return client.put(f"/api/rooms/{room.id}/equipment", json=body, headers=headers)


def audit(db, action: str) -> list[str]:
    return list(db.scalars(select(AuditLog.target).where(AuditLog.action == action).order_by(AuditLog.id)))


# Catalogue


def test_manager_creates_an_equipment_shown_in_the_catalogue(client, db, manager, student):
    response = client.post(URL, json={"label": "  Tableau   blanc ", "category": "mobilier"}, headers=manager)
    assert response.status_code == 201
    assert response.json() == {"id": response.json()["id"], "label": "Tableau blanc", "category": "mobilier"}

    # Tout utilisateur lit le catalogue (filtre de la recherche)
    catalogue = client.get(URL, headers=student).json()
    assert [(item["label"], item["room_count"]) for item in catalogue] == [("Tableau blanc", 0)]
    assert audit(db, "EQUIPMENT_CREATED") == ["Tableau blanc"]


def test_catalogue_is_sorted_by_category_then_label(client, db, student):
    make_equipment(db, "Wi-Fi", EquipmentCategory.INFORMATIQUE)
    make_equipment(db, "Vidéoprojecteur", EquipmentCategory.AUDIOVISUEL)
    make_equipment(db, "Ordinateurs", EquipmentCategory.INFORMATIQUE)
    labels = [item["label"] for item in client.get(URL, headers=student).json()]
    assert labels == ["Vidéoprojecteur", "Ordinateurs", "Wi-Fi"]


def test_label_already_used_is_refused(client, db, manager):
    make_equipment(db, "Vidéoprojecteur")
    response = client.post(URL, json={"label": "vidéoprojecteur", "category": "audiovisuel"}, headers=manager)
    assert response.status_code == 409
    assert response.json()["detail"] == "L'équipement « vidéoprojecteur » existe déjà."


def test_manager_renames_or_recategorises_an_equipment(client, db, manager):
    item = make_equipment(db, "Projecteur")
    make_equipment(db, "Climatisation", EquipmentCategory.CONFORT)
    response = client.patch(f"{URL}/{item.id}", json={"label": "Vidéoprojecteur"}, headers=manager)
    assert (response.status_code, response.json()["label"]) == (200, "Vidéoprojecteur")
    response = client.patch(f"{URL}/{item.id}", json={"category": "informatique"}, headers=manager)
    assert response.json()["category"] == "informatique"
    assert client.patch(f"{URL}/{item.id}", json={"label": "Climatisation"}, headers=manager).status_code == 409
    assert client.patch(f"{URL}/{item.id + 100}", json={"label": "X-Y"}, headers=manager).status_code == 404
    assert audit(db, "EQUIPMENT_UPDATED") == ["Vidéoprojecteur", "Vidéoprojecteur"]


@pytest.mark.parametrize("role", [Role.ETUDIANT, Role.ENSEIGNANT, Role.ADMINISTRATEUR])
def test_only_the_manager_changes_the_catalogue(client, db, make_user, role):
    headers = headers_for(client, make_user, role)
    item = make_equipment(db)
    room = make_room(db)
    assert client.post(URL, json={"label": "Wi-Fi", "category": "informatique"}, headers=headers).status_code == 403
    assert client.patch(f"{URL}/{item.id}", json={"label": "Wi-Fi"}, headers=headers).status_code == 403
    assert equip(client, headers, room, item).status_code == 403


def test_catalogue_requires_a_token(client):
    assert client.get(URL).status_code == 401


# Affectation aux salles


def test_assigned_equipment_shows_on_the_room(client, db, manager, student):
    room = make_room(db, code="A-101")
    board = make_equipment(db, "Tableau blanc", EquipmentCategory.MOBILIER)
    projector = make_equipment(db, "Vidéoprojecteur")
    response = equip(client, manager, room, projector, board)
    assert response.status_code == 200
    assert [item["label"] for item in response.json()["equipment"]] == ["Tableau blanc", "Vidéoprojecteur"]

    [listed] = client.get("/api/rooms", headers=student).json()
    assert [item["label"] for item in listed["equipment"]] == ["Tableau blanc", "Vidéoprojecteur"]
    catalogue = {item["label"]: item["room_count"] for item in client.get(URL, headers=student).json()}
    assert catalogue == {"Tableau blanc": 1, "Vidéoprojecteur": 1}
    assert audit(db, "ROOM_EQUIPMENT_UPDATED") == ["A-101 : +Tableau blanc, +Vidéoprojecteur"]


def test_removing_and_adding_are_both_logged(client, db, manager):
    room = make_room(db, code="A-101")
    board = make_equipment(db, "Tableau blanc", EquipmentCategory.MOBILIER)
    projector = make_equipment(db, "Vidéoprojecteur")
    equip(client, manager, room, board)
    equip(client, manager, room, projector)
    equip(client, manager, room, projector)
    assert audit(db, "ROOM_EQUIPMENT_UPDATED")[1:] == [
        "A-101 : +Vidéoprojecteur, -Tableau blanc",
        "A-101 : aucun changement",
    ]


def test_unknown_equipment_or_archived_room_is_refused(client, db, manager):
    room = make_room(db, code="A-101")
    archived = make_room(db, code="D-001", status=RoomStatus.ARCHIVEE)
    item = make_equipment(db)
    response = client.put(f"/api/rooms/{room.id}/equipment", json={"equipment_ids": [item.id, 999]}, headers=manager)
    assert (response.status_code, response.json()["detail"]) == (400, "Équipement introuvable : 999.")
    assert equip(client, manager, archived, item).status_code == 409
    assert client.put("/api/rooms/9999/equipment", json={"equipment_ids": []}, headers=manager).status_code == 404


# Filtre de la liste et de la recherche (SC-22, 2e critère)


@pytest.fixture
def equipped(db):
    """A-101 a un vidéoprojecteur et un tableau blanc, A-102 un tableau blanc, B-201 rien."""
    projector = make_equipment(db, "Vidéoprojecteur")
    board = make_equipment(db, "Tableau blanc", EquipmentCategory.MOBILIER)
    rooms = {code: make_room(db, code=code) for code in ("A-101", "A-102", "B-201")}
    rooms["A-101"].equipment = [projector, board]
    rooms["A-102"].equipment = [board]
    db.commit()
    return projector, board, rooms


def available(client, headers, *equipment_ids) -> list[str]:
    params = {"date": open_day().isoformat(), "start": "10:00", "end": "12:00", "equipment": list(equipment_ids)}
    return [room["code"] for room in client.get("/api/rooms/available", params=params, headers=headers).json()["rooms"]]


def test_search_returns_only_rooms_with_every_chosen_equipment(client, student, equipped):
    projector, board, _ = equipped
    assert available(client, student, board.id) == ["A-101", "A-102"]
    assert available(client, student, board.id, projector.id) == ["A-101"]
    listed = client.get("/api/rooms", params={"equipment": projector.id}, headers=student).json()
    assert [room["code"] for room in listed] == ["A-101"]


def test_equipment_filter_still_excludes_booked_rooms(client, db, make_user, student, equipped):
    _, board, rooms = equipped
    teacher = make_user(email="prof@usms.ac.ma", role=Role.ENSEIGNANT)
    make_booking(db, rooms["A-101"], teacher, open_day(), time(10), time(12))
    assert available(client, student, board.id) == ["A-102"]


def test_room_without_the_equipment_no_longer_matches(client, db, manager, student, equipped):
    projector, board, rooms = equipped
    equip(client, manager, rooms["A-101"], board)  # le vidéoprojecteur est retiré
    assert available(client, student, projector.id) == []
    db.expire_all()
    assert [item.label for item in db.get(Room, rooms["A-101"].id).equipment] == ["Tableau blanc"]
