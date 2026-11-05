"""Envoi des e-mails de SmartCampus (SC-18).

MAIL_BACKEND choisit le mode :
- console : l'e-mail est affiché dans le terminal d'uvicorn (développement sans serveur SMTP) ;
- smtp : envoi réel par SMTP_HOST:SMTP_PORT (MailHog en développement) ;
- memory : gardé dans OUTBOX, pour les tests.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from src.config import settings

logger = logging.getLogger("smartcampus.mail")


@dataclass
class SentMail:
    to: str
    subject: str
    body: str


OUTBOX: list[SentMail] = []


class MailError(Exception):
    """Le serveur d'e-mail est injoignable ou a refusé le message."""


def send_mail(to: str, subject: str, body: str) -> None:
    if settings.mail_backend == "memory":
        OUTBOX.append(SentMail(to=to, subject=subject, body=body))
        return

    if settings.mail_backend == "console":
        print(f"\n--- E-mail pour {to} ---\nObjet : {subject}\n\n{body}\n--- Fin de l'e-mail ---\n", flush=True)
        return

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        # Le contenu de l'e-mail (lien de réinitialisation) n'est jamais journalisé (ENF-14)
        logger.error("Envoi d'e-mail impossible vers %s : %s", settings.smtp_host, error)
        raise MailError(str(error)) from error
