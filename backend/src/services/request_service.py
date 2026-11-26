"""Demandes administratives des étudiants (SC-34 : EF-REQ-01, EF-REQ-02, RG-13).

Le dépôt crée la demande « En attente » avec son numéro DA-AAAA-NNNNN et la première ligne
de son historique (aucun statut → En attente).
"""

from sqlalchemy import select
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
