"""
Service d'envoi d'emails — SMTP async (aiosmtplib).

Template de vérification : code 6 chiffres + lien cliquable.
"""
from __future__ import annotations
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("email_service")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@precis.app")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

VERIFICATION_HTML = """\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#111;margin-bottom:8px">Vérifiez votre adresse email</h2>
  <p style="color:#444;line-height:1.6">
    Pour activer votre compte Precis, utilisez le code ci-dessous ou cliquez sur le lien.
  </p>

  <div style="background:#f5f5f5;border-radius:12px;padding:24px;text-align:center;margin:24px 0">
    <div style="font-size:36px;font-weight:700;letter-spacing:6px;color:#111;margin-bottom:16px">
      {code}
    </div>
    <a href="{verify_url}"
       style="display:inline-block;background:#111;color:#fff;padding:12px 28px;
              border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">
      Vérifier mon email
    </a>
  </div>

  <p style="color:#888;font-size:13px;line-height:1.5">
    Ce code expire dans 15 minutes. Si vous n'avez pas créé de compte Precis,
    ignorez cet email.
  </p>
</body>
</html>"""


def _build_verification_email(email: str, code: str, token: str) -> MIMEMultipart:
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    html = VERIFICATION_HTML.format(code=code, verify_url=verify_url)
    text = (
        f"Votre code de vérification Precis : {code}\n\n"
        f"Ou cliquez sur ce lien : {verify_url}\n\n"
        f"Ce code expire dans 15 minutes."
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg["Subject"] = f"Code de vérification Precis : {code}"
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


async def send_verification_email(email: str, code: str, token: str) -> None:
    """Envoie l'email de vérification (code + lien)."""
    msg = _build_verification_email(email, code, token)

    if not EMAIL_ENABLED or not SMTP_HOST:
        # Mode dev : log dans la console
        logger.info(f"[DEV] Email vérification → {email} | code={code} | token={token}")
        return

    import aiosmtplib

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER or None,
            password=SMTP_PASSWORD or None,
            start_tls=True,
            use_tls=(SMTP_PORT == 465),
        )
        logger.info(f"Email vérification envoyé à {email}")
    except Exception as exc:
        logger.error(f"Échec envoi email à {email} : {exc}")
        raise
