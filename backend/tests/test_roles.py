"""Dépendance de contrôle du rôle : un cas par rôle (SC-17 : ENF-03)."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.deps import FORBIDDEN, require_roles
from src.main import auth_error
from src.models.user import Role, User
from src.services.common import AuthError
from tests.factories import headers_for

# Application de test : une route réservée à l'administrateur, une autre au gestionnaire et à l'administrateur
role_app = FastAPI()
role_app.add_exception_handler(AuthError, auth_error)


@role_app.get("/admin")
def admin_only(user: User = Depends(require_roles(Role.ADMINISTRATEUR))):
    return {"role": user.role.value}


@role_app.get("/salles")
def managers(user: User = Depends(require_roles(Role.GESTIONNAIRE, Role.ADMINISTRATEUR))):
    return {"role": user.role.value}


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ETUDIANT, 403),
        (Role.ENSEIGNANT, 403),
        (Role.GESTIONNAIRE, 403),
        (Role.SCOLARITE, 403),
        (Role.ADMINISTRATEUR, 200),
    ],
)
def test_admin_route_accepts_only_the_administrator(client, make_user, role, expected):
    headers = headers_for(client, make_user, role)
    with TestClient(role_app) as role_client:
        response = role_client.get("/admin", headers=headers)
    assert response.status_code == expected
    if expected == 403:
        assert response.json() == {"detail": FORBIDDEN}
    else:
        assert response.json() == {"role": "administrateur"}


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ETUDIANT, 403),
        (Role.ENSEIGNANT, 403),
        (Role.GESTIONNAIRE, 200),
        (Role.SCOLARITE, 403),
        (Role.ADMINISTRATEUR, 200),
    ],
)
def test_route_with_several_roles(client, make_user, role, expected):
    headers = headers_for(client, make_user, role)
    with TestClient(role_app) as role_client:
        assert role_client.get("/salles", headers=headers).status_code == expected


def test_protected_route_still_requires_a_token():
    with TestClient(role_app) as role_client:
        assert role_client.get("/admin").status_code == 401


def test_role_is_read_again_on_each_request(client, db, make_user):
    headers = headers_for(client, make_user, Role.ETUDIANT)
    user = db.query(User).filter_by(email="etudiant@usms.ac.ma").one()
    user.role = Role.ADMINISTRATEUR
    db.commit()
    with TestClient(role_app) as role_client:
        assert role_client.get("/admin", headers=headers).status_code == 200
