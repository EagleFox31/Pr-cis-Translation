"""Images d'un document qui contiennent du texte (étude images-documents §5, étape 6.8.1).

Documents générés en mémoire (PDF, DOCX, PPTX, XLSX) : liste des images
distinctes et exclusions, détection par un lecteur simulé (échéance, cache),
route d'analyse sans base de données, puis détection réelle si les poids
PP-OCR sont là.

    backend/venv/Scripts/python.exe backend/tests/test_images_document.py
"""
import io
import os
import shutil
import tempfile
import time
import unittest
import unittest.mock
import zipfile

import racine  # noqa: F401
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services import images_document as module
from app.services.images_document import (Analyse, ImageDoc, analyser, detecter, lister,
                                          vignette)
from app.services.ocr_v2.image import Bloc, ImageTraduite

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


# ── Pose des images traduites (étape 6.8.2) ──────────────────────────────────

NOUVELLE = png_texte("BONJOUR")


def a_texte_sans_lecteur(data, ext):
    """Analyse sans lecteur OCR : les images de 400 px de large portent du texte."""
    images = lister(data, ext)
    return Analyse(images=images, a_texte=[i for i in images
                                           if i.exclusion is None and i.largeur == 400])


class FauxTraducteur:
    """Remplace `traduire_image` : retient les images reçues, rend NOUVELLE."""

    def __init__(self, remplacee=True, erreur=None):
        self.recus, self.remplacee, self.erreur = [], remplacee, erreur

    def __call__(self, octets, traduire, **_):
        self.recus.append(octets)
        if self.erreur:
            raise self.erreur
        return ImageTraduite(NOUVELLE, "image/png",
                             [Bloc("a", (0, 0, 1, 1), remplace=self.remplacee)])


def trois_images():
    return Analyse(a_texte=[ImageDoc(cle, octets=png_texte(mot))
                            for cle, mot in (("a", "AAA"), ("b", "BBB"), ("c", "CCC"))])


def entrees(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return [(e.filename, e.compress_type, z.read(e)) for e in z.infolist()]


class PoserOffice(unittest.TestCase):
    def test_partie_remplacee_reste_inchange(self):
        for data, partie in ((docx_document(), "word/media/image1.png"),
                             (pptx_document(), next(i.cle for i in lister(pptx_document(), "pptx")
                                                    if i.largeur == 400))):
            sortie = module.poser_office(data, {partie: NOUVELLE})
            avant, apres = entrees(data), entrees(sortie)
            self.assertEqual([e[:2] for e in avant], [e[:2] for e in apres])    # ordre, compression
            for (nom, _, a), (_, _, b) in zip(avant, apres):
                if nom == partie:
                    self.assertEqual(b, NOUVELLE)
                else:
                    self.assertEqual(a, b, nom)
            with zipfile.ZipFile(io.BytesIO(sortie)) as z:
                self.assertIsNone(z.testzip())

    def test_table_vide_ou_inconnue_octets_identiques(self):
        data = docx_document()
        self.assertEqual(module.poser_office(data, {}), data)
        self.assertEqual(module.poser_office(data, {"word/media/absente.png": NOUVELLE}), data)


class TraduireImages(unittest.TestCase):
    def setUp(self):
        self.dossier = os.path.join(tempfile.mkdtemp(prefix="imgdoc_"), "images")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.dossier), True)

    def lancer(self, faux, budget=None, analyse=None):
        with unittest.mock.patch.object(module.ocr_image, "traduire_image", faux):
            return module.traduire_images(b"", "docx", lambda t: t, self.dossier, budget,
                                          analyse or trois_images())

    def test_toutes_remplacees(self):
        faux = FauxTraducteur()
        table, rapport = self.lancer(faux)
        self.assertEqual(set(table), {"a", "b", "c"})
        self.assertEqual(table["a"], NOUVELLE)
        self.assertEqual(rapport, {"proposees": 3, "traduites": 3, "inchangees": 0,
                                   "sans_credit": 0, "echecs": 0})

    def test_budget_sans_credit(self):
        faux = FauxTraducteur()
        table, rapport = self.lancer(faux, budget=2)
        self.assertEqual(len(table), 2)
        self.assertEqual((rapport["traduites"], rapport["sans_credit"]), (2, 1))
        self.assertEqual(len(faux.recus), 2)                  # la 3e n'est pas lue
        faux = FauxTraducteur()
        table, rapport = self.lancer(faux, budget=0)
        self.assertEqual((table, faux.recus, rapport["sans_credit"]), ({}, [], 3))

    def test_exception_est_un_echec_d_image(self):
        table, rapport = self.lancer(FauxTraducteur(erreur=RuntimeError("lecture")))
        self.assertEqual(table, {})
        self.assertEqual((rapport["echecs"], rapport["traduites"]), (3, 0))

    def test_octets_absents_est_un_echec(self):
        faux = FauxTraducteur()
        table, rapport = self.lancer(faux, analyse=Analyse(a_texte=[ImageDoc("x")]))
        self.assertEqual((table, rapport["echecs"], faux.recus), ({}, 1, []))

    def test_non_remplacee_est_inchangee(self):
        table, rapport = self.lancer(FauxTraducteur(remplacee=False))
        self.assertEqual(table, {})
        self.assertEqual((rapport["inchangees"], rapport["traduites"], rapport["echecs"]), (3, 0, 0))

    def test_cache_disque(self):
        premier = FauxTraducteur()
        table1, _ = self.lancer(premier)
        second = FauxTraducteur()
        table2, rapport = self.lancer(second)
        self.assertEqual(len(premier.recus), 3)
        self.assertEqual(second.recus, [])                    # tout vient du cache
        self.assertEqual(table2, table1)
        self.assertEqual(rapport["traduites"], 3)

    def test_cache_garde_les_non_remplacees(self):
        self.lancer(FauxTraducteur(remplacee=False))
        second = FauxTraducteur()
        table, rapport = self.lancer(second)
        self.assertEqual((table, second.recus, rapport["inchangees"]), ({}, [], 3))

    def test_document_reel(self):
        faux = FauxTraducteur()
        data = docx_document()
        with unittest.mock.patch.object(module.ocr_image, "traduire_image", faux):
            table, rapport = module.traduire_images(
                data, "docx", lambda t: t, self.dossier, None, a_texte_sans_lecteur(data, "docx"))
        self.assertEqual(list(table), ["word/media/image1.png"])
        self.assertEqual(rapport["proposees"], 1)


class TableDisque(unittest.TestCase):
    def setUp(self):
        self.racine = tempfile.mkdtemp(prefix="imgtab_")
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.trad = os.path.join(self.racine, "translated_fr.json")

    def test_aller_retour(self):
        table = {"word/media/image1.png": NOUVELLE, "xref:12": TEXTE}
        module.ecrire_table(self.trad, table, {"traduites": 2})
        self.assertEqual(module.charger_table(self.trad), table)
        self.assertTrue(module.chemin_table(self.trad).endswith("translated_fr.json.images.json"))

    def test_reecriture_efface_les_restes(self):
        module.ecrire_table(self.trad, {"a": NOUVELLE, "b": TEXTE}, {})
        module.ecrire_table(self.trad, {"a": NOUVELLE}, {})
        self.assertEqual(module.charger_table(self.trad), {"a": NOUVELLE})
        self.assertEqual(len(os.listdir(self.trad + ".images")), 1)

    def test_absente_ou_illisible(self):
        self.assertEqual(module.charger_table(self.trad), {})
        with open(module.chemin_table(self.trad), "w") as f:
            f.write("{pas du json")
        self.assertEqual(module.charger_table(self.trad), {})

    def test_image_manquante_garde_les_autres(self):
        module.ecrire_table(self.trad, {"a": NOUVELLE, "b": TEXTE}, {})
        dossier = self.trad + ".images"
        os.remove(os.path.join(dossier, sorted(os.listdir(dossier))[0]))
        self.assertEqual(len(module.charger_table(self.trad)), 1)


class PdfImages(unittest.TestCase):
    """Substitution par xref dans le rendu PDF (mode structure, sans traduction)."""

    @staticmethod
    def pdf():
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Texte de la page.")
        xref = page.insert_image(fitz.Rect(72, 100, 272, 170), stream=TEXTE)
        return doc.tobytes(), xref

    def rendre(self, images):
        from engines.pdf import stream
        tmp = tempfile.mkdtemp(prefix="imgpdf_")
        self.addCleanup(shutil.rmtree, tmp, True)
        data, xref = self.pdf()
        src = os.path.join(tmp, "original.pdf")
        with open(src, "wb") as f:
            f.write(data)
        sortie = os.path.join(tmp, "sortie.pdf")
        stream.translate_pdf_progressive(
            src, sortie, debug=True, cache_path=os.path.join(tmp, "pages_debug.json"),
            images=images(xref) if callable(images) else images)
        with fitz.open(sortie) as d:
            pixels = d[0].get_pixmap(dpi=72).samples
            images_sortie = [np.array(Image.open(io.BytesIO(d.extract_image(i[0])["image"])).convert("RGB"))
                             for i in d[0].get_images(full=True)]
        return pixels, images_sortie

    def test_image_remplacee_par_xref(self):
        pixels, images = self.rendre(lambda x: {f"xref:{x}": NOUVELLE})
        voulu = np.array(Image.open(io.BytesIO(NOUVELLE)).convert("RGB"))
        self.assertTrue(any(i.shape == voulu.shape and np.array_equal(i, voulu) for i in images))
        sans, _ = self.rendre(None)
        self.assertNotEqual(pixels, sans)

    def test_sans_table_image_d_origine(self):
        original = np.array(Image.open(io.BytesIO(TEXTE)).convert("RGB"))
        for table in (None, {}):
            _, images = self.rendre(table)
            self.assertTrue(any(i.shape == original.shape and np.array_equal(i, original)
                                for i in images))

    def test_cle_inconnue_ignoree(self):
        sans, _ = self.rendre(None)
        pixels, _ = self.rendre({"xref:99999": NOUVELLE, "word/media/x.png": NOUVELLE})
        self.assertEqual(pixels, sans)


if __name__ == "__main__":
    unittest.main()
