"""Images d'un document qui contiennent du texte (étude images-documents §5, étape 6.8.1).

Documents générés en mémoire (PDF, DOCX, PPTX, XLSX) : liste des images
distinctes et exclusions, détection par un lecteur simulé (échéance, cache),
route d'analyse sans base de données, puis détection réelle si les poids
PP-OCR sont là.

    backend/venv/Scripts/python.exe backend/tests/test_images_document.py
"""
import io
import os
import time
import unittest
import zipfile

import racine  # noqa: F401
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services import images_document as module
from app.services.images_document import ImageDoc, analyser, detecter, lister, vignette

POLICE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts",
                      "montserrat-Regular.ttf")


def _png(image):
    sortie = io.BytesIO()
    image.save(sortie, "PNG")
    return sortie.getvalue()


def png_texte(mot="HELLO WORLD"):
    image = Image.new("RGB", (400, 140), "white")
    ImageDraw.Draw(image).text((20, 30), mot, fill="black", font=ImageFont.truetype(POLICE, 56))
    return _png(image)


def png_uni(cote=200, couleur=(205, 205, 205)):
    return _png(Image.new("RGB", (cote, cote), couleur))


TEXTE, UNI, MINUSCULE = png_texte(), png_uni(), png_uni(10)
EMF = b"\x01\x00\x00\x00factice"


def pdf_document():
    """3 pages de texte : logo sur les 3, uni sur la 2, minuscule sur la 1 ; page 4 scannée."""
    doc = fitz.open()
    xref = 0
    for n in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {n + 1} avec du texte courant.")
        xref = page.insert_image(fitz.Rect(72, 100, 272, 170), stream=TEXTE, xref=xref)
        if n == 0:
            page.insert_image(fitz.Rect(72, 300, 92, 320), stream=MINUSCULE)
        if n == 1:
            page.insert_image(fitz.Rect(72, 300, 272, 500), stream=UNI)
    scan = doc.new_page()
    scan.insert_image(scan.rect, stream=png_texte("SCAN"), keep_proportion=False)
    return doc.tobytes()


def _avec_emf(data, partie):
    """Ajoute une image vectorielle factice dans une archive Office."""
    sortie = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(sortie, "w") as dst:
        for e in src.infolist():
            dst.writestr(e, src.read(e))
        dst.writestr(partie, EMF)
    return sortie.getvalue()


def docx_document():
    from docx import Document
    doc = Document()
    doc.add_paragraph("Texte.")
    doc.add_picture(io.BytesIO(TEXTE))
    doc.add_picture(io.BytesIO(UNI))
    sortie = io.BytesIO()
    doc.save(sortie)
    return _avec_emf(sortie.getvalue(), "word/media/schema.emf")


def pptx_document():
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    for n in range(3):
        diapo = prs.slides.add_slide(prs.slide_layouts[6])
        if n < 2:
            diapo.shapes.add_picture(io.BytesIO(TEXTE), Inches(1), Inches(1))
        if n == 1:
            diapo.shapes.add_picture(io.BytesIO(UNI), Inches(1), Inches(3))
    sortie = io.BytesIO()
    prs.save(sortie)
    return _avec_emf(sortie.getvalue(), "ppt/media/schema.emf")


def xlsx_document():
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/media/image1.png", TEXTE)
        z.writestr("xl/media/image2.png", MINUSCULE)
        z.writestr("xl/media/schema.emf", EMF)
        z.writestr("xl/sharedStrings.xml", "<sst/>")
    return sortie.getvalue()


def par_cle(images):
    return {i.cle: i for i in images}


class Simule:
    """Lecteur simulé : une boîte si l'image n'est pas unie."""

    def __init__(self, manque=None, pause=0.0):
        self._manque, self.pause, self.appels = manque, pause, 0

    def manquant(self):
        return self._manque

    def detecter_image(self, image):
        self.appels += 1
        time.sleep(self.pause)
        return [object()] if float(np.std(image)) > 5 else []


class Lister(unittest.TestCase):
    def test_pdf(self):
        images = lister(pdf_document(), "pdf")
        self.assertEqual(len(images), 4)          # logo, uni, minuscule, scan
        logo = next(i for i in images if i.pages == [1, 2, 3])
        self.assertIsNone(logo.exclusion)
        self.assertTrue(logo.cle.startswith("xref:"))
        self.assertEqual((logo.largeur, logo.hauteur), (400, 140))
        self.assertIsNotNone(logo.octets)
        self.assertEqual(next(i for i in images if i.pages == [4]).exclusion, "scan")
        self.assertEqual(next(i for i in images if i.largeur == 10).exclusion, "petite")
        uni = next(i for i in images if i.pages == [2] and i.largeur == 200)
        self.assertIsNone(uni.exclusion)

    def test_docx(self):
        images = par_cle(lister(docx_document(), "docx"))
        self.assertEqual(set(images), {"word/media/image1.png", "word/media/image2.png",
                                       "word/media/schema.emf"})
        self.assertEqual(images["word/media/schema.emf"].exclusion, "vectorielle")
        self.assertIsNone(images["word/media/schema.emf"].octets)
        self.assertIsNone(images["word/media/image1.png"].exclusion)
        self.assertEqual(images["word/media/image1.png"].pages, [])

    def test_pptx(self):
        images = lister(pptx_document(), "pptx")
        logo = next(i for i in images if i.largeur == 400)
        uni = next(i for i in images if i.largeur == 200)
        self.assertEqual(logo.pages, [1, 2])
        self.assertEqual(uni.pages, [2])
        self.assertTrue(logo.cle.startswith("ppt/media/"))
        emf = next(i for i in images if i.cle.endswith(".emf"))
        self.assertEqual(emf.exclusion, "vectorielle")
        self.assertEqual(emf.pages, [])

    def test_xlsx(self):
        images = par_cle(lister(xlsx_document(), "xlsx"))
        self.assertEqual(set(images), {"xl/media/image1.png", "xl/media/image2.png",
                                       "xl/media/schema.emf"})
        self.assertIsNone(images["xl/media/image1.png"].exclusion)
        self.assertEqual(images["xl/media/image2.png"].exclusion, "petite")
        self.assertEqual(images["xl/media/schema.emf"].exclusion, "vectorielle")

    def test_refus(self):
        sortie = io.BytesIO()
        with zipfile.ZipFile(sortie, "w") as z:
            z.writestr("word/media/faux.png", b"ceci n'est pas une image")
        self.assertEqual(lister(sortie.getvalue(), "docx")[0].exclusion, "type")

    def test_invalides(self):
        with self.assertRaises(ValueError):
            lister(b"pas un zip", "docx")
        with self.assertRaises(ValueError):
            lister(b"pas un pdf", "pdf")
        self.assertEqual(lister(b"texte", "txt"), [])


class Detecter(unittest.TestCase):
    def setUp(self):
        module._CACHE.clear()

    def images(self):
        return [ImageDoc("a", octets=TEXTE), ImageDoc("b", octets=UNI),
                ImageDoc("c", exclusion="scan"), ImageDoc("d", octets=MINUSCULE, exclusion="petite")]

    def test_seules_les_images_a_texte(self):
        res = detecter(self.images(), Simule())
        self.assertEqual([i.cle for i in res.a_texte], ["a"])
        self.assertEqual(res.analysees, 2)
        self.assertEqual(len(res.images), 4)
        self.assertFalse(res.incomplet or res.indisponible)

    def test_lecteur_absent(self):
        res = detecter(self.images(), Simule(manque="programme"))
        self.assertTrue(res.indisponible)
        self.assertEqual(res.a_texte, [])

    def test_echeance(self):
        res = detecter(self.images(), Simule(), delai_s=0)
        self.assertTrue(res.incomplet)
        self.assertEqual(res.a_texte, [])
        lent = Simule(pause=0.3)
        res = detecter(self.images(), lent, delai_s=0.1)
        self.assertTrue(res.incomplet)
        self.assertEqual(lent.appels, 1)

    def test_exception_ignoree(self):
        images = [ImageDoc("a", octets=b"illisible"), ImageDoc("b", octets=TEXTE)]
        res = detecter(images, Simule())
        self.assertEqual([i.cle for i in res.a_texte], ["b"])


class Cache(unittest.TestCase):
    def setUp(self):
        module._CACHE.clear()

    def test_un_seul_appel(self):
        data, lecteur = docx_document(), Simule()
        premier = analyser(data, "docx", lecteur)
        appels = lecteur.appels
        self.assertGreater(appels, 0)
        second = analyser(data, "docx", lecteur)
        self.assertEqual(lecteur.appels, appels)
        self.assertIs(premier, second)
        self.assertEqual([i.cle for i in premier.a_texte], ["word/media/image1.png"])
        self.assertIsNotNone(premier.a_texte[0].octets)
        self.assertTrue(all(i.octets is None for i in premier.images if i not in premier.a_texte))

    def test_incomplet_ou_indisponible_non_memorises(self):
        data = docx_document()
        self.assertTrue(analyser(data, "docx", Simule(), delai_s=0).incomplet)
        self.assertTrue(analyser(data, "docx", Simule(manque="programme")).indisponible)
        self.assertEqual(module._CACHE, {})

    def test_borne(self):
        for n in range(module.CACHE_MAX + 3):
            analyser(str(n).encode(), "txt", Simule())
        self.assertEqual(len(module._CACHE), module.CACHE_MAX)


class Vignette(unittest.TestCase):
    def test_reduite(self):
        url = vignette(TEXTE)
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))
        import base64
        im = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        self.assertEqual(im.format, "JPEG")
        self.assertLessEqual(max(im.size), 160)


class Route(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from types import SimpleNamespace
        from app.api import translate as route
        from app.config import FRONTEND_API_KEY
        from app.core.security import require_auth
        cls.route, cls.cle = route, FRONTEND_API_KEY
        app = FastAPI()
        app.include_router(route.router)
        cls.anonyme = TestClient(app)
        connecte = FastAPI()
        connecte.include_router(route.router)
        connecte.dependency_overrides[require_auth] = lambda: SimpleNamespace(id=1, plan="free")
        cls.client = TestClient(connecte)
        cls.original = route.analyser_images
        route.analyser_images = lambda data, ext: analyser(data, ext, Simule())

    @classmethod
    def tearDownClass(cls):
        cls.route.analyser_images = cls.original

    def setUp(self):
        module._CACHE.clear()

    def envoyer(self, nom, data, cle=None, client=None):
        entetes = {"X-API-Key": self.cle if cle is None else cle}
        return (client or self.client).post("/api/translate/analyse", headers=entetes,
                                            files={"file": (nom, data)})

    def test_pdf(self):
        r = self.envoyer("doc.pdf", pdf_document())
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual((j["pages"], j["images"], j["analysees"], j["total"]), (4, 1, 2, 2))
        self.assertFalse(j["incomplet"] or j["indisponible"])
        ap = j["apercus"][0]
        self.assertEqual(ap["pages"], [1, 2, 3])
        self.assertEqual((ap["largeur"], ap["hauteur"]), (400, 140))
        self.assertTrue(ap["vignette"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(set(ap), {"cle", "pages", "largeur", "hauteur", "vignette"})

    def test_pptx(self):
        r = self.envoyer("deck.pptx", pptx_document())
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual((j["pages"], j["images"]), (3, 1))
        self.assertEqual(j["apercus"][0]["pages"], [1, 2])

    def test_txt_sans_analyse(self):
        r = self.envoyer("note.txt", b"Un peu de texte pour la page.")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["images"], r.json()["apercus"]), (0, []))

    def test_extension_refusee(self):
        self.assertEqual(self.envoyer("a.exe", b"x").status_code, 400)

    def test_paquet_corrompu(self):
        self.assertEqual(self.envoyer("a.docx", b"pas un zip").status_code, 400)
        self.assertEqual(self.envoyer("a.pdf", b"pas un pdf").status_code, 400)

    def test_sans_authentification(self):
        self.assertIn(self.envoyer("a.pdf", pdf_document(), client=self.anonyme).status_code, (401, 403))

    def test_cle_api(self):
        self.assertEqual(self.envoyer("a.pdf", pdf_document(), cle="mauvaise").status_code, 401)


class Reel(unittest.TestCase):
    def test_ppocr(self):
        from app.services.ocr_v2.ppocr import PPOCR
        lecteur = PPOCR()
        if lecteur.manquant():
            self.skipTest("poids PP-OCR absents")
        module._CACHE.clear()
        res = detecter([ImageDoc("texte", octets=TEXTE), ImageDoc("uni", octets=UNI)], lecteur)
        self.assertEqual([i.cle for i in res.a_texte], ["texte"])
        self.assertEqual(res.analysees, 2)
        res = analyser(docx_document(), "docx", lecteur)
        self.assertEqual([i.cle for i in res.a_texte], ["word/media/image1.png"])


if __name__ == "__main__":
    unittest.main()
