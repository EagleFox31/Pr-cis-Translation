"""
Prestataire Paddle (carte) : client HTTP, conversion XAF → EUR, webhook signé.

Aucun appel réseau : le transport httpx est simulé (voir [[tests-sans-api]]).

  • le client envoie un prix non-catalogue rattaché à PADDLE_PRODUCT_ID, taxes
    comprises, avec notre identifiant dans `custom_data` ;
  • le franc CFA part en centimes d'euro, arrondis au centime supérieur ;
  • toute panne (4XX, timeout, transaction sans lien) devient une `ProviderError` ;
  • paid/completed → SUCCESSFUL, canceled → FAILED, le reste → PENDING ;
  • la signature `Paddle-Signature` est vérifiée sur le corps brut, fraîche ;
  • le webhook ne croit JAMAIS son corps et ne crédite qu'une fois.

Lancer : python tests/test_paddle.py
"""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
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
from app.core.payment_gateway import (paddle, PaddleClient, ProviderError,  # noqa: E402
                                      paddle_amount)
from app.core.payment_methods import PROVIDERS, provider_for  # noqa: E402
from app.core.pricing import (ZONE_AFRICA, card_fee, plan_price,  # noqa: E402
                              transaction_fee)

engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SECRET = "pdl_ntfset_test_" + uuid.uuid4().hex
LIEN = "https://precis.test/paiement/carte"


class _FauxPaddle:
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
        self.ident = (paddle.api_key, paddle.product_id, paddle.host)
        paddle.api_key, paddle.product_id = "pdl_sdbx_apikey_test", "pro_test"
        paddle.host = pg.PADDLE_SANDBOX_HOST
        return self

    def __exit__(self, *exc):
        pg.httpx.AsyncClient = self.vrai
        paddle.api_key, paddle.product_id, paddle.host = self.ident


def _txn(txn_id, status="ready", url=LIEN):
    data = {"id": txn_id, "status": status,
            "checkout": {"url": f"{url}?_ptxn={txn_id}" if url else None}}
    return {"data": data, "meta": {"request_id": "r"}}


def _signer(corps: bytes, ts: int | None = None, secret: str = SECRET) -> str:
    ts = int(time.time()) if ts is None else ts
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + corps, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


async def check_client(ok):
    ok("CONVERSION  XAF -> centimes d'euro, arrondi superieur",
       paddle_amount(656, "XAF") == (101, "EUR")       # 1,0001 € → 1,01 €
       and paddle_amount(655957, "XAF") == (100000, "EUR")   # parité exacte
       and paddle_amount(100, "XAF") == (16, "EUR")
       and paddle_amount(499, "USD") == (499, "USD")
       and paddle_amount(1200, "EUR") == (1200, "EUR"),
       str([paddle_amount(656, "XAF"), paddle_amount(100, "XAF")]))

    with _FauxPaddle(lambda req: httpx.Response(201, json=_txn("txn_1"))) as f:
        data = await paddle.create_transaction(amount=1312, currency="XAF",
                                               description="Precis", reference="pay-1",
                                               user_id="u-1")
        req = f.requetes[0]
        corps = json.loads(req.content)
        prix = corps["items"][0]["price"]
        ok("CLIENT  transaction : URL sandbox, Bearer, prix non-catalogue en EUR",
           data["id"] == "txn_1"
           and str(req.url) == "https://sandbox-api.paddle.com/transactions"
           and req.headers.get("authorization") == "Bearer pdl_sdbx_apikey_test"
           and corps["items"][0]["quantity"] == 1
           and prix["product_id"] == "pro_test" and prix["tax_mode"] == "internal"
           and prix["unit_price"] == {"amount": "201", "currency_code": "EUR"}
           and corps["currency_code"] == "EUR"
           and corps["custom_data"] == {"payment_id": "pay-1", "user_id": "u-1"},
           str(corps))

    async def erreur(reponse, **kw):
        with _FauxPaddle(reponse):
            try:
                await paddle.create_transaction(amount=500, currency="EUR",
                                                description="x", reference="p", **kw)
            except ProviderError as e:
                return e
        return None

    ok("CLIENT  transaction sans checkout.url : ProviderError",
       await erreur(lambda req: httpx.Response(201, json=_txn("txn_2", url=None))) is not None)
    e = await erreur(lambda req: httpx.Response(
        400, json={"error": {"code": "bad_request", "detail": "invalid"}}))
    ok("CLIENT  400 : ProviderError avec le code Paddle",
       e is not None and "bad_request" in str(e), repr(e))

    def timeout(req):
        raise httpx.ReadTimeout("lent", request=req)
    ok("CLIENT  timeout : ProviderError, pas d'exception brute",
       await erreur(timeout) is not None)

    sauve = (paddle.api_key, paddle.product_id)
    paddle.api_key, paddle.product_id = "cle", ""
    ok("CLIENT  sans PADDLE_PRODUCT_ID : non configure", not paddle.configured)
    paddle.api_key, paddle.product_id = sauve

    statuts = {"txn_a": "billed", "txn_b": "paid", "txn_c": "completed",
               "txn_d": "canceled", "txn_e": "inconnu"}
    with _FauxPaddle(lambda req: httpx.Response(200, json=_txn(
            req.url.path.rsplit("/", 1)[-1], statuts[req.url.path.rsplit("/", 1)[-1]]))):
        p = PROVIDERS["paddle"]
        lus = [await p.status(t) for t in statuts]
    ok("CLIENT  billed/inconnu->PENDING, paid/completed->SUCCESSFUL, canceled->FAILED",
       lus == ["PENDING", "SUCCESSFUL", "SUCCESSFUL", "FAILED", "PENDING"], str(lus))

    sauve = os.environ.get("PADDLE_ENV")
    os.environ["PADDLE_ENV"] = "live"
    live = PaddleClient().host
    os.environ["PADDLE_ENV"] = "PROD"
    autre = PaddleClient().host
    if sauve is None:
        os.environ.pop("PADDLE_ENV")
    else:
        os.environ["PADDLE_ENV"] = sauve
    ok("CLIENT  live seulement sur PADDLE_ENV=LIVE",
       live == pg.PADDLE_LIVE_HOST and autre == pg.PADDLE_SANDBOX_HOST)

    corps = b'{"event_type":"transaction.paid","data":{"id":"txn_1"}}'
    maintenant = int(time.time())
    sauve = os.environ.pop("PADDLE_WEBHOOK_SECRET", None)
    sans = PaddleClient.verify_webhook_signature(_signer(corps), corps)
    os.environ["PADDLE_WEBHOOK_SECRET"] = SECRET
    v = PaddleClient.verify_webhook_signature
    bonne = _signer(corps)
    rotation = f"ts={maintenant};h1={'0' * 64};h1={bonne.split('h1=')[1]}"
    ok("SIGNATURE  absente, secret absent, faux secret, corps modifie : refuses",
       not sans and not v(None, corps) and not v("", corps)
       and not v(_signer(corps, secret="autre"), corps)
       and not v(bonne, corps + b" ") and not v("ts=abc;h1=00", corps))
    ok("SIGNATURE  bonne acceptee, y compris parmi plusieurs h1 (rotation)",
       v(bonne, corps) and v(rotation, corps))
    ok("SIGNATURE  perimee (ou datee du futur) refusee",
       not v(_signer(corps, maintenant - pg.PADDLE_WEBHOOK_MAX_AGE - 5), corps)
       and not v(_signer(corps, maintenant + pg.PADDLE_WEBHOOK_MAX_AGE + 5), corps))
    if sauve is None:
        os.environ.pop("PADDLE_WEBHOOK_SECRET")
    else:
        os.environ["PADDLE_WEBHOOK_SECRET"] = sauve


async def _utilisateur():
    u = User(email=f"paddle-{uuid.uuid4().hex[:10]}@example.com",
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


async def _etat(user_id):
    async with async_session() as db:
        ps = (await db.execute(select(Payment).where(
            Payment.user_id == user_id))).scalars().all()
        return ps, (await db.get(User, user_id)).page_credits


async def check_routes(client, ok):
    u = await _utilisateur()
    txn = "txn_" + uuid.uuid4().hex[:20]
    etat = {"status": "ready"}

    def reponse(req):
        if req.method == "POST":
            # Une transaction neuve par création : la première est `txn`.
            neuve = txn if not etat.get("cree") else "txn_" + uuid.uuid4().hex[:20]
            etat["cree"] = True
            return httpx.Response(201, json=_txn(neuve))
        # Le corps du webhook ment ; seule cette réponse fait foi.
        return httpx.Response(200, json=_txn(req.url.path.rsplit("/", 1)[-1],
                                             etat["status"]))

    ent = {"X-API-Key": cfg.FRONTEND_API_KEY, "X-Country": "CM",
           "Authorization": "Bearer " + create_access_token(u.id, u.email)}
    hook = "/api/payments/paddle/webhook"
    menteur = json.dumps({"event_type": "transaction.completed",
                          "data": {"id": txn, "status": "completed"}}).encode()

    def poster(corps, signature=None):
        h = {"content-type": "application/json"}
        if signature:
            h["paddle-signature"] = signature
        return client.post(hook, content=corps, headers=h)

    sauve_env = {k: os.environ.get(k) for k in ("PAYMENT_METHODS", "PADDLE_WEBHOOK_SECRET",
                                     "PADDLE_CHECKOUT_URL")}
    os.environ["PADDLE_WEBHOOK_SECRET"] = SECRET
    try:
        os.environ["PAYMENT_METHODS"] = "mtn_momo=fapshi,orange_money=fapshi,card=paddle"
        os.environ.pop("PADDLE_CHECKOUT_URL", None)
        with _FauxPaddle(reponse) as f:
            m = client.get("/api/payments/methods", headers=ent).json()["methods"]
            carte = {x["id"]: x for x in m}["card"]
            ok("ROUTE   carte ouverte en zone XAF, sans numero",
               carte["available"] and not carte["needs_phone"], str(carte))
            ok("ROUTE   card=paddle refuse pour un moyen mobile (routage errone)",
               provider_for("mtn_momo", "XAF")[0] is not PROVIDERS["paddle"])

            r = client.post("/api/payments/collect",
                            json={"pages": 2, "method": "card"}, headers=ent)
            ps, _ = await _etat(u.id)
            corps = json.loads(f.requetes[-1].content) if f.requetes else {}
            prix = (corps.get("items") or [{}])[0].get("price", {})
            attendu = paddle_amount(ps[0].amount, "XAF")[0] if ps else None
            ok("ROUTE   /collect carte : lien Paddle rendu, txn note, montant converti",
               r.status_code == 200
               and r.json().get("checkout_url") == f"{LIEN}?_ptxn={txn}"
               and len(ps) == 1 and ps[0].provider == "paddle"
               and ps[0].provider_ref == txn and ps[0].currency == "XAF"
               and prix.get("unit_price") == {"amount": str(attendu), "currency_code": "EUR"}
               and corps.get("custom_data", {}).get("payment_id") == ps[0].id,
               f"{r.status_code} {r.text[:120]} {prix}")

            r1 = poster(menteur)
            r2 = poster(menteur, _signer(menteur, secret="faux"))
            r3 = poster(menteur, _signer(menteur, int(time.time()) - 3600))
            ps, solde = await _etat(u.id)
            ok("ROUTE   webhook non signe / faux / perime : 403, rien credite",
               (r1.status_code, r2.status_code, r3.status_code) == (403, 403, 403)
               and solde == 0 and ps[0].status == "PENDING",
               f"{r1.status_code} {r2.status_code} {r3.status_code}")

            autre = json.dumps({"event_type": "customer.created",
                                "data": {"id": "ctm_1"}}).encode()
            r = poster(autre, _signer(autre))
            ok("ROUTE   webhook hors transaction : 200, ignore", r.status_code == 200)

            r = poster(menteur, _signer(menteur))
            ps, solde = await _etat(u.id)
            ok("ROUTE   webhook qui ment (API dit ready) : rien credite",
               r.status_code == 200 and ps[0].status == "PENDING" and solde == 0,
               f"{r.status_code} {ps[0].status} solde={solde}")

            etat["status"] = "paid"
            r = poster(menteur, _signer(menteur))
            poster(menteur, _signer(menteur))
            client.get(f"/api/payments/{ps[0].id}", headers=ent)
            ps, solde = await _etat(u.id)
            ok("ROUTE   webhook confirme : credite UNE fois (webhook x2 + interrogation)",
               r.status_code == 200 and ps[0].status == "SUCCESSFUL"
               and ps[0].credited and solde == ps[0].pages,
               f"{ps[0].status} solde={solde} pages={ps[0].pages}")

            etat["status"] = "ready"
            achat = {"plan": "starter", "annual": True, "method": "card"}
            avant = len([q for q in f.requetes if q.method == "POST"])
            r1 = client.post("/api/payments/plan", json=achat, headers=ent)
            r2 = client.post("/api/payments/plan", json=achat, headers=ent)
            crees = len([q for q in f.requetes if q.method == "POST"]) - avant
            ok("ROUTE   forfait carte rouvert apres fermeture : meme paiement, pas de 409",
               r1.status_code == r2.status_code == 200 and crees == 1
               and r1.json()["payment_id"] == r2.json()["payment_id"]
               and r2.json().get("checkout_url") == r1.json().get("checkout_url"),
               f"{r1.status_code} {r2.status_code} {r2.text[:120]} crees={crees}")
            # Starter annuel zone A : 12 × 1 200 F nets + frais carte (5 % + 309 F).
            net = 12 * plan_price("starter", ZONE_AFRICA, annual=True)
            q = client.post("/api/payments/plan/quote", json=achat, headers=ent).json()
            ok("ROUTE   forfait carte : frais carte au devis ET a l'encaissement",
               q.get("card", {}).get("amount") == net + card_fee(net, "XAF")
               == r1.json().get("amount")
               and q.get("amount") == net + transaction_fee(net),
               f"{q} {r1.json().get('amount')}")
            r3 =client.post("/api/payments/plan", json={**achat, "annual": False},
                             headers=ent)
            ok("ROUTE   autre offre par carte : nouveau paiement, pas de 409",
               r3.status_code == 200 and r3.json()["payment_id"] != r1.json()["payment_id"],
               f"{r3.status_code} {r3.text[:120]}")
    finally:
        for k, v in sauve_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        await _supprimer(u.id)


async def check_lien_local(ok):
    """PADDLE_CHECKOUT_URL remplace le lien Paddle (localhost refusé chez eux)."""
    prov = PROVIDERS["paddle"]
    orig = paddle.create_transaction
    sauve = os.environ.get("PADDLE_CHECKOUT_URL")

    async def faux(**_k):
        return {"id": "txn_local", "checkout": {"url": f"{LIEN}?_ptxn=txn_local"}}
    paddle.create_transaction = faux
    try:
        os.environ.pop("PADDLE_CHECKOUT_URL", None)
        a = await prov.start(amount=500, currency="XAF", phone=None,
                             description="d", reference="r")
        os.environ["PADDLE_CHECKOUT_URL"] = "http://localhost:3000/paiement/carte"
        b = await prov.start(amount=500, currency="XAF", phone=None,
                             description="d", reference="r")
        ok("PROVIDER lien local PADDLE_CHECKOUT_URL prioritaire, sinon lien Paddle",
           a["checkout_url"] == f"{LIEN}?_ptxn=txn_local"
           and b["checkout_url"] == "http://localhost:3000/paiement/carte?_ptxn=txn_local",
           f"{a['checkout_url']} | {b['checkout_url']}")
    finally:
        paddle.create_transaction = orig
        if sauve is None:
            os.environ.pop("PADDLE_CHECKOUT_URL", None)
        else:
            os.environ["PADDLE_CHECKOUT_URL"] = sauve


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    await check_client(ok)
    await check_lien_local(ok)
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
