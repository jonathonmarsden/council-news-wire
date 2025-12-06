from core.email_utils import send_email


if __name__ == "__main__":
    send_email(
        subject="Council News Bot: SendGrid test",
        body="This is a SendGrid test email from the Council News Bot system.",
    )
