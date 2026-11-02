"""Redessin des aperçus des objets incorporés (6.11.4) — `engines/apercus.py`
et son branchement dans `incorpores.reinjecter`.

Un objet incorporé s'affiche par une IMAGE figée à sa création : traduire
l'objet ne change pas ce qu'on voit tant que l'image n'est pas refaite.

Ce que ce fichier verrouille :
  - PDF -> PNG : rogné à ce qui est peint, transparent ailleurs, pages
    empilées (un tableau et son graphique paginés ne se perdent pas), complété
    — jamais rogné — aux proportions du cadre ;
  - copie de rendu d'un classeur : zone visible (`oleSize`) en zone
    d'impression, autres feuilles masquées, une page, % explicite, octets
    stables (l'empreinte du cache en dépend) ;
  - redessin groupé : UN appel LibreOffice pour tous les objets, nouvel essai
    si rien n'est sorti, cache, règle D3 (page aux mauvaises proportions :
    aperçu d'origine gardé), rien sans LibreOffice ;
  - de bout en bout dans un PPTX : le nouveau PNG est posé, TOUTES les
    relations vers l'ancien aperçu (diapositive et dessin VML) le visent, le
    type PNG est déclaré ; une icône garde son image.

Tout est SYNTHÉTIQUE : LibreOffice est simulé (il « convertit » en un PDF
fabriqué), les fichiers sont fabriqués en mémoire.

Exécution :  PYTHONUTF8=1 <venv>/python.exe tests/test_ole_apercu.py
"""
from __future__ import annotations

import io
import os
import re
import unittest
import zipfile
from unittest import mock

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz  # noqa: E402
from lxml import etree  # noqa: E402
from PIL import Image  # noqa: E402

from engines import apercus as A  # noqa: E402
from engines import incorpores as I  # noqa: E402
from engines import office  # noqa: E402
from test_incorpores_recursion import (  # noqa: E402
    T_PACKAGE, greffer, partie_de, noms_de, reel_docx, reel_pptx, reel_xlsx, traduire)

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
T_IMAGE = R + "/image"


def pdf(pages: list[tuple[float, float]], formes=None) -> bytes:
    """PDF de pages (largeur, hauteur) ; une marque noire par page."""
    doc = fitz.open()
    for i, (l, h) in enumerate(pages):
        p = doc.new_page(width=l, height=h)
        rect = (formes or [None] * len(pages))[i] or fitz.Rect(50, 50, 300, 150)
        p.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))
    octets = doc.tobytes()
    doc.close()
    return octets


def image(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def faux_soffice(sortie_pdf: bytes | None = None, rate: int = 0):
    """Remplace `subprocess.run` : écrit un PDF par fichier dans --outdir.
    `rate` : nombre d'appels qui ne produisent rien (profil neuf)."""
    appels = []

    def run(cmd, **_kw):
        appels.append(cmd)
        if len(appels) <= rate:
            return None
        dossier = cmd[cmd.index("--outdir") + 1]
        for f in cmd[cmd.index("--outdir") + 2:]:
            nom = os.path.splitext(os.path.basename(f))[0] + ".pdf"
            with open(os.path.join(dossier, nom), "wb") as h:
                h.write(sortie_pdf if sortie_pdf is not None
                        else pdf([(842, 595)], [fitz.Rect(100, 100, 400, 250)]))
        return None
    return run, appels


class _AvecSoffice(unittest.TestCase):
    def setUp(self):
        A.vider_cache()
        self._p = mock.patch.object(office, "SOFFICE_PATH", "soffice")
        self._p.start()

    def tearDown(self):
        self._p.stop()
        A.vider_cache()


# --------------------------------------------------------------------------- #
# PDF -> PNG
# --------------------------------------------------------------------------- #

class RenduPng(unittest.TestCase):
    def test_deux_pages_empilees_rognees_transparentes(self):
        png, ratio = A.rendre_png(pdf([(595, 842), (595, 842)],
                                      [fitz.Rect(50, 50, 300, 150), fitz.Rect(90, 340, 210, 460)]))
        im = image(png)
        self.assertEqual(im.mode, "RGBA")
        # Deux morceaux : 100 pt + 120 pt de haut, plus les marges, à 150 dpi.
        self.assertGreater(im.height, (100 + 120) * 150 / 72)
        self.assertLess(im.height, (100 + 120) * 150 / 72 + 40)
        self.assertAlmostEqual(ratio, im.width / im.height, places=3)
        self.assertEqual(im.getpixel((0, 0))[3], 0, "marge transparente")
        self.assertEqual(im.getpixel((im.width // 2, 20))[3], 255, "contenu opaque")

    def test_premiere_page_seulement(self):
        deux = pdf([(595, 842), (595, 842)])
        h1 = image(A.rendre_png(deux, premiere_seulement=True)[0]).height
        h2 = image(A.rendre_png(deux)[0]).height
        self.assertLess(h1, h2)

    def test_complete_au_ratio_sans_rogner(self):
        brut = image(A.rendre_png(pdf([(595, 842)]))[0])
        for ratio in (2.33, 0.5):
            im = image(A.rendre_png(pdf([(595, 842)]), ratio_cible=ratio)[0])
            self.assertAlmostEqual(im.width / im.height, ratio, delta=0.02)
            self.assertGreaterEqual(im.width, brut.width)
            self.assertGreaterEqual(im.height, brut.height)
        large = image(A.rendre_png(pdf([(595, 842)]), ratio_cible=4)[0])
        self.assertEqual(large.getpixel((0, large.height // 2))[3], 0, "complément transparent")

    def test_page_vide_ou_pdf_illisible(self):
        doc = fitz.open()
        doc.new_page()
        self.assertIsNone(A.rendre_png(doc.tobytes()))
        self.assertIsNone(A.rendre_png(b"pas un pdf"))


# --------------------------------------------------------------------------- #
# Copie de rendu d'un classeur
# --------------------------------------------------------------------------- #

def classeur_a_imprimer() -> bytes:
    """Deux feuilles, la seconde active, zone visible B2:D5, un format %."""
    base = reel_xlsx(["Ventes", "Marge"], onglet="Synthèse d'été")
    with zipfile.ZipFile(io.BytesIO(base)) as z:
        parties = {n: z.read(n) for n in z.namelist()}
    parties["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{S}" xmlns:r="{R}"><bookViews><workbookView activeTab="1"/></bookViews>'
        '<sheets><sheet name="Brut" sheetId="1" r:id="rId3"/>'
        "<sheet name=\"Synthèse d'été\" sheetId=\"2\" r:id=\"rId1\"/></sheets>"
        '<oleSize ref="b2:D5"/></workbook>').encode()
    parties["xl/_rels/workbook.xml.rels"] = parties["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>", (f'<Relationship Id="rId3" Type="{R}/worksheet" '
                              'Target="worksheets/sheet2.xml"/></Relationships>').encode())
    parties["xl/worksheets/sheet2.xml"] = f'<worksheet xmlns="{S}"><sheetData/></worksheet>'.encode()
    parties["xl/worksheets/sheet1.xml"] = (
        f'<worksheet xmlns="{S}" xmlns:r="{R}"><sheetData/>'
        '<pageSetup orientation="portrait" r:id="rId9"/><drawing r:id="rId8"/></worksheet>').encode()
    parties["xl/styles.xml"] = (
        f'<styleSheet xmlns="{S}"><cellXfs count="2"><xf numFmtId="0"/>'
        '<xf numFmtId="9" applyNumberFormat="1"/></cellXfs></styleSheet>').encode()
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w") as z:
        for n, b in parties.items():
            z.writestr(n, b)
    return sortie.getvalue()


class CopieDeRendu(unittest.TestCase):
    def setUp(self):
        self.copie = A.copie_de_rendu_classeur(classeur_a_imprimer())
        self.parties = A._parties(self.copie)

    def test_zone_visible_en_zone_d_impression_de_la_feuille_active(self):
        cl = etree.fromstring(self.parties["xl/workbook.xml"])
        zone = cl.find(f"{{{S}}}definedNames/{{{S}}}definedName")
        self.assertEqual(zone.get("name"), "_xlnm.Print_Area")
        self.assertEqual(zone.get("localSheetId"), "1")
        self.assertEqual(zone.text, "'Synthèse d''été'!$B$2:$D$5")
        etats = [f.get("state") for f in cl.iter(f"{{{S}}}sheet")]
        self.assertEqual(etats, ["hidden", None])

    def test_une_page_sur_la_feuille_active_seulement(self):
        f = etree.fromstring(self.parties["xl/worksheets/sheet1.xml"])
        self.assertEqual(f.find(f"{{{S}}}sheetPr/{{{S}}}pageSetUpPr").get("fitToPage"), "1")
        ps = f.find(f"{{{S}}}pageSetup")
        self.assertEqual((ps.get("orientation"), ps.get("fitToWidth"), ps.get("fitToHeight"),
                          ps.get("paperSize")), ("landscape", "1", "1", "9"))
        self.assertIsNone(ps.get(f"{{{R}}}id"), "réglages imprimante retirés")
        ordre = [etree.QName(e).localname for e in f]
        self.assertLess(ordre.index("pageSetup"), ordre.index("drawing"))
        self.assertEqual(ordre[0], "sheetPr")
        self.assertNotIn(b"fitToPage", self.parties["xl/worksheets/sheet2.xml"])

    def test_pourcentage_explicite(self):
        st = etree.fromstring(self.parties["xl/styles.xml"])
        self.assertEqual([x.get("numFmtId") for x in st.iter(f"{{{S}}}xf")], ["0", "164"])
        fmt = st.find(f"{{{S}}}numFmts/{{{S}}}numFmt")
        self.assertEqual((fmt.get("numFmtId"), fmt.get("formatCode")), ("164", "0%"))
        self.assertEqual(etree.QName(st[0]).localname, "numFmts")

    def test_identifiants_de_format_libres(self):
        styles = (f'<styleSheet xmlns="{S}"><numFmts count="1"><numFmt numFmtId="190" '
                  'formatCode="dd/mm/yyyy"/></numFmts><cellXfs count="2"><xf numFmtId="190"/>'
                  '<xf numFmtId="9"/></cellXfs></styleSheet>').encode()
        st = etree.fromstring(A._pourcentages_explicites(styles))
        self.assertEqual([x.get("numFmtId") for x in st.iter(f"{{{S}}}xf")], ["190", "191"])
        ids = [f.get("numFmtId") for f in st.iter(f"{{{S}}}numFmt")]
        self.assertEqual(len(ids), len(set(ids)), "aucun identifiant en double")

    def test_octets_stables(self):
        self.assertEqual(self.copie, A.copie_de_rendu_classeur(classeur_a_imprimer()))

    def test_sans_olesize_ni_styles(self):
        p = A._parties(A.copie_de_rendu_classeur(reel_xlsx(["a"])))
        self.assertNotIn(b"Print_Area", p["xl/workbook.xml"])
        self.assertIn(b"fitToPage", p["xl/worksheets/sheet1.xml"])


# --------------------------------------------------------------------------- #
# Redessin groupé
# --------------------------------------------------------------------------- #

class Redessin(_AvecSoffice):
    def test_un_seul_appel_pour_tous_les_objets(self):
        run, appels = faux_soffice()
        demandes = [A.Demande("a", "xlsx", reel_xlsx(["x"]), 2.0),
                    A.Demande("b", "xlsx", reel_xlsx(["y"]), 1.0),
                    A.Demande("c", "docx", reel_docx(["z"]), None)]
        with mock.patch.object(A.subprocess, "run", run):
            r = A.redessiner(demandes)
        self.assertEqual(set(r), {"a", "b", "c"})
        self.assertEqual(len(appels), 1)
        self.assertEqual(len([a for a in appels[0] if a.endswith((".xlsx", ".docx"))]), 3)
        self.assertAlmostEqual(image(r["a"]).width / image(r["a"]).height, 2.0, delta=0.02)

    def test_nouvel_essai_si_le_profil_neuf_n_a_rien_converti(self):
        run, appels = faux_soffice(rate=1)
        with mock.patch.object(A.subprocess, "run", run):
            r = A.redessiner([A.Demande("a", "xlsx", reel_xlsx(["x"]), None)])
        self.assertEqual((len(appels), set(r)), (2, {"a"}))

    def test_cache_aucun_second_appel(self):
        run, appels = faux_soffice()
        d = A.Demande("a", "xlsx", reel_xlsx(["x"]), 1.5)
        with mock.patch.object(A.subprocess, "run", run):
            r1 = A.redessiner([d])
            r2 = A.redessiner([A.Demande("autre", d.type, d.octets, d.ratio)])
        self.assertEqual(len(appels), 1)
        self.assertEqual(r1["a"], r2["autre"])

    def test_d3_proportions_trop_eloignees_aperçu_d_origine(self):
        # Page portrait rendue pour un cadre très large : refusée (document).
        run, _ = faux_soffice(pdf([(595, 842)], [fitz.Rect(50, 50, 250, 450)]))
        with mock.patch.object(A.subprocess, "run", run):
            r = A.redessiner([A.Demande("doc", "docx", reel_docx(["z"]), 3.0),
                              A.Demande("pres", "pptx", reel_pptx("t"), 0.5)])
        self.assertEqual(set(r), {"pres"})

    def test_echec_de_rendu_non_mis_en_cache(self):
        run, appels = faux_soffice(b"pas un pdf")
        d = A.Demande("a", "xlsx", reel_xlsx(["x"]), 1.0)
        with mock.patch.object(A.subprocess, "run", run):
            self.assertEqual(A.redessiner([d]), {})
            A.redessiner([d])
        self.assertEqual(len(appels), 2, "retenté au passage suivant")

    def test_sans_libreoffice_rien(self):
        with mock.patch.object(office, "SOFFICE_PATH", None), \
                mock.patch.object(A.subprocess, "run", side_effect=AssertionError):
            self.assertEqual(A.redessiner([A.Demande("a", "xlsx", reel_xlsx(["x"]), 1.0)]), {})

    def test_libreoffice_en_echec_rien(self):
        with mock.patch.object(A.subprocess, "run", side_effect=OSError("absent")):
            self.assertEqual(A.redessiner([A.Demande("a", "xlsx", reel_xlsx(["x"]), 1.0)]), {})


# --------------------------------------------------------------------------- #
# De bout en bout dans un PPTX
# --------------------------------------------------------------------------- #

EMF = b"\x01\x00\x00\x00ancien-apercu"


def pptx_avec_apercu(icone: bool = False) -> bytes:
    """PPTX : un classeur incorporé, son aperçu EMF visé par la diapositive
    (blip) ET par un dessin VML."""
    hote = greffer(reel_pptx("Titre"), "ppt/slides/slide1.xml",
                   [("Feuille1.xlsx", "Excel.Sheet.12", reel_xlsx(["Bonjour", "Monde"]),
                     T_PACKAGE)])
    with zipfile.ZipFile(io.BytesIO(hote)) as z:
        ordre = z.namelist()
        p = {n: z.read(n) for n in ordre}
    pic = ('<p:pic><p:nvPicPr><p:cNvPr id="0" name=""/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
           '<p:blipFill><a:blip r:embed="rIdImg"/></p:blipFill><p:spPr/></p:pic>')
    xml = p["ppt/slides/slide1.xml"].decode().replace("<p:embed/></p:oleObj>",
                                                      "<p:embed/>" + pic + "</p:oleObj>")
    if icone:
        xml = xml.replace('progId="Excel.Sheet.12"', 'progId="Excel.Sheet.12" showAsIcon="1"')
    p["ppt/slides/slide1.xml"] = xml.encode()
    p["ppt/slides/_rels/slide1.xml.rels"] = p["ppt/slides/_rels/slide1.xml.rels"].replace(
        b"</Relationships>",
        f'<Relationship Id="rIdImg" Type="{T_IMAGE}" Target="../media/image9.emf"/>'
        "</Relationships>".encode())
    p["ppt/drawings/vmlDrawing1.vml"] = b"<xml/>"
    p["ppt/drawings/_rels/vmlDrawing1.vml.rels"] = (
        f'<Relationships xmlns="{PR}"><Relationship Id="rId1" Type="{T_IMAGE}" '
        'Target="../media/image9.emf"/></Relationships>').encode()
    p["ppt/media/image9.emf"] = EMF
    types = p["[Content_Types].xml"].decode()
    if 'Extension="emf"' not in types:
        types = re.sub(r"(<Types[^>]*>)", r'\1<Default Extension="emf" ContentType="image/x-emf"/>',
                       types, count=1)
    p["[Content_Types].xml"] = re.sub(r'<Default Extension="png"[^>]*/>', "", types).encode()
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for n in list(ordre) + [n for n in p if n not in ordre]:
            z.writestr(n, p[n])
    return sortie.getvalue()


def cible_rel(octets: bytes, rels: str, rid: str) -> tuple[str, str]:
    for e in etree.fromstring(partie_de(octets, rels)):
        if e.get("Id") == rid:
            return e.get("Target"), e.get("Type")
    raise KeyError(rid)


class BoutEnBout(_AvecSoffice):
    def test_pptx_apercu_redessine_et_toutes_les_relations_rebranchees(self):
        source = pptx_avec_apercu()
        objets = I.reperer(source)
        self.assertEqual(objets[0].apercu, "ppt/media/image9.emf")
        self.assertEqual(len(objets[0].relations_apercu), 2)
        run, appels = faux_soffice()
        with mock.patch.object(A.subprocess, "run", run):
            sortie, _ = traduire("pptx", source)
        self.assertGreaterEqual(len(appels), 1)
        noms = noms_de(sortie)
        self.assertIn("ppt/media/image9_traduit.png", noms)
        self.assertIn("ppt/media/image9.emf", noms, "ancien aperçu laissé (peut servir ailleurs)")
        self.assertEqual(cible_rel(sortie, "ppt/slides/_rels/slide1.xml.rels", "rIdImg"),
                         ("../media/image9_traduit.png", T_IMAGE))
        self.assertEqual(cible_rel(sortie, "ppt/drawings/_rels/vmlDrawing1.vml.rels", "rId1"),
                         ("../media/image9_traduit.png", T_IMAGE))
        self.assertIn(b'Extension="png"', partie_de(sortie, "[Content_Types].xml"))
        self.assertEqual(image(partie_de(sortie, "ppt/media/image9_traduit.png")).format, "PNG")

    def test_image_partagee_avec_un_objet_non_traduit(self):
        import dataclasses
        o = I.reperer(pptx_avec_apercu())[0]
        jumeau = dataclasses.replace(o, cible="ppt/embeddings/Copie.xlsx")
        modifs = I.Modifs()
        run, appels = faux_soffice()
        with mock.patch.object(A.subprocess, "run", run):
            I._redessiner_apercus(modifs, {o.cible: ("xlsx", reel_xlsx(["x"]))},
                                  [o], [o, jumeau], set())
        self.assertEqual((appels, modifs.parties, modifs.retouches), ([], {}, []))

    def test_icone_jamais_redessinee(self):
        run, appels = faux_soffice()
        with mock.patch.object(A.subprocess, "run", run):
            sortie, _ = traduire("pptx", pptx_avec_apercu(icone=True))
        self.assertEqual(appels, [])
        self.assertEqual(cible_rel(sortie, "ppt/slides/_rels/slide1.xml.rels", "rIdImg")[0],
                         "../media/image9.emf")

    def test_redessin_en_echec_aperçu_d_origine(self):
        with mock.patch.object(A.subprocess, "run", side_effect=OSError("absent")):
            sortie, _ = traduire("pptx", pptx_avec_apercu())
        self.assertEqual(cible_rel(sortie, "ppt/slides/_rels/slide1.xml.rels", "rIdImg")[0],
                         "../media/image9.emf")
        self.assertFalse(any(n.endswith(".png") for n in noms_de(sortie)
                             if n.startswith("ppt/media/image9")))


if __name__ == "__main__":
    unittest.main(verbosity=1)
