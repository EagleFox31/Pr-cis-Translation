"""Routes de l'extension : gratuites, limitées par page selon le forfait
(étude extension-gratuite-forfaits §4 et §5).

Mesuré à la route elle-même, moteur et OCR remplacés (aucun appel payant) :
  • segments : aucun crédit ni registre d'usage touchés ; texte compté par page,
    cumulé jusqu'à la limite du forfait, puis 413 `page_limit` sans traduire ;
    lot coupé par la limite : premiers blocs traduits, reste en original ;
    Starter plus large, Pro illimité ; 31e page du jour refusée, page déjà
    commencée acceptée ; moteur en panne → compteur rendu ;
  • image : 1 image comptée sur la page si remplacée, rendue sinon, ou si le
    moteur échoue ; plafond de texte par image ; vidéo hors compteur ; limite
    d'images de la page et pages du jour refusées avant toute lecture ;
  • analyse : traduisible ou non, sans rien compter ; la traduction qui suit
    reprend le rendu sans refaire l'OCR ; type et taille refusés avant lecture ;
  • `traduire_textes` : doublons et nombres ne partent pas au moteur ; blocs
    balisés `[[n]]` : balises perdues → bloc rendu tel quel ; titre et blocs
    voisins joints au cadre de page ; balises non comptées au volume ;
  • débit lié à un document (hors extension) : inchangé.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_extension.py
Requiert PostgreSQL.
"""
from __future__ import annotations
import asyncio
import io
import json
import re
import sys
import uuid

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException, UploadFile            # noqa: E402
from fastapi.responses import JSONResponse              # noqa: E402
from PIL import Image                                    # noqa: E402
from sqlalchemy import func, select                      # noqa: E402
from sqlalchemy.ext.asyncio import (                     # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession,
)
from sqlalchemy.pool import NullPool                     # noqa: E402

from app.api import extension as route                   # noqa: E402
from app.core.database import DATABASE_URL               # noqa: E402
from app.models import (Document, ExtensionUsage, UsageRecord, User,  # noqa: E402
                        KIND_CREDITS, KIND_FREE_OFFER, KIND_PLAN)
from app.services import extension as ext                # noqa: E402
from app.services import limites_page as lp              # noqa: E402
from app.services import usage                           # noqa: E402
from app.services.ocr_v2.image import Bloc, ImageTraduite  # noqa: E402

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
async_session = async_sessionmaker(_eng, class_=AsyncSession,
                                   expire_on_commit=False)

segments = route.traduire_segments.__wrapped__
image = route.traduire_une_image.__wrapped__
analyse = route.analyser_une_image.__wrapped__


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


def _png(couleur="white") -> bytes:
    data = io.BytesIO()
    Image.new("RGB", (80, 40), couleur).save(data, "PNG")
    return data.getvalue()


async def _compte(plan: str, credits: int = 0, quota_pris: int = 0) -> str:
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
    # Les lignes d'usage de l'extension partent avec le compte (cascade).
    async with async_session() as db:
        for r in (await db.execute(select(UsageRecord).where(
                UsageRecord.user_id == uid))).scalars().all():
            await db.delete(r)
        u = await db.get(User, uid)
        if u:
            await db.delete(u)
        await db.commit()


def _requete(page: str):
    r = racine.requete_test()
    r.scope["headers"] = [(b"x-page", page.encode())]
    return r


async def _appel(fonction, uid, page="p", **k) -> dict:
    async with async_session() as db:
        user = await db.get(User, uid)
        try:
            rep = await fonction(request=_requete(page), current_user=user, db=db, **k)
        except HTTPException as e:
            rep = JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:  # noqa: BLE001
            rep = JSONResponse(status_code=500, content={"detail": type(e).__name__})
    statut, corps = 200, rep
    if isinstance(rep, JSONResponse):
        statut, corps = rep.status_code, json.loads(bytes(rep.body).decode())
    return {"statut": statut, "corps": corps, **await _etat(uid, page)}


async def _etat(uid, page="p") -> dict:
    async with async_session() as db:
        u = await db.get(User, uid)
        recs = (await db.execute(select(UsageRecord).where(
            UsageRecord.user_id == uid, UsageRecord.document_id.is_(None)))).scalars().all()
        ligne = await db.get(ExtensionUsage, (uid, page))
        nb = (await db.execute(select(func.count()).select_from(ExtensionUsage).where(
            ExtensionUsage.user_id == uid))).scalar_one()
    return {"solde": u.page_credits,
            "registre": sorted((r.kind, r.pages) for r in recs),
            "ligne": (ligne.caracteres, ligne.images) if ligne else None,
            "pages": nb}


async def _prendre(uid, page, **k):
    """Réserve directement sur la page (état de départ d'un scénario)."""
    async with async_session() as db:
        user = await db.get(User, uid)
        return await lp.reserver(db, user, page, **k)


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
    ok("volume : les balises ne comptent pas",
       ext.caracteres(["[[0]]" + "a" * 1500 + "[[/0]]"]) == 1500
       and ext.caracteres(["ab", "[[1]]c[[/1]]"]) == 3)

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

    vrai_textes, vrai_image, vraie_lecture = ext.traduire_textes, route.traduire_image, route.lire_image
    vraie_offre = route.EXTENSION_OFFRE
    cache_actif, route.cache_images.ACTIF = route.cache_images.ACTIF, False
    envoyes, cadres, panne = [], [], {"v": False}
    lectures, rendus = [], []
    LIGNE = [("ポンプ", (1, 2, 3, 4))]
    lu = {"v": LIGNE}

    def faux_textes(textes, langue, traducteur=None, titre="", contexte=()):
        if panne["v"]:
            raise ext.TraductionIndisponible("panne")
        envoyes.append(list(textes))
        cadres.append((titre, list(contexte)))
        return [f"[{langue}] {t}" for t in textes]

    def fausse_image(remplacee, erreur=None):
        def f(data, traduire, lus=None, tour=None):
            rendus.append(lus)
            if erreur:
                raise erreur
            traduire(["ポンプ"])
            return ImageTraduite(b"PNG-TRADUIT" if remplacee else data, "image/png",
                                 [Bloc("ポンプ", (1, 2, 3, 4), traduction="Pompe", remplace=remplacee)])
        return f

    def lecture(data, tour=None):
        lectures.append(1)
        return lu["v"]

    ext.traduire_textes, route.lire_image = faux_textes, lecture
    comptes = []

    async def compte(*a, **k):
        uid = await _compte(*a, **k)
        comptes.append(uid)
        return uid

    def seg(*textes, **k):
        return route.Segments(textes=list(textes), **k)

    try:
        route.EXTENSION_OFFRE = False
        route._recents.clear()
        lp.reinitialiser()

        # ── Segments : gratuits, comptés par page ────────────────────────────
        uid = await compte("free", 5, quota_pris=10_000)
        r = await _appel(segments, uid, "s1", corps=seg("a" * 2000))
        ok("segments : traduits, 0 crédit, registre intact, texte compté sur la page",
           r["statut"] == 200 and r["corps"] == {
               "traductions": ["[fr] " + "a" * 2000], "traduits": 1, "limite": None,
               "offre": False, "pages": 0}
           and r["solde"] == 5 and r["registre"] == [(KIND_FREE_OFFER, 10_000)]
           and r["ligne"] == (2000, 0), str(r)[:300])

        uid = await compte("free")
        for _ in range(3):
            r = await _appel(segments, uid, "s2", corps=seg("a" * 10_000))
        ok("segments : le texte s'accumule sur la page (3 × 10 000 = limite du Gratuit)",
           r["statut"] == 200 and r["ligne"] == (30_000, 0) and not r["registre"], str(r)[:300])
        envoyes.clear()
        r = await _appel(segments, uid, "s2", corps=seg("Bonjour"))
        ok("segments : limite atteinte → 413 page_limit « texte », rien traduit, rien compté",
           r["statut"] == 413 and r["corps"]["reason"] == "page_limit"
           and r["corps"]["limite"] == "texte" and r["corps"]["offre"] is False
           and r["corps"]["detail"] and not envoyes and r["ligne"] == (30_000, 0)
           and r["solde"] == 0 and not r["registre"], str(r)[:300])
        r = await _appel(segments, uid, "s2bis", corps=seg("Bonjour"))
        ok("segments : une autre page repart à zéro", r["statut"] == 200
           and r["ligne"] == (7, 0), str(r)[:300])

        uid = await compte("free")
        await _prendre(uid, "s3", texte=20_000)
        envoyes.clear()
        r = await _appel(segments, uid, "s3", corps=seg("b" * 4000, "c" * 4000, "d" * 4000))
        ok("lot partiel : premiers blocs traduits, reste en original, limite « texte »",
           r["statut"] == 200 and r["corps"]["traduits"] == 2
           and r["corps"]["limite"] == "texte" and r["corps"]["pages"] == 0
           and r["corps"]["traductions"] == ["[fr] " + "b" * 4000, "[fr] " + "c" * 4000, "d" * 4000]
           and envoyes == [["b" * 4000, "c" * 4000]] and r["ligne"] == (28_000, 0),
           f"{str(r)[:200]} {r['ligne']}")
        envoyes.clear()
        r = await _appel(segments, uid, "s3", corps=seg("e" * 2500))
        ok("lot partiel : bloc trop gros pour le reste → rien traduit, réservation rendue",
           r["statut"] == 200 and r["corps"]["traduits"] == 0 and r["corps"]["limite"] == "texte"
           and r["corps"]["traductions"] == ["e" * 2500] and not envoyes
           and r["ligne"] == (28_000, 0), str(r)[:300])
        r = await _appel(segments, uid, "s3", corps=seg("f" * 2000))
        ok("lot partiel : le reste de la limite sert ensuite (28 000 + 2 000)",
           r["corps"]["traduits"] == 1 and r["corps"]["limite"] is None
           and r["ligne"] == (30_000, 0), str(r)[:300])

        uid = await compte("starter")
        for _ in range(5):
            r = await _appel(segments, uid, "st", corps=seg("a" * 20_000))
        ok("Starter : 100 000 caractères sur la page", r["statut"] == 200
           and r["ligne"] == (100_000, 0), str(r)[:300])
        r = await _appel(segments, uid, "st", corps=seg("a"))
        ok("Starter : au-delà → 413 texte", r["statut"] == 413
           and r["corps"]["limite"] == "texte", str(r)[:300])

        uid = await compte("pro")
        for _ in range(7):
            r = await _appel(segments, uid, "pr", corps=seg("a" * 20_000))
        ok("Pro : texte illimité sur la page (140 000 caractères)", r["statut"] == 200
           and r["corps"]["limite"] is None and r["ligne"] == (140_000, 0), str(r)[:300])

        uid = await compte("free")
        r = await _appel(segments, uid, "s4", corps=seg("[[0]]c[[/0]]" * 700))
        ok("segments : les balises ne comptent pas au volume",
           r["statut"] == 200 and r["ligne"] == (700, 0), str(r)[:300])

        panne["v"] = True
        r = await _appel(segments, uid, "s5", corps=seg("Bonjour"))
        ok("segments : moteur en panne → 503, compteur rendu, page non commencée",
           r["statut"] == 503 and r["ligne"] is None and r["pages"] == 1, str(r)[:300])
        panne["v"] = False

        r = await _appel(segments, uid, "s6", corps=seg(*["a"] * (ext.SEGMENTS_MAX + 1)))
        ok("segments : plafond de segments → 413", r["statut"] == 413, str(r["statut"]))
        r = await _appel(segments, uid, "s6", corps=seg(
            "a", contexte=["b" * (ext.CONTEXTE_MAX + 1)]))
        ok("segments : contexte trop long → 413", r["statut"] == 413, str(r["statut"]))
        ok("segments : refus de taille sans rien compter", r["ligne"] is None, str(r["ligne"]))

        uid = await compte("starter")
        cadres.clear()
        r = await _appel(segments, uid, "s7", corps=seg(
            "[[0]]Bonjour[[/0]]", titre="T", contexte=["voisin"]))
        ok("segments : titre et contexte transmis au moteur",
           r["statut"] == 200 and cadres == [("T", ["voisin"])], str(cadres))

        # ── Pages par jour ───────────────────────────────────────────────────
        uid = await compte("free", 4)
        for i in range(30):
            r = await _appel(segments, uid, f"j{i}", corps=seg("Bonjour"))
        ok("pages du jour : 30 pages différentes acceptées (Gratuit)",
           r["statut"] == 200 and r["pages"] == 30, str(r)[:300])
        envoyes.clear()
        r = await _appel(segments, uid, "j30", corps=seg("Bonjour"))
        ok("pages du jour : la 31e page → 413 « pages_jour », rien traduit ni compté",
           r["statut"] == 413 and r["corps"]["limite"] == "pages_jour"
           and r["corps"]["reason"] == "page_limit" and not envoyes
           and r["ligne"] is None and r["pages"] == 30 and r["solde"] == 4,
           str(r)[:300])
        r = await _appel(segments, uid, "j0", corps=seg("Encore"))
        ok("pages du jour : une page déjà commencée reste acceptée",
           r["statut"] == 200 and r["ligne"] == (13, 0), str(r)[:300])
        route.traduire_image = fausse_image(True)
        n = len(rendus)
        r = await _appel(image, uid, "j30", file=_fichier(_png()), langue="fr")
        ok("pages du jour : image sur une page nouvelle → 413 avant tout rendu",
           r["statut"] == 413 and r["corps"]["limite"] == "pages_jour"
           and len(rendus) == n and r["pages"] == 30, str(r)[:300])

        # Offre Starter/Pro : seulement hors bêta, jamais pour Pro ni pour les bornes techniques.
        route.EXTENSION_OFFRE = True
        r = await _appel(segments, uid, "j30", corps=seg("Bonjour"))
        ok("offre : 413 de pages du jour avec l'offre Starter/Pro hors bêta",
           r["statut"] == 413 and r["corps"]["offre"] is True, str(r)[:300])
        ok("offre : jamais pour Pro ni pour une borne technique",
           route._offre("pro", "texte") is False and route._offre("free", "lots") is False
           and route._offre("starter", "images") is True and route._offre("free", None) is False)
        route.EXTENSION_OFFRE = False

        # ── Images ───────────────────────────────────────────────────────────
        route._recents.clear()
        uid = await compte("free", 2, quota_pris=10_000)
        route.traduire_image = fausse_image(True)
        r = await _appel(image, uid, "i1", file=_fichier(_png()), langue="fr")
        ok("image remplacée : renvoyée, 0 crédit, 1 image comptée sur la page",
           r["statut"] == 200 and r["corps"]["remplacee"] and r["corps"]["image"]
           and r["corps"]["pages"] == 0 and r["solde"] == 2
           and r["registre"] == [(KIND_FREE_OFFER, 10_000)] and r["ligne"] == (0, 1),
           str(r)[:300])

        route.traduire_image = fausse_image(False)
        r = await _appel(image, uid, "i2", file=_fichier(_png("blue")), langue="fr")
        ok("image non remplacée : rien compté, pas d'image, traduction pour l'info-bulle",
           r["statut"] == 200 and not r["corps"]["remplacee"] and r["solde"] == 2
           and r["corps"]["image"] is None and r["corps"]["blocs"][0]["traduction"] == "Pompe"
           and r["corps"]["pages"] == 0 and r["ligne"] is None, str(r)[:300])

        route.traduire_image = fausse_image(True, ext.TraductionIndisponible("panne"))
        r = await _appel(image, uid, "i3", file=_fichier(_png("green")), langue="fr")
        ok("image : moteur en panne → 503, image rendue au compteur",
           r["statut"] == 503 and r["ligne"] is None, str(r)[:300])
        route.traduire_image = fausse_image(True, RuntimeError("boum"))
        r = await _appel(image, uid, "i3", file=_fichier(_png("yellow")), langue="fr")
        ok("image : exception imprévue → compteur rendu aussi",
           r["statut"] == 500 and r["ligne"] is None, str(r)[:300])

        route.traduire_image = fausse_image(True)
        r = await _appel(image, uid, "i1", file=_fichier(b"%PDF-1.4 pas une image"), langue="fr")
        ok("image : faux type → 415 avant lecture", r["statut"] == 415, str(r["statut"]))

        # Texte lu dans une seule image : plafond du forfait.
        route._recents.clear()
        route.traduire_image = fausse_image(True)
        lu["v"] = [("ポンプ" * 700, (1, 2, 3, 4))]  # 2 100 caractères
        n = len(rendus)
        r = await _appel(image, uid, "t1", file=_fichier(_png("red")), langue="fr")
        ok("plafond de texte par image (Gratuit 2 000) : non remplacée, limite « texte_image », rien compté",
           r["statut"] == 200 and not r["corps"]["remplacee"] and r["corps"]["image"] is None
           and r["corps"]["limite"] == "texte_image" and r["corps"]["pages"] == 0
           and r["ligne"] is None and len(rendus) == n, str(r)[:300])
        r = await _appel(analyse, uid, "t1", file=_fichier(_png("red")), langue="fr")
        ok("analyse d'une image trop chargée en texte : non traduisible, limite « texte_image »",
           r["corps"] == {"traduisible": False, "limite": "texte_image"} and r["ligne"] is None,
           str(r)[:300])
        uid_s = await compte("starter")
        r = await _appel(image, uid_s, "t1", file=_fichier(_png("red")), langue="fr")
        ok("plafond de texte par image : Starter accepte 2 100 caractères (4 000)",
           r["statut"] == 200 and r["corps"]["remplacee"] and r["ligne"] == (0, 1), str(r)[:300])
        lu["v"] = [("ポンプ" * 2000, (1, 2, 3, 4))]  # 6 000 caractères
        uid_p = await compte("pro")
        r = await _appel(image, uid_p, "t1", file=_fichier(_png("red")), langue="fr")
        ok("plafond de texte par image : Pro sans plafond",
           r["statut"] == 200 and r["corps"]["remplacee"] and r["ligne"] == (0, 1), str(r)[:300])
        lu["v"] = LIGNE
        route._recents.clear()

        # Limite d'images de la page (Gratuit : 30) ; vidéo hors compteur.
        uid = await compte("free")
        for _ in range(30):
            r = await _appel(image, uid, "im", file=_fichier(_png()), langue="fr")
        ok("images : 30 images comptées sur la page (Gratuit)",
           r["statut"] == 200 and r["ligne"] == (0, 30), str(r)[:300])
        n = len(rendus)
        r = await _appel(image, uid, "im", file=_fichier(_png()), langue="fr")
        ok("images : la 31e → 413 « images », rien rendu, rien compté",
           r["statut"] == 413 and r["corps"]["limite"] == "images"
           and len(rendus) == n and r["ligne"] == (0, 30), str(r)[:300])
        n, nl = len(rendus), len(lectures)
        r = await _appel(analyse, uid, "im", file=_fichier(_png("black")), langue="fr")
        ok("analyse : limite d'images de la page atteinte → 413 « images », sans lecture",
           r["statut"] == 413 and r["corps"]["limite"] == "images" and len(lectures) == nl,
           str(r)[:300])
        r = await _appel(segments, uid, "im", corps=seg("Bonjour"))
        ok("images : le texte de la page reste libre", r["statut"] == 200
           and r["ligne"] == (7, 30), str(r)[:300])
        r = await _appel(image, uid, "im", file=_fichier(_png("gray")), langue="fr", video=True)
        ok("vidéo : capture hors compteur d'images, même page à la limite",
           r["statut"] == 200 and r["corps"]["remplacee"] and r["ligne"] == (7, 30)
           and r["solde"] == 0 and not r["registre"], str(r)[:300])
        uid = await compte("free")
        r = await _appel(image, uid, "vi", file=_fichier(_png("gray")), langue="fr", video=True)
        ok("vidéo : aucune ligne créée en base", r["statut"] == 200 and r["ligne"] is None
           and r["pages"] == 0, str(r)[:300])

        uid = await compte("starter")
        await _prendre(uid, "sti", images=79)
        r = await _appel(image, uid, "sti", file=_fichier(_png()), langue="fr")
        ok("Starter : 80e image acceptée", r["statut"] == 200 and r["ligne"] == (0, 80), str(r)[:300])
        r = await _appel(image, uid, "sti", file=_fichier(_png("red")), langue="fr")
        ok("Starter : 81e image → 413 « images »", r["statut"] == 413
           and r["corps"]["limite"] == "images", str(r)[:300])
        uid = await compte("pro")
        await _prendre(uid, "pri", images=200)
        r = await _appel(image, uid, "pri", file=_fichier(_png()), langue="fr")
        ok("Pro : images illimitées sur la page", r["statut"] == 200
           and r["ligne"] == (0, 201), str(r)[:300])

        # ── Analyse avant l'accord : OCR seul, lecture gardée, rien compté ───
        route._recents.clear()
        uid = await compte("free", 2, quota_pris=10_000)
        lectures.clear()
        rendus.clear()
        route.traduire_image = fausse_image(True)
        r = await _appel(analyse, uid, "a1", file=_fichier(_png("red")), langue="fr")
        ok("analyse : image à texte → traduisible, rien compté, rien traduit ni renvoyé",
           r["statut"] == 200 and r["corps"] == {"traduisible": True, "texte": "ポンプ"}
           and r["solde"] == 2 and r["ligne"] is None and r["pages"] == 0
           and len(lectures) == 1 and not rendus, f"{str(r)[:300]} {rendus}")
        r = await _appel(analyse, uid, "a1", file=_fichier(_png("red")), langue="en")
        ok("analyse : même image, autre langue → lecture gardée, pas de nouvel OCR",
           r["corps"] == {"traduisible": True, "texte": "ポンプ"} and len(lectures) == 1,
           f"{r} {lectures}")
        r = await _appel(image, uid, "a1", file=_fichier(_png("red")), langue="fr")
        ok("analyse puis traduction : 1 image comptée, rendu à partir de la lecture gardée",
           r["statut"] == 200 and r["corps"]["remplacee"] and r["corps"]["image"]
           and r["solde"] == 2 and r["ligne"] == (0, 1) and len(lectures) == 1
           and rendus == [LIGNE], f"{str(r)[:300]} {rendus}")
        lu["v"] = []
        r = await _appel(analyse, uid, "a2", file=_fichier(_png("blue")), langue="fr")
        ok("analyse : image sans texte → non traduisible, jamais comptée dans les images",
           r["corps"] == {"traduisible": False} and r["ligne"] is None and r["pages"] == 1,
           str(r)[:300])
        r = await _appel(analyse, uid, "a2", file=_fichier(b"%PDF-1.4"), langue="fr")
        ok("analyse : faux type → 415", r["statut"] == 415, str(r["statut"]))
        lu["v"] = LIGNE

        uid = await compte("free")
        for i in range(30):
            await _prendre(uid, f"aj{i}", texte=1)
        n = len(lectures)
        r = await _appel(analyse, uid, "aj-neuve", file=_fichier(_png("green")), langue="fr")
        ok("analyse : page nouvelle au-delà des pages du jour → 413, sans lecture",
           r["statut"] == 413 and r["corps"]["limite"] == "pages_jour" and len(lectures) == n,
           str(r)[:300])

        # ── Débit lié à un document (hors extension) : inchangé ──────────────
        uid = await compte("starter", 3, quota_pris=99)
        async with async_session() as db:
            doc = Document(user_id=uid, original_name="d.docx", source_lang="auto",
                           target_lang="fr", original_path="x", translated_path=None,
                           size_bytes=1, status="translating")
            db.add(doc)
            await db.commit()
            doc_id = doc.id
        try:
            async with async_session() as db:
                fait = await ext.debiter(db, uid, 3, document_id=doc_id)
            async with async_session() as db:
                recs = (await db.execute(select(UsageRecord).where(
                    UsageRecord.user_id == uid))).scalars().all()
                u = await db.get(User, uid)
            lies = sorted((r.kind, r.pages) for r in recs if r.document_id == doc_id)
            ok("débit lié à un document : 1 du forfait + 2 achetées, document_id inscrit",
               fait and lies == sorted([(KIND_PLAN, 1), (KIND_CREDITS, 2)])
               and u.page_credits == 1, f"{fait} {lies} solde={u.page_credits}")
            async with async_session() as db:
                async with db.begin():
                    await usage.refund_for_document(db, doc_id)
                u = await db.get(User, uid)
            ok("débit lié à un document : l'échec rend les pages achetées",
               u.page_credits == 3, str(u.page_credits))
        finally:
            async with async_session() as db:
                for r in (await db.execute(select(UsageRecord).where(
                        UsageRecord.document_id == doc_id))).scalars().all():
                    await db.delete(r)
                d = await db.get(Document, doc_id)
                if d:
                    await db.delete(d)
                await db.commit()
    finally:
        ext.traduire_textes, route.traduire_image, route.lire_image = vrai_textes, vrai_image, vraie_lecture
        route.EXTENSION_OFFRE = vraie_offre
        route.cache_images.ACTIF = cache_actif
        route._recents.clear()
        lp.reinitialiser()
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
