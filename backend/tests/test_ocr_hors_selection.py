"""Pages hors sélection d'un PDF : mention « non incluse », puis traduire
(une page débitée), garder l'original ou retirer du fichier.
L'OCR est simulé ; la base de test (5433) est requise.

    PYTHONUTF8=1 venv/Scripts/python.exe tests/test_ocr_hors_selection.py
"""
import json
import os
import unittest
import uuid
from unittest.mock import patch

import racine  # noqa: F401
import fitz
from fastapi import HTTPException

from app.models import Document
from app.services import ocr_pages, render_cache, translation_runner
from app.services.jobs import jobs
from app.services.ocr import LecturePage
from app.services.translation_runner import render_translation_bytes, run_pdf_v2_job
from engines import translation_ai
from engines.pdf.stream import mention_non_incluse, mention_non_traduite
from test_ocr_moteur_pages import document, page_lue
from test_ocr_pages import pdf_photo
from test_ocr_pages_choix import LIRE, Choix, api, lancer, session

NON_INCLUSE = mention_non_incluse("en")


def _traduction_factice(self, batch, *_a, **_k):
    for item in batch:
        item["translated_text"] = item["text"]


class HorsSelection(Choix):
    def setUp(self):
        super().setUp()
        # Aucun appel réseau : la CI n'a pas de clé fournisseur.
        for nom, valeur in (("__init__", lambda _self: None),
                            ("_translate_batch", _traduction_factice),
                            ("fiche_document", lambda _self, *_a, **_k: "")):
            fausse = patch.object(translation_ai.TranslatorAI, nom, valeur)
            fausse.start()
            self.addCleanup(fausse.stop)

    def partiel(self, *pages, lectures=None):
        """PDF traduit sur sa page 1 seulement ; les autres restent hors sélection."""
        dossier = os.path.join(self.dir, uuid.uuid4().hex[:8])
        os.makedirs(dossier)
        self.original = os.path.join(dossier, "original.pdf")
        trad = os.path.join(dossier, "pages_1_debug_ocrv3.json")
        self.sortie = os.path.join(dossier, "out.pdf")
        job = jobs.create()
        with patch(LIRE, lambda _src, page: (lectures or {})[page]):
            run_pdf_v2_job(job, document(*pages), self.original, self.sortie, "doc.pdf",
                           os.path.join(dossier, "partial.pdf"), trad, "en", {1}, True)
        jobs.forget(job)

        async def creer():
            async with session() as db:
                doc = Document(user_id=self.user_id, original_name="doc.pdf", source_lang="fr",
                               target_lang="en", original_path=self.original, translated_path=trad,
                               size_bytes=1, status="done", page_count=len(pages),
                               reglages=json.dumps({"pages": "1"}))
                db.add(doc)
                await db.commit()
                return doc.id
        return lancer(creer()), trad

    def rendu(self, trad):
        return fitz.open(stream=render_translation_bytes(self.original, trad, "pdf", "en"),
                         filetype="pdf")

    def textes(self, trad):
        with self.rendu(trad) as rendu:
            return [p.get_text() for p in rendu]

    # -- Cas ---------------------------------------------------------------
    def test_mention_au_job_et_au_rendu(self):
        doc, trad = self.partiel("texte", "texte", "texte")
        self.assertEqual(ocr_pages.lire_selection(trad), {1})
        with fitz.open(self.sortie) as sortie:
            self.assertEqual([NON_INCLUSE in p.get_text() for p in sortie], [False, True, True])
        self.assertEqual([NON_INCLUSE in t for t in self.textes(trad)], [False, True, True])
        self.assertEqual(self.lister(doc)["pages"],
                         [{"page": 2, "motif": "hors_selection", "choix": None},
                          {"page": 3, "motif": "hors_selection", "choix": None}])
        self.assertEqual(api._suivi_scan(self.doc(doc))["pages_a_decider"], 0,
                         "la bibliothèque ne compte que les pages illisibles")

    def test_garder_l_original_sans_mention(self):
        doc, _ = self.partiel("texte", "texte", "texte")
        reponse, soumis = self.choisir(doc, [2], "original")
        self.assertEqual(soumis, [])
        self.assertEqual([p["choix"] for p in reponse["pages"]], ["original", None])
        textes = self.textes(self.doc(doc).translated_path)
        self.assertEqual([NON_INCLUSE in t for t in textes], [False, False, True])
        self.assertIn("Digital page text", textes[1])
        self.assertEqual(self.debits(doc), (0, 0))

    def test_choix_qui_ne_conviennent_pas(self):
        doc, trad = self.partiel("texte", "texte")
        with self.assertRaises(HTTPException) as err:
            self.choisir(doc, [2], "vide")
        self.assertEqual(err.exception.status_code, 409)
        scan, _ = self.scan()
        with self.assertRaises(HTTPException) as err:
            self.choisir(scan, [3], "retirer")
        self.assertEqual(err.exception.status_code, 409)
        with self.assertRaises(HTTPException) as err:
            self.choisir(doc, [1], "original")
        self.assertEqual(err.exception.status_code, 409)
        self.assertEqual(self.doc(doc).translated_path, trad)

    def test_retirer_du_fichier_pas_de_l_apercu(self):
        doc, _ = self.partiel("texte", "texte", "texte")
        self.choisir(doc, [3], "retirer")
        copie = self.doc(doc).translated_path
        self.assertEqual(ocr_pages.pages_retirees(copie), {3})
        textes = self.textes(copie)
        self.assertEqual(len(textes), 3, "l'aperçu garde la page à sa place")
        self.assertNotIn(NON_INCLUSE, textes[2])
        livre = api._sans_pages_retirees(render_translation_bytes(self.original, copie, "pdf", "en"),
                                         copie)
        with fitz.open(stream=livre, filetype="pdf") as fichier:
            self.assertEqual(len(fichier), 2)
        # Le choix se change : la page revient dans le fichier.
        self.choisir(doc, [3], "original")
        self.assertEqual(ocr_pages.pages_retirees(copie), set())

    def test_traduire_une_page_native_debitee(self):
        doc, _ = self.partiel("texte", "texte", "texte")
        reponse, soumis = self.choisir(doc, [2], "traduire")
        self.assertEqual((reponse["en_cours"], len(soumis)), ([2], 1))
        self.executer(soumis, None)
        self.assertEqual(self.debits(doc), (1, 0))
        self.assertEqual([p["page"] for p in self.lister(doc)["pages"]], [3])
        textes = self.textes(self.doc(doc).translated_path)
        self.assertEqual([NON_INCLUSE in t for t in textes], [False, False, True])

    def test_traduire_refuse_au_debit_rien_ne_change(self):
        doc, _ = self.partiel("texte", "texte")
        _, soumis = self.choisir(doc, [2], "traduire")
        copie = self.doc(doc).translated_path
        with open(copie, "rb") as f:
            avant = f.read()

        async def refus(*_a, **_k):
            return False
        with patch.object(translation_runner.ext_service, "debiter", side_effect=refus):
            self.executer(soumis, None)
        self.assertEqual(self.debits(doc), (0, 0))
        with open(copie, "rb") as f:
            self.assertEqual(f.read(), avant)
        self.assertIsNone(ocr_pages.lire(copie, 2))
        self.assertEqual(self.lister(doc)["pages"],
                         [{"page": 2, "motif": "hors_selection", "choix": None}])

    def test_traduire_une_page_scannee_lue(self):
        doc, _ = self.partiel("texte", pdf_photo(), pdf_photo())
        _, soumis = self.choisir(doc, [2], "traduire")
        self.executer(soumis, LecturePage("ok", None, page_lue()))
        self.assertEqual(self.debits(doc), (1, 0))
        textes = self.textes(self.doc(doc).translated_path)
        self.assertIn("Recognized scan text", textes[1])
        self.assertNotIn(NON_INCLUSE, textes[1])
        self.assertIn(NON_INCLUSE, textes[2])

    def test_traduire_une_page_scannee_illisible_devient_a_decider(self):
        doc, _ = self.partiel("texte", pdf_photo())
        _, soumis = self.choisir(doc, [2], "traduire")
        self.executer(soumis, LecturePage("illisible", "lecture"))
        self.assertEqual(self.debits(doc), (0, 0))
        self.assertEqual(self.lister(doc)["pages"], [{"page": 2, "motif": "lecture", "choix": None}])

    def test_illisible_garde_sa_mention_apres_invalidation(self):
        """Un rendu refait (cache invalidé) garde la mention des pages illisibles."""
        _, trad = self.scan()
        render_cache.invalider(trad)
        textes = self.textes(trad)
        self.assertIn(mention_non_traduite("en"), textes[2])
        self.assertNotIn(NON_INCLUSE, textes[2])

    def test_traduction_d_avant_la_selection_ecrite(self):
        doc, trad = self.partiel("texte", "texte")
        os.remove(os.path.join(ocr_pages.dossier(trad), "selection.json"))
        self.assertIsNone(ocr_pages.lire_selection(trad))
        self.assertEqual([p["page"] for p in self.lister(doc)["pages"]], [2])
        self.assertEqual(ocr_pages.lire_selection(trad), {1})
        self.assertIn(NON_INCLUSE, self.textes(trad)[1])


def load_tests(loader, _tests, _pattern):
    """Seuls les cas de ce fichier (pas ceux hérités de `Choix`)."""
    return unittest.TestSuite(HorsSelection(nom) for nom in sorted(vars(HorsSelection))
                              if nom.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
