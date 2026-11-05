"""Réinitialisation du mot de passe par un lien reçu par e-mail (SC-18, EF-AUTH-05).

- La réponse est la même que l'adresse corresponde à un compte ou non : personne ne peut
  savoir quelles adresses ont un compte (même règle que EF-AUTH-03).
- Le lien est valable 30 min et ne sert qu'une fois ; demander un nouveau lien annule l'ancien.
- La base ne garde que l'empreinte SHA-256 du jeton.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.config import settings
from src.models.password_reset_token import PasswordResetToken
from src.models.user import User
from src.services import audit_service, mail_service
from src.services.auth_service import DOMAIN_REFUSED, find_user_by_email, is_institutional_email, normalize_email
from src.services.common import ServiceError
from src.services.password_policy import check_new_password
from src.services.security import hash_password

RESET_REQUESTED = (
    "Si un compte correspond à cette adresse, un e-mail vient d'être envoyé. "
    "Le lien est valable {minutes} min."
)
INVALID_LINK = "Ce lien n'est plus valable. Demandez un nouveau lien de réinitialisation."
PASSWORD_CHANGED = "Mot de passe modifié. Vous pouvez vous connecter."
MAIL_UNAVAILABLE = "L'e-mail n'a pas pu être envoyé. Réessayez dans quelques minutes."

MAIL_SUBJECT = "SmartCampus : réinitialisation de votre mot de passe"
MAIL_BODY = """Bonjour {name},

Vous avez demandé à réinitialiser votre mot de passe SmartCampus.
Ouvrez ce lien pour choisir un nouveau mot de passe :

{link}

Ce lien est valable {minutes} minutes et ne fonctionne qu'une fois.
Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : votre mot de passe ne change pas.

SmartCampus, ENSA Khouribga
"""


def _now() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_link(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/#/reinitialiser?token={token}"


def _cancel_open_tokens(db: Session, user: User) -> None:
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=_now())
    )


def request_reset(db: Session, email: str, ip: str | None) -> str:
    """Envoie un lien si l'adresse correspond à un compte actif ; renvoie le message à afficher."""
    if not is_institutional_email(email):
        raise ServiceError(400, DOMAIN_REFUSED.format(domain=settings.allowed_email_domain))

    message = RESET_REQUESTED.format(minutes=settings.password_reset_minutes)
    user = find_user_by_email(db, email)
    if user is None or not user.is_active:
        # Rien n'est envoyé, mais la demande est tracée et la réponse reste identique
        audit_service.record(
            db, "PASSWORD_RESET_REQUESTED", actor=user, actor_email=normalize_email(email),
            target="aucun e-mail envoyé", ip=ip,
        )
        db.commit()
        return message

    _cancel_open_tokens(db, user)
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=_now() + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    audit_service.record(db, "PASSWORD_RESET_REQUESTED", actor=user, target="lien envoyé", ip=ip)
    db.commit()

    body = MAIL_BODY.format(
        name=user.full_name, link=reset_link(token), minutes=settings.password_reset_minutes
    )
    try:
        mail_service.send_mail(user.email, MAIL_SUBJECT, body)
    except mail_service.MailError:
        raise ServiceError(503, MAIL_UNAVAILABLE) from None
    return message


def _valid_link(db: Session, token: str) -> User:
    """Titulaire d'un lien encore valable : connu, non utilisé, non expiré, compte actif ; 400 sinon."""
    reset = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    if reset is None or reset.used_at is not None or reset.expires_at <= _now():
        raise ServiceError(400, INVALID_LINK)
    user = db.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise ServiceError(400, INVALID_LINK)
    return user


def check_link(db: Session, token: str) -> None:
    """Vérifie le lien dès son ouverture, avant la saisie du nouveau mot de passe."""
    _valid_link(db, token)


def reset_password(db: Session, token: str, new_password: str, ip: str | None) -> None:
    """Change le mot de passe si le lien est valable ; débloque aussi le compte (RG-02)."""
    user = _valid_link(db, token)
    check_new_password(new_password)

    user.password_hash = hash_password(new_password)
    user.failed_attempts = 0
    user.locked_until = None
    _cancel_open_tokens(db, user)
    audit_service.record(db, "PASSWORD_RESET", actor=user, ip=ip)
    db.commit()
