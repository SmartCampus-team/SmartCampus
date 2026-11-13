"""Blocages d'une salle par le gestionnaire (SC-32 : EF-ROOM-06, RG-01, RG-10)."""

from datetime import date as Date
from datetime import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.api.routes.rooms import client_ip
from src.database import get_db
from src.models.blocking import Blocking
from src.models.user import Role, User
from src.services import blocking_service, campus_clock

router = APIRouter(prefix="/api/rooms/{room_id}/blockings", tags=["blockings"])

Manager = Annotated[User, Depends(require_roles(Role.GESTIONNAIRE))]
Db = Annotated[Session, Depends(get_db)]


class BlockingCreate(BaseModel):
    start_date: Date = Field(description="Premier jour, AAAA-MM-JJ")
    start_time: time = Field(description="Heure de début, HH:MM")
    end_date: Date = Field(description="Dernier jour, AAAA-MM-JJ")
    end_time: time = Field(description="Heure de fin, HH:MM")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)] = Field(
        examples=["Examen de mi-semestre"]
    )


class BlockingOut(BaseModel):
    """Un blocage, à l'heure du campus."""

    id: int
    room_id: int
    start_date: Date
    start_time: time
    end_date: Date
    end_time: time
    reason: str
    author_name: str | None


class BlockingCreatedOut(BlockingOut):
    cancelled_bookings: int  # réservations annulées par ce blocage


def blocking_out(blocking: Blocking) -> BlockingOut:
    start, end = campus_clock.local(blocking.start_at), campus_clock.local(blocking.end_at)
    return BlockingOut(
        id=blocking.id,
        room_id=blocking.room_id,
        start_date=start.date(),
        start_time=start.time(),
        end_date=end.date(),
        end_time=end.time(),
        reason=blocking.reason,
        author_name=blocking.author.full_name if blocking.author else None,
    )


@router.get("", response_model=list[BlockingOut])
def list_blockings(room_id: int, _: Manager, db: Db) -> list[BlockingOut]:
    """Blocages en cours ou à venir de la salle."""
    return [blocking_out(blocking) for blocking in blocking_service.list_blockings(db, room_id)]


@router.post("", response_model=BlockingCreatedOut, status_code=status.HTTP_201_CREATED)
def create_blocking(room_id: int, body: BlockingCreate, request: Request, manager: Manager, db: Db) -> BlockingCreatedOut:
    """Bloque la salle sur la période : planning, recherche et réservations en tiennent compte aussitôt.

    Les réservations non terminées de la période passent « Annulée » avec le motif du blocage.
    400 : période hors grille ou passée ; 404 : salle inconnue ou archivée ; 409 : salle déjà bloquée.
    """
    result = blocking_service.create_blocking(
        db, room_id, body.start_date, body.start_time, body.end_date, body.end_time, body.reason,
        manager, client_ip(request),
    )
    return BlockingCreatedOut(**blocking_out(result.blocking).model_dump(), cancelled_bookings=len(result.cancelled))


@router.delete("/{blocking_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_blocking(room_id: int, blocking_id: int, request: Request, manager: Manager, db: Db) -> Response:
    """Lève un blocage en cours ou à venir ; les réservations déjà annulées ne sont pas rétablies."""
    blocking_service.remove_blocking(db, room_id, blocking_id, manager, client_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
