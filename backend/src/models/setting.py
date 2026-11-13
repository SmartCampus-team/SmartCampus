"""Table settings : valeurs des règles de gestion, modifiables sans redéployer (SC-26).

Horizon de réservation (RG-04) et quotas (RG-07) : le code lit toujours leur valeur ici, jamais
une constante. Les valeurs par défaut sont posées par la migration 0009 ; l'écran qui les
modifie arrive avec SC-59 (EF-ADMIN-01).
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Setting(Base):
    __tablename__ = "settings"

    # Nom technique du paramètre : booking_horizon_days_student…
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    # Valeur en texte, convertie à la lecture (entier, date…)
    value: Mapped[str] = mapped_column(String(100))
    # Libellé affiché à l'administrateur (SC-59)
    description: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
