"""Lecture des paramètres des règles de gestion dans la table settings (SC-26)."""

import enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.setting import Setting

MISSING = "Paramètre « {key} » absent de la table settings : lancez « alembic upgrade head »."


class SettingKey(enum.StrEnum):
    # Horizon de réservation, en jours (RG-04)
    HORIZON_DAYS_STUDENT = "booking_horizon_days_student"
    HORIZON_DAYS_TEACHER = "booking_horizon_days_teacher"
    # Quotas d'un étudiant (RG-07)
    MAX_UPCOMING_BOOKINGS_STUDENT = "max_upcoming_bookings_student"
    MAX_WEEKLY_HOURS_STUDENT = "max_weekly_hours_student"


def get_int(db: Session, key: SettingKey) -> int:
    """Valeur entière d'un paramètre ; erreur 500 explicite s'il manque (base pas à jour)."""
    value = db.scalar(select(Setting.value).where(Setting.key == key))
    if value is None:
        raise RuntimeError(MISSING.format(key=key))
    return int(value)
