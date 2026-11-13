"""Catalogue des équipements et leur affectation aux salles (SC-31 : EF-ROOM-05).

Un équipement (vidéoprojecteur, tableau blanc…) appartient à une catégorie ; la table
room_equipment dit quelles salles en sont équipées. La recherche filtre sur ces affectations.
"""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class EquipmentCategory(enum.StrEnum):
    AUDIOVISUEL = "audiovisuel"
    INFORMATIQUE = "informatique"
    MOBILIER = "mobilier"
    CONFORT = "confort"
    ACCESSIBILITE = "accessibilite"


# Association salle ↔ équipement : supprimer l'un retire la ligne, jamais l'autre
room_equipment = Table(
    "room_equipment",
    Base.metadata,
    Column("room_id", ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Libellé unique, affiché sur la fiche de la salle : « Vidéoprojecteur »
    label: Mapped[str] = mapped_column(String(80), unique=True)
    category: Mapped[EquipmentCategory] = mapped_column(
        Enum(
            EquipmentCategory,
            name="equipment_category",
            native_enum=False,
            length=20,
            values_callable=lambda items: [item.value for item in items],
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
