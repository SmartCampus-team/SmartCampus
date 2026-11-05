
INVALID_CREDENTIALS = "E-mail ou mot de passe incorrect"


class AuthError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class ServiceError(AuthError):
    """Refus métier hors connexion (comptes, salles, profil ; SC-17) : même réponse {"detail": message}.

    Hérite d'AuthError pour être traduite en réponse HTTP par le gestionnaire de src/main.py.
    """
