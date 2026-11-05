"""Comptes et rôles, réservés à l'administrateur système (SC-17 : EF-AUTH-07, ENF-03)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.database import get_db
from src.models.user import Role, User
from src.services import account_service
from src.services.account_service import AccountChanges, AccountFilters

router = APIRouter(prefix="/api/users", tags=["users"])

Admin = Annotated[User, Depends(require_roles(Role.ADMINISTRATEUR))]
Db = Annotated[Session, Depends(get_db)]


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class AccountCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, examples=["nouvel.etudiant@usms.ac.ma"])
    full_name: str = Field(min_length=2, max_length=150)
    role: Role


class AccountUpdate(BaseModel):
    """Seuls les champs envoyés sont modifiés."""

    email: str | None = Field(default=None, min_length=3, max_length=255)
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    role: Role | None = None
    is_active: bool | None = None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[AccountOut])
def list_accounts(
    _: Admin,
    db: Db,
    q: Annotated[str | None, Query(max_length=100, description="Nom ou e-mail")] = None,
    role: Role | None = None,
    active: bool | None = None,
) -> list[User]:
    return account_service.list_accounts(db, AccountFilters(query=q, role=role, active=active))


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(body: AccountCreate, request: Request, admin: Admin, db: Db) -> User:
    """Crée un compte actif ; 400 hors domaine (RG-11), 409 si l'adresse existe déjà."""
    return account_service.create_account(db, body.email, body.full_name, body.role, admin, client_ip(request))


@router.patch("/{user_id}", response_model=AccountOut)
def update_account(user_id: int, body: AccountUpdate, request: Request, admin: Admin, db: Db) -> User:
    """Modifie l'e-mail, le nom, le rôle, ou désactive le compte (jamais supprimé)."""
    changes = AccountChanges(**body.model_dump(exclude_unset=True))
    return account_service.update_account(db, user_id, changes, admin, client_ip(request))
