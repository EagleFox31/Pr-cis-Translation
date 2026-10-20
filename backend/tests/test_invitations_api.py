"""`POST /api/invitations` : les garde-fous anti-abus, de bout en bout.

CE QUI EST VÉRIFIÉ
  1. ACCÈS     — un anonyme est refusé ; plus de 10 adresses, refusé.
  2. TRI       — soi-même, doublons de saisie, comptes existants : écartés,
                 sans que la réponse le révèle.
  3. DOUBLON   — une adresse déjà invitée récemment ne reçoit rien de plus.
  4. QUOTA     — au-delà du quota quotidien : 429, rien n'est envoyé.
  5. PANNE     — l'envoi (après la réponse) échoue : 200 quand même, et la
                 trace est effacée pour que l'adresse reste invitable.
  6. PURGE     — les traces de plus de 30 jours sont effacées.

L'envoi réel est remplacé par un enregistreur : aucun e-mail ne part.
Base PostgreSQL requise (DATABASE_URL). Si la migration 0010 n'est pas encore
appliquée, la table est créée pour le test puis supprimée — l'historique
Alembic n'est pas touché.

    backend/venv/Scripts/python.exe backend/tests/test_invitations_api.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi.testclient import TestClient                # noqa: E402
from sqlalchemy import delete, inspect, select           # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

import app.core.email as courriel                         # noqa: E402
import app.services.invitations as module                # noqa: E402
from app import create_app                               # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
from app.core.email import EmailIndisponible             # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app.models import Invitation, User                  # noqa: E402
from app.rate_limit import limiter                       # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)


def _adresse(prefixe="inv"):
    return f"{prefixe}-{uuid.uuid4().hex[:10]}@example.com"


async def _table_absente() -> bool:
    async with _eng.begin() as conn:
        present = await conn.run_sync(lambda c: inspect(c).has_table("invitations"))
        if not present:
            await conn.run_sync(lambda c: Invitation.__table__.create(c))
        return not present


async def _utilisateur(name=None):
    u = User(email=_adresse("hote"), name=name, email_verified=True)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    return u


async def _invitations(emails):
    async with async_session() as db:
        return (await db.scalars(select(Invitation).where(
            Invitation.email.in_(emails)))).all()


async def _remplir(user_id, n):
    async with async_session() as db:
        for _ in range(n):
            db.add(Invitation(inviter_id=user_id, email=_adresse("quota")))
        await db.commit()


async def _nettoyer(users, emails):
    async with async_session() as db:
        await db.execute(delete(Invitation).where(
            (Invitation.inviter_id.in_(users)) | (Invitation.email.in_(emails))))
        await db.execute(delete(User).where(User.id.in_(users)))
        await db.commit()


async def run():
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    envoyes: list[tuple] = []
    panne = {"active": False}

    async def faux_envoi(dest, inviteur, inviteur_email, message, langue):
        if panne["active"]:
            raise EmailIndisponible("panne simulée")
        envoyes.append((dest, inviteur, inviteur_email, message, langue))

    vrai_envoi = courriel.send_invitation_email
    courriel.send_invitation_email = faux_envoi
    creee = await _table_absente()
    hote = await _utilisateur(name="Yves")
    inscrit = await _utilisateur()
    nouveau, autre, autre2 = _adresse(), _adresse(), _adresse()
    users, emails = [hote.id, inscrit.id], [nouveau, autre, autre2]
    ent = {"Authorization": "Bearer " + create_access_token(hote.id, hote.email),
           "Accept-Language": "en-US,en;q=0.9"}

    try:
        with TestClient(create_app()) as client:
            def post(body, headers=ent):
                if limiter:
                    limiter.reset()
                return client.post("/api/invitations", json=body, headers=headers)

            # 1. Accès
            r = post({"emails": [nouveau]}, headers={})
            ok("ACCÈS   anonyme refusé", r.status_code in (401, 403), r.status_code)
            r = post({"emails": [_adresse() for _ in range(11)]})
            ok("ACCÈS   11 adresses → 422", r.status_code == 422, r.status_code)
            ok("ACCÈS   rien envoyé", not envoyes, envoyes)

            # 2. Tri
            r = post({"emails": [nouveau, nouveau.upper(), hote.email, inscrit.email],
                      "message": "  Essaie-le !  "})
            ok("TRI     200", r.status_code == 200, r.text)
            ok("TRI     réponse muette sur les comptes",
               r.json() == {"ok": True, "count": 2}, r.text)
            ok("TRI     un seul envoi, au nouveau", [e[0] for e in envoyes] == [nouveau], envoyes)
            ok("TRI     nom, e-mail, mot nettoyé, langue transmis",
               envoyes and envoyes[0][1:] == ("Yves", hote.email, "Essaie-le !", "en-US,en;q=0.9"),
               envoyes)
            ok("TRI     une trace pour le nouveau, aucune pour l'inscrit",
               [i.email for i in await _invitations([nouveau, inscrit.email])] == [nouveau])
            r = post({"emails": [hote.email]})
            ok("TRI     s'inviter soi-même → 422", r.status_code == 422, r.status_code)

            # 3. Doublon
            envoyes.clear()
            r = post({"emails": [nouveau]})
            ok("DOUBLON 200 mais rien envoyé", r.status_code == 200 and not envoyes, envoyes)
            ok("DOUBLON pas de seconde trace", len(await _invitations([nouveau])) == 1)

            # 4. Quota (1 déjà consommé + 18 = 19 ; il en reste 1)
            await _remplir(hote.id, 18)
            r = post({"emails": [autre, autre2]})
            ok("QUOTA   429 au-delà", r.status_code == 429, r.status_code)
            ok("QUOTA   rien envoyé", not envoyes, envoyes)

            # 5. Panne : la dernière invitation du quota échoue
            panne["active"] = True
            r = post({"emails": [autre]})
            ok("PANNE   200 (réponse muette)", r.status_code == 200, r.status_code)
            ok("PANNE   trace effacée après échec", not await _invitations([autre]))
            panne["active"] = False
            r = post({"emails": [autre]})
            ok("QUOTA   la dernière passe ensuite", r.status_code == 200 and envoyes, r.text)

            # 6. Purge : une trace de 31 jours part, une récente reste
            vieille, recente = _adresse("vieille"), _adresse("recente")
            emails += [vieille, recente]
            async with async_session() as db:
                db.add(Invitation(inviter_id=hote.id, email=vieille,
                                  created_at=datetime.now(timezone.utc) - timedelta(days=31)))
                db.add(Invitation(inviter_id=hote.id, email=recente))
                await db.commit()
            async with async_session() as db:
                n = await module.purger_invitations(db)
                await db.commit()
            ok("PURGE   > 30 j effacée", n >= 1 and not await _invitations([vieille]), n)
            ok("PURGE   récente gardée", len(await _invitations([recente])) == 1)
    finally:
        courriel.send_invitation_email = vrai_envoi
        await _nettoyer(users, emails)
        if creee:
            async with _eng.begin() as conn:
                await conn.run_sync(lambda c: Invitation.__table__.drop(c))
        await _eng.dispose()

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
