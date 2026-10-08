import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage


VERIFICATION_TOKEN_LIFETIME = timedelta(hours=24)


def create_verification_token() -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + VERIFICATION_TOKEN_LIFETIME
    return token, token_hash, expires_at


def send_verification_email(email: str, token: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", smtp_user or "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    portal_url = os.getenv("USER_PORTAL_URL", "http://localhost:8000").rstrip("/")

    if not smtp_host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured")

    message = EmailMessage()
    message["Subject"] = "Verify your Arena Helper email"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "Welcome to Arena Helper. Verify your email address by opening this link:\n\n"
        f"{portal_url}/auth/verify-email?token={token}\n\n"
        "This link expires in 24 hours."
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)