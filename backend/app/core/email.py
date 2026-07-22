"""
Service d'envoi d'emails — Gmail SMTP (aiosmtplib).

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
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ── Template HTML ────────────────────────────────────────────────────────────

VERIFICATION_HTML = """\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:system-ui,-apple-system,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px">
    <tr><td align="center">
      <table width="100%" style="max-width:440px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.05),0 8px 24px rgba(0,0,0,.04)">

        <!-- En-tête -->
        <tr>
          <td style="padding:32px 32px 0;text-align:center">
            <div style="display:inline-block;width:40px;height:40px;background:linear-gradient(135deg,#1a4dc7,#3b82f6);border-radius:10px;margin-bottom:12px"></div>
            <h1 style="font-size:20px;font-weight:700;color:#0f172a;margin:0 0 4px">Précis</h1>
            <p style="font-size:13px;color:#64748b;margin:0 0 24px">Vérification de connexion</p>
            <div style="height:1px;background:#e2e8f0;margin:0 -32px"></div>
          </td>
        </tr>

        <!-- Corps -->
        <tr>
          <td style="padding:28px 32px">
            <p style="font-size:15px;color:#334155;line-height:1.6;margin:0 0 8px">
              Bonjour,
            </p>
            <p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 28px">
              Voici votre code de vérification pour vous connecter à votre compte
              <strong style="color:#0f172a">Précis</strong>.
            </p>

            <!-- Code -->
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px 16px;text-align:center;margin-bottom:24px">
              <div style="font-size:36px;font-weight:800;letter-spacing:10px;color:#0f172a;font-family:'SF Mono','Fira Code',monospace;margin-bottom:16px;user-select:all">
                {code}
              </div>
              <p style="font-size:12px;color:#94a3b8;margin:0">Ou cliquez sur le bouton ci-dessous</p>
            </div>

            <!-- Bouton -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px">
              <tr><td align="center">
                <a href="{verify_url}"
                   style="display:inline-block;background:#1a4dc7;color:#fff;padding:12px 36px;
                          border-radius:10px;text-decoration:none;font-weight:600;font-size:14px">
                  Vérifier mon email
                </a>
              </td></tr>
            </table>

            <p style="font-size:12px;color:#94a3b8;line-height:1.5;margin:0 0 16px">
              Ce code expire dans <strong style="color:#64748b">15 minutes</strong>.
              Si vous n'avez pas demandé ce code, ignorez simplement cet email —
              personne n'a accès à votre compte.
            </p>

            <div style="height:1px;background:#e2e8f0"></div>

            <p style="font-size:11px;color:#cbd5e1;text-align:center;margin:16px 0 0">
              Ceci est un message automatique, merci de ne pas y répondre.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_verification_email(email: str, code: str, token: str) -> MIMEMultipart:
    verify_url = f"{FRONTEND_URL}/verify-email?token={token}"
    html = VERIFICATION_HTML.format(code=code, verify_url=verify_url)
    text = (
        f"Code de vérification Précis : {code}\n\n"
        f"Ou utilisez ce lien : {verify_url}\n\n"
        f"Ce code expire dans 15 minutes.\n"
        f"Ceci est un message automatique, merci de ne pas y répondre."
    )

    msg = MIMEMultipart("alternative")
    # L'expéditeur affiché est « Précis » — l'adresse Gmail sous-jacente
    # est requise par le serveur SMTP mais n'apparaît pas dans la plupart
    # des clients de messagerie.
    msg["From"] = f"Précis <{SMTP_USER}>"
    msg["To"] = email
    msg["Subject"] = f"{code} est votre code de vérification Précis"
    msg["Reply-To"] = "noreply@precis.app"
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


async def send_verification_email(email: str, code: str, token: str) -> None:
    """Envoie l'email de vérification (code + lien)."""
    msg = _build_verification_email(email, code, token)

    if not EMAIL_ENABLED or not SMTP_HOST:
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
