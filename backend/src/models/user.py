

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, LargeBinary, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Role(enum.StrEnum):
    ETUDIANT = "etudiant"
    ENSEIGNANT = "enseignant"
    GESTIONNAIRE = "gestionnaire"
    SCOLARITE = "scolarite"
    ADMINISTRATEUR = "administrateur"


class NotificationChannel(enum.StrEnum):
    """Canal des notifications choisi dans le profil (EF-AUTH-06), utilisé au Sprint 5."""

    LES_DEUX = "les_deux"
    EMAIL = "email"
    APPLICATION = "application"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="user_role",
            native_enum=False,
            length=20,
            values_callable=lambda roles: [r.value for r in roles],
        )
    )
    # Statut du compte : un compte désactivé ne peut plus se connecter (SC-11)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Empreinte bcrypt, jamais le mot de passe en clair (ENF-01)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Compteur d'échecs consécutifs et fin du blocage (RG-02, SC-16)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Profil modifiable par l'utilisateur (SC-19, EF-AUTH-06)
    phone: Mapped[str | None] = mapped_column(String(20))
    notification_channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel",
            native_enum=False,
            length=20,
            values_callable=lambda channels: [c.value for c in channels],
        ),
        default=NotificationChannel.LES_DEUX,
        server_default=NotificationChannel.LES_DEUX.value,
    )
    # Photo stockée en base (PNG ou JPEG, 2 Mo au plus) ; chargée seulement quand on la demande
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    photo_type: Mapped[str | None] = mapped_column(String(20))
