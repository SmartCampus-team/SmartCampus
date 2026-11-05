"""Gestion des comptes et des rôles (SC-17 : EF-AUTH-07, RG-11, ENF-03)."""

import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.models.user import Role, User
from src.services import account_service
from tests.factories import headers_for
from tests.helpers import EMAIL, auth_header, login, reload_user

URL = "/api/users"
NEW = {"email": "Nouvelle.Etudiante@USMS.ac.ma", "full_name": "Nouvelle  Étudiante", "role": "etudiant"}


@pytest.fixture
def admin(client, make_user):
    return headers_for(client, make_user, Role.ADMINISTRATEUR)


def admin_id(db) -> int:
    return db.scalar(select(User.id).where(User.email == "administrateur@usms.ac.ma"))


def audit(db) -> list[tuple[str, str | None]]:
    db.expire_all()
    return list(db.execute(select(AuditLog.action, AuditLog.target).order_by(AuditLog.id)).tuples())


def audit_actions(db) -> list[str]:
    return [action for action, _ in audit(db)]


@pytest.mark.parametrize("role", [Role.ETUDIANT, Role.ENSEIGNANT, Role.GESTIONNAIRE, Role.SCOLARITE])
def test_non_administrators_get_403(client, db, make_user, role):
    headers = headers_for(client, make_user, role)
    user_id = db.scalar(select(User.id))
    assert client.get(URL, headers=headers).status_code == 403
    assert client.post(URL, json=NEW, headers=headers).status_code == 403
    assert client.patch(f"{URL}/{user_id}", json={"is_active": False}, headers=headers).status_code == 403


def test_accounts_require_a_token(client):
    assert client.get(URL).status_code == 401


def test_administrator_creates_an_active_account(client, db, admin):
    response = client.post(URL, json=NEW, headers=admin)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "nouvelle.etudiante@usms.ac.ma"  # adresse normalisée
    assert body["full_name"] == "Nouvelle Étudiante"
    assert (body["role"], body["is_active"]) == ("etudiant", True)
    # Le compte apparaît actif dans la liste
    listed = {a["email"]: a for a in client.get(URL, headers=admin).json()}
    assert listed["nouvelle.etudiante@usms.ac.ma"]["is_active"] is True
    assert ("USER_CREATED", "nouvelle.etudiante@usms.ac.ma (etudiant)") in audit(db)


def test_created_account_has_no_known_password(client, admin):
    client.post(URL, json=NEW, headers=admin)
    # Le titulaire choisira son mot de passe avec le lien de réinitialisation (SC-18)
    for guess in ("SmartCampus2026!", "MotDePasse-2026"):
        assert login(client, email="nouvelle.etudiante@usms.ac.ma", password=guess).status_code == 401


def test_email_outside_domain_is_refused_with_a_precise_message(client, admin):
    response = client.post(URL, json={**NEW, "email": "sara@gmail.com"}, headers=admin)
    assert response.status_code == 400
    assert response.json() == {"detail": "Utilisez votre adresse e-mail institutionnelle (@usms.ac.ma)."}


def test_email_already_used_is_refused_with_a_precise_message(client, make_user, admin):
    make_user(email="sara@usms.ac.ma")
    response = client.post(URL, json={**NEW, "email": "SARA@usms.ac.ma"}, headers=admin)
    assert response.status_code == 409
    assert response.json() == {"detail": "Un compte existe déjà pour l'adresse sara@usms.ac.ma."}


@pytest.mark.parametrize("changes", [{"role": "directeur"}, {"full_name": "A"}, {"email": ""}])
def test_invalid_data_is_rejected(client, admin, changes):
    assert client.post(URL, json={**NEW, **changes}, headers=admin).status_code == 422


def test_list_filters(client, make_user, admin):
    make_user(email="sara@usms.ac.ma", role=Role.ETUDIANT)
    make_user(email="prof@usms.ac.ma", role=Role.ENSEIGNANT, is_active=False)

    def emails(**params):
        return [a["email"] for a in client.get(URL, params=params, headers=admin).json()]

    assert set(emails()) == {"administrateur@usms.ac.ma", "sara@usms.ac.ma", "prof@usms.ac.ma"}
    assert emails(role="enseignant") == ["prof@usms.ac.ma"]
    assert emails(active="false") == ["prof@usms.ac.ma"]
    assert emails(q="SARA") == ["sara@usms.ac.ma"]


def test_role_change_applies_at_once_and_is_logged(client, db, make_user, admin):
    student = make_user(email=EMAIL)
    token = login(client).json()["access_token"]
    response = client.patch(f"{URL}/{student.id}", json={"role": "enseignant"}, headers=admin)
    assert response.status_code == 200
    assert response.json()["role"] == "enseignant"
    # Le rôle est relu à chaque requête : la session en cours voit le nouveau rôle
    assert client.get("/api/auth/me", headers=auth_header(token)).json()["role"] == "enseignant"
    assert ("USER_ROLE_CHANGED", f"{EMAIL} : etudiant → enseignant") in audit(db)


def test_name_and_email_can_be_changed(client, db, make_user, admin):
    student = make_user(email=EMAIL)
    response = client.patch(
        f"{URL}/{student.id}", json={"email": "sara.alami@usms.ac.ma", "full_name": "Sara  Alami"}, headers=admin
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Sara Alami"
    assert login(client, email="sara.alami@usms.ac.ma").status_code == 200
    assert "USER_UPDATED" in audit_actions(db)


def test_update_cannot_take_the_email_of_another_account(client, make_user, admin):
    make_user(email="sara@usms.ac.ma")
    other = make_user(email="nora@usms.ac.ma")
    response = client.patch(f"{URL}/{other.id}", json={"email": "sara@usms.ac.ma"}, headers=admin)
    assert response.status_code == 409


def test_deactivated_account_cannot_log_in_and_loses_its_sessions(client, db, make_user, admin):
    student = make_user(email=EMAIL)
    token = login(client).json()["access_token"]
    response = client.patch(f"{URL}/{student.id}", json={"is_active": False}, headers=admin)
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert login(client).status_code == 403
    assert client.get("/api/auth/me", headers=auth_header(token)).status_code == 401
    assert "USER_DEACTIVATED" in audit_actions(db)
    # Le compte n'est jamais supprimé : il peut être réactivé
    assert reload_user(db) is not None
    client.patch(f"{URL}/{student.id}", json={"is_active": True}, headers=admin)
    assert login(client).status_code == 200
    assert "USER_REACTIVATED" in audit_actions(db)


def test_unchanged_values_write_nothing(client, db, make_user, admin):
    student = make_user(email=EMAIL)
    before = len(audit(db))
    client.patch(f"{URL}/{student.id}", json={"role": "etudiant", "is_active": True, "email": EMAIL}, headers=admin)
    assert len(audit(db)) == before


def test_administrator_cannot_deactivate_or_demote_themself(client, db, admin):
    me = admin_id(db)
    for changes in ({"is_active": False}, {"role": "etudiant"}):
        response = client.patch(f"{URL}/{me}", json=changes, headers=admin)
        assert response.status_code == 409
        assert response.json() == {"detail": account_service.SELF_PROTECTION}
    assert client.patch(f"{URL}/{me}", json={"full_name": "Admin Principal"}, headers=admin).status_code == 200


def test_unknown_account_is_404(client, admin):
    response = client.patch(f"{URL}/9999", json={"is_active": False}, headers=admin)
    assert response.status_code == 404
    assert response.json() == {"detail": account_service.USER_NOT_FOUND}
