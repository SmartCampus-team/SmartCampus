"""Catalogue des équipements et affectation aux salles par le gestionnaire (SC-31 : EF-ROOM-05).

Chaque création, modification et affectation écrit une ligne dans AuditLog.
"""

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.models.equipment import Equipment, EquipmentCategory, room_equipment
from src.models.room import Room, RoomStatus
from src.models.user import User
from src.services import audit_service, room_service
from src.services.common import ServiceError
from src.services.room_admin_service import ROOM_ARCHIVED

LABEL_TAKEN = "L'équipement « {label} » existe déjà."
EQUIPMENT_NOT_FOUND = "Équipement introuvable."
UNKNOWN_EQUIPMENT = "Équipement introuvable : {ids}."


def normalize_label(label: str) -> str:
    """Espaces superflus retirés : «  Tableau   blanc » → « Tableau blanc »."""
    return " ".join(label.split())


def list_equipment(db: Session) -> list[tuple[Equipment, int]]:
    """Le catalogue, par catégorie puis libellé, avec le nombre de salles non archivées équipées."""
    statement = (
        select(Equipment, func.count(Room.id))
        .outerjoin(room_equipment, room_equipment.c.equipment_id == Equipment.id)
        .outerjoin(Room, and_(Room.id == room_equipment.c.room_id, Room.status != RoomStatus.ARCHIVEE))
        .group_by(Equipment.id)
        .order_by(Equipment.category, Equipment.label)
    )
    return [(equipment, count) for equipment, count in db.execute(statement)]


def _check_label_free(db: Session, label: str, equipment_id: int | None = None) -> None:
    statement = select(Equipment.id).where(func.lower(Equipment.label) == label.lower())
    if equipment_id is not None:
        statement = statement.where(Equipment.id != equipment_id)
    if db.scalar(statement) is not None:
        raise ServiceError(409, LABEL_TAKEN.format(label=label))


def create_equipment(db: Session, label: str, category: EquipmentCategory, actor: User, ip: str | None) -> Equipment:
    label = normalize_label(label)
    _check_label_free(db, label)
    equipment = Equipment(label=label, category=category)
    db.add(equipment)
    audit_service.record(db, "EQUIPMENT_CREATED", actor=actor, target=label, ip=ip)
    db.commit()
    return equipment


def update_equipment(
    db: Session,
    equipment_id: int,
    label: str | None,
    category: EquipmentCategory | None,
    actor: User,
    ip: str | None,
) -> Equipment:
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise ServiceError(404, EQUIPMENT_NOT_FOUND)
    if label is not None:
        label = normalize_label(label)
        _check_label_free(db, label, equipment.id)
        equipment.label = label
    if category is not None:
        equipment.category = category
    audit_service.record(db, "EQUIPMENT_UPDATED", actor=actor, target=equipment.label, ip=ip)
    db.commit()
    return equipment


def set_room_equipment(db: Session, room_id: int, equipment_ids: list[int], actor: User, ip: str | None) -> Room:
    """Remplace les équipements de la salle par ceux de la liste ; journalise les ajouts et retraits."""
    room = room_service.get_room(db, room_id, include_archived=True)
    if room.status == RoomStatus.ARCHIVEE:
        raise ServiceError(409, ROOM_ARCHIVED)
    wanted = set(equipment_ids)
    found = list(db.scalars(select(Equipment).where(Equipment.id.in_(wanted)).order_by(Equipment.label)))
    missing = sorted(wanted - {equipment.id for equipment in found})
    if missing:
        raise ServiceError(400, UNKNOWN_EQUIPMENT.format(ids=", ".join(map(str, missing))))

    before = {equipment.label for equipment in room.equipment}
    after = {equipment.label for equipment in found}
    room.equipment = found
    changes = [f"+{label}" for label in sorted(after - before)] + [f"-{label}" for label in sorted(before - after)]
    target = f"{room.code} : {', '.join(changes) or 'aucun changement'}"
    audit_service.record(db, "ROOM_EQUIPMENT_UPDATED", actor=actor, target=target[:255], ip=ip)
    db.commit()
    return room
