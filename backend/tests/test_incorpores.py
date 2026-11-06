"""Repérage des objets incorporés (6.11.1) — `engines/incorpores.py`.

Ce que ce fichier verrouille, pour chacun des trois conteneurs :
  - chaque objet est trouvé, avec sa nature (classeur, document, présentation,
    paquet), son format (OOXML ou OLE2), l'icône et le lien ;
  - l'aperçu et le ratio du cadre sont lus au bon endroit ;
  - TOUTES les relations qui pointent vers l'aperçu sont relevées, y compris
    celles de la branche VML que PowerPoint et Excel affichent réellement ;
  - les objets liés ne sont jamais suivis et apparaissent au compte rendu ;
  - un paquet illisible ou inconnu donne une liste vide, sans exception ;
  - rien n'est modifié.

Tout est SYNTHÉTIQUE : les paquets sont écrits à la main dans un zip.

Exécution :  PYTHONUTF8=1 <venv>/python.exe tests/test_incorpores.py
"""
from __future__ import annotations

import io
import unittest
import zipfile

import racine  # noqa: F401  -- met backend/ sur le chemin

from engines import incorpores  # noqa: E402

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
T_PACKAGE = R + "/package"
T_OLE = R + "/oleObject"
T_IMAGE = R + "/image"
T_VML = R + "/vmlDrawing"


def rels(*items):
    corps = "".join(
        '<Relationship Id="%s" Type="%s" Target="%s"%s/>'
        % (i, t, c, ' TargetMode="External"' if ext else "")
        for i, t, c, ext in ((x + (False,))[:4] for x in items))
    return ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns='
            '"http://schemas.openxmlformats.org/package/2006/relationships">'
            + corps + "</Relationships>")


def paquet(parties: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nom, contenu in parties.items():
            zf.writestr(nom, contenu)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
PPTX_SLIDE = """<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="%s"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"><p:cSld><p:spTree>
 <p:graphicFrame><p:xfrm><a:off x="0" y="0"/><a:ext cx="4000000" cy="2000000"/></p:xfrm>
  <a:graphic><a:graphicData><mc:AlternateContent>
   <mc:Choice Requires="v"><p:oleObj spid="_x0000_s1025" name="Feuille" r:id="rId2"
     progId="Excel.Sheet.12"><p:embed/></p:oleObj></mc:Choice>
   <mc:Fallback><p:oleObj name="Feuille" r:id="rId2" progId="Excel.Sheet.12"><p:embed/>
     <p:pic><p:blipFill><a:blip r:embed="rId3"/></p:blipFill></p:pic></p:oleObj></mc:Fallback>
  </mc:AlternateContent></a:graphicData></a:graphic></p:graphicFrame>
 <p:graphicFrame><p:xfrm><a:off x="0" y="0"/><a:ext cx="3000000" cy="3000000"/></p:xfrm>
  <a:graphic><a:graphicData><p:oleObj r:id="rId4" progId="Word.Document.12" showAsIcon="1">
   <p:embed/><p:pic><p:blipFill><a:blip r:embed="rId5"/></p:blipFill></p:pic></p:oleObj>
  </a:graphicData></a:graphic></p:graphicFrame>
 <p:graphicFrame><p:xfrm><a:off x="0" y="0"/><a:ext cx="1000000" cy="500000"/></p:xfrm>
  <a:graphic><a:graphicData><p:oleObj spid="_x0000_s1027" r:id="rId6" progId="PowerPoint.Show.8">
   <p:embed/></p:oleObj></a:graphicData></a:graphic></p:graphicFrame>
 <p:graphicFrame><p:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></p:xfrm>
  <a:graphic><a:graphicData><p:oleObj r:id="rId7" progId="Excel.Sheet.12">
   <p:link updateAutomatic="1"/></p:oleObj></a:graphicData></a:graphic></p:graphicFrame>
</p:spTree></p:cSld></p:sld>""" % R

PPTX_VML = """<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
 <v:shape id="_x0000_s1025"><v:imagedata o:relid="rId1"/></v:shape>
 <v:shape id="_x0000_s1027"><v:imagedata o:relid="rId2"/></v:shape></xml>"""


def pptx() -> bytes:
    return paquet({
        "[Content_Types].xml": "<Types/>",
        "ppt/presentation.xml": "<p/>",
        "ppt/slides/slide1.xml": PPTX_SLIDE,
        "ppt/slides/_rels/slide1.xml.rels": rels(
            ("rId1", T_VML, "../drawings/vmlDrawing1.vml"),
            ("rId2", T_PACKAGE, "../embeddings/Microsoft_Excel_Worksheet.xlsx"),
            ("rId3", T_IMAGE, "../media/image1.emf"),
            ("rId4", T_PACKAGE, "../embeddings/Microsoft_Word_Document.docx"),
            ("rId5", T_IMAGE, "../media/image2.emf"),
            ("rId6", T_OLE, "../embeddings/oleObject1.bin"),
            ("rId7", T_OLE, "file:///C:/budget.xlsx", True)),
        "ppt/drawings/vmlDrawing1.vml": PPTX_VML,
        "ppt/drawings/_rels/vmlDrawing1.vml.rels": rels(
            ("rId1", T_IMAGE, "../media/image1.emf"),
            ("rId2", T_IMAGE, "../media/image3.emf")),
        "ppt/embeddings/Microsoft_Excel_Worksheet.xlsx": b"PK",
        "ppt/embeddings/Microsoft_Word_Document.docx": b"PK",
        "ppt/embeddings/oleObject1.bin": b"\xd0\xcf",
        "ppt/media/image1.emf": b"e", "ppt/media/image2.emf": b"e",
        "ppt/media/image3.emf": b"e",
    })


DOCX_DOC = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="%s"><w:body>
 <w:p><w:r><w:object w:dxaOrig="9000" w:dyaOrig="3000">
  <v:shape id="_x0000_i1025" style="width:450pt;height:150pt"><v:imagedata r:id="rId2" o:title=""/></v:shape>
  <o:OLEObject Type="Embed" ProgID="Excel.Sheet.12" ShapeID="_x0000_i1025" DrawAspect="Content" r:id="rId3"/>
 </w:object></w:r></w:p>
 <w:p><w:r><w:object w:dxaOrig="1500" w:dyaOrig="1000">
  <v:shape id="_x0000_i1026"><v:imagedata r:id="rId4"/></v:shape>
  <o:OLEObject Type="Embed" ProgID="Package" DrawAspect="Icon" r:id="rId5"/>
 </w:object></w:r></w:p>
 <w:p><w:r><w:object>
  <v:shape id="_x0000_i1027" style="width:2in;height:1in"><v:imagedata r:id="rId6"/></v:shape>
  <o:OLEObject Type="Link" ProgID="Excel.Sheet.12" r:id="rId7"/>
 </w:object></w:r></w:p>
</w:body></w:document>""" % R

DOCX_HEADER = """<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="%s"><w:p><w:r><w:object w:dxaOrig="2000" w:dyaOrig="1000">
  <v:shape style="width:10cm;height:5cm"><v:imagedata r:id="rId1"/></v:shape>
  <o:OLEObject Type="Embed" ProgID="PowerPoint.Show.12" r:id="rId2"/>
 </w:object></w:r></w:p></w:hdr>""" % R


def docx() -> bytes:
    return paquet({
        "[Content_Types].xml": "<Types/>",
        "word/document.xml": DOCX_DOC,
        "word/_rels/document.xml.rels": rels(
            ("rId2", T_IMAGE, "media/image1.emf"),
            ("rId3", T_PACKAGE, "embeddings/Microsoft_Excel_Worksheet.xlsx"),
            ("rId4", T_IMAGE, "media/image2.emf"),
            ("rId5", T_OLE, "embeddings/oleObject1.bin"),
            ("rId6", T_IMAGE, "media/image3.emf"),
            ("rId7", T_OLE, "file:///\\\\serveur\\budget.xlsx", True)),
        "word/header1.xml": DOCX_HEADER,
        "word/_rels/header1.xml.rels": rels(
            ("rId1", T_IMAGE, "media/image1.emf"),
            ("rId2", T_PACKAGE, "/word/embeddings/Microsoft_PowerPoint.pptx")),
        "word/embeddings/Microsoft_Excel_Worksheet.xlsx": b"PK",
        "word/embeddings/oleObject1.bin": b"\xd0\xcf",
        # le PPTX de l'en-tête est volontairement ABSENT du paquet
        "word/media/image1.emf": b"e", "word/media/image2.emf": b"e",
        "word/media/image3.emf": b"e",
    })


XLSX_SHEET = """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="%s" xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
 <sheetFormatPr defaultRowHeight="15"/><cols><col min="1" max="2" width="20"/></cols>
 <sheetData><row r="1" ht="30"/></sheetData>
 <legacyDrawing r:id="rId1"/>
 <oleObjects>
  <oleObject progId="Word.Document.12" shapeId="1025" r:id="rId2">
   <objectPr defaultSize="0" r:id="rId3"><anchor moveWithCells="1">
    <from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row><xdr:rowOff>0</xdr:rowOff></from>
    <to><xdr:col>2</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></to>
   </anchor></objectPr></oleObject>
  <oleObject progId="Excel.Sheet.8" dvAspect="DVASPECT_ICON" shapeId="1026" r:id="rId4"/>
 </oleObjects></worksheet>""" % R

XLSX_VML = """<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
 <v:shape id="_x0000_s1025" style="position:absolute;width:300pt;height:100pt"><v:imagedata o:relid="rId1"/></v:shape>
 <v:shape id="_x0000_s1026" style="width:50pt;height:40pt"><v:imagedata o:relid="rId2"/></v:shape></xml>"""


def xlsx() -> bytes:
    return paquet({
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": "<workbook/>",
        "xl/worksheets/sheet1.xml": XLSX_SHEET,
        "xl/worksheets/_rels/sheet1.xml.rels": rels(
            ("rId1", T_VML, "../drawings/vmlDrawing1.vml"),
            ("rId2", T_PACKAGE, "../embeddings/Microsoft_Word_Document.docx"),
            ("rId3", T_IMAGE, "../media/image1.emf"),
            ("rId4", T_OLE, "../embeddings/oleObject1.bin")),
        "xl/drawings/vmlDrawing1.vml": XLSX_VML,
        "xl/drawings/_rels/vmlDrawing1.vml.rels": rels(
            ("rId1", T_IMAGE, "../media/image1.emf"),
            ("rId2", T_IMAGE, "../media/image2.emf")),
        "xl/embeddings/Microsoft_Word_Document.docx": b"PK",
        "xl/embeddings/oleObject1.bin": b"\xd0\xcf",
        "xl/media/image1.emf": b"e", "xl/media/image2.emf": b"e",
    })


# --------------------------------------------------------------------------- #
class PPTX(unittest.TestCase):
    def setUp(self):
        self.objets = incorpores.reperer(pptx())

    def test_quatre_objets(self):
        self.assertEqual([o.nature for o in self.objets],
                         ["classeur", "document", "presentation", "classeur"])
        self.assertTrue(all(o.conteneur == "pptx" for o in self.objets))

    def test_excel_ratio_et_relations_vml(self):
        xl = self.objets[0]
        self.assertEqual(xl.cible, "ppt/embeddings/Microsoft_Excel_Worksheet.xlsx")
        self.assertEqual((xl.format, xl.icone, xl.lie, xl.present),
                         ("ooxml", False, False, True))
        self.assertEqual(xl.apercu, "ppt/media/image1.emf")
        self.assertAlmostEqual(xl.ratio, 2.0)
        # le blip du fallback ET la forme VML pointent vers le même aperçu
        self.assertEqual(sorted(xl.relations_apercu), [
            ("ppt/drawings/_rels/vmlDrawing1.vml.rels", "rId1"),
            ("ppt/slides/_rels/slide1.xml.rels", "rId3")])

    def test_word_en_icone(self):
        wd = self.objets[1]
        self.assertTrue(wd.icone)
        self.assertEqual(wd.apercu, "ppt/media/image2.emf")
        self.assertAlmostEqual(wd.ratio, 1.0)

    def test_ole2_apercu_par_vml_seulement(self):
        pp = self.objets[2]
        self.assertEqual(pp.format, "ole2")
        self.assertEqual(pp.apercu, "ppt/media/image3.emf")
        self.assertEqual(pp.relations_apercu,
                         [("ppt/drawings/_rels/vmlDrawing1.vml.rels", "rId2")])

    def test_lien_non_suivi(self):
        lien = self.objets[3]
        self.assertTrue(lien.lie)
        self.assertFalse(lien.present)
        self.assertEqual(lien.raison_non_traite, "lie")


class DOCX(unittest.TestCase):
    def setUp(self):
        self.objets = incorpores.reperer(docx())
        self.par_partie = {}
        for o in self.objets:
            self.par_partie.setdefault(o.partie, []).append(o)

    def test_parties_lues(self):
        self.assertEqual(len(self.par_partie["word/document.xml"]), 3)
        self.assertEqual(len(self.par_partie["word/header1.xml"]), 1)

    def test_excel(self):
        xl = self.par_partie["word/document.xml"][0]
        self.assertEqual((xl.nature, xl.format, xl.icone), ("classeur", "ooxml", False))
        self.assertAlmostEqual(xl.ratio, 3.0)
        self.assertEqual(xl.apercu, "word/media/image1.emf")
        # le même aperçu sert aussi à l'en-tête : les deux relations sont relevées
        self.assertEqual(sorted(xl.relations_apercu), [
            ("word/_rels/document.xml.rels", "rId2"),
            ("word/_rels/header1.xml.rels", "rId1")])
        self.assertIsNone(xl.raison_non_traite)

    def test_paquet_en_icone_ratio_dxa(self):
        pk = self.par_partie["word/document.xml"][1]
        self.assertEqual((pk.nature, pk.format, pk.icone), ("paquet", "ole2", True))
        self.assertAlmostEqual(pk.ratio, 1.5)
        self.assertEqual(pk.raison_non_traite, "paquet")

    def test_lien(self):
        lien = self.par_partie["word/document.xml"][2]
        self.assertTrue(lien.lie)
        self.assertAlmostEqual(lien.ratio, 2.0)

    def test_cible_absolue_absente(self):
        pp = self.par_partie["word/header1.xml"][0]
        self.assertEqual(pp.cible, "word/embeddings/Microsoft_PowerPoint.pptx")
        self.assertEqual(pp.nature, "presentation")
        self.assertFalse(pp.present)
        self.assertEqual(pp.raison_non_traite, "absent")
        self.assertAlmostEqual(pp.ratio, 2.0)


class XLSX(unittest.TestCase):
    def setUp(self):
        self.objets = incorpores.reperer(xlsx())

    def test_word_vml_prioritaire(self):
        wd = self.objets[0]
        self.assertEqual((wd.nature, wd.format), ("document", "ooxml"))
        self.assertEqual(wd.apercu, "xl/media/image1.emf")
        self.assertAlmostEqual(wd.ratio, 3.0)
        self.assertEqual(sorted(wd.relations_apercu), [
            ("xl/drawings/_rels/vmlDrawing1.vml.rels", "rId1"),
            ("xl/worksheets/_rels/sheet1.xml.rels", "rId3")])

    def test_excel_97_en_icone(self):
        xl = self.objets[1]
        self.assertEqual((xl.nature, xl.format, xl.icone), ("classeur", "ole2", True))
        self.assertEqual(xl.apercu, "xl/media/image2.emf")
        self.assertAlmostEqual(xl.ratio, 1.25)

    def test_ratio_par_ancre_sans_vml(self):
        # Sans forme VML, le ratio vient des ancres : 2 colonnes de 20 car.
        # (145 px chacune) sur une ligne de 30 pt + une de 15 pt.
        brut = xlsx()
        src = zipfile.ZipFile(io.BytesIO(brut))
        parties = {n: src.read(n) for n in src.namelist()
                   if not n.startswith("xl/drawings/")}
        objets = incorpores.reperer(paquet(parties))
        attendu = (2 * 145 * 9525) / (45 * 12700)
        self.assertAlmostEqual(objets[0].ratio, attendu, places=4)
        self.assertEqual(objets[0].apercu, "xl/media/image1.emf")
        self.assertIsNone(objets[1].ratio)


class AuMieux(unittest.TestCase):
    def test_paquets_illisibles(self):
        self.assertEqual(incorpores.reperer(b"pas un zip"), [])
        self.assertEqual(incorpores.reperer(paquet({"a.txt": "x"})), [])

    def test_xml_casse_ignore(self):
        brut = paquet({"ppt/presentation.xml": "<p/>",
                       "ppt/slides/slide1.xml": "<p:sld",
                       "ppt/slides/_rels/slide1.xml.rels": "<<"})
        self.assertEqual(incorpores.reperer(brut), [])

    def test_entite_externe_non_resolue(self):
        xxe = ('<?xml version="1.0"?><!DOCTYPE d [<!ENTITY e SYSTEM '
               '"file:///etc/passwd">]><w:document xmlns:w="http://schemas.'
               'openxmlformats.org/wordprocessingml/2006/main">&e;</w:document>')
        self.assertEqual(incorpores.reperer(paquet({"word/document.xml": xxe})), [])

    def test_trop_d_entrees(self):
        parties = {"word/document.xml": "<w/>"}
        parties.update({f"x/{i}": "" for i in range(incorpores.ENTREES_MAX + 1)})
        self.assertEqual(incorpores.reperer(paquet(parties)), [])

    def test_rien_n_est_modifie(self):
        brut = pptx()
        incorpores.reperer(brut)
        self.assertEqual(brut, pptx())


class Rapport(unittest.TestCase):
    def test_pptx(self):
        r = incorpores.rapport(incorpores.reperer(pptx()))
        self.assertEqual((r["total"], r["a_traiter"], r["a_redessiner"]), (4, 3, 2))
        self.assertEqual(r["natures"], {"classeur": 2, "document": 1, "presentation": 1})
        self.assertEqual(r["non_traites"], [{
            "cible": "budget.xlsx", "partie": "ppt/slides/slide1.xml",
            "nature": "classeur", "raison": "lie"}])

    def test_marqueurs_tus_et_doublons_fusionnes(self):
        # Modèle réel (CFAO) : 154 repères think-cell dans les dispositions, et
        # un même objet lié affiché sur plusieurs diapos.
        O = incorpores.ObjetIncorpore
        def obj(partie, cible, pid, lie=False):
            return O("pptx", partie, cible, pid, incorpores._nature(pid, cible),
                     "ole2", False, lie, not lie)
        objets = [obj("ppt/slideLayouts/slideLayout%d.xml" % i,
                      "ppt/embeddings/oleObject8.bin", "TCLayout.ActiveDocument.1")
                  for i in range(3)]
        objets += [obj("ppt/slides/slide%d.xml" % i, "file:///b.xlsx",
                       "Excel.Sheet.12", lie=True) for i in range(2)]
        r = incorpores.rapport(objets)
        self.assertEqual(r["natures"], {"marqueur": 3, "classeur": 2})
        self.assertEqual(r["a_traiter"], 0)
        self.assertEqual([x["cible"] for x in r["non_traites"]], ["b.xlsx"])

    def test_docx(self):
        r = incorpores.rapport(incorpores.reperer(docx()))
        self.assertEqual(sorted(x["raison"] for x in r["non_traites"]),
                         ["absent", "lie", "paquet"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
