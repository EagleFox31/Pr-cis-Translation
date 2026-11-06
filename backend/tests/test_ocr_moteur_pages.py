"""Lecture OCR dans la boucle du moteur : page lue, illisible, blanche, vide,
reprise sans relecture, réouverture. L'OCR est simulé : Tesseract n'est pas requis."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import racine  # noqa: F401
import fitz
from app.services import ocr_pages
from app.services.jobs import jobs
from app.services.ocr import LecturePage, OCRUnavailable
from app.services.translation_runner import render_translation_bytes, run_pdf_v2_job
from engines.pdf.stream import mention_non_incluse, mention_non_traduite, translate_pdf_progressive
from test_ocr_pages import pdf_blanc, pdf_photo


def page_lue(texte="Recognized scan text") -> bytes:
    with fitz.open() as doc:
        doc.new_page(width=595, height=842).insert_text((60, 80), texte, fontsize=14)
        return doc.tobytes()


def document(*pages) -> bytes:
    """Assemble un PDF : "texte", ou les octets d'une page image."""
    with fitz.open() as doc:
        for page in pages:
            if page == "texte":
                doc.new_page(width=595, height=842).insert_text(
                    (60, 80), "Digital page text", fontsize=14)
            else:
                with fitz.open(stream=page, filetype="pdf") as image:
                    doc.insert_pdf(image)
        return doc.tobytes()


def pixels(doc, index):
    return doc[index].get_pixmap(dpi=40).samples


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.original = os.path.join(self.dir, "original.pdf")
        self.sortie = os.path.join(self.dir, "output.pdf")
        self.trad = os.path.join(self.dir, "pages_debug_ocrv3.json")

    def ecrire(self, octets):
        with open(self.original, "wb") as f:
            f.write(octets)
        return octets

    def pages_en_cache(self):
        with open(self.trad, encoding="utf-8") as f:
            return {p["page_num"] for p in json.load(f)["pages"]}


class TestMoteur(Base):
    def _traduire(self, **kw):
        evenements = []
        translate_pdf_progressive(self.original, self.sortie, target_lang="en",
                                  debug=True, cache_path=self.trad,
                                  on_event=evenements.append, **kw)
        return {e["page"]: e["status"] for e in evenements if e["type"] == "page"}

    def test_texte_lu_et_illisible(self):
        octets = self.ecrire(document("texte", pdf_photo(), pdf_photo()))
        vus = []

        def lecteur(page, _src, _index):
            vus.append(page)
            if page == 1:
                return None
            if page == 2:
                return LecturePage("ok", None, page_lue())
            return LecturePage("illisible", "lecture")

        statuts = self._traduire(lecteur_ocr=lecteur)
        self.assertEqual(vus, [1, 2, 3])
        self.assertEqual(statuts[3], "illisible")
        self.assertEqual(self.pages_en_cache(), {1, 2})
        with fitz.open(self.sortie) as sortie, fitz.open(stream=octets, filetype="pdf") as source:
            self.assertEqual(sortie.page_count, 3)
            self.assertEqual(pixels(sortie, 2), pixels(source, 2))

    def test_illisible_sans_choix_porte_une_mention(self):
        self.ecrire(document(pdf_photo(), pdf_photo(), pdf_blanc()))
        lectures = {1: LecturePage("illisible", "lecture"),
                    2: LecturePage("illisible", "temps"),
                    3: LecturePage("blanche")}
        self._traduire(lecteur_ocr=lambda p, *_: lectures[p],
                       pages_originales={2}, signaler_illisibles=True)
        with fitz.open(self.sortie) as sortie:
            self.assertIn("Page not translated", sortie[0].get_text())
            self.assertNotIn("not translated", sortie[1].get_text(),
                             "original choisi : aucune mention")
            self.assertNotIn("not translated", sortie[2].get_text(),
                             "page blanche : aucune mention")

    def test_budget_saute_les_illisibles_puis_s_arrete(self):
        from app.services.translation_runner import _avec_budget
        self.ecrire(document(pdf_photo(), pdf_photo(), pdf_blanc(), pdf_photo(), pdf_photo()))
        lectures = {1: LecturePage("ok", None, page_lue()),
                    2: LecturePage("illisible", "lecture"),
                    3: LecturePage("blanche"),
                    4: LecturePage("ok", None, page_lue()),
                    5: LecturePage("ok", None, page_lue())}
        vus, traitees, consommees = [], [], []

        def lire(page, *_):
            vus.append(page)
            return lectures[page]

        statuts = self._traduire(lecteur_ocr=_avec_budget(lire, 2, traitees, consommees),
                                 signaler_illisibles=True)
        self.assertEqual(vus, [1, 2, 3, 4], "page 5 hors budget : jamais lue")
        self.assertEqual((traitees, consommees), ([1, 2, 3, 4], [1, 4]))
        self.assertEqual(statuts[5], "copied")
        with fitz.open(self.sortie) as sortie:
            self.assertEqual(sortie.page_count, 5)
            self.assertIn("Page not translated", sortie[1].get_text())
            self.assertNotIn("not translated", sortie[4].get_text())
            self.assertIn(mention_non_incluse("en"), sortie[4].get_text())

    def test_mention_dans_la_langue_cible(self):
        from engines.pdf.stream import mention_non_traduite
        self.assertTrue(mention_non_traduite("fr").startswith("Page non traduite"))
        self.assertTrue(mention_non_traduite("ja").startswith("Page not translated"))

    def test_blanche_reste_telle_quelle_sans_cache(self):
        self.ecrire(document(pdf_blanc()))
        statuts = self._traduire(lecteur_ocr=lambda *_: LecturePage("blanche"))
        self.assertEqual(statuts[1], "blanche")
        self.assertEqual(self.pages_en_cache(), set())

    def test_page_vide_de_meme_format_meme_hors_selection(self):
        self.ecrire(document("texte", pdf_photo()))
        statuts = self._traduire(pages={1}, pages_vides={2})
        self.assertEqual(statuts[2], "vide")
        with fitz.open(self.sortie) as sortie:
            self.assertEqual((sortie.page_count, sortie[1].rect.width), (2, 595))
            self.assertEqual(sortie[1].get_images(), [])
            self.assertEqual(sortie[1].get_text().strip(), "")

    def test_sans_lecteur_comportement_inchange(self):
        self.ecrire(document("texte", pdf_photo()))
        statuts = self._traduire(pages={1})
        self.assertEqual(statuts[2], "copied")


class TestTravail(Base):
    def _job(self, octets, pages=None):
        job_id = jobs.create()
        run_pdf_v2_job(job_id, octets, self.original, self.sortie, "scan.pdf",
                       os.path.join(self.dir, "partial.pdf"), self.trad,
                       "en", pages, True)
        return job_id

    def _lire(self, _src, page):
        self.lectures.append(page)
        return {2: LecturePage("ok", None, page_lue()),
                3: LecturePage("illisible", "temps"),
                4: LecturePage("blanche")}[page]

    def _document(self):
        self.lectures = []
        return document("texte", pdf_photo(), pdf_photo(), pdf_blanc())

    def test_memoire_gardee_et_reprise_sans_relecture(self):
        octets = self._document()
        with patch("app.services.translation_runner.ocr.lire_page", self._lire):
            self._job(octets)
            self.assertEqual(self.lectures, [2, 3, 4])
            self._job(octets)
        self.assertEqual(self.lectures, [2, 3, 4], "une page lue n'est jamais relue")
        self.assertEqual(ocr_pages.pages_illisibles(self.trad), {3: "temps"})
        self.assertEqual(ocr_pages.pages_non_facturables(self.trad), {3, 4})
        with open(self.original, "rb") as f:
            self.assertEqual(f.read(), octets, "l'original n'est jamais réécrit")

    def test_reouverture_sans_ocr(self):
        octets = self._document()
        with patch("app.services.translation_runner.ocr.lire_page", self._lire):
            self._job(octets)
        with patch("app.services.translation_runner.ocr.lire_page",
                   side_effect=AssertionError("pas d'OCR à la réouverture")):
            rendu = render_translation_bytes(self.original, self.trad, "pdf", "en")
        with fitz.open(stream=rendu, filetype="pdf") as doc, \
                fitz.open(stream=octets, filetype="pdf") as source:
            self.assertEqual(doc.page_count, 4)
            self.assertIn("Recognized scan text", doc[1].get_text())
            # L'illisible reste l'original, avec sa mention (gardée au rendu refait).
            self.assertGreaterEqual(len(doc[2].get_images()), 1)
            self.assertIn(mention_non_traduite("en"), doc[2].get_text())
            self.assertEqual(len(doc[2].get_images()), len(source[2].get_images()))

    def test_rendu_sur_instantane_sans_bloquer_les_ecritures(self):
        """Le moteur rend un instantané : le verrou de la traduction est libre
        pendant le rendu, une page reportée entre-temps garde sa version."""
        import threading
        from app.services import render_cache
        from app.services import translation_runner as tr
        octets = self._document()
        with patch("app.services.translation_runner.ocr.lire_page", self._lire):
            self._job(octets)
        moteur = tr.pdf_v2_stream.translate_pdf_progressive
        libre = []

        def pendant(*args, **kwargs):
            def ecrire():
                with render_cache.verrou_traduction(self.trad).ecrire():
                    with open(self.trad, encoding="utf-8") as f:
                        data = json.load(f)
                    for page in data["pages"]:
                        page["reporte"] = True
                    with open(self.trad, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                libre.append(True)
            t = threading.Thread(target=ecrire)
            t.start()
            t.join(5)
            self.assertNotEqual(kwargs["cache_path"], self.trad)
            return moteur(*args, **kwargs)

        with patch.object(tr.pdf_v2_stream, "translate_pdf_progressive", pendant):
            rendu = render_translation_bytes(self.original, self.trad, "pdf", "en")
        self.assertEqual(libre, [True], "écriture non bloquée pendant le rendu")
        with open(self.trad, encoding="utf-8") as f:
            pages = {p["page_num"]: p for p in json.load(f)["pages"]}
        self.assertTrue(pages)
        self.assertTrue(all(p.get("reporte") for p in pages.values()),
                        "le report concurrent est gardé")
        with fitz.open(stream=rendu, filetype="pdf") as doc:
            self.assertIn(mention_non_traduite("en"), doc[2].get_text())

    def test_retouches_du_rendu_reportees(self):
        from app.services.translation_runner import _reprendre_retouches
        avant = {"pages": [{"page_num": 1, "a": 0}, {"page_num": 2, "a": 0}]}
        with open(self.trad, "w", encoding="utf-8") as f:
            json.dump({"pages": [{"page_num": 1, "a": 0}, {"page_num": 2, "a": 9}]}, f)
        instantane = os.path.join(self.dir, "instantane.json")
        with open(instantane, "w", encoding="utf-8") as f:
            json.dump({"pages": [{"page_num": 1, "a": 1}, {"page_num": 2, "a": 1}],
                       "fiches": {"x": 1}}, f)
        _reprendre_retouches(self.trad, json.dumps(avant).encode(), instantane)
        with open(self.trad, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual([p["a"] for p in data["pages"]], [1, 9],
                         "retouche reportée, page modifiée entre-temps gardée")
        self.assertEqual(data["fiches"], {"x": 1})

    def test_choix_vide_a_la_reouverture(self):
        octets = self._document()
        with patch("app.services.translation_runner.ocr.lire_page", self._lire):
            self._job(octets)
        ocr_pages.ecrire_choix(self.trad, [3], "vide")
        rendu = render_translation_bytes(self.original, self.trad, "pdf", "en")
        with fitz.open(stream=rendu, filetype="pdf") as doc:
            self.assertEqual(doc[2].get_images(), [])
        ocr_pages.ecrire_choix(self.trad, [3], "original")
        rendu = render_translation_bytes(self.original, self.trad, "pdf", "en")
        with fitz.open(stream=rendu, filetype="pdf") as doc:
            self.assertGreaterEqual(len(doc[2].get_images()), 1)

    def test_copie_lue_disparue_n_est_pas_livree_comme_traduite(self):
        octets = self._document()
        with patch("app.services.translation_runner.ocr.lire_page", self._lire):
            self._job(octets)
        os.unlink(os.path.join(ocr_pages.dossier(self.trad), "p0002.pdf"))
        with self.assertRaises(FileNotFoundError):
            render_translation_bytes(self.original, self.trad, "pdf", "en")

    def test_document_entierement_illisible_se_rouvre(self):
        octets = document(pdf_photo(), pdf_photo())
        with patch("app.services.translation_runner.ocr.lire_page",
                   return_value=LecturePage("illisible", "lecture")):
            self._job(octets)
        self.assertEqual(self.pages_en_cache(), set())
        rendu = render_translation_bytes(self.original, self.trad, "pdf", "en")
        with fitz.open(stream=rendu, filetype="pdf") as doc, \
                fitz.open(stream=octets, filetype="pdf") as source:
            self.assertEqual(len(doc[1].get_images()), len(source[1].get_images()))
            self.assertIn(mention_non_traduite("en"), doc[1].get_text())

    def test_panne_ocr_fait_echouer_le_travail(self):
        octets = document(pdf_photo())
        with patch("app.services.translation_runner.ocr.lire_page",
                   side_effect=OCRUnavailable("absent")):
            job_id = self._job(octets)
        self.assertEqual(jobs.get(job_id)["state"], "error")
        self.assertEqual(ocr_pages.lister(self.trad), {})


if __name__ == "__main__":
    unittest.main()
