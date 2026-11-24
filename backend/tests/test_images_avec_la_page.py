"""Images traduites avec leur page (étude images-pendant-traduction).

`ImagesDuTravail` : lecteur et traduction factices, aucun réseau.
  - attendre(page) rend la table avec les images de la page, écrite sur disque ;
  - pages permises : rien n'est lu au-delà ; budget nul : pas de lecture d'avance ;
  - image en échec : la page part, image absente, échec compté ;
  - arrêt du travail : l'attente le propage sans bloquer ;
  - « garder l'original » : l'image retirée n'est pas dans la table ;
  - Word : attendre_tout rend toutes les images ;
  - les routes d'offre et de proposition n'existent plus.

    cd backend && PYTHONUTF8=1 venv/Scripts/python.exe tests/test_images_avec_la_page.py
"""
from __future__ import annotations
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import unittest.mock

import racine  # noqa: F401
import fitz
from PIL import Image

from app.services import images_document as module
from app.services.images_document import ImagesDuTravail, lister
from app.services.jobs import ArretDemande
from app.services.ocr_v2 import image as ocr_image
from test_images_document import png_texte

NB_PAGES = 5
IMAGES = [png_texte(f"PAGE {n}") for n in range(1, NB_PAGES + 1)]
RENDU = b"\x89PNG\r\n\x1a\nrendu"


def _pixels(octets: bytes) -> bytes:
    return Image.open(io.BytesIO(octets)).convert("RGB").tobytes()


PIXELS = [_pixels(octets) for octets in IMAGES]


class FauxLecteur:
    def manquant(self):
        return False

    def detecter_image(self, bgr):
        return [object()]


class FauxTraducteur:
    """Remplace `traduire_image` : retient les images reçues (par numéro de page)."""

    def __init__(self, echec_page=None, bloque=None):
        self.pages, self.echec_page, self.bloque = [], echec_page, bloque
        self._verrou = threading.Lock()

    def __call__(self, octets, traduire, **_):
        page = PIXELS.index(_pixels(octets)) + 1
        with self._verrou:
            self.pages.append(page)
        if self.bloque is not None:
            self.bloque.wait(10)
        if page == self.echec_page:
            raise RuntimeError("lecture impossible")
        return type("Rendu", (), {"remplacee": True, "mime": "image/png", "data": RENDU})()


def pdf_cinq_pages() -> bytes:
    doc = fitz.open()
    for n, image in enumerate(IMAGES, 1):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {n} avec du texte courant.")
        page.insert_image(fitz.Rect(72, 100, 272, 170), stream=image)
    return doc.tobytes()


def docx_deux_images() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("Texte.")
    doc.add_picture(io.BytesIO(IMAGES[0]))
    doc.add_picture(io.BytesIO(IMAGES[1]))
    sortie = io.BytesIO()
    doc.save(sortie)
    return sortie.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="imgpage_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.trad = os.path.join(self.tmp, "translated_fr.json")
        self.cache = os.path.join(self.tmp, "cache")
        self.pdf = pdf_cinq_pages()
        self.faux = FauxTraducteur()
        patch = unittest.mock.patch.object(ocr_image, "traduire_image", self.faux)
        patch.start()
        self.addCleanup(patch.stop)

    def travail(self, data=None, ext="pdf", **kw):
        t = ImagesDuTravail(data or self.pdf, ext, lambda x: x, self.cache, self.trad,
                            langue="fr", lecteur=FauxLecteur(), **kw)
        self.addCleanup(self.fermer, t)
        return t

    @staticmethod
    def fermer(t):
        # Attendre le fil : sinon il lit encore pendant le test suivant et
        # écrit dans le faux traducteur de celui-ci.
        t.fermer()
        if t._fil is not None:
            t._fil.join(15)

    def cle_page(self, page):
        return next(i.cle for i in lister(self.pdf, "pdf") if i.pages == [page])

    def attendre_lectures(self, pages, delai=5.0):
        fin = time.time() + delai
        while time.time() < fin and set(pages) - set(self.faux.pages):
            time.sleep(0.05)


class Pdf(Base):
    def test_attendre_rend_la_table_et_l_ecrit(self):
        t = self.travail()
        table = t.attendre(2)
        self.assertIn(self.cle_page(2), table)
        self.assertTrue(self.cle_page(2).startswith("xref:"))
        self.assertEqual(table[self.cle_page(2)], RENDU)
        with open(self.trad + ".images.json", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertIn(self.cle_page(2), meta["images"])
        self.assertEqual(module.charger_table(self.trad)[self.cle_page(2)], RENDU)

    def test_pages_permises_seulement(self):
        t = self.travail(pages=[1, 2])
        t.attendre(1)
        table = t.attendre(2)
        time.sleep(0.8)
        self.assertEqual(sorted(self.faux.pages), [1, 2])
        self.assertEqual(set(table), {self.cle_page(1), self.cle_page(2)})
        # Une page hors sélection n'attend rien et ne déclenche aucune lecture.
        t.attendre(4)
        self.assertEqual(sorted(self.faux.pages), [1, 2])

    def test_lecture_d_avance_par_defaut(self):
        t = self.travail(avance=2)
        t.attendre(2)
        self.attendre_lectures([2, 3, 4])
        time.sleep(0.5)
        self.assertEqual(sorted(self.faux.pages), [2, 3, 4])

    def test_budget_nul_pas_de_lecture_d_avance(self):
        t = self.travail(reste=lambda: 0)
        t.attendre(2)
        time.sleep(0.8)
        self.assertEqual(self.faux.pages, [2])

    def test_image_en_echec(self):
        self.faux.echec_page = 2
        t = self.travail()
        table = t.attendre(2)
        self.assertNotIn(self.cle_page(2), table)
        self.assertEqual(t.rapport["echecs"], 1)
        self.assertIn(self.cle_page(1), t.attendre(1))

    def test_arret_leve_sans_bloquer(self):
        bloque = threading.Event()
        self.faux.bloque = bloque
        etat = {"arret": False}

        def arret():
            if etat["arret"]:
                raise ArretDemande("pause")

        t = self.travail(arret=arret)
        t.demander([1])
        time.sleep(0.3)
        etat["arret"] = True
        debut = time.time()
        with self.assertRaises(ArretDemande):
            t.attendre(1)
        self.assertLess(time.time() - debut, 5)
        bloque.set()

    def test_garder_l_original(self):
        t = self.travail()
        cle = self.cle_page(1)
        self.assertIn(cle, t.attendre(1))
        self.assertTrue(module.marquer_originale(self.trad, cle, True))
        self.assertNotIn(cle, t.table())
        self.assertNotIn(cle, module.charger_table(self.trad))
        self.assertTrue(module.marquer_originale(self.trad, cle, False))
        self.assertIn(cle, t.table())

    def test_un_nouveau_travail_garde_les_choix_deja_faits(self):
        cle = self.cle_page(1)
        self.travail().attendre(1)
        module.marquer_originale(self.trad, cle, True)
        autre = self.travail()
        autre.attendre(3)
        self.assertNotIn(cle, autre.table())
        with open(self.trad + ".images.json", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertIn(cle, meta["images"])
        self.assertEqual(meta["retirees"], [cle])


    def test_sans_persister_rien_n_est_ecrit_avant_reporter(self):
        # Page incluse après coup : ses images n'entrent dans la table du
        # document qu'une fois la page payée.
        t = self.travail(pages=[2], avance=0, persister=False)
        self.assertIn(self.cle_page(2), t.attendre(2))
        self.assertEqual(t.traduites, 1)
        self.assertEqual(module.charger_table(self.trad), {})
        t.reporter()
        self.assertEqual(module.charger_table(self.trad)[self.cle_page(2)], RENDU)

    def test_fil_mort_sur_arret_puis_attendre_leve(self):
        # Le fil meurt sur l'arrêt (avalé) avant que la page attende : la
        # page ne part pas avec ses images d'origine, l'arrêt remonte.
        etat = {"arret": False}

        def arret():
            if etat["arret"]:
                raise ArretDemande("pause")

        with unittest.mock.patch.object(ocr_image, "traduire_image",
                                        side_effect=ArretDemande("pause")):
            t = self.travail(arret=arret)
            t.demander([1])
            fin = time.time() + 5
            while not t._fini and time.time() < fin:
                time.sleep(0.05)
        self.assertTrue(t._fini)
        etat["arret"] = True
        with self.assertRaises(ArretDemande):
            t.attendre(2)

    def test_reprise_ne_relit_pas_les_images_deja_traduites(self):
        self.travail(pages=[1, 2], avance=0).attendre(2)
        self.faux.pages.clear()
        t = self.travail(pages=[1, 2], avance=0)
        table = t.attendre(2)
        self.assertIn(self.cle_page(2), table)
        self.assertEqual(self.faux.pages, [])


class Word(Base):
    def test_attendre_tout(self):
        t = self.travail(docx_deux_images(), "docx")
        table = t.attendre_tout()
        self.assertEqual(len(table), 2)
        self.assertTrue(all(octets == RENDU for octets in table.values()))
        self.assertEqual(sorted(self.faux.pages), [1, 2])


class RoutesRetirees(unittest.TestCase):
    def test_offre_et_proposition_absentes(self):
        from fastapi.testclient import TestClient
        from app import config as cfg, create_app
        h = {"X-API-Key": cfg.FRONTEND_API_KEY}
        with TestClient(create_app()) as c:
            doc = "00000000-0000-0000-0000-000000000000"
            self.assertIn(c.post(f"/api/documents/{doc}/images/traduire", headers=h).status_code,
                          (404, 405))
            self.assertIn(c.get(f"/api/documents/{doc}/images/proposition", headers=h).status_code,
                          (404, 405))


if __name__ == "__main__":
    unittest.main(verbosity=1)
