"""Demandes administratives des étudiants (SC-34 : EF-REQ-01, EF-REQ-02, RG-13).

Le dépôt crée la demande « En attente » avec son numéro DA-AAAA-NNNNN et la première ligne
de son historique (aucun statut → En attente).

SC-35 (EF-REQ-04, RG-14) : « Mes demandes ». Le filtre sur l'étudiant vient toujours du jeton,
jamais d'un paramètre : un étudiant ne voit que ses demandes.

SC-36 (EF-REQ-05, RG-14) : le détail d'une demande. Un étudiant n'ouvre que les siennes : pour
une autre, même existante, l'API répond 404, comme si elle n'existait pas. L'agent de scolarité
ouvre toutes les demandes.
"""

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from src.models.admin_request import REQUEST_NUMBER_SEQ, AdminRequest, RequestStatus, RequestType
from src.models.request_history import RequestHistory
from src.models.user import Role, User
from src.services import campus_clock
from src.services.common import ServiceError

REQUEST_NOT_FOUND = "Demande introuvable."


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


def get_request(db: Session, user: User, request_id: int) -> AdminRequest:
    """La demande, si l'utilisateur en est l'auteur ou travaille à la scolarité ; 404 sinon."""
    request = db.get(AdminRequest, request_id)
    if request is None or (user.role != Role.SCOLARITE and request.student_id != user.id):
        raise ServiceError(404, REQUEST_NOT_FOUND)
    return request
