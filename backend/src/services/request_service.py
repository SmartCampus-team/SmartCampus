"""Demandes administratives des étudiants (SC-34 : EF-REQ-01, EF-REQ-02, RG-13).

Le dépôt crée la demande « En attente » avec son numéro DA-AAAA-NNNNN et la première ligne
de son historique (aucun statut → En attente).

SC-35 (EF-REQ-04, RG-14) : « Mes demandes ». Le filtre sur l'étudiant vient toujours du jeton,
jamais d'un paramètre : un étudiant ne voit que ses demandes.
"""

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.models.admin_request import REQUEST_NUMBER_SEQ, AdminRequest, RequestStatus, RequestType
from src.models.request_history import RequestHistory
from src.models.user import User
from src.services import campus_clock


def next_number(db: Session) -> str:
    """DA-AAAA-NNNNN : année du dépôt (heure du campus) et valeur suivante de la séquence PostgreSQL."""
    value = db.scalar(select(REQUEST_NUMBER_SEQ.next_value()))
    return f"DA-{campus_clock.now().year}-{value:05d}"


def create_request(db: Session, student: User, request_type: RequestType, description: str) -> AdminRequest:
    """Dépose une demande au nom de l'étudiant connecté ; nom et e-mail viennent de son compte."""
    request = AdminRequest(
        number=next_number(db),
        student=student,
        request_type=request_type,
        description=description.strip(),
        status=RequestStatus.EN_ATTENTE,
    )
    db.add(request)
    db.flush()  # attribue l'identifiant
    deposit = RequestHistory(request_id=request.id, from_status=None, to_status=RequestStatus.EN_ATTENTE)
    deposit.author_id = student.id
    db.add(deposit)
    db.commit()
    return request


@dataclass
class RequestFilters:
    query: str | None = None  # numéro, ou partie du numéro : « 00042 »
    status: RequestStatus | None = None
    request_type: RequestType | None = None


def apply_filters(statement: Select, filters: RequestFilters) -> Select:
    if filters.query and filters.query.strip():
        statement = statement.where(AdminRequest.number.ilike(f"%{filters.query.strip()}%"))
    if filters.status:
        statement = statement.where(AdminRequest.status == filters.status)
    if filters.request_type:
        statement = statement.where(AdminRequest.request_type == filters.request_type)
    return statement


def list_mine(db: Session, student: User, filters: RequestFilters) -> list[AdminRequest]:
    """Les demandes de l'étudiant connecté, la dernière mise à jour d'abord."""
    statement = select(AdminRequest).where(AdminRequest.student_id == student.id)
    statement = apply_filters(statement, filters).order_by(AdminRequest.updated_at.desc(), AdminRequest.id.desc())
    return list(db.scalars(statement))
