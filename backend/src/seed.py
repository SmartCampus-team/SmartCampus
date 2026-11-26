"""Données de démonstration : un compte par rôle (SC-12), les salles du campus (SC-20),
des réservations et des blocages sur les prochains jours ouvrés (SC-22), le catalogue
d'équipements et leur affectation aux salles (SC-31), des demandes administratives (SC-34).

Usage, depuis le dossier backend :  python -m src.seed
Le script peut être relancé : il ne recrée pas ce qui existe déjà, et ne recrée les
réservations et blocages de démonstration que s'il n'y en a plus à venir.
"""

from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import settings
from src.database import SessionLocal
from src.models.admin_request import AdminRequest, RequestType
from src.models.blocking import Blocking
from src.models.booking import Booking, BookingStatus
from src.models.equipment import Equipment, EquipmentCategory
from src.models.request_history import RequestHistory
from src.models.room import Room, RoomStatus, RoomType
from src.models.user import Role, User
from src.services import campus_clock, request_service
from src.services.security import hash_password

DEMO_ACCOUNTS = [
    ("etudiant", "Étudiant Démo", Role.ETUDIANT, True),
    ("enseignant", "Enseignant Démo", Role.ENSEIGNANT, True),
    ("gestionnaire", "Gestionnaire Démo", Role.GESTIONNAIRE, True),
    ("scolarite", "Agent Scolarité Démo", Role.SCOLARITE, True),
    ("admin", "Administrateur Démo", Role.ADMINISTRATEUR, True),
    ("desactive", "Compte Désactivé Démo", Role.ETUDIANT, False),
    ("etudiant2", "Étudiante Démo 2", Role.ETUDIANT, True),  # SC-36 : la demande d'un autre étudiant
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

# Catalogue d'équipements (SC-31) : (libellé, catégorie)
DEMO_EQUIPMENT = [
    ("Vidéoprojecteur", EquipmentCategory.AUDIOVISUEL),
    ("Écran interactif", EquipmentCategory.AUDIOVISUEL),
    ("Sonorisation", EquipmentCategory.AUDIOVISUEL),
    ("Visioconférence", EquipmentCategory.AUDIOVISUEL),
    ("Postes informatiques", EquipmentCategory.INFORMATIQUE),
    ("Prises réseau", EquipmentCategory.INFORMATIQUE),
    ("Tableau blanc", EquipmentCategory.MOBILIER),
    ("Tables modulables", EquipmentCategory.MOBILIER),
    ("Climatisation", EquipmentCategory.CONFORT),
    ("Accès PMR", EquipmentCategory.ACCESSIBILITE),
]

# Équipements de chaque salle (SC-31)
DEMO_ROOM_EQUIPMENT = {
    "AMPHI-A": ["Vidéoprojecteur", "Sonorisation", "Visioconférence", "Climatisation", "Accès PMR"],
    "A-101": ["Vidéoprojecteur", "Tableau blanc", "Climatisation", "Accès PMR"],
    "A-102": ["Vidéoprojecteur", "Tableau blanc"],
    "A-103": ["Tableau blanc"],
    "B-201": ["Postes informatiques", "Prises réseau", "Vidéoprojecteur", "Climatisation"],
    "B-202": ["Prises réseau", "Tableau blanc"],
    "C-001": ["Écran interactif", "Tables modulables", "Tableau blanc"],
    "C-002": ["Tables modulables", "Tableau blanc"],
}

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


def seed_equipment(db: Session) -> None:
    """Crée les équipements manquants et les ajoute aux salles qui ne les ont pas encore (SC-31)."""
    catalogue = {equipment.label: equipment for equipment in db.scalars(select(Equipment))}
    for label, category in DEMO_EQUIPMENT:
        if label not in catalogue:
            catalogue[label] = Equipment(label=label, category=category)
            db.add(catalogue[label])
            print(f"créé          : équipement {label}")
    db.flush()

    added = 0
    for room in db.scalars(select(Room).where(Room.code.in_(DEMO_ROOM_EQUIPMENT))):
        for label in DEMO_ROOM_EQUIPMENT[room.code]:
            if catalogue[label] not in room.equipment:
                room.equipment.append(catalogue[label])
                added += 1
    print(f"affectés      : {added} équipements aux salles" if added else "équipements des salles déjà affectés")
    db.flush()


# Demandes administratives (SC-34) : (étudiant, type, description, déposée il y a N jours)
DEMO_REQUESTS = [
    ("etudiant", RequestType.ATTESTATION_SCOLARITE, "Attestation de scolarité pour le dossier de bourse.", 6),
    ("etudiant", RequestType.RELEVE_NOTES, "Relevé de notes du semestre 3, en deux exemplaires.", 4),
    ("etudiant2", RequestType.DEMANDE_STAGE, "Convention de stage de fin d'année, du 2 février au 30 avril.", 3),
    ("etudiant", RequestType.RECLAMATION, "La note du module Réseaux n'apparaît pas sur mon relevé.", 1),
    ("etudiant2", RequestType.CERTIFICAT_REUSSITE, "Certificat de réussite de la première année.", 0),
]


def seed_requests(db: Session) -> None:
    """Dépose les demandes de démonstration, « En attente », avec des dates de dépôt échelonnées.

    Rien n'est créé s'il existe déjà des demandes : celles saisies pendant les essais sont gardées.
    """
    if db.scalar(select(func.count()).select_from(AdminRequest)):
        print("demandes administratives déjà présentes")
        return
    users = {user.email.split("@")[0]: user for user in db.scalars(select(User))}
    for login, request_type, description, days_ago in DEMO_REQUESTS:
        request = request_service.create_request(db, users[login], request_type, description)
        deposited = campus_clock.now() - timedelta(days=days_ago, hours=2)
        request.created_at = request.updated_at = deposited
        for line in db.scalars(select(RequestHistory).where(RequestHistory.request_id == request.id)):
            line.created_at = deposited
    db.flush()
    print(f"créées         : {len(DEMO_REQUESTS)} demandes administratives en attente")


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
        seed_equipment(db)
        seed_bookings(db)
        seed_requests(db)
        db.commit()
    print("Mot de passe des comptes : valeur SEED_PASSWORD de backend/.env")


if __name__ == "__main__":
    main()
