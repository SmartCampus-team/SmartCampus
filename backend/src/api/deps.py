"""Dépendances FastAPI communes : utilisateur connecté à partir du jeton (SC-15, ENF-02)
et contrôle du rôle sur les routes protégées (SC-17, ENF-03)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import Role, User
from src.services import token_service
from src.services.common import AuthError
from src.services.security import decode_access_token

AUTH_REQUIRED = "Authentification requise. Veuillez vous reconnecter."
SESSION_EXPIRED = "Session expirée. Veuillez vous reconnecter."
FORBIDDEN = "Vous n'avez pas les droits nécessaires pour cette action."

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentSession:
    user: User
    jti: str
    expires_at: datetime


def get_current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentSession:
    """Refuse (401) un jeton absent, invalide, expiré, révoqué ou d'un compte désactivé."""
    if credentials is None:
        raise AuthError(401, AUTH_REQUIRED)
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise AuthError(401, SESSION_EXPIRED) from None
    except jwt.InvalidTokenError:
        raise AuthError(401, AUTH_REQUIRED) from None

    if token_service.is_revoked(db, payload["jti"]):
        raise AuthError(401, AUTH_REQUIRED)

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError(401, AUTH_REQUIRED)

    return CurrentSession(
        user=user,
        jti=payload["jti"],
        expires_at=datetime.fromtimestamp(payload["exp"], UTC),
    )


def get_current_user(
    session: Annotated[CurrentSession, Depends(get_current_session)],
) -> User:
    return session.user


def require_roles(*roles: Role) -> Callable[..., User]:
    """Dépendance qui refuse (403) un utilisateur connecté dont le rôle n'est pas dans la liste.

    Usage : user: Annotated[User, Depends(require_roles(Role.GESTIONNAIRE))]
    Le rôle est relu en base à chaque requête : un changement de rôle s'applique tout de suite.
    """

    def check_role(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise AuthError(403, FORBIDDEN)
        return user

    return check_role
