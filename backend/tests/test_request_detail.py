"""Consulter le détail d'une de ses demandes (SC-36 : EF-REQ-05, RG-14, ENF-16)."""

import pytest

from src.models.admin_request import RequestType
from src.models.user import Role
from src.services import request_service
from tests.factories import headers_for
from tests.helpers import reload_user


@pytest.fixture
def student(client, make_user):
    return headers_for(client, make_user, Role.ETUDIANT)


@pytest.fixture
def mine(db, student):
    me = reload_user(db, "etudiant@usms.ac.ma")
    return request_service.create_request(db, me, RequestType.RELEVE_NOTES, "Relevé du semestre 3")


@pytest.fixture
def theirs(db, make_user):
    other = make_user(email="autre@usms.ac.ma")
    return request_service.create_request(db, other, RequestType.DEMANDE_STAGE, "Convention de stage")


def url(request_id: int) -> str:
    return f"/api/requests/{request_id}"


def test_detail_requires_a_token(client, mine):
    assert client.get(url(mine.id)).status_code == 401


def test_student_opens_his_request(client, student, mine):
    response = client.get(url(mine.id), headers=student)
    assert response.status_code == 200
    body = response.json()
    assert (body["number"], body["request_type"], body["status"]) == (mine.number, "releve_notes", "en_attente")
    assert body["description"] == "Relevé du semestre 3"
    assert body["created_at"] and body["updated_at"]


def test_someone_elses_request_is_not_found(client, student, theirs):
    """Même en changeant l'identifiant dans l'URL : 404, comme une demande qui n'existe pas."""
    for request_id in (theirs.id, theirs.id + 1000):
        response = client.get(url(request_id), headers=student)
        assert response.status_code == 404
        assert response.json()["detail"] == "Demande introuvable."


def test_registrar_opens_any_request(client, make_user, mine, theirs):
    registrar = headers_for(client, make_user, Role.SCOLARITE)
    for request in (mine, theirs):
        body = client.get(url(request.id), headers=registrar).json()
        assert body["number"] == request.number
    assert client.get(url(theirs.id), headers=registrar).json()["student"]["email"] == "autre@usms.ac.ma"


@pytest.mark.parametrize("role", [Role.ENSEIGNANT, Role.GESTIONNAIRE, Role.ADMINISTRATEUR])
def test_other_roles_cannot_open_a_request(client, make_user, mine, role):
    assert client.get(url(mine.id), headers=headers_for(client, make_user, role)).status_code == 403
