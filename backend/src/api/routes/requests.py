"""Demandes administratives (SC-34 : EF-REQ-01, EF-REQ-02, RG-13) et « Mes demandes » (SC-35 : EF-REQ-04, RG-14)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.database import get_db
from src.models.admin_request import AdminRequest, RequestStatus, RequestType
from src.models.user import Role, User
from src.services import request_service
from src.services.request_service import RequestFilters

router = APIRouter(prefix="/api/requests", tags=["requests"])

Student = Annotated[User, Depends(require_roles(Role.ETUDIANT))]
Db = Annotated[Session, Depends(get_db)]

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class RequestCreate(BaseModel):
    request_type: RequestType
    description: Description = Field(examples=["Attestation pour la demande de bourse, en deux exemplaires."])


class RequestStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class RequestOut(BaseModel):
    """Une demande : numéro, type, description, statut, dates de dépôt et de mise à jour."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    request_type: RequestType
    description: str
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    student: RequestStudentOut


class RequestSummaryOut(BaseModel):
    """Une ligne de liste : numéro, type, statut, dates de dépôt et de dernière mise à jour."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    request_type: RequestType
    status: RequestStatus
    created_at: datetime
    updated_at: datetime


@router.get("/me", response_model=list[RequestSummaryOut])
def my_requests(
    student: Student,
    db: Db,
    q: Annotated[str | None, Query(max_length=20, description="Numéro ou partie du numéro")] = None,
    request_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
    request_type: Annotated[RequestType | None, Query(alias="type")] = None,
) -> list[AdminRequest]:
    """Mes demandes, la dernière mise à jour d'abord ; filtrées côté serveur à partir du jeton."""
    filters = RequestFilters(query=q, status=request_status, request_type=request_type)
    return request_service.list_mine(db, student, filters)


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(body: RequestCreate, student: Student, db: Db) -> AdminRequest:
    """Dépose une demande « En attente » au nom de l'étudiant connecté et renvoie son numéro.

    422 : description vide ; 403 : un autre rôle qu'étudiant.
    """
    return request_service.create_request(db, student, body.request_type, body.description)
