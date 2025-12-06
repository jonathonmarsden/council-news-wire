import logging
import os
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


logger = logging.getLogger(__name__)


def send_email(subject: str, body: str, to_address: Optional[str] = None) -> None:
    """Send a plain-text email using SendGrid settings from environment variables.

    Expected env vars:
      SENDGRID_API_KEY: SendGrid API key
      SENDGRID_FROM_EMAIL: Verified sender email address
      SENDGRID_TO_EMAIL: Default recipient if to_address not provided
    """

    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL")
    default_to = os.getenv("SENDGRID_TO_EMAIL")
    recipient = to_address or default_to

    if not api_key:
        logger.warning("SENDGRID_API_KEY not set; email not sent")
        return

    if not from_email:
        logger.warning("SENDGRID_FROM_EMAIL not set; email not sent")
        return

    if not recipient:
        logger.warning("No recipient email configured; email not sent")
        return

    message = Mail(
        from_email=from_email,
        to_emails=recipient,
        subject=subject,
        plain_text_content=body,
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        logger.info("SendGrid email sent to %s (status %s)", recipient, response.status_code)
    except Exception as exc:
        logger.warning("Failed to send SendGrid email: %s", exc)
