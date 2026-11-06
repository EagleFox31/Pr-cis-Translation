"""Paiement à la page — montant minimum de l'opérateur (100 F en XAF).

Ce qui est MESURÉ :
  • `billable_pages` atteint le minimum, et pas une page de plus (pour chaque
    taille de 1 à 20 pages) ; hors XAF, rien n'est arrondi ;
  • la ROUTE `/quote` annonce les pages facturées et le montant arrondi ;
  • la ROUTE `/collect` envoie à Campay un montant ≥ minimum, enregistre les
    pages facturées, et facture un document à SA taille (pas à celle envoyée) ;
  • `_apply_credit` débloque le document ET reverse le surplus au compte ;
    un achat d'avance crédite toutes les pages payées ; un document supprimé
    pendant le paiement rend TOUT le paiement au compte ;
  • un document dont la taille n'a jamais été consignée est RECOMPTÉ depuis
    son fichier : devis et encaissement à sa taille, pas à celle envoyée.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_paiement_minimum.py
PostgreSQL local requis (comme test_revue_ultra).
"""
from __future__ import annotations
import asyncio
import os
import sys
import uuid
from unittest.mock import patch, PropertyMock

import racine  # noqa: F401  -- met backend/ sur le chemin

from sqlalchemy import select                            # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402

from app.core.database import DATABASE_URL               # noqa: E402
from app.core.pricing import (CURRENCY, MIN_PAYMENT_AMOUNT,  # noqa: E402
                              CARD_FEE_FIXED, CARD_FEE_PERCENT,
                              ZONE_AFRICA, ZONE_EMERGING, ZONE_GLOBAL,
                              billable_pages, card_fee, page_price,
                              transaction_fee)
from app.models import User, Payment, Document           # noqa: E402
from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app.api import payments as route_payments           # noqa: E402
from app.api.payments import _apply_credit               # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)


async def _utilisateur():
    u = User(email=f"minpay-{uuid.uuid4().hex[:10]}@example.com",
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


async def _document(user_id, page_count, original_path="x.pdf"):
    d = Document(user_id=user_id, original_name="d.pdf", source_lang="auto",
                 target_lang="en", original_path=original_path, size_bytes=10,
                 status="done", paid=False, page_count=page_count)
    async with async_session() as db:
        db.add(d)
        await db.commit()
    return d


def check_calcul(ok):
    minimum = MIN_PAYMENT_AMOUNT[CURRENCY[ZONE_AFRICA]]
    unit = page_price(ZONE_AFRICA)
    juste = True
    for n in range(1, 21):
        b = billable_pages(ZONE_AFRICA, n)
        # Atteint le minimum, ne facture jamais moins que demandé, et une page
        # de moins serait soit sous le minimum, soit sous la demande.
        if not (b >= n and b * unit >= minimum
                and (b == n or (b - 1) * unit < minimum)):
            juste = False
    ok("CALCUL  zone A : minimum atteint, sans page superflue (1..20)", juste)
    ok("CALCUL  zone A : 1 page -> 2 pages facturees",
       billable_pages(ZONE_AFRICA, 1) == 2, str(billable_pages(ZONE_AFRICA, 1)))
    ok("CALCUL  hors XAF : aucun arrondi",
       billable_pages(ZONE_EMERGING, 1) == 1 and billable_pages(ZONE_GLOBAL, 1) == 1)
    # Carte : minimum technique de Paddle (427 F, 0,70 $, 0,65 €) sur le montant net.
    juste = all(billable_pages(z, 1, "card") * page_price(z) >= m
                and (billable_pages(z, 1, "card") - 1) * page_price(z) < m
                for z, m in ((ZONE_AFRICA, 427), (ZONE_EMERGING, 70), (ZONE_GLOBAL, 65)))
    ok("CALCUL  carte : minimum atteint dans chaque zone, sans page superflue", juste)
    ok("CALCUL  carte : 6 / 6 / 4 pages minimum (zones A / B / C)",
       [billable_pages(z, 1, "card") for z in (ZONE_AFRICA, ZONE_EMERGING, ZONE_GLOBAL)]
       == [6, 6, 4])

    # Frais carte : après la commission de Paddle (taux + part fixe, arrondis
    # au plus défavorable), il reste au moins le net, et une unité de frais en
    # moins ne le garantirait plus.
    juste = True
    for cur in ("XAF", "EUR", "USD"):
        fixe = CARD_FEE_FIXED[cur]
        for net in list(range(1, 2000)) + [3000, 4500, 19900, 54000, 10 ** 6]:
            fee = card_fee(net, cur)
            for f in (fee, fee - 1):
                total = net + f
                reste = total - (-(-total * CARD_FEE_PERCENT // 100)) - fixe
                if (f == fee) != (reste >= net):
                    juste = False
    ok("CALCUL  frais carte : net preserve, au centime pres (XAF, EUR, USD)", juste)
    ok("CALCUL  frais carte : 3 000 F -> 484 F ; 19,90 EUR -> 1,55 EUR",
       card_fee(3000, "XAF") == 484 and card_fee(1990, "EUR") == 155,
       str([card_fee(3000, "XAF"), card_fee(1990, "EUR")]))
    ok("CALCUL  frais mobile money inchanges (3 %)",
       transaction_fee(3000) == 90 and transaction_fee(3000, "XAF", "mtn_momo") == 90)


async def check_routes(client, ok):
    u = await _utilisateur()
    envoye = []

    async def faux_collect(**kw):
        envoye.append(kw)
        return {"reference": uuid.uuid4().hex, "ussd_code": None,
                "operator": "MTN"}

    # Routage forcé sur Campay simulé : sans cela, `PAYMENT_METHODS` du .env
    # (Fapshi, en LIVE) recevait la requête — un appel réel depuis un test.
    c = route_payments.campay
    vrais = (c.collect, c.username, c.password)
    c.collect, c.username, c.password = faux_collect, "u", "p"
    saved_env = os.environ.pop("PAYMENT_METHODS", None)
    ent = {"X-API-Key": cfg.FRONTEND_API_KEY, "X-Country": "CM",
           "Authorization": "Bearer " + create_access_token(u.id, u.email)}
    try:
        r = client.post("/api/payments/quote", json={"pages": 1}, headers=ent)
        q = r.json()
        ok("ROUTE   /quote 1 page : 2 facturees, 150 F + 5 F de frais, minimum publie",
           r.status_code == 200 and q.get("billed_pages") == 2
           and q.get("subtotal") == 150 and q.get("fee") == 5
           and q.get("amount") == 155 and q.get("min_amount") == 100, str(q))
        carte = q.get("card") or {}
        ok("ROUTE   /quote carte 1 page : 6 facturees, 450 F + 349 F de frais, minimum 427 F",
           carte.get("billed_pages") == 6 and carte.get("subtotal") == 450
           and carte.get("fee") == 349 and carte.get("amount") == 799
           and carte.get("min_amount") == 427, str(carte))

        r = client.post("/api/payments/collect",
                        json={"pages": 1, "phone": "237670000000"}, headers=ent)
        ok("ROUTE   /collect 1 page : le prestataire recoit 155 F (frais compris)",
           r.status_code == 200 and envoye and envoye[-1]["amount"] == 155,
           f"{r.status_code} {envoye[-1:] }")
        async with async_session() as db:
            p = await db.get(Payment, r.json().get("payment_id"))
        ok("ROUTE   /collect enregistre les pages facturees (2)",
           p is not None and p.pages == 2 and p.amount == 155)

        d = await _document(u.id, 3)
        r = client.post("/api/payments/collect",
                        json={"pages": 1, "phone": "237670000000",
                              "document_id": d.id}, headers=ent)
        ok("ROUTE   document de 3 pages annonce a 1 : facture 3 pages (225 F + 7 F de frais)",
           r.status_code == 200 and envoye[-1]["amount"] == 232,
           f"{r.status_code} {envoye[-1:]}")

        # Taille jamais consignée (page_count NULL) : le serveur recompte.
        import fitz, tempfile
        fd, chemin = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        pdf = fitz.open()
        for _ in range(3):
            pdf.new_page()
        pdf.save(chemin)
        pdf.close()
        try:
            d2 = await _document(u.id, None, original_path=chemin)
            r = client.post("/api/payments/quote",
                            json={"pages": 1, "document_id": d2.id}, headers=ent)
            q = r.json()
            ok("ROUTE   /quote document sans taille : recompte 3 pages (225 F + 7 F de frais)",
               r.status_code == 200 and q.get("pages") == 3
               and q.get("amount") == 232, str(q))
            async with async_session() as db:
                n = (await db.get(Document, d2.id)).page_count
            ok("ROUTE   la taille recomptee est consignee sur le document",
               n == 3, str(n))
            async with async_session() as db:
                await db.execute(Document.__table__.update()
                                 .where(Document.id == d2.id).values(page_count=None))
                await db.commit()
            r = client.post("/api/payments/collect",
                            json={"pages": 1, "phone": "237670000000",
                                  "document_id": d2.id}, headers=ent)
            ok("ROUTE   /collect document sans taille : facture 3 pages (225 F + 7 F de frais)",
               r.status_code == 200 and envoye[-1]["amount"] == 232,
               f"{r.status_code} {envoye[-1:]}")
            async with async_session() as db:
                for p in (await db.execute(select(Payment).where(
                        Payment.document_id == d2.id))).scalars():
                    await db.delete(p)
                await db.delete(await db.get(Document, d2.id))
                await db.commit()
        finally:
            os.remove(chemin)
    finally:
        c.collect, c.username, c.password = vrais
        if saved_env is not None:
            os.environ["PAYMENT_METHODS"] = saved_env
        await _supprimer(u.id)


async def check_credit(ok):
    u = await _utilisateur()
    try:
        d = await _document(u.id, 1)
        async with async_session() as db:
            pd = Payment(user_id=u.id, document_id=d.id, pages=2, amount=150,
                         currency="XAF", zone="A", status="SUCCESSFUL",
                         provider_ref=uuid.uuid4().hex)
            pa = Payment(user_id=u.id, pages=2, amount=150, currency="XAF",
                         zone="A", status="SUCCESSFUL",
                         provider_ref=uuid.uuid4().hex)
            db.add_all([pd, pa])
            await db.commit()
        async with async_session() as db:
            await _apply_credit(db, await db.get(Payment, pd.id))
        async with async_session() as db:
            doc = await db.get(Document, d.id)
            solde = (await db.get(User, u.id)).page_credits
        ok("CREDIT  document 1 page paye 2 : debloque + 1 page au compte",
           doc.paid and solde == 1, f"paid={doc.paid} solde={solde}")
        async with async_session() as db:
            await _apply_credit(db, await db.get(Payment, pa.id))
        async with async_session() as db:
            solde = (await db.get(User, u.id)).page_credits
        ok("CREDIT  achat d'avance de 2 pages : +2", solde == 3, f"solde={solde}")
        async with async_session() as db:
            await db.delete(await db.get(Document, d.id))
            await db.commit()

        # Document supprimé PENDANT le paiement : le paiement chargé le cite
        # encore, mais il n'y a plus rien à débloquer.
        d3 = await _document(u.id, 1)
        async with async_session() as db:
            pz = Payment(user_id=u.id, document_id=d3.id, pages=2, amount=150,
                         currency="XAF", zone="A", status="SUCCESSFUL",
                         provider_ref=uuid.uuid4().hex)
            db.add(pz)
            await db.commit()
        async with async_session() as db:
            charge = await db.get(Payment, pz.id)
            async with async_session() as autre:
                await autre.delete(await autre.get(Document, d3.id))
                await autre.commit()
            await _apply_credit(db, charge)
        async with async_session() as db:
            solde = (await db.get(User, u.id)).page_credits
        ok("CREDIT  document supprime pendant le paiement : +2 au compte",
           solde == 5, f"solde={solde}")
    finally:
        await _supprimer(u.id)


async def check_document_vide(ok):
    """Un TXT sans mot ne se chiffre pas : 422 clair, pas une erreur 500."""
    import tempfile
    from types import SimpleNamespace
    from fastapi import HTTPException
    with tempfile.TemporaryDirectory() as dossier:
        chemin = os.path.join(dossier, "vide.txt")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("   \n")
        doc = SimpleNamespace(page_count=None, original_path=chemin, original_name="vide.txt")
        try:
            await route_payments._document_pages(None, doc)
            statut = None
        except HTTPException as exc:
            statut = exc.status_code
    ok("ROUTE   devis d'un TXT vide : 422", statut == 422, str(statut))


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    check_calcul(ok)
    await check_document_vide(ok)
    await check_credit(ok)
    # The collection transport is replaced by faux_collect above. Its local
    # availability gate must also represent a configured synthetic provider;
    # no real Campay credentials belong in this billing regression test.
    with patch.object(type(route_payments.campay), "configured",
                      new_callable=PropertyMock, return_value=True):
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
