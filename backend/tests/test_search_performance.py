"""La recherche répond en moins de 2 s pour 95 % des requêtes sur le jeu de démonstration (SC-22 : ENF-05)."""

import time as clock

from src import seed
from src.config import settings
from src.services import campus_clock
from tests.helpers import auth_header, login

SLOTS = [("08:00", "10:00"), ("10:00", "12:00"), ("12:00", "14:00"), ("14:00", "16:00"), ("16:00", "18:00")]


def seeded_student(client, db) -> dict[str, str]:
    """Charge le jeu de démonstration et connecte le compte étudiant de démonstration."""
    seed.seed_accounts(db)
    seed.seed_rooms(db)
    seed.seed_bookings(db)
    db.commit()
    token = login(client, email="etudiant@usms.ac.ma", password=settings.seed_password).json()["access_token"]
    return auth_header(token)


def test_95_percent_of_searches_answer_in_under_2_seconds(client, db):
    headers = seeded_student(client, db)

    durations = []
    for day in seed.next_open_days(4):
        for start, end in SLOTS:
            began = clock.perf_counter()
            response = client.get(
                "/api/rooms/available",
                params={"date": day.isoformat(), "start": start, "end": end, "min_capacity": 4},
                headers=headers,
            )
            durations.append(clock.perf_counter() - began)
            assert response.status_code == 200

    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 2.0, f"95e centile : {p95:.3f} s"


def test_demo_set_gives_the_expected_answer(client, db):
    """Sur le jeu de démonstration, 10:00-12:00 le premier jour ouvré pour 20 personnes."""
    headers = seeded_student(client, db)
    day = seed.next_open_days(1)[0]
    response = client.get(
        "/api/rooms/available",
        params={"date": day.isoformat(), "start": "10:00", "end": "12:00", "min_capacity": 20},
        headers=headers,
    )
    # A-101 et B-201 sont réservées, B-202 bloquée, A-103 hors service, D-001 archivée
    assert [room["code"] for room in response.json()["rooms"]] == ["A-102", "AMPHI-A"]
    assert campus_clock.is_open_day(day) and day > campus_clock.today()
