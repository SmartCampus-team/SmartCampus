"""Gestion des comptes et des rôles par l'administrateur système (SC-17 : EF-AUTH-07, RG-11).

- Un compte n'est jamais supprimé : il est désactivé, ce qui refuse la connexion et coupe
  ses sessions en cours (get_current_session refuse le jeton d'un compte désactivé).
- L'administrateur ne fixe pas le mot de passe : le titulaire le choisit avec le lien de
  réinitialisation (SC-18). D'ici là, le compte a un mot de passe aléatoire que personne ne connaît.
- Chaque création, changement de rôle et désactivation écrit une ligne dans AuditLog.
"""

import secrets
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import settings
from src.models.user import Role, User
from src.services import audit_service
from src.services.auth_service import DOMAIN_REFUSED, find_user_by_email, is_institutional_email, normalize_email
from src.services.common import ServiceError
from src.services.security import hash_password

USER_NOT_FOUND = "Compte introuvable."
EMAIL_TAKEN = "Un compte existe déjà pour l'adresse {email}."
SELF_PROTECTION = "Vous ne pouvez ni désactiver votre propre compte ni retirer vos droits d'administrateur."


@dataclass
class AccountFilters:
    query: str | None = None  # nom ou e-mail, sans tenir compte des majuscules
    role: Role | None = None
    active: bool | None = None


@dataclass
class AccountChanges:
    """Champs à modifier ; None = inchangé."""

    email: str | None = None
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None


def clean_name(full_name: str) -> str:
    return " ".join(full_name.split())


def list_accounts(db: Session, filters: AccountFilters) -> list[User]:
    statement = select(User).order_by(User.full_name, User.email)
    if filters.query:
        pattern = f"%{filters.query.strip()}%"
        statement = statement.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    if filters.role:
        statement = statement.where(User.role == filters.role)
    if filters.active is not None:
        statement = statement.where(User.is_active.is_(filters.active))
    return list(db.scalars(statement))


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ServiceError(404, USER_NOT_FOUND)
    return user


def _check_email(db: Session, email: str, user_id: int | None = None) -> str:
    """Adresse de l'établissement (RG-11) et pas encore utilisée ; renvoie l'adresse normalisée."""
    if not is_institutional_email(email):
        raise ServiceError(400, DOMAIN_REFUSED.format(domain=settings.allowed_email_domain))
    email = normalize_email(email)
    existing = find_user_by_email(db, email)
    if existing is not None and existing.id != user_id:
        raise ServiceError(409, EMAIL_TAKEN.format(email=email))
    return email


def create_account(db: Session, email: str, full_name: str, role: Role, actor: User, ip: str | None) -> User:
    email = _check_email(db, email)
    user = User(
        email=email,
        full_name=clean_name(full_name),
        role=role,
        is_active=True,
        # Mot de passe aléatoire jamais communiqué : le titulaire choisit le sien avec SC-18
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    db.add(user)
    audit_service.record(db, "USER_CREATED", actor=actor, target=f"{email} ({role.value})", ip=ip)
    db.commit()
    return user


def update_account(db: Session, user_id: int, changes: AccountChanges, actor: User, ip: str | None) -> User:
    user = _get(db, user_id)
    is_self = user.id == actor.id
    if is_self and (changes.is_active is False or changes.role not in (None, Role.ADMINISTRATEUR)):
        raise ServiceError(409, SELF_PROTECTION)

    if changes.email is not None:
        email = _check_email(db, changes.email, user.id)
        if email != user.email:
            audit_service.record(db, "USER_UPDATED", actor=actor, target=f"e-mail {user.email} → {email}", ip=ip)
            user.email = email
    if changes.full_name is not None:
        user.full_name = clean_name(changes.full_name)
    if changes.role is not None and changes.role != user.role:
        audit_service.record(
            db, "USER_ROLE_CHANGED", actor=actor,
            target=f"{user.email} : {user.role.value} → {changes.role.value}", ip=ip,
        )
        user.role = changes.role
    if changes.is_active is not None and changes.is_active != user.is_active:
        action = "USER_REACTIVATED" if changes.is_active else "USER_DEACTIVATED"
        audit_service.record(db, action, actor=actor, target=user.email, ip=ip)
        user.is_active = changes.is_active

    db.commit()
    return user
