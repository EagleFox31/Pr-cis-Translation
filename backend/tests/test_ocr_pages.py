"""Lecture par page : mémoire `.ocr/`, choix, et statuts rendus par `lire_page`.

Les tests de statuts demandent Tesseract (image Docker `precis-ocr-test`) : ils
sont ignorés sans lui. Le reste tourne partout.
"""
import io
import json
import os
import shutil
import tempfile
import threading
import unittest

import racine  # noqa: F401
import fitz
from PIL import Image
from app.services import ocr_pages
from app.services.ocr import LecturePage, OCRUnavailable, lire_page


def _pdf_image(image: Image.Image) -> bytes:
    tampon = io.BytesIO()
    image.save(tampon, format="PNG")
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=tampon.getvalue())
        return doc.tobytes()


def pdf_scan() -> bytes:
    with fitz.open() as source:
        page = source.new_page(width=595, height=842)
        page.insert_text((60, 80), "Congratulations on your graduation", fontsize=20)
        for ligne in range(10):
            page.insert_text((60, 130 + ligne * 28),
                             "This official certificate confirms successful studies.", fontsize=12)
        pix = page.get_pixmap(dpi=180)
    return _pdf_image(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))


def pdf_blanc() -> bytes:
    return _pdf_image(Image.new("RGB", (800, 1100), (255, 255, 255)))


def pdf_photo() -> bytes:
    """Une « photo » : dégradés et formes, aucune lettre, mais pas une page unie."""
    largeur, hauteur = 800, 1100
    pixels = bytearray()
    for y in range(hauteur):
        for x in range(largeur):
            pixels += bytes(((x * 255) // largeur, (y * 255) // hauteur,
                             ((x * y) // 900) % 256))
    return _pdf_image(Image.frombytes("RGB", (largeur, hauteur), bytes(pixels)))


class TestMemoire(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trad = os.path.join(self.tmp.name, "pages_ocrv3.json")

    def test_page_jamais_lue(self):
        self.assertIsNone(ocr_pages.lire(self.trad, 3))
        self.assertEqual(ocr_pages.lister(self.trad), {})
        self.assertEqual(ocr_pages.pages_illisibles(self.trad), {})
        self.assertIsNone(ocr_pages.pdf_de(self.trad, 3))

    def test_ecrire_et_relire(self):
        ocr_pages.ecrire(self.trad, 1, "ok", pdf=b"%PDF-un")
        ocr_pages.ecrire(self.trad, 2, "blanche")
        ocr_pages.ecrire(self.trad, 12, "illisible", "temps")
        self.assertEqual(ocr_pages.lire(self.trad, 12), {"statut": "illisible", "motif": "temps"})
        self.assertEqual(ocr_pages.pdf_de(self.trad, 1), b"%PDF-un")
        self.assertEqual(ocr_pages.pages_illisibles(self.trad), {12: "temps"})
        self.assertEqual(ocr_pages.pages_non_facturables(self.trad), {2, 12})

    def test_ok_sans_pdf_refuse(self):
        with self.assertRaises(ValueError):
            ocr_pages.ecrire(self.trad, 1, "ok")
        self.assertIsNone(ocr_pages.lire(self.trad, 1))

    def test_statut_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            ocr_pages.ecrire(self.trad, 1, "peut-etre")

    def test_retour_a_illisible_retire_le_pdf(self):
        # « Traduire quand même » annulé : la page ne doit plus se rendre lue.
        ocr_pages.ecrire(self.trad, 4, "ok", pdf=b"%PDF")
        ocr_pages.ecrire(self.trad, 4, "illisible", "solde")
        self.assertIsNone(ocr_pages.pdf_de(self.trad, 4))
        self.assertEqual(ocr_pages.pages_illisibles(self.trad), {4: "solde"})

    def test_fichier_abime_ignore(self):
        d = ocr_pages.dossier(self.trad)
        os.makedirs(d)
        with open(os.path.join(d, "p0001.json"), "w", encoding="utf-8") as f:
            f.write("{pas du json")
        with open(os.path.join(d, "p0002.json"), "w", encoding="utf-8") as f:
            json.dump({"statut": "inconnu"}, f)
        self.assertEqual(ocr_pages.lister(self.trad), {})

    def test_choix_poser_changer_retirer(self):
        ocr_pages.ecrire_choix(self.trad, [3, 5], "vide")
        ocr_pages.ecrire_choix(self.trad, [5], "original")
        self.assertEqual(ocr_pages.lire_choix(self.trad), {3: "vide", 5: "original"})
        self.assertEqual(ocr_pages.pages_vides(self.trad), {3})
        ocr_pages.ecrire_choix(self.trad, [3], None)
        self.assertEqual(ocr_pages.pages_vides(self.trad), set())

    def test_choix_n_est_pas_une_page(self):
        ocr_pages.ecrire_choix(self.trad, [3], "vide")
        self.assertEqual(ocr_pages.lister(self.trad), {})

    def test_choix_simultanes_ne_s_ecrasent_pas(self):
        fils = [threading.Thread(target=ocr_pages.ecrire_choix, args=(self.trad, [n], "vide"))
                for n in range(1, 31)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        self.assertEqual(ocr_pages.pages_vides(self.trad), set(range(1, 31)))


class LecteurAbsent:
    def __init__(self, manque):
        self._manque = manque

    def manquant(self):
        return self._manque


class TestIndisponible(unittest.TestCase):
    def test_tesseract_absent_est_une_panne_pas_une_page_illisible(self):
        with fitz.open() as doc:
            doc.new_page()
            for manque in ("tesseract", "langues"):
                with self.assertRaises(OCRUnavailable):
                    lire_page(doc, 1, lecteur=LecteurAbsent(manque))


@unittest.skipUnless(shutil.which("tesseract"), "Tesseract absent")
class TestStatuts(unittest.TestCase):
    def _lire(self, octets, **kw) -> LecturePage:
        with fitz.open(stream=octets, filetype="pdf") as doc:
            return lire_page(doc, 1, **kw)

    def test_scan_lisible(self):
        r = self._lire(pdf_scan())
        self.assertEqual(r.statut, "ok")
        with fitz.open(stream=r.pdf, filetype="pdf") as lue:
            self.assertEqual(lue.page_count, 1)
            self.assertIn("Congratulations", lue[0].get_text())

    def test_page_blanche(self):
        r = self._lire(pdf_blanc())
        self.assertEqual((r.statut, r.pdf), ("blanche", None))

    def test_photo_sans_texte_est_illisible_pas_blanche(self):
        r = self._lire(pdf_photo())
        self.assertEqual(r.statut, "illisible")
        self.assertIsNotNone(r.motif)

    def test_delai_epuise_page_illisible_motif_temps(self):
        r = self._lire(pdf_scan(), delai_s=0)
        self.assertEqual((r.statut, r.motif), ("illisible", "temps"))


if __name__ == "__main__":
    unittest.main()
