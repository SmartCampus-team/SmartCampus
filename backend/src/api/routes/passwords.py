"""Mot de passe oublié : demande du lien et choix du nouveau mot de passe (SC-18, EF-AUTH-05)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.services import password_reset_service

router = APIRouter(prefix="/api/auth/password", tags=["passwords"])

LINK_VALID = "Lien valable."


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, examples=["etudiant@usms.ac.ma"])


class CheckLinkRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=1, max_length=128)


class Message(BaseModel):
    detail: str


@router.post("/forgot", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotPasswordRequest, request: Request, db: Annotated[Session, Depends(get_db)]
) -> Message:
    """Envoie un lien valable 30 min ; même réponse que l'adresse ait un compte ou non."""
    ip = request.client.host if request.client else None
    return Message(detail=password_reset_service.request_reset(db, body.email, ip))


@router.post("/check", response_model=Message)
def check_link(body: CheckLinkRequest, db: Annotated[Session, Depends(get_db)]) -> Message:
    """Vérifie un lien à son ouverture ; 400 s'il est expiré, déjà utilisé ou inconnu.

    Le jeton voyage dans le corps de la requête, jamais dans l'URL : il n'apparaît pas
    dans les journaux du serveur.
    """
    password_reset_service.check_link(db, body.token)
    return Message(detail=LINK_VALID)


@router.post("/reset", response_model=Message)
def reset_password(
    body: ResetPasswordRequest, request: Request, db: Annotated[Session, Depends(get_db)]
) -> Message:
    """Remplace le mot de passe ; 400 si le lien est expiré, déjà utilisé ou inconnu."""
    ip = request.client.host if request.client else None
    password_reset_service.reset_password(db, body.token, body.new_password, ip)
    return Message(detail=password_reset_service.PASSWORD_CHANGED)
