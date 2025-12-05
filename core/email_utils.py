import os
import smtplib
from email.message import EmailMessage
from typing import Optional

def send_email(subject: str, body: str, to_address: Optional[str] = None) -> None:
    """Send a plain-text email using SMTP settings from environment variables.

    Expected env vars:
      EMAIL_HOST: SMTP host (default: smtp.gmail.com)
      EMAIL_PORT: SMTP port (default: 587)
      EMAIL_USE_TLS: 'true' / 'false' (default: true)
      EMAIL_HOST_USER: SMTP username (email address)
      EMAIL_HOST_PASSWORD: SMTP password (or app password)
      EMAIL_TO: Default recipient if to_address not provided
    """
    host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    port = int(os.getenv("EMAIL_PORT", "587"))
    use_tls = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
    user = os.getenv("EMAIL_HOST_USER")
    password = os.getenv("EMAIL_HOST_PASSWORD")
    to_address = to_address or os.getenv("EMAIL_TO")

    if not (user and password and to_address):
        print("Email not configured correctly; skipping send.")
        return

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(user, password)
        server.send_message(msg)
        print(f"Email sent to {to_address}")
