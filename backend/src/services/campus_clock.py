"""Heure locale du campus (SC-22, RG-03).

Les créneaux s'expriment en heure de Khouribga, quel que soit le fuseau du serveur
(Kubernetes tourne en UTC). Les dates sont stockées en base avec leur fuseau (timestamptz).
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.config import settings


def campus_tz() -> ZoneInfo:
    return ZoneInfo(settings.campus_timezone)


def now() -> datetime:
    return datetime.now(campus_tz())


def today() -> date:
    return now().date()


def at(day: date, moment: time) -> datetime:
    """Date et heure du campus, avec son fuseau : at(lundi, 10:00) → lundi 10:00 à Khouribga."""
    return datetime.combine(day, moment, tzinfo=campus_tz())


def local(moment: datetime) -> datetime:
    """Convertit une date lue en base (UTC) en heure du campus."""
    return moment.astimezone(campus_tz())


def opening_time() -> time:
    return time(settings.opening_hour)


def closing_time() -> time:
    return time(settings.closing_hour)


def is_open_day(day: date) -> bool:
    """Le campus ouvre du lundi (0) au samedi (5)."""
    return day.weekday() < 6


def next_open_day(day: date) -> date:
    """Le jour lui-même s'il est ouvré, sinon le suivant (dimanche → lundi)."""
    while not is_open_day(day):
        day += timedelta(days=1)
    return day
