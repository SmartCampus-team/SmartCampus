"""Catalogue des équipements et affectation aux salles (SC-31 : EF-ROOM-05).

Tout utilisateur consulte le catalogue (filtre de la recherche) ; seul le gestionnaire le modifie.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, require_roles
from src.api.routes.rooms import EquipmentOut, RoomOut, client_ip
from src.database import get_db
from src.models.equipment import Equipment, EquipmentCategory
from src.models.room import Room
from src.models.user import Role, User
from src.services import equipment_service

router = APIRouter(tags=["equipment"])

CurrentUser = Annotated[User, Depends(get_current_user)]
Manager = Annotated[User, Depends(require_roles(Role.GESTIONNAIRE))]
Db = Annotated[Session, Depends(get_db)]

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


class CatalogueItemOut(EquipmentOut):
    room_count: int  # salles non archivées qui en sont équipées


class EquipmentCreate(BaseModel):
    label: Label = Field(examples=["Vidéoprojecteur"])
    category: EquipmentCategory


class EquipmentUpdate(BaseModel):
    """Seuls les champs envoyés sont modifiés."""

    label: Label | None = None
    category: EquipmentCategory | None = None


class RoomEquipmentIn(BaseModel):
    equipment_ids: list[int] = Field(max_length=50, description="Tous les équipements de la salle")


@router.get("/api/equipment", response_model=list[CatalogueItemOut])
def list_equipment(_: CurrentUser, db: Db) -> list[CatalogueItemOut]:
    """Le catalogue, par catégorie puis libellé, avec le nombre de salles équipées."""
    return [
        CatalogueItemOut(id=item.id, label=item.label, category=item.category, room_count=count)
        for item, count in equipment_service.list_equipment(db)
    ]


@router.post("/api/equipment", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
def create_equipment(body: EquipmentCreate, request: Request, manager: Manager, db: Db) -> Equipment:
    """Ajoute un équipement au catalogue ; 409 si le libellé existe déjà."""
    return equipment_service.create_equipment(db, body.label, body.category, manager, client_ip(request))


@router.patch("/api/equipment/{equipment_id}", response_model=EquipmentOut)
def update_equipment(equipment_id: int, body: EquipmentUpdate, request: Request, manager: Manager, db: Db) -> Equipment:
    return equipment_service.update_equipment(
        db, equipment_id, body.label, body.category, manager, client_ip(request)
    )


@router.put("/api/rooms/{room_id}/equipment", response_model=RoomOut)
def set_room_equipment(room_id: int, body: RoomEquipmentIn, request: Request, manager: Manager, db: Db) -> Room:
    """Affecte à la salle exactement ces équipements : ils s'affichent sur sa fiche et servent de filtre."""
    return equipment_service.set_room_equipment(db, room_id, body.equipment_ids, manager, client_ip(request))
