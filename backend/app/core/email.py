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

import html as _html
import logging
import os
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.email_content import (MARQUE, normaliser_langue, textes,
                                    textes_invitation)

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


# ── Gabarit de l'invitation ─────────────────────────────────────────────────
# Même charpente que le code de connexion (tableaux, styles en ligne), mais un
# message de PRÉSENTATION : plus large, un liseré aux couleurs de la marque,
# trois arguments, un seul bouton. Le mot personnel est optionnel ({mot}).
GABARIT_INVITATION = """\
<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{fond};font-family:system-ui,-apple-system,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px">
    <tr><td align="center">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.05)">

        <tr><td style="height:4px;background:{bleu};font-size:0;line-height:0">&nbsp;</td></tr>

        <tr><td style="padding:32px 36px 8px;text-align:center">
          <img src="cid:{cid}" width="52" alt="{marque}"
               style="display:block;margin:0 auto 10px;border:0">
          <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:{gris_clair}">{bandeau}</div>
        </td></tr>

        <tr><td style="padding:14px 36px 6px;text-align:center">
          <h1 style="font-size:22px;line-height:1.3;font-weight:700;color:{encre};margin:0 0 8px">{titre}</h1>
          <p style="font-size:15px;line-height:1.5;color:{gris};margin:0">{sous_titre}</p>
        </td></tr>
{mot}
        <tr><td style="padding:22px 36px 4px">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td width="24" valign="top" style="color:{bleu};font-weight:700;font-size:14px;padding:0 0 10px">&#10003;</td>
                <td style="font-size:14px;line-height:1.5;color:{encre};padding:0 0 10px">{atout_1}</td></tr>
            <tr><td width="24" valign="top" style="color:{bleu};font-weight:700;font-size:14px;padding:0 0 10px">&#10003;</td>
                <td style="font-size:14px;line-height:1.5;color:{encre};padding:0 0 10px">{atout_2}</td></tr>
            <tr><td width="24" valign="top" style="color:{bleu};font-weight:700;font-size:14px;padding:0">&#10003;</td>
                <td style="font-size:14px;line-height:1.5;color:{encre};padding:0">{atout_3}</td></tr>
          </table>
        </td></tr>

        <tr><td style="padding:26px 36px 8px;text-align:center">
          <a href="{url}" style="display:inline-block;background:{bleu};color:#fff;
             padding:14px 44px;border-radius:10px;text-decoration:none;
             font-weight:600;font-size:15px">{bouton}</a>
          <p style="font-size:12px;color:{gris_clair};margin:14px 0 0;word-break:break-all">{lien}</p>
        </td></tr>

        <tr><td style="padding:22px 36px 28px">
          <div style="height:1px;background:{trait};margin-bottom:14px"></div>
          <p style="font-size:11.5px;line-height:1.5;color:{gris_clair};text-align:center;margin:0">{pourquoi}</p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

# Le mot personnel, en citation. Absent, la ligne {mot} reste vide.
BLOC_MOT = """
        <tr><td style="padding:22px 36px 0">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:{fond};border-left:3px solid {bleu};border-radius:8px">
            <tr><td style="padding:14px 16px">
              <div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{gris_clair};margin:0 0 6px">{mot_de}</div>
              <div style="font-size:14px;line-height:1.55;color:{encre};font-style:italic">{texte}</div>
            </td></tr>
          </table>
        </td></tr>
"""


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


def _message_invitation(destinataire: str, inviteur: str, inviteur_email: str,
                        message: str | None, langue: str) -> MIMEMultipart:
    """Compose l'invitation. `inviteur` et `message` sont saisis par un
    utilisateur : ils sont ÉCHAPPÉS avant d'entrer dans le HTML — sinon
    n'importe quel compte pourrait glisser un lien ou un formulaire dans un
    e-mail qui part sous notre nom."""
    t = textes_invitation(langue)
    url = FRONTEND_URL
    esc = _html.escape
    nom_h, email_h, url_h = esc(inviteur), esc(inviteur_email), esc(url)
    couleurs = {k: v for k, v in MARQUE.items() if k != "nom"}

    mot = ""
    if message:
        mot = BLOC_MOT.format(
            mot_de=t["mot_de"].format(inviteur=nom_h),
            texte=esc(message).replace("\n", "<br>"), **couleurs)

    html = GABARIT_INVITATION.format(
        lang=langue, cid=LOGO_CID, url=url_h, marque=MARQUE["nom"], mot=mot,
        bandeau=t["bandeau"], titre=t["titre"].format(inviteur=nom_h),
        sous_titre=t["sous_titre"], atout_1=t["atout_1"],
        atout_2=t["atout_2"], atout_3=t["atout_3"], bouton=t["bouton"],
        lien=t["lien"].format(url=url_h),
        pourquoi=t["pourquoi"].format(inviteur=nom_h, email=email_h),
        **couleurs)
    texte = t["texte_brut"].format(
        inviteur=inviteur, email=inviteur_email, url=url,
        message=f"\n« {message} »\n" if message else "")

    msg = MIMEMultipart("related")
    msg["From"] = f"{MARQUE['nom']} <{SMTP_USER}>"
    msg["To"] = destinataire
    # Un en-tête ne supporte pas les sauts de ligne : un nom qui en contiendrait
    # casserait le message, voire injecterait des en-têtes.
    msg["Subject"] = " ".join(t["sujet"].format(inviteur=inviteur).split())
    # Répondre à l'invitation, c'est répondre à la personne qui invite — pas à
    # une boîte que personne ne lit.
    msg["Reply-To"] = inviteur_email
    msg["X-Auto-Response-Suppress"] = "All"

    corps = MIMEMultipart("alternative")
    corps.attach(MIMEText(texte, "plain", "utf-8"))
    corps.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(corps)

    logo = _logo()
    if logo is not None:
        msg.attach(logo)
    return msg


async def send_plain(to: list[str] | str, subject: str, body: str) -> None:
    """Envoi d'un e-mail texte simple — alertes internes (journal d'erreurs).

    Pas de gabarit de marque : ce n'est pas un message client, c'est une notif
    d'exploitation. Comme le reste du module, si l'envoi est coupé
    (`EMAIL_ENABLED=false` ou pas de SMTP), on JOURNALISE au lieu d'envoyer —
    ce qui rend la fonction testable hors ligne, et jamais bloquante.
    """
    destinataires = [to] if isinstance(to, str) else list(to)
    destinataires = [d for d in destinataires if d]
    if not destinataires:
        return

    if not EMAIL_ENABLED or not SMTP_HOST:
        logger.info("[DEV] Alerte → %s | %s", ", ".join(destinataires), subject)
        return

    import aiosmtplib

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER or "no-reply@precis"
    msg["To"] = ", ".join(destinataires)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        await aiosmtplib.send(
            msg, hostname=SMTP_HOST, port=SMTP_PORT,
            username=SMTP_USER or None, password=SMTP_PASSWORD or None,
            start_tls=(SMTP_PORT != 465), use_tls=(SMTP_PORT == 465),
        )
        logger.info("Alerte envoyée à %s", ", ".join(destinataires))
    except Exception as exc:
        # Une alerte qui échoue ne doit jamais casser l'appelant (souvent un
        # thread de traitement) : on la note et on passe.
        logger.warning("Alerte e-mail non envoyée : %s", exc)


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
            start_tls=(SMTP_PORT != 465),
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


async def send_invitation_email(destinataire: str, inviteur: str,
                                inviteur_email: str, message: str | None = None,
                                accept_language: str | None = None) -> None:
    """Envoie une invitation à découvrir Précis, dans la langue de l'inviteur.

    Lève `EmailIndisponible` si le serveur refuse : l'appelant décide s'il
    continue avec les destinataires suivants."""
    langue = normaliser_langue(accept_language)
    msg = _message_invitation(destinataire, inviteur, inviteur_email,
                              message, langue)

    if not EMAIL_ENABLED or not SMTP_HOST:
        logger.info("[DEV] Invitation → %s | de=%s | langue=%s",
                    destinataire, inviteur_email, langue)
        return

    import aiosmtplib

    try:
        await aiosmtplib.send(
            msg, hostname=SMTP_HOST, port=SMTP_PORT,
            username=SMTP_USER or None, password=SMTP_PASSWORD or None,
            start_tls=(SMTP_PORT != 465), use_tls=(SMTP_PORT == 465),
        )
        logger.info("Invitation envoyée à %s (%s)", destinataire, langue)
    except Exception as exc:
        logger.error("Échec invitation à %s : %s", destinataire, exc)
        raise EmailIndisponible(
            "L'envoi de l'e-mail a échoué. Réessayez dans un instant.") from exc
