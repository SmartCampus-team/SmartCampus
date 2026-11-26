"""Demandes administratives (SC-34 : EF-REQ-01, EF-REQ-02, RG-13)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.database import get_db
from src.models.admin_request import AdminRequest, RequestStatus, RequestType
from src.models.user import Role, User
from src.services import request_service

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


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(body: RequestCreate, student: Student, db: Db) -> AdminRequest:
    """Dépose une demande « En attente » au nom de l'étudiant connecté et renvoie son numéro.

    422 : description vide ; 403 : un autre rôle qu'étudiant.
    """
    return request_service.create_request(db, student, body.request_type, body.description)
