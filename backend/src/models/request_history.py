"""Table request_history : une ligne par changement de statut d'une demande (SC-34, SC-39 : EF-REQ-13).

Le dépôt écrit la première ligne (aucun statut → En attente). Les lignes ne sont jamais
modifiées ni supprimées : aucune route ne le permet.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.models.admin_request import RequestStatus
from src.models.user import User


def _status() -> Enum:
    return Enum(
        RequestStatus,
        name="request_status",
        native_enum=False,
        length=30,
        values_callable=lambda items: [item.value for item in items],
    )


class RequestHistory(Base):
    __tablename__ = "request_history"
    __table_args__ = (Index("ix_request_history_request", "request_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("admin_requests.id", ondelete="CASCADE"))
    from_status: Mapped[RequestStatus | None] = mapped_column(_status())  # None : dépôt
    to_status: Mapped[RequestStatus] = mapped_column(_status())
    comment: Mapped[str | None] = mapped_column(String(1000))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    author: Mapped[User] = relationship()
