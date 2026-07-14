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
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:system-ui,-apple-system,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#f8fafc">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:white;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)">
    <tr>
      <td style="padding:32px 28px 24px;text-align:center">
        <h1 style="font-size:22px;font-weight:700;color:#1a4dc7;margin:0 0 8px">Précis</h1>
        <p style="font-size:14px;color:#64748b;margin:0">Vérification de votre adresse email</p>
      </td>
    </tr>
    <tr>
      <td style="padding:0 28px 32px">
        <p style="font-size:15px;color:#334155;line-height:1.6;margin:0 0 24px">
          Utilisez le code ci-dessous pour vous connecter à votre compte Précis.
          Vous pouvez aussi cliquer sur le lien.
        </p>

        <div style="background:#f1f5f9;border-radius:12px;padding:28px 16px;text-align:center;margin-bottom:24px">
          <div style="font-size:38px;font-weight:800;letter-spacing:8px;color:#0f172a;margin-bottom:20px;font-family:monospace">
            {code}
          </div>
          <a href="{verify_url}"
             style="display:inline-block;background:#1a4dc7;color:#fff;padding:12px 32px;
                    border-radius:10px;text-decoration:none;font-weight:600;font-size:14px">
            Vérifier mon email
          </a>
        </div>

        <p style="font-size:13px;color:#94a3b8;line-height:1.5;margin:0">
          Ce code expire dans 15 minutes. Si vous n'avez pas demandé cette vérification,
          ignorez cet email.
        </p>
      </td>
    </tr>
  </table>
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
    from_name = os.getenv("SMTP_FROM_NAME", "Précis")
    from_email = SMTP_USER or SMTP_FROM
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = email
    msg["Subject"] = f"{code} — Code de vérification Précis"
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
