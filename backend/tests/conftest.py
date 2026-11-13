"""Fixtures pytest (SC-14) : base PostgreSQL de test, client HTTP et comptes.

Les tests n'utilisent jamais la base de développement : l'URL vient de
TEST_DATABASE_URL et le nom de la base doit finir par « _test ».
"""

import importlib
import os
import pkgutil
from collections.abc import Callable, Iterator

from dotenv import dotenv_values  # fourni par pydantic-settings

# Lire backend/.env si présent, puis fixer l'environnement AVANT d'importer src
_dotenv = dotenv_values(".env")
TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or _dotenv.get("TEST_DATABASE_URL")
    or ("postgresql+psycopg://smartcampus:smartcampus@localhost:5432/smartcampus_test")
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BCRYPT_ROUNDS"] = "4"  # hachage rapide pour les tests uniquement
os.environ["ALLOWED_EMAIL_DOMAIN"] = "usms.ac.ma"
os.environ["MAIL_BACKEND"] = "memory"  # e-mails gardés en mémoire, jamais envoyés (SC-18)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL doit désigner une base dont le nom finit par _test")

import src.models
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.user import Role, User
from src.services.security import hash_password
from tests.helpers import PASSWORD

for _module in pkgutil.iter_modules(src.models.__path__):
    importlib.import_module(f"src.models.{_module.name}")


@pytest.fixture(scope="session", autouse=True)
def schema() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(
        email: str = "etudiant@usms.ac.ma",
        password: str = PASSWORD,
        role: Role = Role.ETUDIANT,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            full_name="Étudiant Test",
            role=role,
            is_active=is_active,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        return user

    return _make
