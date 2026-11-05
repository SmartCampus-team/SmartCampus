"""Paramètres de l'API, lus dans les variables d'environnement puis dans backend/.env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://smartcampus:smartcampus@localhost:5432/smartcampus"

    # Jeton JWT (ENF-02)
    jwt_secret: str = "dev-secret-a-remplacer-en-production-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    # Domaine des adresses autorisées (RG-11)
    allowed_email_domain: str = "usms.ac.ma"

    # Blocage après échecs de connexion (RG-02)
    max_failed_attempts: int = 3
    lock_minutes: int = 15

    # Coût du hachage bcrypt (ENF-01) ; les tests le baissent pour aller plus vite
    bcrypt_rounds: int = 12

    # Mot de passe des comptes de démonstration (src/seed.py)
    seed_password: str = "SmartCampus2026!"

    # Créneaux des salles (RG-03) : heure locale du campus, pas de 30 min, du lundi au samedi
    campus_timezone: str = "Africa/Casablanca"
    opening_hour: int = 8
    closing_hour: int = 20
    slot_minutes: int = 30

    # Réinitialisation du mot de passe (EF-AUTH-05) : lien valable 30 min, à usage unique
    password_reset_minutes: int = 30
    # Adresse de l'interface, pour construire le lien envoyé par e-mail
    frontend_url: str = "http://localhost:5173"

    # E-mails : « console » les affiche dans le terminal d'uvicorn, « smtp » les envoie
    # (MailHog en développement : localhost:1025, boîte visible sur http://localhost:8025)
    mail_backend: str = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    mail_from: str = "SmartCampus <no-reply@usms.ac.ma>"


settings = Settings()
