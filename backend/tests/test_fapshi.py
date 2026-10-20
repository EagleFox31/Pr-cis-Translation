"""
Prestataire Fapshi : client HTTP, statuts, webhook.

Aucun appel réseau : le transport httpx est simulé (voir [[tests-sans-api]]).

  • le client parle le format de la doc (en-têtes apiuser/apikey, numéro sans
    indicatif, montant entier, externalId = notre identifiant) ;
  • toute panne (4XX, timeout) devient une `ProviderError`, jamais un 500 ;
  • CREATED/PENDING → PENDING, EXPIRED → FAILED ;
  • l'interrogation d'état respecte la limite de 6/min par transaction ;
  • le webhook exige `x-wh-secret` et ne croit JAMAIS son corps ;
  • un encaissement ne crédite qu'une fois, webhook et interrogation confondus.

Lancer : python tests/test_fapshi.py
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

import httpx                                             # noqa: E402
from sqlalchemy import select                            # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession)
from sqlalchemy.pool import NullPool                     # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402

from app.core.database import DATABASE_URL               # noqa: E402
from app.models import User, Payment                     # noqa: E402
from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app.core import payment_gateway as pg               # noqa: E402
from app.core.payment_gateway import fapshi, FapshiClient, ProviderError  # noqa: E402
from app.core.payment_methods import PROVIDERS           # noqa: E402

engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SECRET = "secret-de-test-" + uuid.uuid4().hex


class _FauxFapshi:
    """Remplace le transport httpx du module : enregistre les requêtes et
    répond selon `self.reponse(request)`."""

    def __init__(self, reponse):
        self.reponse, self.requetes = reponse, []

    def __enter__(self):
        self.vrai = pg.httpx.AsyncClient

        def fabrique(*a, **kw):
            def gerer(req):
                self.requetes.append(req)
                return self.reponse(req)
            kw["transport"] = httpx.MockTransport(gerer)
            return self.vrai(*a, **kw)
        pg.httpx.AsyncClient = fabrique
        # Indépendant du .env local, qui peut viser le live.
        self.ident = (fapshi.api_user, fapshi.api_key, fapshi.host)
        fapshi.api_user, fapshi.api_key = "user-test", "cle-test"
        fapshi.host = pg.FAPSHI_SANDBOX_HOST
        fapshi._last_status.clear()
        return self

    def __exit__(self, *exc):
        pg.httpx.AsyncClient = self.vrai
        fapshi.api_user, fapshi.api_key, fapshi.host = self.ident
        fapshi._last_status.clear()


def _json(status, corps):
    return lambda req: httpx.Response(status, json=corps)


async def check_client(ok):
    with _FauxFapshi(_json(200, {"message": "ok", "transId": "T123",
                                 "dateInitiated": "2026-10-20"})) as f:
        res = await fapshi.direct_pay(amount=200, phone="237670000000",
                                      message="Precis", external_id="pay-1")
        req = f.requetes[0]
        corps = json.loads(req.content)
        ok("CLIENT  direct-pay : URL sandbox, en-tetes, numero sans indicatif",
           res["transId"] == "T123"
           and str(req.url) == "https://sandbox.fapshi.com/direct-pay"
           and req.headers.get("apiuser") == "user-test"
           and req.headers.get("apikey") == "cle-test"
           and corps == {"amount": 200, "phone": "670000000",
                         "message": "Precis", "externalId": "pay-1"}, str(corps))

    with _FauxFapshi(_json(200, {"message": "ok", "transId": "T456",
                                 "link": "https://checkout.fapshi.com/link/abc"})) as f:
        res = await fapshi.initiate_pay(amount=300, message="Precis",
                                        external_id="pay-2")
        req = f.requetes[0]
        ok("CLIENT  initiate-pay : URL, corps sans numero, lien rendu",
           res["link"].endswith("/abc") and req.url.path == "/initiate-pay"
           and json.loads(req.content) == {"amount": 300, "message": "Precis",
                                           "externalId": "pay-2"},
           str(req.content))

    with _FauxFapshi(_json(200, {"message": "ok", "transId": "T457"})):
        try:
            await fapshi.initiate_pay(amount=300, message="x", external_id="p")
            err = None
        except ProviderError as e:
            err = e
        ok("CLIENT  initiate-pay sans lien : ProviderError", err is not None)

    with _FauxFapshi(_json(400, {"message": "Invalid phone number"})):
        try:
            await fapshi.direct_pay(amount=200, phone="620000000", message="x",
                                    external_id="p")
            err = None
        except ProviderError as e:
            err = e
        ok("CLIENT  400 numero : ProviderError avec conseil utilisateur",
           err is not None and "MTN" in err.user_message, repr(err))

    def timeout(req):
        raise httpx.ReadTimeout("lent", request=req)
    with _FauxFapshi(timeout):
        try:
            await fapshi.payment_status("T1")
            err = None
        except ProviderError as e:
            err = e
        ok("CLIENT  timeout : ProviderError, pas d'exception brute", err is not None)

    statuts = iter(["CREATED", "PENDING", "SUCCESSFUL", "SUCCESSFUL"])
    with _FauxFapshi(lambda req: httpx.Response(
            200, json={"transId": "T9", "status": next(statuts)})) as f:
        p = PROVIDERS["fapshi"]

        def vieillir():
            fapshi._last_status["T9"] = (0.0, fapshi._last_status["T9"][1])
        s1 = await p.status("T9")
        s2 = await p.status("T9")          # dans l'intervalle : cache
        vieillir()
        s3 = await p.status("T9")
        vieillir()
        s4 = await p.status("T9")
        s5 = await p.status("T9")          # final : jamais mis en cache
        ok("CLIENT  CREATED->PENDING, cache sous la limite 6/min, final non cache",
           [s1, s2, s3, s4, s5] == ["PENDING"] * 3 + ["SUCCESSFUL"] * 2
           and len(f.requetes) == 4, f"{[s1, s2, s3, s4, s5]} appels={len(f.requetes)}")

    with _FauxFapshi(_json(200, {"transId": "TE", "status": "EXPIRED"})):
        ok("CLIENT  EXPIRED -> FAILED", await PROVIDERS["fapshi"].status("TE") == "FAILED")

    sauve = os.environ.get("FAPSHI_ENV")
    os.environ["FAPSHI_ENV"] = "live"
    live = FapshiClient().host
    os.environ["FAPSHI_ENV"] = "PROD"
    autre = FapshiClient().host
    if sauve is None:
        os.environ.pop("FAPSHI_ENV")
    else:
        os.environ["FAPSHI_ENV"] = sauve
    ok("CLIENT  live seulement sur FAPSHI_ENV=LIVE",
       live == pg.FAPSHI_LIVE_HOST and autre == pg.FAPSHI_SANDBOX_HOST)

    sauve = os.environ.pop("FAPSHI_WEBHOOK_SECRET", None)
    sans = FapshiClient.verify_webhook_secret("n'importe")
    os.environ["FAPSHI_WEBHOOK_SECRET"] = SECRET
    ok("CLIENT  secret webhook : absent, faux, vide refuses ; bon accepte",
       not sans and not FapshiClient.verify_webhook_secret("faux")
       and not FapshiClient.verify_webhook_secret("")
       and FapshiClient.verify_webhook_secret(SECRET))
    if sauve is not None:
        os.environ["FAPSHI_WEBHOOK_SECRET"] = sauve


async def _utilisateur():
    u = User(email=f"fapshi-{uuid.uuid4().hex[:10]}@example.com",
             plan="free", email_verified=True, page_credits=0)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    return u


async def _supprimer(user_id):
    async with async_session() as db:
        for p in (await db.execute(select(Payment).where(
                Payment.user_id == user_id))).scalars():
            await db.delete(p)
        obj = await db.get(User, user_id)
        if obj:
            await db.delete(obj)
        await db.commit()


async def _supprimer_paiements(user_id):
    async with async_session() as db:
        for p in (await db.execute(select(Payment).where(
                Payment.user_id == user_id))).scalars():
            await db.delete(p)
        await db.commit()


async def _etat(user_id):
    async with async_session() as db:
        ps = (await db.execute(select(Payment).where(
            Payment.user_id == user_id))).scalars().all()
        return ps, (await db.get(User, user_id)).page_credits


async def check_routes(client, ok):
    u = await _utilisateur()
    trans = "T" + uuid.uuid4().hex[:12]
    etat = {"status": "PENDING"}

    def reponse(req):
        if req.url.path == "/direct-pay":
            return httpx.Response(200, json={"transId": trans, "message": "ok"})
        # Le corps du webhook ment ; seule cette réponse fait foi.
        return httpx.Response(200, json={"transId": trans, "status": etat["status"]})

    ent = {"X-API-Key": cfg.FRONTEND_API_KEY, "X-Country": "CM",
           "Authorization": "Bearer " + create_access_token(u.id, u.email)}
    hook = "/api/payments/fapshi/webhook"
    menteur = {"transId": trans, "status": "SUCCESSFUL"}
    sauve_env = {k: os.environ.get(k) for k in ("PAYMENT_METHODS", "FAPSHI_WEBHOOK_SECRET", "FAPSHI_FLOW")}
    os.environ["PAYMENT_METHODS"] = "mtn_momo=fapshi,orange_money=fapshi,card="
    os.environ["FAPSHI_WEBHOOK_SECRET"] = SECRET
    try:
        os.environ["FAPSHI_FLOW"] = "checkout"
        with _FauxFapshi(lambda req: httpx.Response(200, json={
                "transId": "C" + trans, "link": "https://checkout.fapshi.com/x"})) as f:
            r = client.post("/api/payments/collect",
                            json={"pages": 2, "method": "orange_money",
                                  "phone": "690000000"}, headers=ent)
            ps, _ = await _etat(u.id)
            ok("ROUTE   parcours checkout : lien rendu, transId note, pas de direct-pay",
               r.status_code == 200
               and r.json().get("checkout_url") == "https://checkout.fapshi.com/x"
               and [q.url.path for q in f.requetes] == ["/initiate-pay"]
               and len(ps) == 1 and ps[0].provider_ref == "C" + trans,
               f"{r.status_code} {r.text[:120]}")
            corps = json.loads(f.requetes[0].content) if f.requetes else {}
            ok("ROUTE   parcours checkout : e-mail du compte pre-rempli",
               corps.get("email") == u.email and corps.get("userId") == u.id,
               str(corps))
            m = client.get("/api/payments/methods", headers=ent).json()["methods"]
            ok("ROUTE   parcours checkout : numero non demande chez nous",
               all(not x["needs_phone"] for x in m), str(m))
        await _supprimer_paiements(u.id)
        with _FauxFapshi(lambda req: httpx.Response(200, json={
                "transId": "D" + trans, "link": "https://checkout.fapshi.com/y"})) as f:
            r = client.post("/api/payments/collect",
                            json={"pages": 2, "method": "mtn_momo"}, headers=ent)
            ok("ROUTE   parcours checkout : paiement lance sans numero",
               r.status_code == 200 and r.json().get("checkout_url") == "https://checkout.fapshi.com/y",
               f"{r.status_code} {r.text[:120]}")
        await _supprimer_paiements(u.id)

        # FAPSHI_FLOW absent : le parcours direct est celui par defaut.
        os.environ.pop("FAPSHI_FLOW", None)
        m = client.get("/api/payments/methods", headers=ent).json()["methods"]
        r = client.post("/api/payments/collect",
                        json={"pages": 2, "method": "mtn_momo"}, headers=ent)
        ok("ROUTE   parcours direct par defaut : numero exige (methods + 422)",
           {x["id"]: x["needs_phone"] for x in m}.get("mtn_momo") is True
           and r.status_code == 422, f"{r.status_code} {m}")
        with _FauxFapshi(reponse) as f:
            r = client.post("/api/payments/collect",
                            json={"pages": 2, "method": "mtn_momo",
                                  "phone": "670000000"}, headers=ent)
            ps, _ = await _etat(u.id)
            ok("ROUTE   /collect : Fapshi appele, transId note comme reference",
               r.status_code == 200 and len(ps) == 1 and ps[0].provider == "fapshi"
               and ps[0].provider_ref == trans
               and json.loads(f.requetes[0].content)["externalId"] == ps[0].id,
               f"{r.status_code} {r.text[:120]}")

            r1 = client.post(hook, json=menteur)
            r2 = client.post(hook, json=menteur, headers={"x-wh-secret": "faux"})
            ps, solde = await _etat(u.id)
            ok("ROUTE   webhook sans secret / faux secret : 403, rien credite",
               r1.status_code == 403 and r2.status_code == 403 and solde == 0
               and ps[0].status == "PENDING", f"{r1.status_code} {r2.status_code}")

            r = client.post(hook, json=menteur, headers={"x-wh-secret": SECRET})
            ps, solde = await _etat(u.id)
            ok("ROUTE   webhook qui ment (API dit PENDING) : rien credite",
               r.status_code == 200 and ps[0].status == "PENDING" and solde == 0,
               f"{ps[0].status} solde={solde}")

            # Le PENDING ci-dessus est en cache : le webhook doit passer outre.
            etat["status"] = "SUCCESSFUL"
            r = client.post(hook, json=menteur, headers={"x-wh-secret": SECRET})
            client.post(hook, json=menteur, headers={"x-wh-secret": SECRET})
            client.get(f"/api/payments/{ps[0].id}", headers=ent)
            ps, solde = await _etat(u.id)
            ok("ROUTE   webhook confirme : credite UNE fois (webhook x2 + interrogation)",
               r.status_code == 200 and ps[0].status == "SUCCESSFUL"
               and ps[0].credited and solde == ps[0].pages,
               f"{ps[0].status} solde={solde} pages={ps[0].pages}")
    finally:
        for k, v in sauve_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        await _supprimer(u.id)


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    await check_client(ok)
    with TestClient(create_app()) as client:
        await check_routes(client, ok)

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
