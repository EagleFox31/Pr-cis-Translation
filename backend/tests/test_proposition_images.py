"""Proposition de traduire les images (retours 18/11 §3, option D1).

  • `images_document.proposer` : lit et traduit les images à texte sans débit,
    écrit `{etat, n, total}` dans proposition.json ; `aucune` sans lecteur ;
  • `_proposition_du_document` : aucune (xlsx, pas de marqueur), faite (images
    déjà posées), pret (fichier écrit), en_cours (calcul relancé si perdu) ;
  • `POST /api/documents/{id}/images/traduire` : 409 sans proposition prête,
    402 si le solde manque, débit d'une page par image posée, copie propre au
    document, puis 409 (déjà faite).

    cd backend && PYTHONUTF8=1 venv/Scripts/python.exe tests/test_proposition_images.py
Requiert PostgreSQL de test (5433) pour la route.
"""
from __future__ import annotations
import asyncio
import json
import os
import shutil
import tempfile
import types
import unittest
import unittest.mock
import uuid

import racine  # noqa: F401

from app.api import documents as route
from app.services import images_document as module
from app.services import translation_runner
from app.services.images_document import Analyse
from test_images_document import FauxTraducteur, png_texte, trois_images

ROUGE = png_texte("ROUGE")


def ecrire_proposition(dossier, prop):
    with open(module.chemin_proposition(dossier), "w", encoding="utf-8") as f:
        json.dump(prop, f)


class Proposer(unittest.TestCase):
    def setUp(self):
        self.dossier = os.path.join(tempfile.mkdtemp(prefix="imgprop_"), "images")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.dossier), True)

    def lancer(self, analyse, faux=None):
        with unittest.mock.patch.object(module, "analyse_complete", return_value=analyse), \
             unittest.mock.patch.object(module.ocr_image, "traduire_image",
                                        faux or FauxTraducteur()):
            return module.proposer(b"", "docx", lambda t: t, self.dossier, langue="fr")

    def test_pret(self):
        analyse = trois_images()
        analyse.analysees = 8
        prop = self.lancer(analyse)
        self.assertEqual(prop, {"etat": "pret", "n": 3, "total": 8})
        self.assertEqual(module.lire_proposition(self.dossier), prop)

    def test_images_non_remplacees_non_comptees(self):
        analyse = trois_images()
        analyse.analysees = 3
        prop = self.lancer(analyse, FauxTraducteur(remplacee=False))
        self.assertEqual((prop["etat"], prop["n"]), ("pret", 0))

    def test_lecteur_indisponible(self):
        prop = self.lancer(Analyse(indisponible=True))
        self.assertEqual(prop, {"etat": "aucune", "n": 0, "total": 0})
        self.assertEqual(module.lire_proposition(self.dossier), prop)


class EtatDuDocument(unittest.TestCase):
    def setUp(self):
        racine_tmp = tempfile.mkdtemp(prefix="imgetat_")
        self.addCleanup(shutil.rmtree, racine_tmp, True)
        self.trad = os.path.join(racine_tmp, "translated_fr.json")
        self.orig = os.path.join(racine_tmp, "original.docx")
        open(self.orig, "wb").write(b"docx")
        self.dossier = translation_runner.dossier_images(self.trad)

    def doc(self, nom="r.docx", images=True):
        return types.SimpleNamespace(original_name=nom, original_path=self.orig,
                                     translated_path=self.trad, target_lang="fr",
                                     reglages=json.dumps({"images": images}))

    def etat(self, doc):
        return route._proposition_du_document(doc)["etat"]

    def test_aucune(self):
        self.assertEqual(self.etat(self.doc("r.xlsx")), "aucune")
        self.assertEqual(self.etat(self.doc(images=False)), "aucune")

    def test_pret_puis_faite(self):
        os.makedirs(self.dossier)
        ecrire_proposition(self.dossier, {"etat": "pret", "n": 2, "total": 8})
        self.assertEqual(route._proposition_du_document(self.doc()),
                         {"etat": "pret", "n": 2, "total": 8})
        module.ecrire_table(self.trad, {"a": ROUGE}, {})
        self.assertEqual(self.etat(self.doc()), "faite")

    def test_calcul_perdu_relance(self):
        with unittest.mock.patch.object(translation_runner, "lancer_proposition") as lancer:
            self.assertEqual(self.etat(self.doc()), "en_cours")
        lancer.assert_called_once_with(b"docx", "docx", "fr", self.dossier)

    def test_calcul_en_cours_pas_relance(self):
        with unittest.mock.patch.object(translation_runner, "proposition_en_cours",
                                        return_value=True), \
             unittest.mock.patch.object(translation_runner, "lancer_proposition") as lancer:
            self.assertEqual(self.etat(self.doc()), "en_cours")
        lancer.assert_not_called()


class Route(unittest.TestCase):
    """Route réelle sur la base de test ; couverture et débit simulés."""

    def test_route(self):
        asyncio.run(self._run())

    async def _run(self):
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
        from sqlalchemy.ext.asyncio import (create_async_engine, async_sessionmaker,
                                            AsyncSession)
        from sqlalchemy.pool import NullPool
        from app import config as cfg, create_app
        from app.api.documents import STORAGE_BASE
        from app.core.database import DATABASE_URL
        from app.core.security import create_access_token
        from app.models import User, Document

        eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
        session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        dossier = os.path.join(STORAGE_BASE, f"_test_imgprop_{uuid.uuid4().hex[:8]}")
        os.makedirs(dossier)
        orig = os.path.join(dossier, "original.docx")
        open(orig, "wb").write(b"pas un vrai docx")
        trad = os.path.join(dossier, "translated_fr.json")
        open(trad, "w", encoding="utf-8").write("{}")
        images = translation_runner.dossier_images(trad)

        moi = User(email=f"imgprop-{uuid.uuid4().hex[:10]}@example.com",
                   plan="starter", email_verified=True)
        async with session() as db:
            db.add(moi)
            await db.commit()
            d = Document(user_id=moi.id, original_name="r.docx", source_lang="auto",
                         target_lang="fr", original_path=orig, translated_path=trad,
                         size_bytes=1, status="done", reglages=json.dumps({"images": True}))
            db.add(d)
            await db.commit()
            doc_id = d.id

        h = {"X-API-Key": cfg.FRONTEND_API_KEY,
             "Authorization": f"Bearer {create_access_token(moi.id, moi.email)}"}
        cle = "word/media/image1.png"
        refus = JSONResponse(status_code=402, content={"reason": "insufficient_credits",
                                                       "required": 2})
        debits = []

        async def debiter(db, user_id, pages, document_id=None):
            debits.append(pages)
            return True

        async def couvre(*_):
            return None

        try:
            with TestClient(create_app()) as c, \
                 unittest.mock.patch.object(translation_runner, "proposition_en_cours",
                                            return_value=True), \
                 unittest.mock.patch.object(route, "_table_depuis_le_cache",
                                            return_value=({cle: ROUGE}, {})), \
                 unittest.mock.patch.object(route.extension, "debiter", debiter):
                url = f"/api/documents/{doc_id}/images/traduire"

                # Lecture pas finie : rien à accepter.
                self.assertEqual(c.post(url, headers=h).status_code, 409)

                os.makedirs(images)
                ecrire_proposition(images, {"etat": "pret", "n": 1, "total": 4})
                r = c.get(f"/api/documents/{doc_id}/images/proposition", headers=h)
                self.assertEqual(r.json(), {"etat": "pret", "n": 1, "total": 4})

                # Solde insuffisant : 402, rien débité, l'offre reste ouverte.
                async def manque(*_):
                    return refus
                with unittest.mock.patch.object(route, "_couvre_les_pages", manque):
                    r = c.post(url, headers=h)
                self.assertEqual(r.status_code, 402)
                self.assertEqual(r.json()["reason"], "insufficient_credits")
                self.assertEqual(debits, [])
                self.assertEqual(c.get(f"/api/documents/{doc_id}/images/proposition",
                                       headers=h).json()["etat"], "pret")

                # Acceptée : une page par image posée, copie propre au document.
                with unittest.mock.patch.object(route, "_couvre_les_pages", couvre):
                    r = c.post(url, headers=h)
                    self.assertEqual(r.status_code, 200, r.text)
                    self.assertEqual([i["cle"] for i in r.json()["images"]], [cle])
                    self.assertEqual(debits, [1])
                    async with session() as db:
                        copie = (await db.get(Document, doc_id)).translated_path
                    self.assertNotEqual(copie, trad)
                    self.assertEqual(module.charger_table(copie), {cle: ROUGE})
                    self.assertEqual(module.charger_table(trad), {})

                    # Déjà faite : pas de second débit.
                    self.assertEqual(c.post(url, headers=h).status_code, 409)
                    self.assertEqual(debits, [1])
        finally:
            async with session() as db:
                obj = await db.get(User, moi.id)
                if obj:
                    await db.delete(obj)
                await db.commit()
            await eng.dispose()
            shutil.rmtree(dossier, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=1)
