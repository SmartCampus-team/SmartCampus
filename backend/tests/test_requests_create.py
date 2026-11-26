"""Déposer une demande administrative (SC-34 : EF-REQ-01, EF-REQ-02, RG-13)."""

import re
import threading

import pytest
from sqlalchemy import select

from src.database import SessionLocal
from src.models.admin_request import AdminRequest, RequestStatus
from src.models.request_history import RequestHistory
from src.models.user import Role, User
from src.services import campus_clock, request_service
from tests.factories import headers_for

URL = "/api/requests"
BODY = {"request_type": "attestation_scolarite", "description": "Attestation pour le dossier de bourse."}


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


def test_deposit_requires_a_token(client):
    assert client.post(URL, json=BODY).status_code == 401


def test_student_deposits_a_pending_request_with_a_number(client, db, student):
    response = client.post(URL, json=BODY, headers=student)
    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(rf"DA-{campus_clock.now().year}-\d{{5}}", body["number"])
    assert (body["request_type"], body["status"]) == ("attestation_scolarite", "en_attente")
    assert body["description"] == "Attestation pour le dossier de bourse."
    assert body["created_at"] and body["updated_at"]

    stored = db.get(AdminRequest, body["id"])
    assert (stored.number, stored.status) == (body["number"], RequestStatus.EN_ATTENTE)


def test_name_and_email_come_from_the_account(client, student):
    body = {**BODY, "student_email": "autre@usms.ac.ma", "full_name": "Quelqu'un d'autre"}
    response = client.post(URL, json=body, headers=student)
    assert response.json()["student"]["email"] == "etudiant@usms.ac.ma"
    assert response.json()["student"]["full_name"] == "Étudiant Test"


def test_deposit_writes_the_first_history_line(client, db, student):
    request_id = client.post(URL, json=BODY, headers=student).json()["id"]
    [line] = db.scalars(select(RequestHistory).where(RequestHistory.request_id == request_id))
    assert (line.from_status, line.to_status, line.comment) == (None, RequestStatus.EN_ATTENTE, None)
    assert db.get(User, line.author_id).email == "etudiant@usms.ac.ma"


@pytest.mark.parametrize("description", ["", "   ", "ok"])
def test_empty_description_is_refused(client, db, student, description):
    response = client.post(URL, json={**BODY, "description": description}, headers=student)
    assert response.status_code == 422
    assert db.scalar(select(AdminRequest)) is None


def test_unknown_type_is_refused(client, student):
    assert client.post(URL, json={**BODY, "request_type": "passeport"}, headers=student).status_code == 422


@pytest.mark.parametrize("role", [Role.ENSEIGNANT, Role.SCOLARITE, Role.GESTIONNAIRE, Role.ADMINISTRATEUR])
def test_other_roles_cannot_deposit(client, make_user, role):
    assert client.post(URL, json=BODY, headers=headers_for(client, make_user, role)).status_code == 403


def test_numbers_follow_each_other_and_are_never_reused(client, db, student):
    first = client.post(URL, json=BODY, headers=student).json()["number"]
    second = client.post(URL, json=BODY, headers=student).json()["number"]
    assert int(second[-5:]) == int(first[-5:]) + 1
    # Même après la suppression d'une demande, la séquence ne redonne pas son numéro
    db.delete(db.scalar(select(AdminRequest).where(AdminRequest.number == second)))
    db.commit()
    third = client.post(URL, json=BODY, headers=student).json()["number"]
    assert third not in (first, second)


def test_two_simultaneous_deposits_get_two_numbers(db, make_user):
    students = [make_user(email=f"etudiant{n}@usms.ac.ma") for n in range(1, 9)]
    barrier = threading.Barrier(len(students))
    numbers: list[str] = []

    def deposit(student_id: int) -> None:
        with SessionLocal() as session:
            student = session.get(User, student_id)
            barrier.wait()  # les dépôts partent ensemble
            numbers.append(request_service.create_request(session, student, "autre", "Demande simultanée").number)

    threads = [threading.Thread(target=deposit, args=(student.id,)) for student in students]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(numbers) == len(set(numbers)) == len(students)
