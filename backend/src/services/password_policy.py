"""Règles d'un nouveau mot de passe (SC-18), communes à la réinitialisation et aux comptes."""

from src.services.common import ServiceError

MIN_LENGTH = 8
MAX_LENGTH = 64  # bcrypt ne lit que 72 octets : 64 caractères laissent la marge des accents

PASSWORD_POLICY = (
    f"Le mot de passe doit contenir de {MIN_LENGTH} à {MAX_LENGTH} caractères, "
    "dont au moins une lettre et un chiffre."
)


def is_acceptable(password: str) -> bool:
    return (
        MIN_LENGTH <= len(password) <= MAX_LENGTH
        and len(password.encode("utf-8")) <= 72
        and any(char.isalpha() for char in password)
        and any(char.isdigit() for char in password)
    )


def check_new_password(password: str) -> None:
    """Lève une erreur 400 avec la règle à respecter si le mot de passe est trop faible."""
    if not is_acceptable(password):
        raise ServiceError(400, PASSWORD_POLICY)
