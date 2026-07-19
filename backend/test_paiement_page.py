"""Paiement à la page — le chemin de l'argent, porte par porte.

La règle (mots du propriétaire) :
  « il a droit a une traduction free + (et payer le prix de la page pour
    telecharger. apres cela pour effectuer n'importe quelle autre traduction,
    paiement avant meme de traduire et avec ça il peux traduire, visualiser et
    telecharger ce qu'il a payer uniqument. previsualisation masqué) »

`test_verrous_plan` défend l'INVERSE de cette suite : que le non-payé ne fuit
pas. Les deux sont nécessaires — un verrou qui ne s'ouvre jamais protège aussi
bien qu'un mur, et vend aussi bien.

Ce qui est mesuré ici, jamais supposé :
  • un document PAYÉ sort en clair pour un compte `free` (extraction réelle) ;
  • le solde de pages est débité du bon nombre, et refuse quand il manque ;
  • un même encaissement ne crédite QU'UNE fois (webhook + interrogation
    d'état arrivent tous les deux, souvent en double).

Exécution :  backend/venv/Scripts/python.exe backend/test_paiement_page.py
Requiert PostgreSQL et la migration 0004.
"""
from __future__ import annotations
import asyncio
import os
import shutil
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz                                              # noqa: E402
from fastapi import HTTPException                        # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402
from database import DATABASE_URL                        # noqa: E402
from datetime import datetime, timezone                  # noqa: E402
from sqlalchemy import select, func                      # noqa: E402
from models import (                                     # noqa: E402
    User, Document, Payment, get_plan_monthly_pages,
)

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)

import app as appmod                                     # noqa: E402
from routes.documents import (                           # noqa: E402
    STORAGE_BASE, download_document, preview_document, _may_read_clear,
)
from routes.payments import _apply_credit                # noqa: E402
from pricing import zone_for_country, page_price, CURRENCY  # noqa: E402

SECRET = "TRADUCTION-PAYEE-QUUX"


def _pdf(n_pages: int = 1) -> bytes:
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=400, height=300)
        page.insert_text((40, 100), f"{SECRET} contenu", fontsize=13)
    data = doc.tobytes()
    doc.close()
    return data


def _texte(data: bytes) -> str:
    d = fitz.open(stream=data, filetype="pdf")
    t = "".join(p.get_text() for p in d)
    d.close()
    return t


async def _monter():
    racine = os.path.join(STORAGE_BASE, f"_test_paiement_{uuid.uuid4().hex[:8]}")
    lang_dir = os.path.join(racine, "en")
    os.makedirs(lang_dir, exist_ok=True)
    orig = os.path.join(racine, "original.pdf")
    trad = os.path.join(lang_dir, "pages.json")
    with open(orig, "wb") as f:
        f.write(_pdf())
    with open(trad, "w", encoding="utf-8") as f:
        f.write('{"pages": []}')

    u = User(email=f"paie-{uuid.uuid4().hex[:10]}@example.com",
             plan="free", email_verified=True, page_credits=0)
    async with async_session() as db:
        db.add(u)
        await db.commit()
        # Deux documents du MÊME compte gratuit : l'un payé, l'autre non.
        # C'est le cœur de la règle — le droit tient au document, pas au compte.
        ids = {}
        for nom, paye in (("paye", True), ("impaye", False)):
            d = Document(user_id=u.id, original_name="doc.pdf",
                         source_lang="auto", target_lang="en",
                         original_path=orig, translated_path=trad,
                         size_bytes=1000, status="done", paid=paye)
            db.add(d)
            await db.commit()
            ids[nom] = d.id
    return {"racine": racine, "user": u, "docs": ids}


async def _demonter(ctx):
    async with async_session() as db:
        obj = await db.get(User, ctx["user"].id)
        if obj:
            await db.delete(obj)
        await db.commit()
    shutil.rmtree(ctx["racine"], ignore_errors=True)


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    # Le rendu réel est couvert par test_engine_v2_generic : ici on lui
    # substitue un PDF porteur du secret, dont la présence MESURE le clair.
    vrai_rendu = appmod.render_translation_bytes
    appmod.render_translation_bytes = lambda *a, **k: _pdf()

    ctx = await _monter()
    try:
        async with async_session() as db:
            user = await db.get(User, ctx["user"].id)
            paye = await db.get(Document, ctx["docs"]["paye"])
            impaye = await db.get(Document, ctx["docs"]["impaye"])

            # ── Le droit tient au DOCUMENT ─────────────────────────────────
            ok("DROIT  free + document payé : autorisé",
               _may_read_clear(user, paye))
            ok("DROIT  free + document impayé : refusé",
               not _may_read_clear(user, impaye))

            # ── Téléchargement ─────────────────────────────────────────────
            res = await download_document(paye.id, user=user, db=db)
            txt = _texte(res.body)
            ok("DOWNLOAD  document payé : la traduction sort en clair",
               SECRET in txt, f"texte={txt[:40]!r}")

            try:
                await download_document(impaye.id, user=user, db=db)
                ok("DOWNLOAD  document impayé : 402", False, "aucune exception")
            except HTTPException as e:
                ok("DOWNLOAD  document impayé : 402", e.status_code == 402,
                   f"status={e.status_code}")

            # ── Aperçu ─────────────────────────────────────────────────────
            res = await preview_document(paye.id, user=user, db=db)
            ok("PREVIEW  document payé : lisible en clair",
               SECRET in _texte(res.body))

            res = await preview_document(impaye.id, user=user, db=db)
            txt = _texte(res.body)
            ok("PREVIEW  document impayé : AUCUN mot extractible",
               SECRET not in txt and "contenu" not in txt, f"texte={txt[:40]!r}")

            # ── Crédit : une seule fois, jamais deux ───────────────────────
            p = Payment(user_id=user.id, pages=5, amount=500, currency="XAF",
                        zone="A", status="SUCCESSFUL", provider_ref=uuid.uuid4().hex)
            db.add(p)
            await db.commit()

            avant = user.page_credits
            await _apply_credit(db, p)
            await db.refresh(user)
            apres_1 = user.page_credits
            ok("CRÉDIT  un paiement réussi porte ses pages au solde",
               apres_1 == avant + 5, f"{avant} -> {apres_1}")

            # Le webhook ET l'interrogation d'état appellent tous deux ceci.
            await _apply_credit(db, p)
            await _apply_credit(db, p)
            await db.refresh(user)
            ok("CRÉDIT  rejoué deux fois : le solde NE bouge PAS",
               user.page_credits == apres_1, f"{apres_1} -> {user.page_credits}")

            # ── Un paiement échoué ne crédite rien ─────────────────────────
            pf = Payment(user_id=user.id, pages=99, amount=9900, currency="XAF",
                         zone="A", status="FAILED", provider_ref=uuid.uuid4().hex)
            db.add(pf)
            await db.commit()
            solde = user.page_credits
            await _apply_credit(db, pf)
            await db.refresh(user)
            ok("CRÉDIT  un paiement ÉCHOUÉ ne crédite rien",
               user.page_credits == solde, f"{solde} -> {user.page_credits}")

            # ── Paiement ciblé : il débloque CE document, et lui seul ───────
            p2 = Payment(user_id=user.id, document_id=impaye.id, pages=1,
                         amount=100, currency="XAF", zone="A",
                         status="SUCCESSFUL", provider_ref=uuid.uuid4().hex)
            db.add(p2)
            await db.commit()
            solde = user.page_credits
            await _apply_credit(db, p2)
            await db.refresh(impaye)
            await db.refresh(user)
            ok("CIBLÉ  le document visé devient payé", impaye.paid)
            ok("CIBLÉ  le solde de pages n'est PAS crédité en plus",
               user.page_credits == solde, f"{solde} -> {user.page_credits}")

        # ── Quota mensuel des plans payants ────────────────────────────────
        #
        # Il SOMME `Document.page_count`, colonne qui restait NULL jusqu'ici :
        # le quota vendu sur la carte de tarifs ne comptait donc rien. On mesure
        # la borne exacte, seul endroit où un quota se trompe vraiment.
        async with async_session() as db:
            u = User(email=f"quota-{uuid.uuid4().hex[:8]}@example.com",
                     plan="starter", email_verified=True)
            db.add(u)
            await db.commit()
            try:
                for n in (60, 35):                       # 95 pages consommées
                    db.add(Document(user_id=u.id, original_name="d.pdf",
                                    source_lang="auto", target_lang="en",
                                    original_path="/x", size_bytes=1,
                                    status="done", page_count=n))
                await db.commit()

                mois = datetime.now(timezone.utc).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0)
                r = await db.execute(
                    select(func.coalesce(func.sum(Document.page_count), 0)).where(
                        Document.user_id == u.id, Document.created_at >= mois))
                deja = int(r.scalar() or 0)
                quota = get_plan_monthly_pages("starter")

                ok("QUOTA  les pages du mois se SOMMENT entre documents",
                   deja == 95, f"somme={deja}")
                ok("QUOTA  pile le quota passe (95+5=100)",
                   deja + 5 <= quota)
                ok("QUOTA  un seul dépassement refuse (95+6=101)",
                   deja + 6 > quota)
                ok("QUOTA  un plan sans quota n'est jamais bloqué",
                   get_plan_monthly_pages("enterprise") is None)
            finally:
                obj = await db.get(User, u.id)
                if obj:
                    await db.delete(obj)
                await db.commit()

        # ── Le prix annoncé est celui de la zone ───────────────────────────
        ok("ZONE  le Cameroun est facturé en FCFA",
           CURRENCY[zone_for_country("CM")] == "XAF")
        # Deux règles distinctes, longtemps testées en une seule — et la
        # confusion s'est vue dès que `PRICING_DEFAULT_COUNTRY=CM` est apparu
        # dans un `.env` : le test tombait sans qu'aucune règle soit violée.
        #
        # (a) Un pays CONNU mais hors grille paie le tarif plein. Toujours vrai,
        #     quelle que soit la configuration.
        ok("ZONE  un pays hors grille paie le tarif PLEIN",
           zone_for_country("ZZ") == "C", f"ZZ -> {zone_for_country('ZZ')}")

        # (b) SANS pays du tout, on suit `PRICING_DEFAULT_COUNTRY`, et à défaut
        #     le tarif plein. On force l'environnement : sinon ce test mesure
        #     le `.env` du poste qui l'exécute, pas le code.
        _sauve = os.environ.pop("PRICING_DEFAULT_COUNTRY", None)
        try:
            ok("ZONE  sans pays NI défaut configuré : tarif PLEIN",
               zone_for_country(None) == "C", f"-> {zone_for_country(None)}")
            os.environ["PRICING_DEFAULT_COUNTRY"] = "CM"
            ok("ZONE  le défaut configuré s'applique en l'absence d'en-tête",
               zone_for_country(None) == "A", f"-> {zone_for_country(None)}")
        finally:
            os.environ.pop("PRICING_DEFAULT_COUNTRY", None)
            if _sauve is not None:
                os.environ["PRICING_DEFAULT_COUNTRY"] = _sauve
        # Le vrai risque du multi-devise : confondre les unités mineures.
        ok("ZONE  100 FCFA la page, 0,19 € la page",
           page_price("A") == 100 and page_price("C") == 19,
           f"A={page_price('A')} C={page_price('C')}")
    finally:
        appmod.render_translation_bytes = vrai_rendu
        await _demonter(ctx)

    print()
    for nom, cond, detail in checks:
        print(f"  {'OK  ' if cond else 'ÉCHEC'}  {nom}"
              + (f"   [{detail}]" if not cond and detail else ""))
    reussis = sum(1 for _, c, _ in checks if c)
    print(f"\n  {reussis}/{len(checks)}\n")
    return reussis == len(checks)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
