"""`/api/nouveautes` : à voir, vues, abonnement, désabonnement signé.

CE QUI EST VÉRIFIÉ
  1. LISTE      — publique, dans la langue demandée (repli sur le français).
  2. À VOIR     — jamais vu : accueil (phares) ; vu avant le dernier élément :
                  seulement les éléments postérieurs ; à jour : RIEN (mode nul,
                  liste vide), pour que le site n'affiche ni fenêtre ni pastille.
  3. VUES       — `POST /vues` pose la date, et `a-voir` devient vide.
  4. ABONNEMENT — `PUT` enregistre l'état, la date du consentement et la langue.
  5. DÉSABONNEMENT — jeton faux : 400 ; GET ne change rien ; POST un clic : 200
                  et compte désabonné.

Base PostgreSQL requise (DATABASE_URL, port 5433 en local).

    backend/.venv/Scripts/python.exe backend/tests/test_nouveautes_api.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi.testclient import TestClient                # noqa: E402
from sqlalchemy import delete                            # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app import create_app                               # noqa: E402
from app.content import nouveautes as catalogue          # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app.models import User                              # noqa: E402
from app.rate_limit import limiter                       # noqa: E402
from app.services.nouveautes import jeton_desabonnement  # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)


async def _compte(vues_le=None):
    u = User(email=f"nouv-{uuid.uuid4().hex[:10]}@example.com", email_verified=True,
             nouveautes_vues_le=vues_le)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    return u


async def _relire(user_id):
    async with async_session() as db:
        return await db.get(User, user_id)


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # Juste avant le dernier élément du catalogue : seuls les plus récents restent.
    dates = sorted({e["date"] for e in catalogue.FONCTIONNALITES})
    avant_dernier = datetime.fromisoformat(dates[-2]).replace(tzinfo=timezone.utc)
    attendus = [e["id"] for e in catalogue.FONCTIONNALITES if e["date"] > dates[-2]]

    neuf = await _compte()
    ancien = await _compte(avant_dernier)
    a_jour = await _compte(datetime.now(timezone.utc))
    users = [neuf.id, ancien.id, a_jour.id]

    def ent(u, lang=None):
        h = {"Authorization": "Bearer " + create_access_token(u.id, u.email)}
        if lang:
            h["Accept-Language"] = lang
        return h

    try:
        with TestClient(create_app()) as client:
            if limiter:
                limiter.reset()
            # 1. LISTE
            r = client.get("/api/nouveautes?lang=en")
            corps = r.json()
            ok("LISTE   publique", r.status_code == 200, r.status_code)
            ok("LISTE   19 éléments", len(corps.get("elements", [])) == 19)
            ok("LISTE   en anglais", corps["elements"][0]["titre"] ==
               catalogue.elements("en")[0]["titre"])
            ok("LISTE   version", corps.get("version") == catalogue.VERSION)

            # 2. À VOIR
            r = client.get("/api/nouveautes/a-voir")
            ok("A-VOIR  anonyme refusé", r.status_code in (401, 403), r.status_code)
            r = client.get("/api/nouveautes/a-voir", headers=ent(neuf)).json()
            ok("A-VOIR  jamais vu : accueil", r["mode"] == "accueil"
               and [e["id"] for e in r["elements"]] == [p["id"] for p in catalogue.phares("fr")], r)
            r = client.get("/api/nouveautes/a-voir", headers=ent(ancien)).json()
            ok("A-VOIR  depuis : éléments postérieurs seuls", r["mode"] == "depuis"
               and sorted(e["id"] for e in r["elements"]) == sorted(attendus), r)
            r = client.get("/api/nouveautes/a-voir", headers=ent(a_jour)).json()
            ok("A-VOIR  rien de neuf : rien à afficher",
               r == {"mode": None, "depuis": None, "elements": []}, r)

            # 3. VUES
            r = client.post("/api/nouveautes/vues", headers=ent(ancien))
            ok("VUES    200", r.status_code == 200, r.status_code)
            ok("VUES    date posée", (await _relire(ancien.id)).nouveautes_vues_le is not None)
            r = client.get("/api/nouveautes/a-voir", headers=ent(ancien)).json()
            ok("VUES    a-voir devient vide", r["mode"] is None and r["elements"] == [], r)
            me = client.get("/api/auth/me", headers=ent(ancien)).json()
            ok("ME      champs nouveautés", me.get("nouveautes_vues_le")
               and me.get("abonne_nouveautes") is False, me)

            # 4. ABONNEMENT
            r = client.put("/api/nouveautes/abonnement", json={"actif": True},
                           headers=ent(neuf, "en-US,en;q=0.9"))
            u = await _relire(neuf.id)
            ok("ABONNE  200", r.status_code == 200, r.status_code)
            ok("ABONNE  état + preuve", u.abonne_nouveautes and u.abonne_nouveautes_le)
            ok("ABONNE  langue de l'interface", u.langue == "en", u.langue)
            client.put("/api/nouveautes/abonnement", json={"actif": False},
                       headers=ent(neuf))
            u = await _relire(neuf.id)
            ok("ABONNE  retrait", not u.abonne_nouveautes and u.abonne_nouveautes_le is None)
            client.put("/api/nouveautes/abonnement", json={"actif": True}, headers=ent(neuf))

            # 5. DÉSABONNEMENT
            jeton = jeton_desabonnement(neuf.id)
            faux = neuf.id + "." + "x" * 43
            for j in (faux, "nimporte", "", jeton_desabonnement("inconnu")):
                r = client.post(f"/api/nouveautes/desabonnement?jeton={j}")
                ok(f"DESAB   jeton faux 400 ({j[:12]!r})", r.status_code == 400, r.status_code)
            r = client.get(f"/api/nouveautes/desabonnement?jeton={jeton}")
            ok("DESAB   GET lit sans changer", r.status_code == 200
               and r.json()["abonne_nouveautes"] is True
               and (await _relire(neuf.id)).abonne_nouveautes, r.text)
            r = client.post(f"/api/nouveautes/desabonnement?jeton={jeton}",
                            data={"List-Unsubscribe": "One-Click"})
            ok("DESAB   POST un clic 200", r.status_code == 200, r.status_code)
            ok("DESAB   compte désabonné", not (await _relire(neuf.id)).abonne_nouveautes)
    finally:
        async with async_session() as db:
            await db.execute(delete(User).where(User.id.in_(users)))
            await db.commit()
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
