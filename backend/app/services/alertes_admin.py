"""Mails envoyés aux admins quand il y a du nouveau (docs/etude-retours-18-11.md §2).

- Candidature bêta : un mail tout de suite, elle attend une décision.
- Journal d'erreurs, selon la gravité :
  - `critical` : un mail tout de suite, au plus un par heure pour une même panne
    (même empreinte) et au plus `_MAX_CRITIQUES_HEURE` par heure en tout ;
  - `error` : dès la première, puis au plus un mail par heure qui regroupe tout ;
  - `warning` : pas de mail, compté dans le récapitulatif quotidien.
- Récapitulatif quotidien : nouveaux comptes et avertissements de la veille,
  un seul mail, aucun les jours sans rien.

Tout est « au mieux » : un mail qui échoue ne fait jamais échouer l'action qui
l'a déclenché.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, time as dtime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import ADMIN_ALERT_EMAIL, ERROR_LOG_ALERT_COOLDOWN, logger
from app.models import (AdminRecap, ErrorLog, STATUS_NEW, User, utcnow)

# Garde-fou contre une avalanche de pannes « critiques » différentes.
_MAX_CRITIQUES_HEURE = 5

_verrou = threading.Lock()
_dernier_mail_erreurs = 0.0          # horodatage (time.time) du dernier mail « error »
_critiques: dict[str, float] = {}    # empreinte → horodatage du dernier mail


def _reinitialiser() -> None:
    """Remet les délais à zéro (tests)."""
    global _dernier_mail_erreurs
    with _verrou:
        _dernier_mail_erreurs = 0.0
        _critiques.clear()


async def destinataires(db) -> list[str]:
    """Comptes `admin` en base ; à défaut `ADMIN_ALERT_EMAIL` (démarrage)."""
    rows = (await db.execute(select(User.email).where(User.plan == "admin"))).scalars().all()
    emails = [e for e in rows if e]
    if not emails and ADMIN_ALERT_EMAIL:
        emails = [ADMIN_ALERT_EMAIL]
    return emails


async def _envoyer(db, sujet: str, corps: str, **carte) -> bool:
    from app.core.email import send_plain
    emails = await destinataires(db)
    if not emails:
        return False
    await send_plain(emails, sujet, corps, **carte)
    return True


def _url(chemin: str) -> str:
    from app.core.email import FRONTEND_URL
    return f"{FRONTEND_URL}{chemin}"


# ── Candidature bêta ──────────────────────────────────────────────────────────

async def candidature_beta(db, candidature, nom: str | None = None) -> bool:
    try:
        qui = nom or candidature.email
        return await _envoyer(
            db, f"[Précis] Nouvelle candidature bêta : {qui}",
            f"Nouvelle candidature bêta de {candidature.email}.\n\n"
            f"{candidature.motivation}",
            titre="Nouvelle candidature bêta",
            resume="Une personne demande à rejoindre la bêta. Accepte ou refuse "
                   "sa candidature depuis l'espace bêta.",
            bandeau="Bêta",
            details=[("De", candidature.email),
                     ("Format principal", candidature.primary_format)],
            citation=("Motivation", candidature.motivation),
            bouton=("Voir la candidature", _url("/admin/beta")),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Alerte candidature bêta non envoyée : %s", e)
        return False


# ── Journal d'erreurs ─────────────────────────────────────────────────────────

def niveau_alerte(source: str, level: str) -> str:
    """Le navigateur choisit lui-même le niveau qu'il déclare : on ne le croit
    pas pour `critical`, sinon n'importe qui pourrait déclencher des mails."""
    if level == "critical" and source == "frontend":
        return "error"
    return level


async def apres_erreur(db, source: str, level: str, message: str,
                       location: str, empreinte: str) -> bool:
    """Applique la règle du niveau à une entrée qui vient d'être écrite.
    Retourne True si un mail est parti. Ne lève jamais."""
    try:
        niveau = niveau_alerte(source, level)
        if niveau == "critical":
            return await _critique(db, source, message, location, empreinte)
        if niveau == "error":
            return await _erreurs(db)
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning("Alerte journal non envoyée : %s", e)
        return False


async def _critique(db, source, message, location, empreinte) -> bool:
    maintenant = time.time()
    with _verrou:
        for fp, t in list(_critiques.items()):
            if maintenant - t >= ERROR_LOG_ALERT_COOLDOWN:
                del _critiques[fp]
        if empreinte in _critiques or len(_critiques) >= _MAX_CRITIQUES_HEURE:
            return False
        _critiques[empreinte] = maintenant
    extrait = message if len(message) <= 500 else message[:500] + "…"
    return await _envoyer(
        db, "[Précis] Erreur critique",
        f"Erreur critique ({source}, {location or 'lieu inconnu'}) :\n\n{extrait}\n\n"
        f"Ouvre /admin/logs pour le détail.",
        titre="Erreur critique",
        resume="Une erreur grave vient de se produire. Elle peut bloquer les "
               "clients : regarde-la dès que possible.",
        niveau="critique", bandeau="Journal",
        details=[("Source", source), ("Lieu", location or "inconnu")],
        citation=("Message", extrait),
        bouton=("Ouvrir le journal", _url("/admin/logs")),
    )


async def _erreurs(db) -> bool:
    global _dernier_mail_erreurs
    maintenant = time.time()
    with _verrou:
        precedent = _dernier_mail_erreurs
        if maintenant - precedent < ERROR_LOG_ALERT_COOLDOWN:
            return False
        _dernier_mail_erreurs = maintenant
    # Fenêtre : depuis le mail précédent, au plus une heure en arrière.
    depuis = datetime.fromtimestamp(
        max(precedent, maintenant - ERROR_LOG_ALERT_COOLDOWN), tz=timezone.utc)
    filtre = (ErrorLog.status == STATUS_NEW, ErrorLog.level != "warning",
              ErrorLog.created_at >= depuis)
    total = await db.scalar(select(func.count()).select_from(ErrorLog).where(*filtre)) or 0
    if not total:
        return False
    groupes = (await db.execute(
        select(func.min(ErrorLog.message), func.count())
        .where(*filtre).group_by(ErrorLog.fingerprint)
        .order_by(func.count().desc()).limit(3))).all()
    heure = depuis.strftime("%H h %M")
    pluriel = "s" if total > 1 else ""
    titre = f"{total} nouvelle{pluriel} erreur{pluriel} depuis {heure} (UTC)"
    details = [((msg or "")[:80], str(n)) for msg, n in groupes]
    return await _envoyer(
        db, f"[Précis] {titre}",
        titre + ".\n\n" + "\n".join(f"- {m} ({n})" for m, n in details)
        + "\n\nOuvre /admin/logs pour les traiter.",
        titre=titre,
        resume="Les erreurs les plus fréquentes sont listées ci-dessous. Tu ne "
               "recevras pas d'autre mail d'erreur avant une heure.",
        niveau="avertissement", bandeau="Journal", details=details,
        bouton=("Ouvrir le journal", _url("/admin/logs")),
    )


# ── Récapitulatif quotidien ───────────────────────────────────────────────────

def _mode(user: User) -> str:
    if user.google_id:
        return "Google"
    if user.password_hash:
        return "mot de passe"
    return "code par e-mail"


async def recapitulatif_quotidien(db, aujourd_hui=None) -> bool:
    """Envoie le récapitulatif de la veille (UTC), une seule fois par jour."""
    jour = (aujourd_hui or utcnow().date()) - timedelta(days=1)
    if await db.get(AdminRecap, jour):
        return False
    debut = datetime.combine(jour, dtime.min, tzinfo=timezone.utc)
    fin = debut + timedelta(days=1)
    comptes = (await db.execute(
        select(User).where(User.created_at >= debut, User.created_at < fin)
        .order_by(User.created_at))).scalars().all()
    avertissements = await db.scalar(
        select(func.count()).select_from(ErrorLog).where(
            ErrorLog.level == "warning",
            ErrorLog.created_at >= debut, ErrorLog.created_at < fin)) or 0

    # Le jour est marqué AVANT l'envoi : deux processus en même temps, un seul gagne.
    db.add(AdminRecap(jour=jour))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return False

    if not comptes and not avertissements:
        return False
    date_txt = jour.strftime("%d/%m/%Y")
    n = len(comptes)
    titre = (f"{n} nouveau{'x' if n > 1 else ''} compte{'s' if n > 1 else ''} le {date_txt}"
             if n else f"Récapitulatif du {date_txt}")
    lignes = [f"- {u.email} ({_mode(u)})" for u in comptes]
    details = [(u.email, _mode(u)) for u in comptes[:30]]
    if n > 30:
        details.append(("…", f"et {n - 30} autres"))
    details.append(("Avertissements du journal", str(avertissements)))
    try:
        return await _envoyer(
            db, f"[Précis] {titre}",
            titre + ".\n\n" + "\n".join(lignes)
            + f"\n\nAvertissements du journal : {avertissements}.",
            titre=titre,
            resume="Récapitulatif de la veille : comptes créés et nombre "
                   "d'avertissements du journal.",
            bandeau="Récapitulatif", details=details,
            bouton=("Voir les comptes", _url("/admin/users")),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Récapitulatif admin non envoyé : %s", e)
        return False
