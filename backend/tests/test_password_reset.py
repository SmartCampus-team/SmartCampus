"""Réinitialisation du mot de passe par e-mail (SC-18 : EF-AUTH-05, RG-02)."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.config import settings
from src.models.audit_log import AuditLog
from src.models.password_reset_token import PasswordResetToken
from src.models.user import Role
from src.services import mail_service, password_reset_service
from src.services.password_policy import PASSWORD_POLICY, is_acceptable
from tests.factories import headers_for
from tests.helpers import EMAIL, PASSWORD, login, reload_user

NEW_PASSWORD = "NouveauMotDePasse-2027"


@pytest.fixture(autouse=True)
def empty_outbox():
    mail_service.OUTBOX.clear()
    yield
    mail_service.OUTBOX.clear()


def forgot(client, email=EMAIL):
    return client.post("/api/auth/password/forgot", json={"email": email})


def reset(client, token, password=NEW_PASSWORD):
    return client.post("/api/auth/password/reset", json={"token": token, "new_password": password})


def token_from_last_mail() -> str:
    match = re.search(r"#/reinitialiser\?token=([\w-]+)", mail_service.OUTBOX[-1].body)
    assert match is not None
    return match.group(1)


def test_forgot_password_sends_a_link_valid_30_minutes(client, db, make_user):
    make_user()
    response = forgot(client)
    assert response.status_code == 202
    assert "30 min" in response.json()["detail"]

    assert len(mail_service.OUTBOX) == 1
    mail = mail_service.OUTBOX[0]
    assert mail.to == EMAIL
    assert "réinitialisation" in mail.subject
    assert f"{settings.frontend_url}/#/reinitialiser?token=" in mail.body

    stored = db.scalar(select(PasswordResetToken))
    minutes = (stored.expires_at - datetime.now(UTC)).total_seconds() / 60
    assert 29 < minutes <= 30


def test_only_the_hash_of_the_token_is_stored(client, db, make_user):
    make_user()
    forgot(client)
    token = token_from_last_mail()
    stored = db.scalar(select(PasswordResetToken))
    assert stored.token_hash != token
    assert stored.token_hash == password_reset_service.hash_token(token)


def test_unknown_email_gets_the_same_answer_and_no_mail(client, db, make_user):
    make_user()
    known = forgot(client)
    mail_service.OUTBOX.clear()
    unknown = forgot(client, "inconnu@usms.ac.ma")
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert mail_service.OUTBOX == []
    entry = db.scalar(select(AuditLog).where(AuditLog.actor_email == "inconnu@usms.ac.ma"))
    assert entry.action == "PASSWORD_RESET_REQUESTED"


def test_disabled_account_receives_no_mail(client, make_user):
    make_user(is_active=False)
    assert forgot(client).status_code == 202
    assert mail_service.OUTBOX == []


def test_email_outside_domain_is_refused(client):
    response = forgot(client, "etudiant@gmail.com")
    assert response.status_code == 400
    assert "@usms.ac.ma" in response.json()["detail"]


def test_link_sets_the_new_password(client, db, make_user):
    make_user()
    forgot(client)
    response = reset(client, token_from_last_mail())
    assert response.status_code == 200
    assert response.json() == {"detail": password_reset_service.PASSWORD_CHANGED}
    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200
    actions = db.scalars(select(AuditLog.action).order_by(AuditLog.id)).all()
    assert "PASSWORD_RESET" in actions


def test_link_works_only_once(client, make_user):
    make_user()
    forgot(client)
    token = token_from_last_mail()
    assert reset(client, token).status_code == 200
    second = reset(client, token, "EncoreUnAutre-2028")
    assert second.status_code == 400
    assert second.json() == {"detail": password_reset_service.INVALID_LINK}


def test_new_request_cancels_the_previous_link(client, make_user):
    make_user()
    forgot(client)
    first = token_from_last_mail()
    forgot(client)
    second = token_from_last_mail()
    assert reset(client, first).status_code == 400
    assert reset(client, second).status_code == 200


def test_expired_link_is_refused(client, db, make_user):
    make_user()
    forgot(client)
    stored = db.scalar(select(PasswordResetToken))
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert reset(client, token_from_last_mail()).status_code == 400


def test_unknown_token_is_refused(client):
    response = reset(client, "jeton-qui-n-existe-pas")
    assert response.status_code == 400
    assert response.json() == {"detail": password_reset_service.INVALID_LINK}


def test_account_disabled_after_the_request_cannot_reset(client, db, make_user):
    make_user()
    forgot(client)
    user = reload_user(db)
    user.is_active = False
    db.commit()
    assert reset(client, token_from_last_mail()).status_code == 400


@pytest.mark.parametrize("weak", ["court1", "sanschiffre", "12345678901", "a1" * 40])
def test_weak_password_is_refused_and_the_link_stays_valid(client, make_user, weak):
    make_user()
    forgot(client)
    token = token_from_last_mail()
    response = reset(client, token, weak)
    assert response.status_code == 400
    assert response.json() == {"detail": PASSWORD_POLICY}
    assert reset(client, token).status_code == 200


def test_password_policy():
    assert is_acceptable("Campus2026")
    assert is_acceptable("ÉtéÀKhouribga1")
    assert not is_acceptable("Campus")
    assert not is_acceptable("é" * 40 + "1")  # 81 octets : trop long pour bcrypt


def test_reset_unlocks_a_locked_account(client, db, make_user):
    make_user()
    for _ in range(3):
        login(client, password="faux")
    assert login(client).status_code == 423
    forgot(client)
    assert reset(client, token_from_last_mail()).status_code == 200
    user = reload_user(db)
    assert user.failed_attempts == 0
    assert user.locked_until is None
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_mail_failure_returns_503(client, make_user, monkeypatch):
    make_user()

    def broken(to, subject, body):
        raise mail_service.MailError("SMTP injoignable")

    monkeypatch.setattr(mail_service, "send_mail", broken)
    response = forgot(client)
    assert response.status_code == 503
    assert response.json() == {"detail": password_reset_service.MAIL_UNAVAILABLE}


def check(client, token):
    return client.post("/api/auth/password/check", json={"token": token})


def test_link_is_checked_when_it_is_opened(client, db, make_user):
    make_user()
    forgot(client)
    token = token_from_last_mail()
    response = check(client, token)
    assert response.status_code == 200
    assert response.json() == {"detail": "Lien valable."}
    # Vérifier le lien ne le consomme pas
    assert reset(client, token).status_code == 200
    # Une fois utilisé, il est refusé dès l'ouverture
    refused = check(client, token)
    assert refused.status_code == 400
    assert refused.json() == {"detail": password_reset_service.INVALID_LINK}


def test_expired_or_unknown_link_is_refused_when_opened(client, db, make_user):
    make_user()
    forgot(client)
    stored = db.scalar(select(PasswordResetToken))
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert check(client, token_from_last_mail()).status_code == 400
    assert check(client, "jeton-qui-n-existe-pas").status_code == 400


def test_account_created_by_the_administrator_chooses_its_password_with_the_link(client, make_user):
    """SC-17 crée le compte sans mot de passe connu ; son titulaire le choisit ici."""
    admin = headers_for(client, make_user, Role.ADMINISTRATEUR)
    client.post("/api/users", json={"email": "nouveau@usms.ac.ma", "full_name": "Nouveau Compte", "role": "etudiant"}, headers=admin)
    forgot(client, "nouveau@usms.ac.ma")
    assert reset(client, token_from_last_mail()).status_code == 200
    assert login(client, email="nouveau@usms.ac.ma", password=NEW_PASSWORD).status_code == 200
