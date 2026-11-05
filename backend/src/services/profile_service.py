
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.user import NotificationChannel, User
from src.services import audit_service
from src.services.common import ServiceError

MAX_PHOTO_BYTES = 2 * 1024 * 1024
PHOTO_SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}

PHOTO_TOO_LARGE = "Photo trop lourde : 2 Mo au plus."
PHOTO_BAD_TYPE = "Format refusé : choisissez une image PNG ou JPEG."
PHOTO_EMPTY = "Aucune image reçue."
NO_PHOTO = "Aucune photo de profil."


@dataclass
class ProfileChanges:
    """Champs à modifier ; None = inchangé. Un téléphone vide ("") efface le numéro."""

    full_name: str | None = None
    phone: str | None = None
    notification_channel: NotificationChannel | None = None


def update_profile(db: Session, user: User, changes: ProfileChanges, ip: str | None) -> User:
    if changes.full_name is not None:
        user.full_name = " ".join(changes.full_name.split())  # espaces superflus retirés
    if changes.phone is not None:
        user.phone = changes.phone.strip() or None
    if changes.notification_channel is not None:
        user.notification_channel = changes.notification_channel
    audit_service.record(db, "PROFILE_UPDATED", actor=user, ip=ip)
    db.commit()
    return user


def set_photo(db: Session, user: User, content: bytes, content_type: str | None, ip: str | None) -> User:
    """Enregistre la photo après avoir vérifié sa taille et son vrai format (signature du fichier)."""
    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type not in PHOTO_SIGNATURES:
        raise ServiceError(415, PHOTO_BAD_TYPE)
    if not content:
        raise ServiceError(400, PHOTO_EMPTY)
    if len(content) > MAX_PHOTO_BYTES:
        raise ServiceError(413, PHOTO_TOO_LARGE)
    if not content.startswith(PHOTO_SIGNATURES[media_type]):
        # Le contenu ne correspond pas au type annoncé (fichier renommé, par exemple)
        raise ServiceError(415, PHOTO_BAD_TYPE)

    user.photo = content
    user.photo_type = media_type
    audit_service.record(db, "PROFILE_PHOTO_UPDATED", actor=user, ip=ip)
    db.commit()
    return user


def get_photo(user: User) -> tuple[bytes, str]:
    if user.photo_type is None or user.photo is None:
        raise ServiceError(404, NO_PHOTO)
    return user.photo, user.photo_type


def delete_photo(db: Session, user: User, ip: str | None) -> None:
    user.photo = None
    user.photo_type = None
    audit_service.record(db, "PROFILE_PHOTO_DELETED", actor=user, ip=ip)
    db.commit()
