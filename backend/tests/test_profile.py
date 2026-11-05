
import pytest
from sqlalchemy import select

from src.models.audit_log import AuditLog
from src.services import profile_service
from tests.helpers import EMAIL, auth_header, login, reload_user

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture
def headers(client, make_user):
    make_user()
    return auth_header(login(client).json()["access_token"])


def put_photo(client, headers, content: bytes, content_type: str = "image/png"):
    return client.put("/api/me/photo", content=content, headers={**headers, "Content-Type": content_type})


def test_profile_requires_a_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.patch("/api/me", json={}).status_code == 401
    assert client.get("/api/me/photo").status_code == 401


def test_profile_shows_identity_and_preferences(client, headers):
    response = client.get("/api/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": body["id"],
        "email": EMAIL,
        "full_name": "Étudiant Test",
        "role": "etudiant",
        "phone": None,
        "notification_channel": "les_deux",
        "has_photo": False,
    }


def test_user_updates_name_phone_and_notifications(client, db, headers):
    response = client.patch(
        "/api/me",
        json={"full_name": "  Sara   El Amrani ", "phone": "+212 6 12 34 56 78", "notification_channel": "email"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Sara El Amrani"
    assert body["phone"] == "+212 6 12 34 56 78"
    assert body["notification_channel"] == "email"
    # Le nouveau nom est aussi celui de /api/auth/me (barre du haut)
    assert client.get("/api/auth/me", headers=headers).json()["full_name"] == "Sara El Amrani"
    assert db.scalar(select(AuditLog.action).order_by(AuditLog.id.desc())) == "PROFILE_UPDATED"


def test_empty_phone_is_removed(client, headers):
    client.patch("/api/me", json={"full_name": "Sara", "phone": "0612345678", "notification_channel": "email"}, headers=headers)
    body = client.patch(
        "/api/me", json={"full_name": "Sara", "phone": "", "notification_channel": "application"}, headers=headers
    ).json()
    assert body["phone"] is None
    assert body["notification_channel"] == "application"


@pytest.mark.parametrize(
    "changes",
    [
        {"full_name": "S"},
        {"phone": "abc"},
        {"phone": "12"},
        {"notification_channel": "sms"},
    ],
)
def test_invalid_profile_is_rejected(client, headers, changes):
    body = {"full_name": "Sara", "phone": None, "notification_channel": "email", **changes}
    assert client.patch("/api/me", json=body, headers=headers).status_code == 422


def test_email_and_role_cannot_be_changed(client, db, headers):
    client.patch(
        "/api/me",
        json={"full_name": "Sara", "notification_channel": "email", "email": "autre@usms.ac.ma", "role": "administrateur"},
        headers=headers,
    )
    user = reload_user(db)
    assert user.email == EMAIL
    assert user.role.value == "etudiant"


def test_user_uploads_downloads_and_deletes_a_photo(client, db, headers):
    response = put_photo(client, headers, PNG)
    assert response.status_code == 200
    assert response.json()["has_photo"] is True

    photo = client.get("/api/me/photo", headers=headers)
    assert photo.status_code == 200
    assert photo.content == PNG
    assert photo.headers["content-type"] == "image/png"
    assert "no-store" in photo.headers["cache-control"]

    assert put_photo(client, headers, JPEG, "image/jpeg").status_code == 200
    assert client.get("/api/me/photo", headers=headers).headers["content-type"] == "image/jpeg"

    assert client.delete("/api/me/photo", headers=headers).status_code == 204
    assert client.get("/api/me", headers=headers).json()["has_photo"] is False
    missing = client.get("/api/me/photo", headers=headers)
    assert missing.status_code == 404
    assert missing.json() == {"detail": profile_service.NO_PHOTO}
    actions = db.scalars(select(AuditLog.action)).all()
    assert "PROFILE_PHOTO_UPDATED" in actions and "PROFILE_PHOTO_DELETED" in actions


def test_photo_must_be_png_or_jpeg(client, headers):
    response = put_photo(client, headers, b"GIF89a" + b"\x00" * 10, "image/gif")
    assert response.status_code == 415
    assert response.json() == {"detail": profile_service.PHOTO_BAD_TYPE}


def test_photo_content_must_match_its_type(client, headers):
    # Un fichier texte renommé en .png est refusé (ENF-17)
    assert put_photo(client, headers, b"<script>alert(1)</script>", "image/png").status_code == 415


def test_empty_photo_is_refused(client, headers):
    assert put_photo(client, headers, b"").status_code == 400


def test_photo_over_2_megabytes_is_refused(client, headers):
    too_big = PNG + b"\x00" * profile_service.MAX_PHOTO_BYTES
    response = put_photo(client, headers, too_big)
    assert response.status_code == 413
    assert response.json() == {"detail": profile_service.PHOTO_TOO_LARGE}


def test_photo_over_the_limit_without_declared_size_is_refused(db, make_user):
    user = make_user()
    with pytest.raises(profile_service.ServiceError) as error:
        profile_service.set_photo(db, user, PNG + b"\x00" * profile_service.MAX_PHOTO_BYTES, "image/png", None)
    assert error.value.status == 413


def test_login_does_not_load_the_photo(client, db, headers):
    put_photo(client, headers, PNG)
    db.expire_all()
    user = reload_user(db)
    # Colonne différée : absente tant qu'on ne la lit pas
    assert "photo" not in user.__dict__


def test_patch_changes_only_the_fields_sent(client, headers):
    client.patch("/api/me", json={"full_name": "Sara Alami", "phone": "0612345678", "notification_channel": "email"}, headers=headers)
    body = client.patch("/api/me", json={"notification_channel": "application"}, headers=headers).json()
    assert (body["full_name"], body["phone"], body["notification_channel"]) == ("Sara Alami", "0612345678", "application")


def test_profile_shows_every_field_of_the_screen(client, headers):
    """Nom, e-mail, rôle, téléphone, photo et préférences de notification."""
    assert set(client.get("/api/me", headers=headers).json()) == {
        "id", "email", "full_name", "role", "phone", "notification_channel", "has_photo"
    }
