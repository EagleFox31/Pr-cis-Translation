"""Graphiques natifs (6.11.5) — `engines/incorpores.py`, moteurs PPTX et DOCX.

Ce que ce fichier verrouille :
  - dans un PPTX et un DOCX, le titre, les séries et les catégories d'un
    graphique sont traduits ;
  - le classeur caché du graphique est traduit, et les caches du graphique
    (`c:strCache`) sont égaux aux cellules du classeur traduit ;
  - les formules `c:f` suivent le nom d'onglet traduit ;
  - un graphique dont le classeur est LIÉ (fichier externe) n'est pas relevé
    comme objet : ses textes restent traduits par le moteur, une seule fois ;
  - la voie progressive du PPTX (diapositive par diapositive) aligne aussi.

Exécution :  PYTHONUTF8=1 <venv>/python.exe tests/test_incorpores_graphiques.py
"""
from __future__ import annotations

import io
import os
import posixpath
import re
import shutil
import tempfile
import unittest
import zipfile

import racine  # noqa: F401  -- met backend/ sur le chemin

from lxml import etree  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE  # noqa: E402
from pptx.util import Inches  # noqa: E402

from engines import incorpores as I  # noqa: E402
from engines.pptx.engine import PPTXTranslatorEngine  # noqa: E402
from test_incorpores_recursion import (  # noqa: E402
    PREFIXE_TRAD, marquer, paragraphes, reel_docx, relisible, traduire)

NC = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NA = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NP = "http://schemas.openxmlformats.org/package/2006/relationships"
RE_REF = re.compile(r"^(?:'((?:[^']|'')+)'|([^!]+))!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$")


# --------------------------------------------------------------------------- #
# Fabrication
# --------------------------------------------------------------------------- #

def reel_pptx_graphique() -> bytes:
    prs = Presentation()
    diapo = prs.slides.add_slide(prs.slide_layouts[5])
    diapo.shapes.title.text = "Résultats"
    donnees = CategoryChartData()
    donnees.categories = ["Nord", "Sud", "Est"]
    donnees.add_series("Ventes", (12, 30, 7))
    donnees.add_series("Achats", (4, 9, 15))
    forme = diapo.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.5),
                                   Inches(6), Inches(4), donnees)
    forme.chart.has_title = True
    forme.chart.chart_title.text_frame.text = "Bilan annuel"
    tampon = io.BytesIO()
    prs.save(tampon)
    return tampon.getvalue()


def parties_graphique(pptx: bytes) -> tuple[bytes, bytes, str]:
    """(XML du graphique, classeur caché, nom de partie du classeur) d'un PPTX."""
    with zipfile.ZipFile(io.BytesIO(pptx)) as zf:
        nom = next(n for n in zf.namelist() if re.match(r"ppt/charts/chart\d+\.xml$", n))
        rels = etree.fromstring(zf.read(posixpath.join(
            "ppt/charts/_rels", posixpath.basename(nom) + ".rels")))
        cible = next(r.get("Target") for r in rels if r.get("Type").endswith("/package"))
        chemin = posixpath.normpath(posixpath.join("ppt/charts", cible))
        return zf.read(nom), zf.read(chemin), posixpath.basename(chemin)


def docx_graphique(lie: bool = False) -> bytes:
    """DOCX avec un graphique natif greffé (XML et classeur pris d'un PPTX réel).
    `lie` : le classeur est un fichier externe (graphique lié)."""
    chart, classeur, nom_classeur = parties_graphique(reel_pptx_graphique())
    if lie:
        rel = ('<Relationship Id="rId1" Type="%s/oleObject" Target="file:///C:/x/%s" '
               'TargetMode="External"/>' % (NR, nom_classeur))
    else:
        rel = '<Relationship Id="rId1" Type="%s/package" Target="../embeddings/%s"/>' % (
            NR, nom_classeur)
    src = io.BytesIO(reel_docx(["Avant le graphique"]))
    sortie = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            donnees = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                donnees = donnees.replace(b"</Types>", (
                    '<Default Extension="xlsx" ContentType="application/vnd.openxmlformats-'
                    'officedocument.spreadsheetml.sheet"/>'
                    '<Override PartName="/word/charts/chart1.xml" ContentType="application/'
                    'vnd.openxmlformats-officedocument.drawingml.chart+xml"/></Types>').encode())
            elif item.filename == "word/_rels/document.xml.rels":
                donnees = donnees.replace(b"</Relationships>", (
                    '<Relationship Id="rIdGraph" Type="%s/chart" Target="charts/chart1.xml"/>'
                    "</Relationships>" % NR).encode())
            elif item.filename == "word/document.xml":
                dessin = (
                    '<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/'
                    'drawingml/2006/wordprocessingDrawing"><wp:extent cx="5486400" cy="3200400"/>'
                    '<wp:docPr id="99" name="Graphique 1"/><a:graphic xmlns:a="%s">'
                    '<a:graphicData uri="%s"><c:chart xmlns:c="%s" xmlns:r="%s" r:id="rIdGraph"/>'
                    "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
                    % (NA, NC, NC, NR))
                donnees = re.sub(rb"(<w:sectPr)", dessin.encode() + rb"\1", donnees, count=1)
            zout.writestr(item, donnees)
        zout.writestr("word/charts/chart1.xml", chart)
        zout.writestr("word/charts/_rels/chart1.xml.rels",
                      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                      '<Relationships xmlns="%s">%s</Relationships>' % (NP, rel))
        if not lie:
            zout.writestr("word/embeddings/" + nom_classeur, classeur)
    return sortie.getvalue()


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #

def valeurs_classeur(octets: bytes) -> dict[tuple[str, str], str]:
    """{(onglet, réf. cellule): texte} des cellules texte d'un classeur."""
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        noms = zf.namelist()
        partagees = []
        if "xl/sharedStrings.xml" in noms:
            for si in etree.fromstring(zf.read("xl/sharedStrings.xml")).iter(f"{{{NS}}}si"):
                partagees.append("".join(t.text or "" for t in si.iter(f"{{{NS}}}t")))
        classeur = etree.fromstring(zf.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target") for r in etree.fromstring(
            zf.read("xl/_rels/workbook.xml.rels"))}
        resultat = {}
        for f in classeur.iter(f"{{{NS}}}sheet"):
            cible = rels[f.get(f"{{{NR}}}id")].lstrip("/")
            cible = cible if cible.startswith("xl/") else "xl/" + cible
            for c in etree.fromstring(zf.read(cible)).iter(f"{{{NS}}}c"):
                if c.get("t") == "s":
                    resultat[(f.get("name"), c.get("r"))] = partagees[int(c.findtext(f"{{{NS}}}v"))]
                elif c.get("t") in ("inlineStr", "str"):
                    resultat[(f.get("name"), c.get("r"))] = "".join(
                        t.text or "" for t in c.iter(f"{{{NS}}}t")) or c.findtext(f"{{{NS}}}v")
        return resultat


def _lettres(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def _col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def refs_et_caches(chart_xml: bytes) -> list[tuple[str, list[tuple[str, str]], list[str]]]:
    """[(formule, [(onglet, cellule)] des points, textes du cache)] des c:strRef."""
    sortie = []
    for ref in etree.fromstring(chart_xml).iter(f"{{{NC}}}strRef"):
        f = ref.findtext(f"{{{NC}}}f")
        m = RE_REF.match(f)
        onglet = (m.group(1) or "").replace("''", "'") or m.group(2)
        c1, l1 = _lettres(m.group(3)), int(m.group(4))
        c2, l2 = (_lettres(m.group(5)), int(m.group(6))) if m.group(5) else (c1, l1)
        largeur = c2 - c1 + 1
        cellules, textes = [], []
        for pt in ref.iter(f"{{{NC}}}pt"):
            ligne, col = divmod(int(pt.get("idx")), largeur)
            cellules.append((onglet, f"{_col(c1 + col)}{l1 + ligne}"))
            textes.append(pt.findtext(f"{{{NC}}}v"))
        sortie.append((f, cellules, textes))
    return sortie


def titre(chart_xml: bytes) -> str:
    racine_ = etree.fromstring(chart_xml)
    t = racine_.find(f"{{{NC}}}chart/{{{NC}}}title")
    return "".join(x.text or "" for x in t.iter(f"{{{NA}}}t"))


def graphique_de(octets: bytes, dossier: str) -> tuple[bytes, bytes]:
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        nom = next(n for n in zf.namelist() if re.match(dossier + r"/charts/chart\d+\.xml$", n))
        rels = etree.fromstring(zf.read(posixpath.join(
            dossier, "charts/_rels", posixpath.basename(nom) + ".rels")))
        cible = next(r.get("Target") for r in rels if r.get("Type").endswith("/package"))
        return zf.read(nom), zf.read(posixpath.normpath(posixpath.join(dossier, "charts", cible)))


# --------------------------------------------------------------------------- #

class Alignement(unittest.TestCase):
    def verifier(self, chart: bytes, classeur: bytes):
        self.assertTrue(titre(chart).startswith(PREFIXE_TRAD), titre(chart))
        cellules = valeurs_classeur(classeur)
        refs = refs_et_caches(chart)
        self.assertEqual(len(refs), 4, refs)          # 2 noms de séries + 2 x catégories
        for f, points, textes in refs:
            self.assertIn("EN Sheet1", f)
            self.assertTrue(points)
            for cle, texte in zip(points, textes):
                self.assertIn(cle, cellules, (f, cle))
                self.assertEqual(texte, cellules[cle], (f, cle))
                self.assertTrue(texte.startswith(PREFIXE_TRAD), texte)
        tous = {t for _, _, ts in refs for t in ts}
        for mot in ("Nord", "Sud", "Est", "Ventes", "Achats"):
            self.assertIn(PREFIXE_TRAD + mot, tous)

    def test_pptx(self):
        sortie, _ = traduire("pptx", reel_pptx_graphique())
        relisible("pptx", sortie)
        self.verifier(*graphique_de(sortie, "ppt"))

    def test_cellule_non_traduite_ne_fait_pas_foi(self):
        """Une cellule que la traduction du classeur n'a pas changée ne remet
        pas la langue source dans un cache déjà traduit."""
        from lxml import etree
        chart, classeur = graphique_de(reel_pptx_graphique(), "ppt")
        racine = etree.fromstring(chart)
        v = racine.find(".//{%s}strCache/{%s}pt/{%s}v" % ((I.NS["c"],) * 3))
        v.text = "deja traduit"
        self.assertFalse(I._aligner_graphique(racine, classeur, classeur))
        self.assertEqual(v.text, "deja traduit")

    def test_docx(self):
        sortie, data = traduire("docx", docx_graphique())
        relisible("docx", sortie)
        # Les caches liés au classeur ne sont pas relevés par le moteur DOCX.
        textes = [e["text"] for e in data["document"]["charts"]]
        self.assertTrue(any("Bilan annuel" in t for t in textes), textes)
        self.assertFalse(any("Nord" in t for t in textes), textes)
        self.assertTrue(data["objets"])
        self.verifier(*graphique_de(sortie, "word"))
        self.assertEqual(paragraphes(sortie), [PREFIXE_TRAD + "Avant le graphique"])

    def test_docx_lie(self):
        octets = docx_graphique(lie=True)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = os.path.join(tmp, "lie.docx")
            with open(src, "wb") as f:
                f.write(octets)
            self.assertFalse([o for o in I.reperer(src) if o.graphique])
        sortie, data = traduire("docx", octets)
        textes = [e["text"] for e in data["document"]["charts"]]
        # Sans classeur incorporé, les caches sont traduits par le moteur.
        self.assertTrue(any("Nord" in t for t in textes), textes)
        with zipfile.ZipFile(io.BytesIO(sortie)) as zf:
            chart = zf.read("word/charts/chart1.xml")
        caches = {t for _, _, ts in refs_et_caches(chart) for t in ts}
        self.assertIn(PREFIXE_TRAD + "Nord", caches)
        self.assertNotIn("Nord", caches)

    def test_pptx_progressif(self):
        octets = reel_pptx_graphique()
        dossier = tempfile.mkdtemp(prefix="graph_pptx_")
        try:
            src = os.path.join(dossier, "src.pptx")
            with open(src, "wb") as f:
                f.write(octets)
            eng = PPTXTranslatorEngine()
            try:
                eng._cleanup_temp()
                eng._extract_zip(src)
                sd, _ = eng.extract_slide(1)
                carte = {el["id"]: marquer(el["text"], el["id"]) for el in I._elements_de(sd)}
                self.assertTrue(sd["excel_elements"])
                eng.inject_slide(1, carte)
                final = os.path.join(dossier, "final.pptx")
                eng.build_partial_pptx(final, 1)
            finally:
                eng._cleanup_temp()
            with open(final, "rb") as f:
                sortie = f.read()
            relisible("pptx", sortie)
            self.verifier(*graphique_de(sortie, "ppt"))
        finally:
            shutil.rmtree(dossier, ignore_errors=True)


class ApercuFeuilleGraphique(unittest.TestCase):
    def test_pas_de_zone_d_impression(self):
        """Feuille active = feuille graphique : la copie de rendu n'y pose ni
        zone d'impression ni mise en page de feuille de calcul."""
        from engines import apercus
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as zf:
            zf.writestr("xl/workbook.xml",
                        '<workbook xmlns="%s" xmlns:r="%s"><bookViews><workbookView activeTab="0"/>'
                        '</bookViews><sheets><sheet name="Graph1" sheetId="1" r:id="rId1"/></sheets>'
                        '<oleSize ref="A1:H20"/></workbook>' % (NS, NR))
            zf.writestr("xl/_rels/workbook.xml.rels",
                        '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%s/chartsheet" '
                        'Target="chartsheets/sheet1.xml"/></Relationships>' % (NP, NR))
            feuille = '<chartsheet xmlns="%s"><sheetViews><sheetView workbookViewId="0"/></sheetViews></chartsheet>' % NS
            zf.writestr("xl/chartsheets/sheet1.xml", feuille)
        copie = apercus.copie_de_rendu_classeur(tampon.getvalue())
        with zipfile.ZipFile(io.BytesIO(copie)) as zf:
            self.assertNotIn(b"Print_Area", zf.read("xl/workbook.xml"))
            self.assertEqual(zf.read("xl/chartsheets/sheet1.xml"), feuille.encode())


if __name__ == "__main__":
    unittest.main(verbosity=1)
