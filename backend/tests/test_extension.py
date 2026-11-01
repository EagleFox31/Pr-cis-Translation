"""Routes de l'extension : rien de traduit qui ne soit payé, rien de payé qui
ne soit livré (étude extension §6 et §8).

Mesuré à la route elle-même, moteur et OCR remplacés (aucun appel payant) :
  • segments : débit au volume (1 page par 1 500 caractères), forfait d'abord,
    puis pages achetées ; 402 `need_credits` sans traduire si rien ne couvre ;
  • image : 1 page si remplacée, 0 sinon (et l'image n'est pas renvoyée) ;
    type et taille refusés avant toute lecture ;
  • `traduire_textes` : doublons et nombres ne partent pas au moteur ; blocs
    balisés `[[n]]` : balises perdues → bloc rendu tel quel ; titre et blocs
    voisins joints au cadre de page ; balises non comptées au débit.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_extension.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import io
import re
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException, UploadFile            # noqa: E402
from fastapi.responses import JSONResponse              # noqa: E402
from PIL import Image                                    # noqa: E402
from sqlalchemy import select                            # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app.api import extension as route                   # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
from app.models import (UsageRecord, User,               # noqa: E402
                        KIND_CREDITS, KIND_FREE_OFFER, KIND_PLAN)
from app.services import extension as ext                # noqa: E402
from app.services.ocr_v2.image import Bloc, ImageTraduite  # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)

segments = route.traduire_segments.__wrapped__
image = route.traduire_une_image.__wrapped__


class Moteur:
    """Faux `TranslatorAI` : retient ce qui lui est envoyé."""
    def __init__(self, ok=True, perd_balises=False):
        self.recu, self.cadres, self.ok, self.perd = [], [], ok, perd_balises

    def lang_name(self, code):
        return code

    def _translate_batch(self, lot, langue, cb, cadre=None):
        self.recu.append([b["text"] for b in lot])
        self.cadres.append(cadre)
        for b in lot:
            t = re.sub(r"\[\[/?\d+\]\]", "", b["text"]) if self.perd else b["text"]
            b["translated_text"] = f"[{langue}] {t}"
        return self.ok


def _png() -> bytes:
    data = io.BytesIO()
    Image.new("RGB", (80, 40), "white").save(data, "PNG")
    return data.getvalue()


async def _compte(plan: str, credits: int, quota_pris: int = 0) -> str:
    async with async_session() as db:
        u = User(email=f"ext-{uuid.uuid4().hex[:10]}@example.com",
                 plan=plan, email_verified=True, page_credits=credits)
        db.add(u)
        await db.flush()
        if quota_pris:
            db.add(UsageRecord(user_id=u.id, kind=KIND_PLAN if plan != "free"
                               else KIND_FREE_OFFER, pages=quota_pris))
        await db.commit()
        return u.id


async def _supprimer(uid: str):
    async with async_session() as db:
        for r in (await db.execute(select(UsageRecord).where(
                UsageRecord.user_id == uid))).scalars().all():
            await db.delete(r)
        u = await db.get(User, uid)
        if u:
            await db.delete(u)
        await db.commit()


async def _appel(fonction, uid, **k) -> dict:
    async with async_session() as db:
        user = await db.get(User, uid)
        try:
            rep = await fonction(request=None, current_user=user, db=db, **k)
        except HTTPException as e:
            rep = JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    statut, corps = 200, rep
    if isinstance(rep, JSONResponse):
        import json
        statut, corps = rep.status_code, json.loads(bytes(rep.body).decode())
    async with async_session() as db:
        u = await db.get(User, uid)
        recs = (await db.execute(select(UsageRecord).where(
            UsageRecord.user_id == uid, UsageRecord.document_id.is_(None)))).scalars().all()
    return {"statut": statut, "corps": corps, "solde": u.page_credits,
            "registre": sorted((r.kind, r.pages) for r in recs)}


def _fichier(data):
    return UploadFile(filename="i.png", file=io.BytesIO(data))


async def run():
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    m = Moteur()
    r = ext.traduire_textes(["Pompe", "12", "Pompe", "Joint"], "fr", m)
    ok("textes : doublons et nombres ne partent pas au moteur",
       m.recu == [["Pompe", "Joint"]] and r == ["[fr] Pompe", "12", "[fr] Pompe", "[fr] Joint"],
       f"{m.recu} {r}")
    try:
        ext.traduire_textes(["Pompe"], "fr", Moteur(ok=False))
        ok("textes : lot en échec → TraductionIndisponible", False)
    except ext.TraductionIndisponible:
        ok("textes : lot en échec → TraductionIndisponible", True)
    ok("volume : 1 page jusqu'à 1 500 caractères, 2 au-delà",
       ext.pages_pour_segments(["a" * 1500]) == 1 and ext.pages_pour_segments(["a" * 1501]) == 2)
    ok("volume : les balises ne se paient pas",
       ext.pages_pour_segments(["[[0]]" + "a" * 1500 + "[[/0]]"]) == 1)

    bloc = "[[0]]Serrer[[/0]] l'écrou"
    m = Moteur()
    r = ext.traduire_textes([bloc], "en", m)
    ok("bloc balisé : traduction rendue avec ses balises", r == [f"[en] {bloc}"], str(r))
    r = ext.traduire_textes([bloc], "en", Moteur(perd_balises=True))
    ok("bloc balisé : balises perdues → bloc rendu tel quel", r == [bloc], str(r))
    ok("cadre sans contexte : le lot fait la page (pas de doublon au moteur)",
       m.cadres[0]["n_page"] == 1 and "Serrer l'écrou" in m.cadres[0]["page"],
       str(m.cadres))
    m = Moteur()
    ext.traduire_textes([bloc], "en", m, titre="Leçon G49001",
                        contexte=["Retirer le capot.", "Contrôler le couple."])
    c = m.cadres[0]
    ok("cadre avec titre et voisins : joint au lot, titre marqué",
       c["n_page"] > len(m.recu[0]) and c["page"].startswith("# Leçon G49001")
       and "Contrôler le couple." in c["page"], str(c))

    vrai_textes, vrai_image = ext.traduire_textes, route.traduire_image
    envoyes, cadres = [], []

    def faux_textes(textes, langue, traducteur=None, titre="", contexte=()):
        envoyes.append(list(textes))
        cadres.append((titre, list(contexte)))
        return [f"[{langue}] {t}" for t in textes]

    def fausse_image(remplacee):
        def f(data, traduire):
            traduire(["ポンプ"])
            return ImageTraduite(b"PNG-TRADUIT" if remplacee else data, "image/png",
                                 [Bloc("ポンプ", (1, 2, 3, 4), traduction="Pompe", remplace=remplacee)])
        return f

    ext.traduire_textes = faux_textes
    comptes = []

    async def compte(*a, **k):
        uid = await _compte(*a, **k)
        comptes.append(uid)
        return uid

    try:
        uid = await compte("starter", 5)
        r = await _appel(segments, uid, corps=route.Segments(textes=["a" * 2000], langue="fr"))
        ok("segments : forfait payant débité de 2 pages, solde intact",
           r["statut"] == 200 and r["corps"]["pages"] == 2 and r["solde"] == 5
           and r["registre"] == [(KIND_PLAN, 2)], str(r))

        uid = await compte("free", 3, quota_pris=10_000)
        envoyes.clear()
        r = await _appel(segments, uid, corps=route.Segments(textes=["a" * 3100]))
        ok("segments : offre épuisée → pages achetées (3)",
           r["statut"] == 200 and r["solde"] == 0 and (KIND_CREDITS, 3) in r["registre"],
           str(r)[:300])

        uid = await compte("free", 0, quota_pris=10_000)
        envoyes.clear()
        r = await _appel(segments, uid, corps=route.Segments(textes=["Bonjour"]))
        ok("segments : rien ne couvre → 402 need_credits, rien traduit",
           r["statut"] == 402 and r["corps"]["reason"] == "need_credits" and not envoyes,
           str(r)[:300])

        r = await _appel(segments, uid, corps=route.Segments(textes=["a"] * (ext.SEGMENTS_MAX + 1)))
        ok("segments : plafond de segments → 413", r["statut"] == 413, str(r["statut"]))
        r = await _appel(segments, uid, corps=route.Segments(
            textes=["a"], contexte=["b" * (ext.CONTEXTE_MAX + 1)]))
        ok("segments : contexte trop long → 413", r["statut"] == 413, str(r["statut"]))

        uid = await compte("starter", 0)
        cadres.clear()
        r = await _appel(segments, uid, corps=route.Segments(
            textes=["[[0]]Bonjour[[/0]]"], titre="T", contexte=["voisin"]))
        ok("segments : titre et contexte transmis au moteur",
           r["statut"] == 200 and cadres == [("T", ["voisin"])], str(cadres))

        uid = await compte("free", 2, quota_pris=10_000)
        route.traduire_image = fausse_image(True)
        r = await _appel(image, uid, file=_fichier(_png()), langue="fr")
        ok("image remplacée : 1 page achetée débitée, image renvoyée",
           r["statut"] == 200 and r["corps"]["remplacee"] and r["solde"] == 1
           and r["corps"]["image"] and (KIND_CREDITS, 1) in r["registre"], str(r)[:300])

        route.traduire_image = fausse_image(False)
        r = await _appel(image, uid, file=_fichier(_png()), langue="fr")
        ok("image non remplacée : 0 débit, pas d'image, traduction pour l'info-bulle",
           r["statut"] == 200 and not r["corps"]["remplacee"] and r["solde"] == 1
           and r["corps"]["image"] is None and r["corps"]["blocs"][0]["traduction"] == "Pompe",
           str(r)[:300])

        r = await _appel(image, uid, file=_fichier(b"%PDF-1.4 pas une image"), langue="fr")
        ok("image : faux type → 415 avant lecture", r["statut"] == 415, str(r["statut"]))

        uid = await compte("free", 0, quota_pris=10_000)
        route.traduire_image = fausse_image(True)
        r = await _appel(image, uid, file=_fichier(_png()), langue="fr")
        ok("image : rien ne couvre → 402 avant lecture", r["statut"] == 402, str(r))
    finally:
        ext.traduire_textes, route.traduire_image = vrai_textes, vrai_image
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
