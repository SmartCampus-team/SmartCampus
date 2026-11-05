"""Données de démonstration : le script se relance sans doublon (SC-20, SC-22)."""

from sqlalchemy import func, select

from src import seed
from src.models.blocking import Blocking
from src.models.booking import Booking
from src.models.room import Room, RoomStatus, RoomType
from src.models.user import User
from src.services import campus_clock


def run_seed(db) -> None:
    seed.seed_accounts(db)
    seed.seed_rooms(db)
    seed.seed_bookings(db)
    db.commit()


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_seed_creates_accounts_and_rooms(db):
    run_seed(db)
    assert count(db, User) == len(seed.DEMO_ACCOUNTS)
    assert count(db, Room) == len(seed.DEMO_ROOMS)
    types = set(db.scalars(select(Room.room_type)))
    # Les types utilisés par RG-09 sont présents
    assert {RoomType.SALLE_TD, RoomType.SALLE_TRAVAIL, RoomType.AMPHITHEATRE} <= types
    assert db.scalar(select(Room.status).where(Room.code == "D-001")) == RoomStatus.ARCHIVEE


def test_seed_can_run_twice_without_duplicates(db):
    run_seed(db)
    run_seed(db)
    assert count(db, User) == len(seed.DEMO_ACCOUNTS)
    assert count(db, Room) == len(seed.DEMO_ROOMS)
    assert count(db, Booking) == len(seed.DEMO_BOOKINGS)
    assert count(db, Blocking) == len(seed.DEMO_BLOCKINGS)


def test_demo_bookings_and_blockings_are_upcoming_on_open_days(db):
    run_seed(db)
    starts = list(db.scalars(select(Booking.start_at))) + list(db.scalars(select(Blocking.start_at)))
    assert len(starts) == len(seed.DEMO_BOOKINGS) + len(seed.DEMO_BLOCKINGS)
    assert all(start > campus_clock.now() for start in starts)
    assert all(campus_clock.is_open_day(campus_clock.local(start).date()) for start in starts)
