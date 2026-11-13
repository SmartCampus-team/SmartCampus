"""Horizon et quotas de réservation (SC-26 : EF-BOOK-01, RG-04, RG-07).

- Horizon (RG-04) : un étudiant réserve au plus 7 jours à l'avance, un enseignant 30 jours.
- Quotas d'un étudiant (RG-07) : 4 réservations à venir et 8 h par semaine au plus.

Les valeurs 7, 30, 4 et 8 sont lues dans la table settings, jamais écrites dans le code.
À partir de SC-50, une demande hors quota partira en validation au lieu d'être refusée (RG-07).
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.booking import OCCUPYING_STATUSES, Booking, BookingStatus
from src.models.user import Role, User
from src.services import campus_clock, setting_service
from src.services.common import ServiceError
from src.services.setting_service import SettingKey

TOO_FAR = "Réservation trop lointaine : {who} réserve au plus {days} jours à l'avance, soit jusqu'au {last:%d/%m/%Y}."
UPCOMING_QUOTA = (
    "Quota atteint : un étudiant a au plus {limit} réservations à venir. Annulez-en une pour en créer une autre."
)
WEEKLY_QUOTA = "Quota atteint : un étudiant réserve au plus {limit} h de salle par semaine (du lundi au samedi)."

WHO = {Role.ETUDIANT: "un étudiant", Role.ENSEIGNANT: "un enseignant"}
HORIZON_KEYS = {Role.ETUDIANT: SettingKey.HORIZON_DAYS_STUDENT, Role.ENSEIGNANT: SettingKey.HORIZON_DAYS_TEACHER}

# Réservations comptées dans les heures de la semaine : en cours de validité ou déjà tenues
WEEKLY_STATUSES = (*OCCUPYING_STATUSES, BookingStatus.TERMINEE)


def check_horizon(db: Session, user: User, start_at: datetime, today: date | None = None) -> None:
    """400 si le créneau commence plus de N jours après aujourd'hui (RG-04)."""
    days = setting_service.get_int(db, HORIZON_KEYS[user.role])
    last = (today or campus_clock.today()) + timedelta(days=days)
    if campus_clock.local(start_at).date() > last:
        raise ServiceError(400, TOO_FAR.format(who=WHO[user.role], days=days, last=last))


def week_bounds(day: date) -> tuple[datetime, datetime]:
    """Du lundi 00:00 au lundi suivant 00:00, à l'heure du campus."""
    monday = day - timedelta(days=day.weekday())
    return campus_clock.at(monday, time(0)), campus_clock.at(monday + timedelta(days=7), time(0))


def check_quotas(db: Session, user: User, start_at: datetime, end_at: datetime, now: datetime | None = None) -> None:
    """Quotas d'un étudiant (RG-07) ; l'enseignant n'en a pas."""
    if user.role != Role.ETUDIANT:
        return
    now = now or campus_clock.now()

    limit = setting_service.get_int(db, SettingKey.MAX_UPCOMING_BOOKINGS_STUDENT)
    upcoming = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.holder_id == user.id, Booking.status.in_(OCCUPYING_STATUSES), Booking.start_at > now)
    )
    if upcoming >= limit:
        raise ServiceError(400, UPCOMING_QUOTA.format(limit=limit))

    hours = setting_service.get_int(db, SettingKey.MAX_WEEKLY_HOURS_STUDENT)
    week_start, week_end = week_bounds(campus_clock.local(start_at).date())
    booked = db.scalars(
        select(Booking).where(
            Booking.holder_id == user.id,
            Booking.status.in_(WEEKLY_STATUSES),
            Booking.start_at >= week_start,
            Booking.start_at < week_end,
        )
    )
    total = sum((booking.end_at - booking.start_at for booking in booked), timedelta()) + (end_at - start_at)
    if total > timedelta(hours=hours):
        raise ServiceError(400, WEEKLY_QUOTA.format(limit=hours))
