"""Planning d'occupation d'une salle (SC-23 : EF-ROOM-03)."""

from datetime import date as Date
from datetime import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.api.routes.rooms import RoomOut
from src.config import settings
from src.database import get_db
from src.models.booking import BookingStatus
from src.models.user import Role, User
from src.services import campus_clock, room_service
from src.services.planning_service import EntryKind, PlanningView, build_planning

router = APIRouter(prefix="/api/rooms", tags=["planning"])


class PlanningEntryOut(BaseModel):
    kind: EntryKind
    id: int
    day: Date
    start: time
    end: time
    label: str
    status: BookingStatus | None
    detail: str | None
    holder_name: str | None
    mine: bool


class PlanningOut(BaseModel):
    room: RoomOut
    view: PlanningView
    days: list[Date]
    opening: time
    closing: time
    slot_minutes: int
    entries: list[PlanningEntryOut]


@router.get("/{room_id}/planning", response_model=PlanningOut)
def room_planning(
    room_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    day: Annotated[Date | None, Query(alias="date", description="AAAA-MM-JJ ; aujourd'hui par défaut")] = None,
    view: PlanningView = PlanningView.DAY,
) -> PlanningOut:
    """Planning du jour (par défaut) ou de la semaine, du lundi au samedi, de 08:00 à 20:00.

    Les créneaux sans entrée sont libres. Le gestionnaire peut ouvrir le planning d'une
    salle archivée, pour consulter ses réservations passées ; pour les autres, 404.
    """
    room = room_service.get_room(db, room_id, include_archived=user.role == Role.GESTIONNAIRE)
    planning = build_planning(db, room, day or campus_clock.today(), view, user)
    return PlanningOut(
        room=RoomOut.model_validate(room),
        view=planning.view,
        days=planning.days,
        opening=campus_clock.opening_time(),
        closing=campus_clock.closing_time(),
        slot_minutes=settings.slot_minutes,
        entries=[PlanningEntryOut.model_validate(entry, from_attributes=True) for entry in planning.entries],
    )
