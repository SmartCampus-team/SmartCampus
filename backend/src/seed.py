"""Données de démonstration : un compte par rôle (SC-12), les salles du campus (SC-20),
des réservations et des blocages sur les prochains jours ouvrés (SC-22).

Usage, depuis le dossier backend :  python -m src.seed
Le script peut être relancé : il ne recrée pas ce qui existe déjà, et ne recrée les
réservations et blocages de démonstration que s'il n'y en a plus à venir.
"""

from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.database import SessionLocal
from src.models.blocking import Blocking
from src.models.booking import Booking, BookingStatus
from src.models.room import Room, RoomStatus, RoomType
from src.models.user import Role, User
from src.services import campus_clock
from src.services.security import hash_password

DEMO_ACCOUNTS = [
    ("etudiant", "Étudiant Démo", Role.ETUDIANT, True),
    ("enseignant", "Enseignant Démo", Role.ENSEIGNANT, True),
    ("gestionnaire", "Gestionnaire Démo", Role.GESTIONNAIRE, True),
    ("scolarite", "Agent Scolarité Démo", Role.SCOLARITE, True),
    ("admin", "Administrateur Démo", Role.ADMINISTRATEUR, True),
    ("desactive", "Compte Désactivé Démo", Role.ETUDIANT, False),
]

# (code, bâtiment, type, capacité, statut, description)
DEMO_ROOMS = [
    ("AMPHI-A", "Bâtiment A", RoomType.AMPHITHEATRE, 200, RoomStatus.ACTIVE,
     "Grand amphithéâtre, accès par le hall principal."),
    ("A-101", "Bâtiment A", RoomType.SALLE_COURS, 40, RoomStatus.ACTIVE, None),
    ("A-102", "Bâtiment A", RoomType.SALLE_TD, 30, RoomStatus.ACTIVE, None),
    ("A-103", "Bâtiment A", RoomType.SALLE_TD, 30, RoomStatus.HORS_SERVICE, "Vidéoprojecteur en réparation."),
    ("B-201", "Bâtiment B", RoomType.SALLE_TP, 24, RoomStatus.ACTIVE, "Laboratoire informatique, 24 postes."),
    ("B-202", "Bâtiment B", RoomType.SALLE_TP, 20, RoomStatus.ACTIVE, "Laboratoire réseaux."),
    ("C-001", "Bâtiment C", RoomType.SALLE_TRAVAIL, 8, RoomStatus.ACTIVE,
     "Salle de travail en groupe, rez-de-chaussée de la bibliothèque."),
    ("C-002", "Bâtiment C", RoomType.SALLE_TRAVAIL, 6, RoomStatus.ACTIVE, None),
    ("D-001", "Bâtiment D", RoomType.SALLE_COURS, 35, RoomStatus.ARCHIVEE, "Ancienne salle, remplacée par A-101."),
]

# (jour ouvré à venir : 0 = le prochain, salle, titulaire, début, fin, motif, participants, statut)
DEMO_BOOKINGS = [
    (0, "A-101", "enseignant", time(10), time(12), "Cours de bases de données", 35, BookingStatus.CONFIRMEE),
    (0, "B-201", "enseignant", time(8, 30), time(10, 30), "TP Docker", 22, BookingStatus.CONFIRMEE),
    (0, "C-001", "etudiant", time(14), time(16), "Révision en groupe", 5, BookingStatus.CONFIRMEE),
    (1, "AMPHI-A", "enseignant", time(9), time(11), "Conférence DevOps", 150, BookingStatus.EN_ATTENTE),
    (1, "A-101", "etudiant", time(14), time(15, 30), "Préparation de soutenance", 4, BookingStatus.CONFIRMEE),
    (2, "A-102", "enseignant", time(16), time(18), "TD d'architecture d'entreprise", 28, BookingStatus.CONFIRMEE),
]

# (jour ouvré à venir, salle, début, fin, motif)
DEMO_BLOCKINGS = [
    (0, "B-202", time(8), time(20), "Maintenance du réseau"),
    (1, "A-102", time(8), time(12), "Examen de mi-semestre"),
]


def next_open_days(count: int, after: date | None = None) -> list[date]:
    """Les `count` jours ouvrés (lundi à samedi) qui suivent aujourd'hui."""
    days: list[date] = []
    day = after or campus_clock.today()
    while len(days) < count:
        day = campus_clock.next_open_day(day + timedelta(days=1))
        days.append(day)
    return days


def seed_accounts(db: Session) -> None:
    domain = settings.allowed_email_domain.lower()
    for local_part, full_name, role, is_active in DEMO_ACCOUNTS:
        email = f"{local_part}@{domain}"
        if db.scalar(select(User).where(User.email == email)) is not None:
            print(f"déjà présent  : {email}")
            continue
        db.add(
            User(
                email=email,
                full_name=full_name,
                role=role,
                is_active=is_active,
                password_hash=hash_password(settings.seed_password),
            )
        )
        print(f"créé          : {email} ({role.value})")
    db.flush()


def seed_rooms(db: Session) -> None:
    for code, building, room_type, capacity, status, description in DEMO_ROOMS:
        if db.scalar(select(Room).where(Room.code == code)) is not None:
            print(f"déjà présente : salle {code}")
            continue
        db.add(
            Room(
                code=code,
                building=building,
                room_type=room_type,
                capacity=capacity,
                status=status,
                description=description,
            )
        )
        print(f"créée         : salle {code}")
    db.flush()


def seed_bookings(db: Session) -> None:
    now = campus_clock.now()
    upcoming = db.scalar(select(Booking.id).where(Booking.start_at >= now).limit(1))
    upcoming = upcoming or db.scalar(select(Blocking.id).where(Blocking.start_at >= now).limit(1))
    if upcoming is not None:
        print("réservations et blocages de démonstration déjà présents")
        return

    days = next_open_days(3)
    rooms = {room.code: room for room in db.scalars(select(Room))}
    domain = settings.allowed_email_domain.lower()
    users = {user.email: user for user in db.scalars(select(User))}
    manager = users.get(f"gestionnaire@{domain}")

    for index, code, holder, start, end, purpose, participants, status in DEMO_BOOKINGS:
        user = users.get(f"{holder}@{domain}")
        if code not in rooms or user is None:
            continue
        db.add(
            Booking(
                room=rooms[code],
                holder=user,
                start_at=campus_clock.at(days[index], start),
                end_at=campus_clock.at(days[index], end),
                purpose=purpose,
                participants=participants,
                status=status,
            )
        )
    for index, code, start, end, reason in DEMO_BLOCKINGS:
        if code not in rooms:
            continue
        db.add(
            Blocking(
                room=rooms[code],
                start_at=campus_clock.at(days[index], start),
                end_at=campus_clock.at(days[index], end),
                reason=reason,
                author_id=manager.id if manager else None,
            )
        )
    print(
        f"créés         : {len(DEMO_BOOKINGS)} réservations et {len(DEMO_BLOCKINGS)} blocages "
        f"du {days[0]:%d/%m} au {days[-1]:%d/%m}"
    )
    db.flush()


def main() -> None:
    with SessionLocal() as db:
        seed_accounts(db)
        seed_rooms(db)
        seed_bookings(db)
        db.commit()
    print("Mot de passe des comptes : valeur SEED_PASSWORD de backend/.env")


if __name__ == "__main__":
    main()
