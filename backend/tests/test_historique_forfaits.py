"""Historique des forfaits — `plan_events` et `GET /api/admin/users/{id}/plan-history`.

Ce qui est MESURÉ :
  • un abonnement payé, puis son renouvellement anticipé, laissent chacun leur
    ligne (abonnement, renouvellement) avec mois et échéance ;
  • une échéance passée laisse une ligne « retour au Gratuit » datée de la fin
    réelle du plan, par le passage du compte comme par la liste d'administration ;
  • un plan attribué par l'administration laisse une ligne ; réattribuer le
    même plan sans échéance n'en ajoute pas ;
  • la route renvoie les lignes de la plus récente à la plus ancienne, finit par
    l'inscription (Gratuit) et compte abonnements / renouvellements ;
  • la route est réservée aux admins.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_historique_forfaits.py
PostgreSQL local requis, migration 0016.
"""
from __future__ import annotations
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

import racine  # noqa: F401  -- met backend/ sur le chemin

from sqlalchemy import select                            # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402

from app.core.database import DATABASE_URL               # noqa: E402
from app.models import Payment, PlanEvent, User          # noqa: E402
from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app.api.payments import _apply_credit               # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)


async def _utilisateur(plan="free", expires=None):
    u = User(email=f"hist-{uuid.uuid4().hex[:10]}@example.com", plan=plan,
             plan_expires_at=expires, email_verified=True)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    return u


async def _crediter(user_id, plan, months):
    async with async_session() as db:
        p = Payment(user_id=user_id, pages=0, amount=1, currency="XAF", zone="A",
                    status="SUCCESSFUL", provider="campay", plan=plan, months=months,
                    provider_ref="ref-" + uuid.uuid4().hex)
        db.add(p)
        await db.commit()
        await _apply_credit(db, await db.get(Payment, p.id))


async def _evenements(user_id):
    async with async_session() as db:
        return (await db.execute(select(PlanEvent).where(PlanEvent.user_id == user_id)
                                 .order_by(PlanEvent.created_at))).scalars().all()


async def _supprimer(ids):
    async with async_session() as db:
        for uid in ids:
            for model in (PlanEvent, Payment):
                for r in (await db.execute(select(model).where(model.user_id == uid))).scalars():
                    await db.delete(r)
            obj = await db.get(User, uid)
            if obj:
                await db.delete(obj)
        await db.commit()


def ent(u):
    return {"X-API-Key": cfg.FRONTEND_API_KEY,
            "Authorization": "Bearer " + create_access_token(u.id, u.email)}


async def check_routes(client, ok, a_nettoyer):
    adm = await _utilisateur(plan="admin")
    a_nettoyer.append(adm.id)

    # Abonnement puis renouvellement anticipé du même plan.
    x = await _utilisateur()
    a_nettoyer.append(x.id)
    await _crediter(x.id, "starter", 1)
    await _crediter(x.id, "starter", 12)
    ev = await _evenements(x.id)
    ok("PAIEMENT abonnement puis renouvellement tracés",
       [(e.kind, e.plan, e.months) for e in ev]
       == [("subscription", "starter", 1), ("renewal", "starter", 12)]
       and all(e.payment_id and e.expires_at for e in ev),
       f"{[(e.kind, e.plan, e.months) for e in ev]}")

    # Échéance constatée par le passage du compte.
    fin = datetime.now(timezone.utc) - timedelta(days=3)
    y = await _utilisateur(plan="pro", expires=fin)
    a_nettoyer.append(y.id)
    client.get("/api/auth/me", headers=ent(y))
    ev = await _evenements(y.id)
    ok("ECHEANCE retour au Gratuit daté de la fin réelle (passage du compte)",
       len(ev) == 1 and ev[0].kind == "expiry" and ev[0].plan == "free"
       and abs(ev[0].created_at - fin) < timedelta(seconds=1),
       f"{[(e.kind, e.created_at) for e in ev]}")
    client.get("/api/auth/me", headers=ent(y))
    ok("ECHEANCE pas de doublon au passage suivant", len(await _evenements(y.id)) == 1)

    # Échéance constatée par la liste d'administration.
    z = await _utilisateur(plan="starter", expires=fin)
    a_nettoyer.append(z.id)
    client.get("/api/admin/users", params={"q": z.email}, headers=ent(adm))
    ev = await _evenements(z.id)
    ok("ECHEANCE retour au Gratuit tracé par la liste d'administration",
       [e.kind for e in ev] == ["expiry"], f"{[e.kind for e in ev]}")

    # Attribution par l'administration.
    r1 = client.post(f"/api/admin/users/{x.id}/plan", json={"plan": "pro"}, headers=ent(adm))
    r2 = client.post(f"/api/admin/users/{x.id}/plan", json={"plan": "pro"}, headers=ent(adm))
    ev = await _evenements(x.id)
    ok("ADMIN   attribution tracée, réattribution identique ignorée",
       r1.status_code == 200 and r2.status_code == 200
       and [e.kind for e in ev] == ["subscription", "renewal", "admin"] and ev[-1].plan == "pro",
       f"{[e.kind for e in ev]}")

    # Route d'historique.
    r = client.get(f"/api/admin/users/{x.id}/plan-history", headers=ent(adm))
    body = r.json() if r.status_code == 200 else {}
    kinds = [i["kind"] for i in body.get("items", [])]
    ok("ROUTE   lignes récentes d'abord, inscription en dernier",
       kinds == ["admin", "renewal", "subscription", "signup"], f"{r.status_code} {kinds}")
    ok("ROUTE   totaux : 3 abonnements (Gratuit compris), 1 renouvellement",
       body.get("subscriptions") == 3 and body.get("renewals") == 1
       and body.get("expiries") == 0, f"{ {k: body.get(k) for k in ('subscriptions', 'renewals', 'expiries')} }")
    r = client.get(f"/api/admin/users/{x.id}/plan-history", headers=ent(x))
    ok("ROUTE   réservée aux admins", r.status_code == 403, f"{r.status_code}")
    r = client.get(f"/api/admin/users/{uuid.uuid4().hex}/plan-history", headers=ent(adm))
    ok("ROUTE   compte inconnu : 404", r.status_code == 404, f"{r.status_code}")


async def run():
    checks, a_nettoyer = [], []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    try:
        with TestClient(create_app()) as client:
            await check_routes(client, ok, a_nettoyer)
    finally:
        await _supprimer(a_nettoyer)

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
