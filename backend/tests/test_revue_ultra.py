"""Correctifs de la revue ultra (paiement, acces, jobs, quota admin).

Chaque verification ci-dessous etait AVEUGLE avant le correctif : les tests
existants rejouent `_apply_credit` sur le MEME objet Payment, dont le drapeau
`credited` vit alors en memoire. Le vrai risque -- webhook et interrogation
d'etat, deux sessions, deux objets -- n'y etait jamais exerce.

Execution :  backend/venv/Scripts/python.exe backend/tests/test_revue_ultra.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import sys
import os
import shutil
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
import fitz                                              # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402
from app.models import User, Payment, Document           # noqa: E402
from app import config as cfg                            # noqa: E402
from app import create_app                               # noqa: E402
from app.core.security import create_access_token        # noqa: E402
from app.services.jobs import jobs                       # noqa: E402
from app.api.payments import _apply_credit               # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)


async def _utilisateur(plan="free"):
    u = User(email=f"revue-{uuid.uuid4().hex[:10]}@example.com",
             plan=plan, email_verified=True, page_credits=0)
    async with async_session() as db:
        db.add(u)
        await db.commit()
    return u


async def _supprimer(user_id):
    async with async_session() as db:
        obj = await db.get(User, user_id)
        if obj:
            await db.delete(obj)
        await db.commit()


async def check_credit_deux_sessions(ok):
    u = await _utilisateur()
    try:
        async with async_session() as db:
            p = Payment(user_id=u.id, pages=5, amount=500, currency="XAF",
                        zone="A", status="SUCCESSFUL",
                        provider_ref=uuid.uuid4().hex)
            db.add(p)
            await db.commit()
            pid = p.id
        # Webhook ET interrogation d'etat : chacun charge SON objet, avant que
        # l'autre n'ait commite -> les deux voient credited=False.
        async with async_session() as s1, async_session() as s2:
            p1 = await s1.get(Payment, pid)
            p2 = await s2.get(Payment, pid)
            # Ordre force : le second agit sur un objet PERIME (credited=False
            # en memoire alors que la base dit True) -- c'est l'entrelacement
            # du webhook et de l'interrogation d'etat, rendu deterministe.
            await _apply_credit(s1, p1)
            await _apply_credit(s2, p2)
        async with async_session() as db:
            solde = (await db.get(User, u.id)).page_credits
        ok("CREDIT  deux sessions sur le meme paiement : UN seul credit",
           solde == 5, f"solde={solde}")
    finally:
        await _supprimer(u.id)


SECRET = "CLAIR-PAYE-QUUX"


def _pdf() -> bytes:
    d = fitz.open()
    d.new_page(width=400, height=300).insert_text(
        (40, 100), f"{SECRET} contenu", fontsize=13)
    data = d.tobytes()
    d.close()
    return data


def _texte(data: bytes) -> str:
    d = fitz.open(stream=data, filetype="pdf")
    t = "".join(p.get_text() for p in d)
    d.close()
    return t


async def check_acces_document_paye(client, ok, tmp):
    """Un compte gratuit qui a PAYE ce document lit le clair sur /result et
    /partial ; sans achat, il reste en 402 / aperçu rastérisé."""
    u = await _utilisateur()
    rendu = os.path.join(tmp, "rendu.pdf")
    with open(rendu, "wb") as f:
        f.write(_pdf())
    try:
        async with async_session() as db:
            docs = {}
            for nom, paye in (("paye", True), ("impaye", False)):
                d = Document(user_id=u.id, original_name="d.pdf",
                             source_lang="auto", target_lang="en",
                             original_path=rendu, size_bytes=10,
                             status="done", paid=paye)
                db.add(d)
                await db.commit()
                docs[nom] = d.id
        ent = {"X-API-Key": cfg.FRONTEND_API_KEY,
               "Authorization": "Bearer "
               + create_access_token(u.id, u.email)}
        res = {}
        for nom, doc_id in docs.items():
            job_id = jobs.create()
            jobs.set(job_id, state="done", result_path=rendu,
                     result_filename="d_TRADUIT.pdf", partial_path=rendu,
                     user_id=u.id, pages=None, document_id=doc_id)
            try:
                res[nom] = (client.get(f"/api/translate/result/{job_id}",
                                       headers=ent),
                            client.get(f"/api/translate/partial/{job_id}",
                                       headers=ent))
            finally:
                jobs.forget(job_id)
        r, pa = res["paye"]
        ok("ACCES  free + document PAYE : /result rend le fichier (200)",
           r.status_code == 200, f"status={r.status_code}")
        ok("ACCES  free + document PAYE : /partial en clair",
           pa.status_code == 200 and SECRET in _texte(pa.content),
           f"status={pa.status_code}")
        r, pa = res["impaye"]
        ok("ACCES  free + document IMPAYE : /result reste 402",
           r.status_code == 402, f"status={r.status_code}")
        ok("ACCES  free + document IMPAYE : /partial sans aucun mot extractible",
           pa.status_code == 200 and SECRET not in _texte(pa.content),
           f"status={pa.status_code}")
    finally:
        await _supprimer(u.id)


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    await check_credit_deux_sessions(ok)

    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       f"_revue_{uuid.uuid4().hex[:8]}")
    os.makedirs(tmp, exist_ok=True)
    try:
        # Contexte unique : cf. test_verrous_plan (boucle du TestClient).
        with TestClient(create_app()) as client:
            await check_acces_document_paye(client, ok, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ECHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
