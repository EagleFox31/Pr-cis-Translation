"""Envoi de l'e-mail de version aux abonnés : sélection, lots, reprise.

IDEMPOTENT
    Chaque envoi réservé dans `nouveautes_envois` (unique par compte et
    version) DANS la même transaction que l'envoi : si l'e-mail échoue, la
    réservation est annulée ; s'il part, elle est validée. Une relance saute
    donc tous ceux qui l'ont reçu, et deux lancements simultanés ne doublent
    personne (la contrainte unique refuse le second).

ÉTALÉ
    Spacemail limite les envois par jour : par lots, avec une pause entre deux.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.content import nouveautes as catalogue
from app.core.email import send_nouveautes_email
from app.models import NouveauteEnvoi, User
from app.services.nouveautes import jeton_desabonnement


def selection(lang: str, *, entrees: list[str] | None = None,
              depuis: str | None = None) -> list[dict]:
    """Éléments de l'e-mail : ids choisis, ou tous ceux datés après `depuis`."""
    tous = catalogue.elements(lang)
    if entrees:
        inconnus = set(entrees) - {e["id"] for e in tous}
        if inconnus:
            raise ValueError(f"Éléments inconnus : {', '.join(sorted(inconnus))}")
        return [e for e in tous if e["id"] in entrees]
    if depuis:
        return [e for e in tous if e["date"] > depuis]
    raise ValueError("Choisir les éléments : --entrees ou --depuis.")


async def destinataires(session_factory, version: str) -> list[tuple[str, str, str]]:
    """(id, e-mail, langue) des abonnés vérifiés qui n'ont pas encore reçu `version`."""
    deja = select(NouveauteEnvoi.user_id).where(NouveauteEnvoi.version == version)
    async with session_factory() as db:
        lignes = await db.execute(
            select(User.id, User.email, User.langue)
            .where(User.abonne_nouveautes.is_(True), User.email_verified.is_(True),
                   User.id.not_in(deja))
            .order_by(User.created_at))
        return [tuple(l) for l in lignes]


async def envoyer_version(session_factory, *, entrees: list[str] | None = None,
                          depuis: str | None = None, lot: int = 50,
                          pause: float = 60.0, version: str = catalogue.VERSION,
                          envoyer: Callable[..., Awaitable[None]] = send_nouveautes_email,
                          journal: Callable[[str], None] = print) -> int:
    """Envoie la version à chaque abonné qui ne l'a pas reçue ; renvoie le nombre envoyé."""
    par_langue = {l: selection(l, entrees=entrees, depuis=depuis) for l in catalogue.LANGUES}
    if not par_langue["fr"]:
        raise ValueError("Aucun élément sélectionné : rien à envoyer.")
    liste = await destinataires(session_factory, version)
    journal(f"{len(liste)} abonné(s) à servir pour la version {version}.")
    envoyes = 0
    for i, (user_id, email, langue) in enumerate(liste):
        if i and lot and i % lot == 0:
            journal(f"Lot terminé ({i}/{len(liste)}), pause {pause:g} s.")
            await asyncio.sleep(pause)
        langue = langue if langue in catalogue.LANGUES else "fr"
        async with session_factory() as db:
            db.add(NouveauteEnvoi(user_id=user_id, version=version))
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()          # reçu entre-temps (autre lancement)
                continue
            await envoyer(email, langue, par_langue[langue], version=version,
                          date_version=catalogue.DATE_VERSION,
                          jeton=jeton_desabonnement(user_id))
            await db.commit()
        envoyes += 1
    journal(f"{envoyes} e-mail(s) envoyé(s).")
    return envoyes


async def envoyer_essai(adresse: str, *, langue: str = "fr",
                        entrees: list[str] | None = None, depuis: str | None = None,
                        envoyer: Callable[..., Awaitable[None]] = send_nouveautes_email) -> None:
    """Un exemplaire à `adresse`, sans rien enregistrer (lien de désabonnement factice)."""
    await envoyer(adresse, langue, selection(langue, entrees=entrees, depuis=depuis),
                  version=catalogue.VERSION, date_version=catalogue.DATE_VERSION,
                  jeton=jeton_desabonnement("essai"))
