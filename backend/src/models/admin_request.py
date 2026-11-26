"""Table admin_requests : demandes administratives des étudiants (SC-34 : EF-REQ-01, EF-REQ-02, RG-13).

Chaque demande reçoit un numéro DA-AAAA-NNNNN : AAAA est l'année du dépôt, NNNNN vient de la
séquence PostgreSQL request_number_seq. La séquence ne repart pas à 1 chaque année : deux dépôts
simultanés, même sur deux réplicas de l'API, reçoivent deux numéros différents, et un numéro
n'est jamais réutilisé.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Sequence, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.user import User


class RequestType(enum.StrEnum):
    ATTESTATION_SCOLARITE = "attestation_scolarite"
    RELEVE_NOTES = "releve_notes"
    CERTIFICAT_REUSSITE = "certificat_reussite"
    DEMANDE_STAGE = "demande_stage"
    RECLAMATION = "reclamation"
    AUTRE = "autre"


class RequestStatus(enum.StrEnum):
    """Statuts du cycle de vie d'une demande (RG-13, tableau 13 du cahier des charges)."""

    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    INFOS_DEMANDEES = "infos_demandees"
    ACCEPTEE = "acceptee"
    REFUSEE = "refusee"
    TERMINEE = "terminee"


# Numéro NNNNN des demandes, partagé par toutes les années
REQUEST_NUMBER_SEQ = Sequence("request_number_seq", metadata=Base.metadata)


def _enum(enum_class: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        length=30,
        values_callable=lambda items: [item.value for item in items],
    )


class AdminRequest(Base):
    __tablename__ = "admin_requests"
    __table_args__ = (
        Index("ix_admin_requests_student", "student_id"),
        Index("ix_admin_requests_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # DA-2026-00042 : affiché à l'étudiant après le dépôt
    number: Mapped[str] = mapped_column(String(20), unique=True)
    # Nom et e-mail viennent du compte de l'étudiant, jamais du formulaire
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_type: Mapped[RequestType] = mapped_column(_enum(RequestType, "request_type"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "request_status"), default=RequestStatus.EN_ATTENTE
    )
    # Date de dépôt, et date de dernière mise à jour (changée à chaque transition)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped[User] = relationship(foreign_keys=[student_id])
