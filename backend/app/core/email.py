"""Envoi des e-mails transactionnels — SMTP (aiosmtplib).

CE QUE FAIT CE MODULE, ET CE QU'IL NE FAIT PAS
----------------------------------------------
Il compose et il envoie. Ce qui est ÉCRIT — les phrases, les langues, les
couleurs de marque — vit dans `email_content.py`. Les mélanger obligeait à
relire une fonction d'envoi pour corriger une virgule.

LE LOGO EST EMBARQUÉ, PAS LIÉ
-----------------------------
Il voyage dans le message (pièce jointe `cid:`) au lieu d'être chargé depuis une
URL. Deux raisons :

  * la plupart des clients de messagerie BLOQUENT les images distantes par
    défaut — un logo lié s'affiche en cadre vide chez la majorité des
    destinataires ;
  * une image distante est un mouchard : elle dit à l'expéditeur quand et où
    le message a été ouvert. Nous n'avons pas à le savoir.

Il est aplati sur du blanc : de nombreux clients rendent la transparence en
NOIR, ce qui donnait un logo illisible sur fond clair.
"""
from __future__ import annotations

import logging
import os
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.email_content import MARQUE, normaliser_langue, textes

logger = logging.getLogger("email_service")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class EmailIndisponible(RuntimeError):
    """Le service d'envoi est momentanement injoignable.

    Distincte d'une erreur de programmation : l'appelant sait qu'il peut
    proposer de reessayer, plutot que de rendre une trace technique.
    """


LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"
LOGO_CID = "logo-precis"


# ── Gabarit ──────────────────────────────────────────────────────────────────
# Tableaux et styles en ligne : c'est laid, et c'est la seule chose qui tienne
# dans Outlook, Gmail et Apple Mail à la fois. Aucune feuille de style externe,
# aucun flex, aucune grille — ils sont ignorés ou cassés selon le client.
GABARIT = """\
<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{fond};font-family:system-ui,-apple-system,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px">
    <tr><td align="center">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:420px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.05)">

        <tr><td style="padding:32px 32px 20px;text-align:center">
          <img src="cid:{cid}" width="48" alt="{marque}"
               style="display:block;margin:0 auto 10px;border:0">
          <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:{gris_clair}">{bandeau}</div>
        </td></tr>

        <tr><td style="padding:0 32px">
          <div style="height:1px;background:{trait}"></div>
        </td></tr>

        <tr><td style="padding:26px 32px 30px;text-align:center">
          <h1 style="font-size:19px;font-weight:700;color:{encre};margin:0 0 4px">{titre}</h1>
          <p style="font-size:13px;color:{gris};margin:0 0 22px">{sous_titre}</p>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px">
            <tr><td align="center">
              <a href="{url}" style="display:inline-block;background:{bleu};color:#fff;
                 padding:13px 40px;border-radius:10px;text-decoration:none;
                 font-weight:600;font-size:14px">{bouton}</a>
            </td></tr>
          </table>

          <p style="font-size:12px;color:{gris_clair};margin:0 0 10px">{ou}</p>
          <div style="font-size:30px;font-weight:800;letter-spacing:9px;color:{encre};
                      font-family:'SF Mono','Fira Code',Consolas,monospace">{code}</div>
        </td></tr>

        <tr><td style="padding:0 32px 26px">
          <div style="height:1px;background:{trait};margin-bottom:14px"></div>
          <p style="font-size:12px;color:{gris_clair};text-align:center;margin:0 0 4px">{ignorer}</p>
          <p style="font-size:11px;color:{trait};text-align:center;margin:0">{auto}</p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _logo() -> MIMEImage | None:
    """Le logo en pièce jointe INLINE, ou None s'il est introuvable.

    Introuvable n'est pas fatal : le message part sans logo plutôt que pas du
    tout. Un code de connexion qui n'arrive pas coûte un compte ; un logo
    manquant coûte une image.
    """
    try:
        with open(LOGO_PATH, "rb") as f:
            img = MIMEImage(f.read(), _subtype="png")
        img.add_header("Content-ID", f"<{LOGO_CID}>")
        img.add_header("Content-Disposition", "inline", filename="precis.png")
        return img
    except Exception as exc:
        logger.warning("Logo d'e-mail introuvable (%s) : %s", LOGO_PATH, exc)
        return None


def _message_verification(email: str, code: str, token: str,
                          langue: str) -> MIMEMultipart:
    t = textes(langue)
    url = f"{FRONTEND_URL}/verify-email?token={token}"

    html = GABARIT.format(lang=langue, cid=LOGO_CID, code=code, url=url,
                          marque=MARQUE["nom"], **MARQUE, **t)
    texte = t["texte_brut"].format(code=code, url=url)

    # `related` enveloppe `alternative` : le HTML et son image forment UN tout,
    # dont la version texte est l'alternative. L'ordre inverse fait apparaître
    # le logo comme une pièce jointe séparée dans plusieurs clients.
    msg = MIMEMultipart("related")
    # L'expéditeur AFFICHÉ est « Précis » — l'adresse sous-jacente est exigée
    # par le serveur SMTP mais n'apparaît pas dans la plupart des clients.
    msg["From"] = f"{MARQUE['nom']} <{SMTP_USER}>"
    msg["To"] = email
    msg["Subject"] = t["sujet_verification"].format(code=code)
    msg["Reply-To"] = "noreply@precis.app"
    # Un e-mail transactionnel ne doit JAMAIS déclencher de réponse
    # automatique : ni absence du bureau, ni accusé de réception.
    msg["Auto-Submitted"] = "auto-generated"
    msg["X-Auto-Response-Suppress"] = "All"

    corps = MIMEMultipart("alternative")
    corps.attach(MIMEText(texte, "plain", "utf-8"))
    corps.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(corps)

    logo = _logo()
    if logo is not None:
        msg.attach(logo)
    return msg


async def send_verification_email(email: str, code: str, token: str,
                                  accept_language: str | None = None) -> None:
    """Envoie le code de connexion, dans la langue de l'interface.

    `accept_language` vient de l'en-tête de la requête qui a déclenché l'envoi :
    c'est la langue dans laquelle l'utilisateur venait de lire le bouton sur
    lequel il a cliqué. Absent, on retombe sur le français.
    """
    langue = normaliser_langue(accept_language)
    msg = _message_verification(email, code, token, langue)

    if not EMAIL_ENABLED or not SMTP_HOST:
        logger.info("[DEV] Vérification → %s | langue=%s | code=%s | token=%s",
                    email, langue, code, token)
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
        logger.info("Vérification envoyée à %s (%s)", email, langue)
    except Exception as exc:
        # Le serveur SMTP est injoignable, ou refuse. L'exception BRUTE
        # remontait jusqu'au client : une trace technique en 500 pour une panne
        # qui n'a rien à voir avec sa demande, et rien qui lui dise quoi faire.
        #
        # On lève une erreur PARLANTE. Le compte, lui, existe déjà : l'appelant
        # pourra redemander un code (`/auth/resend-verification`) dès que le
        # service d'envoi sera rétabli — rien n'est perdu.
        #
        # On ne l'avale PAS : répondre « c'est envoyé » quand rien n'est parti,
        # c'est laisser quelqu'un attendre un e-mail qui n'arrivera jamais.
        logger.error("Échec envoi à %s : %s", email, exc)
        raise EmailIndisponible(
            "L'envoi de l'e-mail a échoué. Réessayez dans un instant.") from exc
