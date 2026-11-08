"""Cache des images de l'extension et images simultanées (étude vitesse-images-extension).

  • la clé dépend des octets et de la langue ; absente → None ;
  • une entrée écrite se relit telle quelle, puis expire après 30 jours ;
  • la purge efface les entrées de plus de 30 jours, garde les récentes ;
  • route : une image déjà traduite revient sans OCR, toujours comptée sur la page ;
  • route : deux images à la fois par utilisateur, la troisième reçoit 429 ;
  • route : une image non remplacée, ou rendue à la hâte, n'entre pas au cache.

Exécution :  backend/venv/Scripts/python.exe backend/tests/test_cache_images.py
Sans base de données (compteurs de page simulés).
"""
from __future__ import annotations
import asyncio
import io
import os
import shutil
import sys
import tempfile
import threading
import time

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException, UploadFile            # noqa: E402

from app.api import extension as route                   # noqa: E402
from app.services import cache_images as ci              # noqa: E402
from app.services import limites_page as lp              # noqa: E402
from app.services.ocr_v2.image import Bloc, ImageTraduite  # noqa: E402

JOUR = 86400


def test_lecture_ecriture_expiration(dossier):
    c = ci.cle(b"image", "fr")
    assert c != ci.cle(b"image", "en") and c != ci.cle(b"autre", "fr")
    assert ci.cle(b"image", "../x") is None and ci.cle(b"image", "fr.") is None
    assert ci.lire(c, dossier) is None
    blocs = [{"texte": "ポンプ", "traduction": "Pompe", "boite": [1, 2, 3, 4], "remplace": True}]
    ci.ecrire(c, "image/png", blocs, b"PNG", dossier)
    e = ci.lire(c, dossier)
    assert e == {"mime": "image/png", "blocs": blocs, "image": b"PNG"}, e
    assert ci.lire(c, dossier, maintenant=time.time() + 31 * JOUR) is None


def test_purge(dossier):
    vieille, recente = ci.cle(b"vieille", "fr"), ci.cle(b"recente", "fr")
    for c in (vieille, recente):
        ci.ecrire(c, "image/png", [], b"x", dossier)
    passe = time.time() - 31 * JOUR
    for ext_ in (".json", ".bin"):
        os.utime(os.path.join(dossier, vieille[:2], vieille + ext_), (passe, passe))
    assert ci.purger(dossier) == 1
    assert ci.lire(vieille, dossier) is None and ci.lire(recente, dossier) is not None


class _User:
    id = "u-cache"
    plan = "free"


def _requete():
    r = racine.requete_test()
    r.scope["headers"] = [(b"x-page", b"https://exemple.test/p")]
    return r


async def _appel(data, langue="fr"):
    try:
        r = await route.traduire_une_image(
            request=_requete(), file=UploadFile(filename="i.png", file=io.BytesIO(data)),
            langue=langue, video=False, current_user=_User(), db=None)
        return 200, r
    except HTTPException as e:
        return e.status_code, None


def _png(couleur) -> bytes:
    from PIL import Image
    data = io.BytesIO()
    Image.new("RGB", (80, 40), couleur).save(data, "PNG")
    return data.getvalue()


async def test_route(dossier):
    ci.DOSSIER, ci.ACTIF = dossier, True
    reserves, rendus, appels = [], [], []
    porte = threading.Event()
    remplacee = {"v": True, "complet": True}

    def fausse(data, traduire, lus=None, tour=None):
        appels.append(data)
        porte.wait(5)
        r = remplacee["v"]
        return ImageTraduite(b"TRADUITE" if r else data, "image/png",
                             [Bloc("ポンプ", (1, 2, 3, 4), traduction="Pompe", remplace=r)],
                             durees={"total": 0.0}, complet=remplacee["complet"])

    def lecture(data, tour=None):
        return [("ポンプ", (1, 2, 3, 4))]

    async def reserver(db, user, page, texte=0, images=0):
        reserves.append(images)
        return 0, images, None

    async def rendre(db, uid, page, texte=0, images=0):
        rendus.append(images)

    vrais = route.traduire_image, route.lire_image, lp.reserver, lp.rendre
    route.traduire_image, route.lire_image = fausse, lecture
    lp.reserver, lp.rendre = reserver, rendre
    lp.reinitialiser()
    try:
        porte.set()
        statut, r = await _appel(_png("white"))
        assert statut == 200 and r["remplacee"] and len(appels) == 1, (statut, r)
        statut, r = await _appel(_png("white"))
        assert statut == 200 and r["image"] == "VFJBRFVJVEU=" and len(appels) == 1, r
        assert r["blocs"][0]["traduction"] == "Pompe" and reserves == [1, 1], (r, reserves)
        assert lp._compteurs[(_User.id, route._page(_requete()))]["analyses"] == 1
        # Autre langue : nouvelle traduction.
        await _appel(_png("white"), langue="en")
        assert len(appels) == 2

        # Deux images en cours : la troisième est refusée.
        porte.clear()
        t1 = asyncio.create_task(_appel(_png("red")))
        t2 = asyncio.create_task(_appel(_png("blue")))
        for _ in range(100):
            if route._en_cours.get(_User.id) == 2:
                break
            await asyncio.sleep(0.02)
        assert route._en_cours.get(_User.id) == 2, route._en_cours
        statut, _ = await _appel(_png("green"))
        assert statut == 429, statut
        porte.set()
        assert [s for s, _ in await asyncio.gather(t1, t2)] == [200, 200]
        assert _User.id not in route._en_cours, route._en_cours

        # Non remplacée : réservation rendue, pas de cache.
        remplacee["v"] = False
        n = len(rendus)
        await _appel(_png("black"))
        await _appel(_png("black"))
        assert rendus[n:] == [1, 1] and len(appels) == 6, (rendus, len(appels))

        # Rendu hâtif (délai dépassé) : compté, mais pas gardé.
        remplacee.update(v=True, complet=False)
        n = len(rendus)
        await _appel(_png("gray"))
        await _appel(_png("gray"))
        assert len(appels) == 8 and len(rendus) == n, len(appels)
    finally:
        porte.set()
        route.traduire_image, route.lire_image, lp.reserver, lp.rendre = vrais
        ci.ACTIF = False


def run() -> bool:
    ok = True
    for nom, f in [("lecture, écriture, expiration", test_lecture_ecriture_expiration),
                   ("purge", test_purge), ("route", test_route)]:
        dossier = tempfile.mkdtemp(prefix="cache_images_test_")
        try:
            r = f(dossier)
            if asyncio.iscoroutine(r):
                asyncio.run(r)
            print(f"  OK     {nom}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  ÉCHEC  {nom}   [{type(e).__name__}: {e}]")
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
