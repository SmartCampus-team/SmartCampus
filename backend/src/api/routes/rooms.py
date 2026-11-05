from datetime import date as Date
from datetime import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.deps import FORBIDDEN, get_current_user, require_roles
from src.database import get_db
from src.models.room import Room, RoomStatus, RoomType
from src.models.user import Role, User
from src.services import room_admin_service, room_service
from src.services.common import ServiceError
from src.services.room_admin_service import RoomChanges
from src.services.room_service import RoomFilters

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

CurrentUser = Annotated[User, Depends(get_current_user)]
Manager = Annotated[User, Depends(require_roles(Role.GESTIONNAIRE))]
Db = Annotated[Session, Depends(get_db)]


CODE_PATTERN = r"^\s*[A-Za-z0-9][A-Za-z0-9-]*\s*$"


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    building: str
    room_type: RoomType
    capacity: int
    status: RoomStatus
    description: str | None


class RoomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=CODE_PATTERN, examples=["A-104"])
    building: str = Field(min_length=2, max_length=80, examples=["Bâtiment A"])
    room_type: RoomType
    capacity: int = Field(ge=1, le=500)
    description: str | None = Field(default=None, max_length=500)


class RoomUpdate(BaseModel):
    

    code: str | None = Field(default=None, min_length=1, max_length=20, pattern=CODE_PATTERN)
    building: str | None = Field(default=None, min_length=2, max_length=80)
    room_type: RoomType | None = None
    capacity: int | None = Field(default=None, ge=1, le=500)
    description: str | None = Field(default=None, max_length=500)


class AvailabilityOut(BaseModel):
    date: Date
    start: time
    end: time
    rooms: list[RoomOut]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def room_filters(
    q: Annotated[str | None, Query(max_length=50, description="Code ou bâtiment")] = None,
    building: Annotated[str | None, Query(max_length=80)] = None,
    room_type: RoomType | None = None,
    min_capacity: Annotated[int | None, Query(ge=1, le=1000, description="Nombre de participants")] = None,
) -> RoomFilters:
    return RoomFilters(query=q, building=building, room_type=room_type, min_capacity=min_capacity)


Filters = Annotated[RoomFilters, Depends(room_filters)]


@router.get("", response_model=list[RoomOut])
def list_rooms(user: CurrentUser, db: Db, filters: Filters, include_archived: bool = False) -> list[Room]:
    """Salles non archivées : bâtiment, type, capacité, statut (EF-ROOM-01).

    Filtres facultatifs : code ou bâtiment (q), bâtiment exact, type, capacité minimale.
    Le gestionnaire peut aussi demander les salles archivées.
    """
    if include_archived and user.role != Role.GESTIONNAIRE:
        raise ServiceError(403, FORBIDDEN)
    return room_service.list_rooms(db, include_archived, filters)


@router.get("/available", response_model=AvailabilityOut)
def available_rooms(
    _: CurrentUser,
    db: Db,
    filters: Filters,
    date: Annotated[Date, Query(description="Jour, AAAA-MM-JJ")],
    start: Annotated[time, Query(description="Début, HH:MM")],
    end: Annotated[time, Query(description="Fin, HH:MM")],
) -> AvailabilityOut:
    """Salles libres sur un créneau (EF-ROOM-02) ; 400 si le créneau ne respecte pas RG-03."""
    rooms = room_service.find_available(db, date, start, end, filters)
    return AvailabilityOut(date=date, start=start, end=end, rooms=[RoomOut.model_validate(r) for r in rooms])


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(body: RoomCreate, request: Request, manager: Manager, db: Db) -> Room:
    """Crée une salle « active » ; 409 si le code existe déjà, 422 si la capacité est nulle."""
    return room_admin_service.create_room(
        db, body.code, body.building, body.room_type, body.capacity, body.description,
        manager, client_ip(request),
    )


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, body: RoomUpdate, request: Request, manager: Manager, db: Db) -> Room:
    changes = RoomChanges(**body.model_dump(exclude_unset=True))
    return room_admin_service.update_room(db, room_id, changes, manager, client_ip(request))


@router.post("/{room_id}/archive", response_model=RoomOut)
def archive_room(room_id: int, request: Request, manager: Manager, db: Db) -> Room:
    """Archive la salle : elle disparaît de la liste et de la recherche, jamais supprimée."""
    return room_admin_service.archive_room(db, room_id, manager, client_ip(request))
