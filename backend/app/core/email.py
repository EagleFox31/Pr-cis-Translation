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
from email.utils import formatdate, formataddr, make_msgid
from pathlib import Path

from app.core.email_content import (MARQUE, normaliser_langue, textes,
                                    textes_invitation)

logger = logging.getLogger("email_service")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
# Adresse vue par les destinataires, distincte du compte de connexion : on se
# connecte avec une boîte, on envoie au nom d'un alias de la marque.
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER
SMTP_REPLY_TO = os.getenv("SMTP_REPLY_TO", "").strip() or SMTP_FROM
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class EmailIndisponible(RuntimeError):
    """Le service d'envoi est momentanement injoignable.

    Distincte d'une erreur de programmation : l'appelant sait qu'il peut
    proposer de reessayer, plutot que de rendre une trace technique.
    """


LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"
LOGO_CID = "logo-precis"


# ── Gabarits ─────────────────────────────────────────────────────────────────
# Tableaux et styles en ligne : c'est laid, et c'est la seule chose qui tienne
# dans Outlook, Gmail et Apple Mail à la fois. Aucune feuille de style externe,
# aucun flex, aucune grille — ils sont ignorés ou cassés selon le client.
#
# Une seule CARTE pour tous les e-mails (code, invitation, alertes) : 600 px,
# texte aligné à gauche et justifié, boutons et blocs sur toute la largeur.
# Une carte étroite et centrée laissait de grands vides de part et d'autre
# dans les messageries de bureau. Tout texte venu d'un utilisateur est
# échappé par l'appelant avant d'arriver ici.

_POLICE = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_MONO = "'SF Mono','Fira Code',Consolas,monospace"

#: Couleur du liseré et de la pastille, selon la gravité du message.
NIVEAUX = {
    "info": ("#1a4dc7", "#e8eefb"),
    "avertissement": ("#b45309", "#fef3c7"),
    "critique": ("#b91c1c", "#fee2e2"),
}


def _carte(*, lang: str, niveau: str, bandeau: str, corps: str,
           pied: str) -> str:
    m = MARQUE
    accent, fond_accent = NIVEAUX.get(niveau, NIVEAUX["info"])
    return f"""\
<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>@media (max-width:480px){{.pz{{padding-left:20px!important;padding-right:20px!important}}.pz p,.pz div{{text-align:left!important}}}}</style></head>
<body style="margin:0;padding:0;background:{m['fond']};font-family:{_POLICE}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{m['fond']}">
    <tr><td align="center" style="padding:28px 12px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid {m['trait']};border-radius:14px;overflow:hidden">
        <tr><td style="height:4px;background:{accent};font-size:0;line-height:0">&nbsp;</td></tr>
        <tr><td class="pz" style="padding:20px 36px 18px;border-bottom:1px solid {m['trait']}">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td valign="middle" width="34" style="width:34px"><img src="cid:{LOGO_CID}" width="30" height="33" alt="{m['nom']}" style="display:block;border:0"></td>
            <td valign="middle" style="padding-left:10px;font-size:18px;font-weight:700;color:{m['encre']}">{m['nom']}</td>
            <td valign="middle" align="right"><span style="display:inline-block;padding:5px 12px;border-radius:999px;background:{fond_accent};color:{accent};font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase">{bandeau}</span></td>
          </tr></table>
        </td></tr>
        <tr><td class="pz" style="padding:28px 36px 4px;text-align:left">
{corps}
        </td></tr>
        <tr><td class="pz" style="padding:22px 36px 26px">
          <div style="height:1px;background:{m['trait']};margin:0 0 14px;font-size:0;line-height:0">&nbsp;</div>
{pied}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _titre(texte: str) -> str:
    return (f'<h1 style="font-size:22px;line-height:1.3;font-weight:700;'
            f'color:{MARQUE["encre"]};margin:0 0 10px;text-align:left">{texte}</h1>')


def _para(texte: str, *, taille: int = 15, couleur: str | None = None,
          marge: int = 18) -> str:
    return (f'<p style="font-size:{taille}px;line-height:1.6;'
            f'color:{couleur or MARQUE["gris"]};margin:0 0 {marge}px;'
            f'text-align:justify">{texte}</p>')


def _petit(texte: str, *, marge: int = 6) -> str:
    return (f'<p style="font-size:12px;line-height:1.55;color:{MARQUE["gris_clair"]};'
            f'margin:0 0 {marge}px;text-align:justify">{texte}</p>')


def _bouton(libelle: str, url: str, couleur: str | None = None) -> str:
    """Bouton pleine largeur : il occupe la ligne au lieu de flotter au centre."""
    c = couleur or MARQUE["bleu"]
    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:6px 0 16px">
  <tr><td align="center" bgcolor="{c}" style="background:{c};border-radius:10px">
    <a href="{url}" style="display:block;padding:14px 20px;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;text-align:center">{libelle}</a>
  </td></tr>
</table>"""


def _bloc_code(etiquette: str, code: str) -> str:
    m = MARQUE
    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;background:{m['fond']};border:1px solid {m['trait']};border-radius:10px">
  <tr><td style="padding:18px 20px">
    <div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:{m['gris']};margin:0 0 8px">{etiquette}</div>
    <div style="font-size:32px;font-weight:800;letter-spacing:10px;color:{m['encre']};font-family:{_MONO}">{code}</div>
  </td></tr>
</table>"""


def _citation(etiquette: str, texte: str, couleur: str | None = None) -> str:
    m = MARQUE
    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;background:{m['fond']};border-left:3px solid {couleur or m['bleu']};border-radius:8px">
  <tr><td style="padding:14px 18px">
    <div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{m['gris']};margin:0 0 6px">{etiquette}</div>
    <div style="font-size:14px;line-height:1.6;color:{m['encre']};text-align:justify">{texte}</div>
  </td></tr>
</table>"""


def _details(lignes: list[tuple[str, str]]) -> str:
    """Tableau libellé / valeur sur toute la largeur."""
    m = MARQUE
    rangs = "".join(
        f'<tr><td width="38%" valign="top" style="padding:10px 12px 10px 0;'
        f'border-top:1px solid {m["trait"]};font-size:13px;color:{m["gris"]}">{lib}</td>'
        f'<td valign="top" style="padding:10px 0;border-top:1px solid {m["trait"]};'
        f'font-size:14px;font-weight:600;color:{m["encre"]};word-break:break-word">{val}</td></tr>'
        for lib, val in lignes)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 20px;border-bottom:1px solid {m["trait"]}">{rangs}</table>')


def _atouts(atouts: list[str]) -> str:
    m = MARQUE
    rangs = "".join(
        f'<tr><td width="28" valign="top" style="padding:0 0 10px;color:{m["bleu"]};'
        f'font-weight:700;font-size:15px">&#10003;</td>'
        f'<td style="padding:0 0 10px;font-size:15px;line-height:1.5;color:{m["encre"]}">{a}</td></tr>'
        for a in atouts)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 14px">{rangs}</table>')


def _html_verification(langue: str, code: str, url: str) -> str:
    t = textes(langue)
    corps = (_titre(t["titre"]) + _para(t["sous_titre"])
             + _bouton(t["bouton"], url) + _bloc_code(t["ou"], code))
    pied = _petit(t["ignorer"]) + _petit(t["auto"], marge=0)
    return _carte(lang=langue, niveau="info", bandeau=t["bandeau"],
                  corps=corps, pied=pied)


def _html_invitation(langue: str, *, nom_h: str, email_h: str, url_h: str,
                     message_h: str | None) -> str:
    t = textes_invitation(langue)
    corps = _titre(t["titre"].format(inviteur=nom_h)) + _para(t["sous_titre"])
    if message_h:
        corps += _citation(t["mot_de"].format(inviteur=nom_h),
                           message_h.replace("\n", "<br>"))
    corps += (_atouts([t["atout_1"], t["atout_2"], t["atout_3"]])
              + _bouton(t["bouton"], url_h)
              + _petit(t["lien"].format(url=url_h), marge=8)
                 .replace("text-align:justify", "text-align:left;word-break:break-all"))
    pied = _petit(t["pourquoi"].format(inviteur=nom_h, email=email_h), marge=0)
    return _carte(lang=langue, niveau="info", bandeau=t["bandeau"],
                  corps=corps, pied=pied)


def _html_alerte(*, titre: str, resume: str, niveau: str, bandeau: str,
                 details: list[tuple[str, str]] | None,
                 citation: tuple[str, str] | None,
                 bouton: tuple[str, str] | None) -> str:
    """Alerte interne (support, solde, journal). Tout est échappé ici : un
    ticket de support porte du texte saisi par n'importe quel client."""
    esc = _html.escape
    accent = NIVEAUX.get(niveau, NIVEAUX["info"])[0]
    corps = _titre(esc(titre))
    for bloc in [b for b in resume.split("\n\n") if b.strip()]:
        corps += _para(esc(bloc.strip()).replace("\n", "<br>"),
                       couleur=MARQUE["encre"])
    if details:
        corps += _details([(esc(str(l)), esc(str(v))) for l, v in details])
    if citation:
        corps += _citation(esc(citation[0]),
                           esc(citation[1]).replace("\n", "<br>"), accent)
    if bouton:
        corps += _bouton(esc(bouton[0]), esc(bouton[1]), accent)
    pied = _petit("Alerte automatique de Précis, envoyée aux comptes "
                  "administrateurs. Ne pas transférer à un client.", marge=0)
    return _carte(lang="fr", niveau=niveau, bandeau=esc(bandeau),
                  corps=corps, pied=pied)


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



def _expediteur(msg) -> None:
    """From, Date et Message-ID conformes (RFC 5322).

    Seul le NOM est encodé (« Précis ») : encodé avec l'adresse, le From
    devient invalide et Gmail rejette le message sans le livrer.
    """
    msg["From"] = formataddr((MARQUE["nom"], SMTP_FROM))
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=SMTP_FROM.rpartition("@")[2] or None)

def _message_verification(email: str, code: str, token: str,
                          langue: str) -> MIMEMultipart:
    t = textes(langue)
    url = f"{FRONTEND_URL}/verify-email?token={token}"

    html = _html_verification(langue, code, url)
    texte = t["texte_brut"].format(code=code, url=url)

    # `related` enveloppe `alternative` : le HTML et son image forment UN tout,
    # dont la version texte est l'alternative. L'ordre inverse fait apparaître
    # le logo comme une pièce jointe séparée dans plusieurs clients.
    msg = MIMEMultipart("related")
    # L'expéditeur AFFICHÉ est « Précis » — l'adresse sous-jacente est exigée
    # par le serveur SMTP mais n'apparaît pas dans la plupart des clients.
    _expediteur(msg)
    msg["To"] = email
    msg["Subject"] = t["sujet_verification"].format(code=code)
    msg["Reply-To"] = SMTP_REPLY_TO
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
    html = _html_invitation(langue, nom_h=esc(inviteur),
                            email_h=esc(inviteur_email), url_h=esc(url),
                            message_h=esc(message) if message else None)
    texte = t["texte_brut"].format(
        inviteur=inviteur, email=inviteur_email, url=url,
        message=f"\n« {message} »\n" if message else "")

    msg = MIMEMultipart("related")
    _expediteur(msg)
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


def _message_alerte(destinataires: list[str], subject: str, body: str, *,
                    titre: str | None, resume: str | None, niveau: str,
                    bandeau: str, details, citation, bouton) -> MIMEMultipart:
    """Alerte interne : carte de marque + version texte (`body`, complétée du
    lien du bouton pour les messageries sans HTML)."""
    texte = body + (f"\n\n{bouton[0]} : {bouton[1]}" if bouton else "")
    html = _html_alerte(titre=titre or subject, resume=resume if resume is not None else body,
                        niveau=niveau, bandeau=bandeau, details=details,
                        citation=citation, bouton=bouton)
    msg = MIMEMultipart("related")
    _expediteur(msg)
    msg["To"] = ", ".join(destinataires)
    msg["Subject"] = subject
    msg["Auto-Submitted"] = "auto-generated"
    corps = MIMEMultipart("alternative")
    corps.attach(MIMEText(texte, "plain", "utf-8"))
    corps.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(corps)
    logo = _logo()
    if logo is not None:
        msg.attach(logo)
    return msg


async def send_plain(to: list[str] | str, subject: str, body: str, *,
                     titre: str | None = None, resume: str | None = None,
                     niveau: str = "info", bandeau: str = "Alerte",
                     details: list[tuple[str, str]] | None = None,
                     citation: tuple[str, str] | None = None,
                     bouton: tuple[str, str] | None = None) -> None:
    """Alerte interne (support, solde IA, journal d'erreurs).

    `body` est la version TEXTE ; la version HTML reprend la carte Précis
    (titre, `resume` — par défaut `body` —, `details`, `citation`, `bouton`).
    Comme le reste du module, si l'envoi est coupé
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

    msg = _message_alerte(destinataires, subject, body, titre=titre,
                          resume=resume, niveau=niveau, bandeau=bandeau,
                          details=details, citation=citation, bouton=bouton)
    try:
        await aiosmtplib.send(
            msg, hostname=SMTP_HOST, port=SMTP_PORT,
            sender=SMTP_FROM or None, username=SMTP_USER or None, password=SMTP_PASSWORD or None,
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
            sender=SMTP_FROM or None, username=SMTP_USER or None,
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
            sender=SMTP_FROM or None, username=SMTP_USER or None, password=SMTP_PASSWORD or None,
            start_tls=(SMTP_PORT != 465), use_tls=(SMTP_PORT == 465),
        )
        logger.info("Invitation envoyée à %s (%s)", destinataire, langue)
    except Exception as exc:
        logger.error("Échec invitation à %s : %s", destinataire, exc)
        raise EmailIndisponible(
            "L'envoi de l'e-mail a échoué. Réessayez dans un instant.") from exc
