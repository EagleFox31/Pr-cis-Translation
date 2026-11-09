"""Couche de texte d'un scan (OCR v2, étude §7.1).

Un PDF natif de style connu (police, corps, gras, italique) est rendu en image,
« scanné » (teinte du papier, éclairage, flou, bruit, JPEG), puis réécrit par
`render.ecrire` à partir des boîtes de ses mots : on retrouve son style.

    backend/venv/Scripts/python.exe backend/tests/test_ocr_v2_rendu.py
"""
import os
import time
import unittest

import racine  # noqa: F401
import cv2
import fitz
import numpy as np
from app.services.ocr_v2 import render
from app.services.ocr_v2.detect import Mot

DPI = 200
DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
CORPS = ("Le rapport annuel présente les résultats obtenus par chaque service au cours de "
         "l'exercice écoulé. Les montants indiqués tiennent compte des ajustements validés "
         "lors de la dernière réunion du comité, ainsi que des prévisions établies pour "
         "le prochain trimestre. Chaque responsable dispose d'un délai de quinze jours "
         "pour transmettre ses observations écrites.")


def natif(famille):
    """Page A4 : titre gras 16 pt, paragraphe 11 pt avec un mot gras, ligne italique 11 pt."""
    doc = fitz.open()
    page = doc.new_page()
    f = {s: os.path.join(DOSSIER, f"{famille}-{s}.ttf") for s in ("Regular", "Bold", "Italic")}
    for s, p in f.items():
        page.insert_font(fontname=s, fontfile=p)
    page.insert_text((72, 90), "Bilan général des activités", fontname="Bold", fontsize=16)
    y, ligne = 130, ""
    largeur = fitz.Font(fontfile=f["Regular"])
    for mot in CORPS.split():
        essai = f"{ligne} {mot}".strip()
        if largeur.text_length(essai, 11) > 450:
            page.insert_text((72, y), ligne, fontname="Regular", fontsize=11)
            y, ligne = y + 15, mot
        else:
            ligne = essai
    page.insert_text((72, y), ligne, fontname="Regular", fontsize=11)
    x = 72 + largeur.text_length("Montant total : ", 11)
    page.insert_text((72, y + 15), "Montant total :", fontname="Regular", fontsize=11)
    page.insert_text((x, y + 15), "important", fontname="Bold", fontsize=11)
    page.insert_text((72, y + 45), "Document établi pour usage interne seulement.",
                     fontname="Italic", fontsize=11)
    return doc


def scanner(page, angle=0.0, seed=0):
    rng = np.random.default_rng(seed)
    pix = page.get_pixmap(dpi=DPI, colorspace=fitz.csRGB, alpha=False)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3)[:, :, ::-1]
    h, w = img.shape[:2]
    f = img.astype(np.float32) * np.array([0.90, 0.94, 0.97])
    yy, xx = np.mgrid[0:h, 0:w]
    f *= (0.94 + 0.06 * np.cos(xx / w * 2.5) * np.cos(yy / h * 1.7))[..., None]
    f = cv2.GaussianBlur(f, (0, 0), 0.8)
    if angle:
        f = cv2.warpAffine(f, cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1), (w, h),
                           borderValue=(225, 232, 238))
    f += rng.normal(0, 3, f.shape)
    _, jpg = cv2.imencode(".jpg", np.clip(f, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR)


def mots(page):
    """Boîtes des mots du natif, resserrées sur l'encre comme celles d'un lecteur OCR."""
    S = DPI / 72
    out = []
    for x0, y0, x1, y1, t, b, l, _ in page.get_text("words"):
        out.append(Mot(t, (int(x0 * S), int(y0 * S), int((x1 - x0) * S) + 1, int((y1 - y0) * S) + 1),
                       95.0, (b, l)))
    return out


def relire(famille):
    doc = natif(famille)
    bgr = scanner(doc[0])
    sortie = fitz.open()
    cible = sortie.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
    debut = time.monotonic()
    nom = render.ecrire(cible, bgr, mots(doc[0]), DPI)
    duree = time.monotonic() - debut
    spans = [s for b in cible.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]
             if s["text"].strip()]
    return nom, spans, duree


class Rendu(unittest.TestCase):
    def verifier(self, famille, attendu):
        nom, spans, duree = relire(famille)
        print(f"{famille}: {nom}, {duree:.1f} s")
        self.assertEqual(nom, attendu)
        titre = [s for s in spans if "Bilan" in s["text"]][0]
        self.assertEqual(titre["size"], 16)
        self.assertTrue(titre["flags"] & fitz.TEXT_FONT_BOLD or "Bold" in titre["font"])
        corps = [s for s in spans if "rapport" in s["text"]][0]
        self.assertEqual(corps["size"], 11)
        self.assertNotIn("Bold", corps["font"])
        gras = [s for s in spans if "important" in s["text"]][0]
        self.assertIn("Bold", gras["font"])
        self.assertNotIn("Montant", gras["text"])
        ital = [s for s in spans if "interne" in s["text"]][0]
        self.assertIn("Italic", ital["font"])
        self.assertEqual(ital["size"], 11)
        # Le texte écrit couvre la largeur lue : une ligne pleine finit au même bord.
        self.assertLess(abs(corps["bbox"][0] - 72), 1.5)

    def test_roboto(self):
        self.verifier("roboto", "Roboto")

    def test_pt_serif(self):
        self.verifier("ptserif", "PT Serif")

    def test_redressement(self):
        bgr = scanner(natif("roboto")[0], angle=0.6)
        droit, angle = render.redresser(bgr)
        self.assertAlmostEqual(angle, -0.6, delta=0.1)
        self.assertEqual(droit.shape, bgr.shape)
        self.assertEqual(render.redresser(scanner(natif("roboto")[0]))[1], 0.0)


if __name__ == "__main__":
    unittest.main()
