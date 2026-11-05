"""Création, modification et archivage des salles par le gestionnaire (SC-20 : EF-ROOM-04).

Une salle n'est jamais supprimée : archivée, elle disparaît de la liste et de la recherche,
mais reste en base avec ses réservations passées. Chaque action écrit une ligne dans AuditLog.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.room import Room, RoomStatus, RoomType
from src.models.user import User
from src.services import audit_service
from src.services.common import ServiceError
from src.services.room_service import get_room

CODE_TAKEN = "Une salle porte déjà le code {code}."
ROOM_ARCHIVED = "Cette salle est archivée : elle ne peut plus être modifiée."
ALREADY_ARCHIVED = "Cette salle est déjà archivée."


@dataclass
class RoomChanges:
    """Champs à enregistrer ; None = inchangé (modification)."""

    code: str | None = None
    building: str | None = None
    room_type: RoomType | None = None
    capacity: int | None = None
    description: str | None = None


def normalize_code(code: str) -> str:
    return code.strip().upper()


def _check_code_free(db: Session, code: str, room_id: int | None = None) -> None:
    statement = select(Room.id).where(func.upper(Room.code) == code)
    if room_id is not None:
        statement = statement.where(Room.id != room_id)
    if db.scalar(statement) is not None:
        raise ServiceError(409, CODE_TAKEN.format(code=code))


def create_room(
    db: Session,
    code: str,
    building: str,
    room_type: RoomType,
    capacity: int,
    description: str | None,
    actor: User,
    ip: str | None,
) -> Room:
    code = normalize_code(code)
    _check_code_free(db, code)
    room = Room(
        code=code,
        building=building.strip(),
        room_type=room_type,
        capacity=capacity,
        description=(description or "").strip() or None,
        status=RoomStatus.ACTIVE,
    )
    db.add(room)
    audit_service.record(db, "ROOM_CREATED", actor=actor, target=code, ip=ip)
    db.commit()
    return room


def update_room(db: Session, room_id: int, changes: RoomChanges, actor: User, ip: str | None) -> Room:
    room = get_room(db, room_id, include_archived=True)
    if room.status == RoomStatus.ARCHIVEE:
        raise ServiceError(409, ROOM_ARCHIVED)
    if changes.code is not None:
        code = normalize_code(changes.code)
        _check_code_free(db, code, room.id)
        room.code = code
    if changes.building is not None:
        room.building = changes.building.strip()
    if changes.room_type is not None:
        room.room_type = changes.room_type
    if changes.capacity is not None:
        room.capacity = changes.capacity
    if changes.description is not None:
        room.description = changes.description.strip() or None
    audit_service.record(db, "ROOM_UPDATED", actor=actor, target=room.code, ip=ip)
    db.commit()
    return room


def archive_room(db: Session, room_id: int, actor: User, ip: str | None) -> Room:
    room = get_room(db, room_id, include_archived=True)
    if room.status == RoomStatus.ARCHIVEE:
        raise ServiceError(409, ALREADY_ARCHIVED)
    room.status = RoomStatus.ARCHIVEE
    audit_service.record(db, "ROOM_ARCHIVED", actor=actor, target=room.code, ip=ip)
    db.commit()
    return room
