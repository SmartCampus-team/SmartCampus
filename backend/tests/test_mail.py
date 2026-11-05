"""Envoi des e-mails : console, SMTP (MailHog) et mémoire pour les tests (SC-18)."""

import smtplib

import pytest

from src.config import settings
from src.services import mail_service


@pytest.fixture(autouse=True)
def empty_outbox():
    mail_service.OUTBOX.clear()
    yield
    mail_service.OUTBOX.clear()


def test_memory_backend_keeps_the_mail_for_the_tests():
    mail_service.send_mail("a@usms.ac.ma", "Objet", "Corps")
    assert mail_service.OUTBOX == [mail_service.SentMail(to="a@usms.ac.ma", subject="Objet", body="Corps")]


def test_console_backend_prints_the_mail(monkeypatch, capsys):
    monkeypatch.setattr(settings, "mail_backend", "console")
    mail_service.send_mail("a@usms.ac.ma", "Objet", "Corps du message")
    printed = capsys.readouterr().out
    assert "a@usms.ac.ma" in printed
    assert "Corps du message" in printed


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append(f"login:{username}")

    def send_message(self, message):
        FakeSMTP.sent.append((self.host, self.port, message, list(self.calls)))


def test_smtp_backend_sends_the_mail(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "mail_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_username", "smartcampus")
    mail_service.send_mail("a@usms.ac.ma", "Objet", "Corps")
    host, port, message, calls = FakeSMTP.sent[0]
    assert (host, port) == (settings.smtp_host, settings.smtp_port)
    assert message["To"] == "a@usms.ac.ma"
    assert message["Subject"] == "Objet"
    assert calls == ["starttls", "login:smartcampus"]


def test_smtp_failure_raises_mail_error(monkeypatch):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("refusé")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(settings, "mail_backend", "smtp")
    with pytest.raises(mail_service.MailError):
        mail_service.send_mail("a@usms.ac.ma", "Objet", "Corps")
