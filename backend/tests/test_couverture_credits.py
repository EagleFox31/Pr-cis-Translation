"""Couverture d'un document par le solde : rien de traduit qui ne soit payé.

La règle (demande du propriétaire) : à l'import, AVANT toute traduction, un
solde insuffisant le dit — « crédits insuffisants pour traduire tout le
document » — et propose deux choix : acheter les pages manquantes, ou
traduire uniquement les pages couvertes. Jamais de troncature silencieuse,
jamais une page de plus que ce qui est couvert.

Ce qui est mesuré ici, à la route elle-même (le worker est remplacé par un
enregistreur : aucune traduction, aucun appel payant) :
  • le 402 `need_credits` porte les pages manquantes et la possibilité du partiel ;
  • `covered_only=1` traduit les N PREMIÈRES pages visées, et elles seules ;
  • le débit suit le titre exact (offre / quota / pages achetées), une ligne
    du registre par titre, et un échec rend les pages achetées.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_couverture_credits.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import io
import json
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz                                              # noqa: E402
from fastapi import HTTPException, Response, UploadFile            # noqa: E402
from fastapi.responses import JSONResponse              # noqa: E402
from sqlalchemy import select                            # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app import config as cfg                            # noqa: E402
from app.api import translate as trmod                   # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
from app.models import (Document, UsageRecord, User,     # noqa: E402
                        KIND_CREDITS, KIND_FREE_OFFER, KIND_PLAN)
from app.services import usage                           # noqa: E402
from app.services.jobs import jobs                       # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)


class _File:
    """Remplace l'ordonnanceur : retient ce qui AURAIT été traduit."""
    def __init__(self):
        self.soumis = []

    def submit(self, job_id, prio, target, args):
        self.soumis.append((job_id, args))


def _docx() -> bytes:
    from docx import Document as WordDocument
    data = io.BytesIO()
    document = WordDocument()
    document.add_paragraph("A valid small document")
    document.save(data)
    return data.getvalue()


def _pdf(n: int) -> bytes:
    doc = fitz.open()
    for i in range(n):
        p = doc.new_page(width=400, height=300)
        # Contenu unique : aucun cache d'un autre test ne répond à sa place.
        p.insert_text((40, 100), f"Page {i + 1} {uuid.uuid4().hex}", fontsize=13)
    data = doc.tobytes()
    doc.close()
    return data


async def _compte(plan: str, credits: int, offre_prise: bool = False,
                  quota_pris: int = 0) -> str:
    async with async_session() as db:
        u = User(email=f"couv-{uuid.uuid4().hex[:10]}@example.com",
                 plan=plan, email_verified=True, page_credits=credits,
                 created_at=racine.compte_ancien())
        db.add(u)
        await db.flush()
        if offre_prise:
            db.add(UsageRecord(user_id=u.id, kind=KIND_FREE_OFFER, pages=5))
        if quota_pris:
            db.add(UsageRecord(user_id=u.id, kind=KIND_PLAN, pages=quota_pris))
        await db.commit()
        return u.id


async def _supprimer(uid: str):
    async with async_session() as db:
        for d in (await db.execute(select(Document).where(
                Document.user_id == uid))).scalars().all():
            await db.delete(d)
        for r in (await db.execute(select(UsageRecord).where(
                UsageRecord.user_id == uid))).scalars().all():
            await db.delete(r)
        u = await db.get(User, uid)
        if u:
            await db.delete(u)
        await db.commit()


async def _importer(uid: str, data: bytes, nom="doc.pdf", pages="",
                    covered_only="", solde_entre_temps=None) -> dict:
    """Appelle la route ; renvoie statut, corps, pages soumises, état final.

    `solde_entre_temps` : solde écrit par une AUTRE session après le
    chargement de l'utilisateur par l'authentification (requête concurrente,
    webhook de paiement) — la route doit décider sur la valeur verrouillée."""
    file = _File()
    vrai, trmod.scheduler = trmod.scheduler, file
    try:
        async with async_session() as db:
            user = await db.get(User, uid)
            if solde_entre_temps is not None:
                async with async_session() as autre:
                    (await autre.get(User, uid)).page_credits = solde_entre_temps
                    await autre.commit()
            try:
                rep = await trmod.translate_endpoint(
                    request=racine.requete_test(), response=Response(), file=UploadFile(filename=nom, file=io.BytesIO(data)),
                    target_lang="en", format_options="{}", quality="fast",
                    precise="", pages=pages, debug="", covered_only=covered_only,
                    x_api_key=cfg.FRONTEND_API_KEY, current_user=user, db=db)
            except HTTPException as e:
                rep = JSONResponse(status_code=e.status_code,
                                   content={"detail": e.detail})
    finally:
        trmod.scheduler = vrai
    statut = getattr(rep, "status_code", 200)
    corps = (json.loads(bytes(rep.body).decode())
             if hasattr(rep, "body") else rep)
    soumis = None
    for job_id, args in file.soumis:
        soumis = args[8] if nom.endswith((".pdf", ".pptx")) else args[15]
        jobs.forget(job_id)
    async with async_session() as db:
        u = await db.get(User, uid)
        recs = (await db.execute(select(UsageRecord).where(
            UsageRecord.user_id == uid, UsageRecord.document_id.is_not(None))
        )).scalars().all()
        doc = (await db.execute(select(Document).where(
            Document.user_id == uid))).scalars().first()
    return {"statut": statut, "corps": corps, "soumis": soumis,
            "solde": u.page_credits, "doc": doc,
            "registre": sorted((r.kind, r.pages) for r in recs)}


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    comptes = []

    async def compte(*a, **k):
        uid = await _compte(*a, **k)
        comptes.append(uid)
        return uid

    try:
        # ── Gratuit, offre du mois libre, document de 3 pages ──────────────
        uid = await compte("free", 0)
        r = await _importer(uid, _pdf(7))
        c = r["corps"]
        ok("GRATUIT-ESSAI  7 pages sans solde : 402 need_credits AVANT traduction",
           r["statut"] == 402 and c.get("reason") == "need_credits"
           and r["soumis"] is None, f"{r['statut']} {c}")
        ok("GRATUIT-ESSAI  manquent 2 pages, 5 couvertes (offre), partiel possible",
           c.get("pages_missing") == 2 and c.get("pages_available") == 5
           and c.get("partial_possible") is True and c.get("trial") is True, str(c))
        ok("GRATUIT-ESSAI  refus : rien consommé", r["registre"] == [], str(r["registre"]))

        r = await _importer(uid, _pdf(7), covered_only="1")
        ok("GRATUIT-ESSAI  choix « couvertes » : pages 1 à 5 traduites",
           r["statut"] == 200 and r["soumis"] == {1, 2, 3, 4, 5}, f"{r['statut']} {r['soumis']}")
        ok("GRATUIT-ESSAI  offre consommée, aperçu seul (non téléchargeable)",
           r["registre"] == [(KIND_FREE_OFFER, 5)] and r["doc"].paid is False,
           f"{r['registre']} paid={r['doc'] and r['doc'].paid}")

        # ── Gratuit, document d'une page, offre libre : passe sans question ─
        uid = await compte("free", 0)
        r = await _importer(uid, _pdf(1))
        ok("GRATUIT-ESSAI  1 page : l'offre couvre tout, aucun avertissement",
           r["statut"] == 200 and r["soumis"] is None, f"{r['statut']} {r['soumis']}")

        # ── Gratuit avec solde partiel ─────────────────────────────────────
        uid = await compte("free", 2, offre_prise=True)
        r = await _importer(uid, _pdf(5))
        c = r["corps"]
        ok("GRATUIT-SOLDE  2 pages pour 5 : 402, manquent 3",
           r["statut"] == 402 and c.get("pages_missing") == 3
           and c.get("pages_available") == 2 and c.get("trial") is False, str(c))
        ok("GRATUIT-SOLDE  refus : solde INTACT", r["solde"] == 2, str(r["solde"]))

        r = await _importer(uid, _pdf(5), covered_only="1")
        ok("GRATUIT-SOLDE  « couvertes » : pages 1-2 seules",
           r["soumis"] == {1, 2}, str(r["soumis"]))
        ok("GRATUIT-SOLDE  débit exact 2, document payé",
           r["solde"] == 0 and r["registre"] == [(KIND_CREDITS, 2)]
           and r["doc"].paid is True, f"solde={r['solde']} {r['registre']}")

        # ── Gratuit, solde présent : l'achat passe AVANT l'essai ───────────
        uid = await compte("free", 5)
        r = await _importer(uid, _pdf(3))
        ok("GRATUIT-SOLDE  offre disponible : utilisée avant les crédits achetés",
           r["statut"] == 200 and r["soumis"] is None and r["solde"] == 5
           and r["registre"] == [(KIND_FREE_OFFER, 3)] and r["doc"].paid is False,
           f"{r['statut']} {r['soumis']} solde={r['solde']} {r['registre']}")

        # ── Solde modifié entre l'authentification et le verrou ────────────
        uid = await compte("free", 5, offre_prise=True)
        r = await _importer(uid, _pdf(3), solde_entre_temps=0)
        ok("VERROU  solde dépensé ailleurs entre-temps : 402, pas de double dépense",
           r["statut"] == 402 and r["solde"] == 0 and r["registre"] == [],
           f"{r['statut']} solde={r['solde']} {r['registre']}")
        uid = await compte("free", 0, offre_prise=True)
        r = await _importer(uid, _pdf(3), solde_entre_temps=10)
        ok("VERROU  pages créditées entre-temps (webhook) : conservées",
           r["statut"] == 200 and r["solde"] == 7,
           f"{r['statut']} solde={r['solde']}")

        # ── Gratuit, autres formats : les pages achetées y donnent droit ───
        uid = await compte("free", 0)
        r = await _importer(uid, _docx(), nom="d.docx")
        ok("GRATUIT-DOCX  sans solde : couvert par l'offre, aperçu seul",
           r["statut"] == 200 and r["registre"] == [(KIND_FREE_OFFER, 1)] and r["doc"].paid is False, f"{r['statut']} {r['corps']}")
        uid = await compte("free", 4)
        r = await _importer(uid, _docx(), nom="d.docx")
        ok("GRATUIT-DOCX  offre disponible : crédits achetés conservés",
           r["statut"] == 200 and r["registre"] == [(KIND_FREE_OFFER, 1)]
           and r["solde"] == 4 and r["doc"].paid is False,
           f"{r['statut']} {r['corps'] if r['statut'] != 200 else ''} "
           f"solde={r['solde']} {r['registre']}")

        # ── Gratuit sans rien : aucun partiel ──────────────────────────────
        uid = await compte("free", 0, offre_prise=True)
        r = await _importer(uid, _pdf(2), covered_only="1")
        ok("GRATUIT-VIDE  rien de couvert : 402 même en « couvertes »",
           r["statut"] == 402 and r["corps"].get("partial_possible") is False
           and r["soumis"] is None, f"{r['statut']} {r['corps']}")

        # ── Plan payant : quota d'abord, pages achetées pour le dépassement ─
        uid = await compte("starter", 3, quota_pris=98)
        r = await _importer(uid, _pdf(4))
        ok("STARTER  98/100 + solde 3, 4 pages : passe (2 quota + 2 achetées)",
           r["statut"] == 200 and r["solde"] == 1
           and r["registre"] == sorted([(KIND_PLAN, 2), (KIND_CREDITS, 2)]),
           f"{r['statut']} solde={r['solde']} {r['registre']}")
        async with async_session() as db:
            await usage.refund_for_document(db, r["doc"].id)
            await db.commit()
            u = await db.get(User, uid)
            ok("STARTER  échec remboursé : les 2 pages achetées reviennent",
               u.page_credits == 3, str(u.page_credits))
            ok("STARTER  échec remboursé : le quota redevient libre",
               await usage.pages_used_this_month(db, u) == 98)

        uid = await compte("starter", 1, quota_pris=99)
        r = await _importer(uid, _pdf(5), pages="2-5")
        c = r["corps"]
        ok("STARTER  sélection 2-5, 2 couvertes : 402, manquent 2",
           r["statut"] == 402 and c.get("pages_missing") == 2
           and c.get("partial_possible") is True, str(c))
        r = await _importer(uid, _pdf(5), pages="2-5", covered_only="1")
        ok("STARTER  « couvertes » : les 2 PREMIÈRES pages de la sélection (2, 3)",
           r["soumis"] == {2, 3}, str(r["soumis"]))
        ok("STARTER  une ligne par titre : quota 1 + achetée 1",
           r["registre"] == sorted([(KIND_PLAN, 1), (KIND_CREDITS, 1)])
           and r["solde"] == 0, f"{r['registre']} solde={r['solde']}")

        uid = await compte("starter", 0, quota_pris=100)
        r = await _importer(uid, _docx(), nom="d.docx",
                            covered_only="1")
        ok("STARTER  quota épuisé, DOCX : 402, partiel impossible",
           r["statut"] == 402 and r["corps"].get("partial_possible") is False,
           f"{r['statut']} {r['corps']}")

        uid = await compte("starter", 0)
        r = await _importer(uid, _pdf(3), covered_only="1")
        ok("STARTER  « couvertes » sur un document couvert : rien n'est tronqué",
           r["statut"] == 200 and r["soumis"] is None
           and r["registre"] == [(KIND_PLAN, 3)], f"{r['soumis']} {r['registre']}")

        uid = await compte("enterprise", 0)
        r = await _importer(uid, _pdf(3))
        ok("ENTERPRISE  sans quota : jamais d'avertissement",
           r["statut"] == 200 and r["solde"] == 0, str(r["statut"]))
    finally:
        for uid in comptes:
            await _supprimer(uid)

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ÉCHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
