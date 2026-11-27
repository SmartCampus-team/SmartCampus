"""Consulter « Mes demandes » (SC-35 : EF-REQ-04, RG-14, ENF-16)."""

from datetime import timedelta

import pytest

from src.models.admin_request import RequestStatus, RequestType
from src.models.user import Role
from src.services import campus_clock, request_service
from tests.factories import headers_for
from tests.helpers import reload_user

URL = "/api/requests/me"


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def me(db, student):
    return reload_user(db, "etudiant@usms.ac.ma")


def deposit(db, user, request_type=RequestType.ATTESTATION_SCOLARITE, status=RequestStatus.EN_ATTENTE, days_ago=0):
    request = request_service.create_request(db, user, request_type, "Demande de test")
    request.status = status
    request.created_at = request.updated_at = campus_clock.now() - timedelta(days=days_ago)
    db.commit()
    return request


def numbers(response) -> list[str]:
    return [line["number"] for line in response.json()]


def test_my_requests_requires_a_token(client):
    assert client.get(URL).status_code == 401


def test_each_line_shows_number_type_status_and_dates(client, db, student, me):
    request = deposit(db, me)
    [line] = client.get(URL, headers=student).json()
    assert line == {
        "id": request.id,
        "number": request.number,
        "request_type": "attestation_scolarite",
        "status": "en_attente",
        "created_at": line["created_at"],
        "updated_at": line["updated_at"],
    }
    assert line["created_at"] and line["updated_at"]


def test_latest_update_comes_first(client, db, student, me):
    old = deposit(db, me, days_ago=5)
    recent = deposit(db, me, days_ago=1)
    assert numbers(client.get(URL, headers=student)) == [recent.number, old.number]


def test_i_only_see_my_requests(client, db, make_user, student, me):
    other = make_user(email="autre@usms.ac.ma")
    mine = deposit(db, me)
    deposit(db, other)
    assert numbers(client.get(URL, headers=student)) == [mine.number]
    # Aucun paramètre ne permet de voir celles d'un autre : il n'y a pas de filtre par étudiant
    assert numbers(client.get(URL, params={"student_id": other.id}, headers=student)) == [mine.number]


def test_search_by_number(client, db, student, me):
    first = deposit(db, me)
    deposit(db, me)
    assert numbers(client.get(URL, params={"q": first.number[-5:]}, headers=student)) == [first.number]
    assert numbers(client.get(URL, params={"q": first.number.lower()}, headers=student)) == [first.number]
    assert client.get(URL, params={"q": "DA-1999"}, headers=student).json() == []


def test_filter_by_status_and_type(client, db, student, me):
    pending = deposit(db, me, RequestType.RELEVE_NOTES)
    accepted = deposit(db, me, RequestType.RELEVE_NOTES, RequestStatus.ACCEPTEE)
    deposit(db, me, RequestType.DEMANDE_STAGE, RequestStatus.ACCEPTEE)
    assert numbers(client.get(URL, params={"status": "en_attente"}, headers=student)) == [pending.number]
    both = {"status": "acceptee", "type": "releve_notes"}
    assert numbers(client.get(URL, params=both, headers=student)) == [accepted.number]


def test_unknown_filter_value_is_refused(client, student):
    assert client.get(URL, params={"status": "perdue"}, headers=student).status_code == 422


def test_no_request_gives_an_empty_list(client, student):
    assert client.get(URL, headers=student).json() == []


@pytest.mark.parametrize("role", [Role.ENSEIGNANT, Role.SCOLARITE, Role.GESTIONNAIRE])
def test_my_requests_is_for_students(client, make_user, role):
    assert client.get(URL, headers=headers_for(client, make_user, role)).status_code == 403
