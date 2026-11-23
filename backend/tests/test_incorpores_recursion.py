"""Traduction des objets incorporés, récursive (6.11.3b) — `engines/incorpores.py`
et les trois moteurs (DOCX, XLSX, PPTX).

Ce que ce fichier verrouille :
  - un classeur, un document ou une présentation incorporé dans un DOCX, un XLSX
    ou un PPTX est relevé puis réinjecté par le moteur de SON format : cellules,
    noms d'onglet, paragraphes, titres de diapositive ;
  - la récursion va jusqu'à PROFONDEUR_MAX : Excel dans Word dans PowerPoint est
    traduit, le troisième niveau n'est jamais relevé et reste intact ;
  - un objet rangé dans une enveloppe OLE2 `Package` est réécrit dans la MÊME
    enveloppe, et le compte rendu ne le classe plus « paquet » ;
  - un objet 97-2003 est converti par LibreOffice (D4) : il devient une partie
    OOXML nouvelle, sa relation, son progId et le type de contenu suivent ;
  - si la conversion échoue : le document est produit, l'objet d'origine est
    intact, le compte rendu donne la raison « conversion » ;
  - sans objet, ou sans modification, le fichier n'est pas touché (octets égaux) ;
  - toutes les sorties se relisent avec python-docx, openpyxl et python-pptx.

Le traducteur est FACTICE : il pose `translated_text = "[EN] " + text` sur tous
les blocs du relevé. Les fichiers sont fabriqués en mémoire, avec les vraies
bibliothèques, pour que les moteurs aient réellement quelque chose à traduire.

Exécution :  PYTHONUTF8=1 <venv>/python.exe tests/test_incorpores_recursion.py
"""
from __future__ import annotations

import io
import json
import os
import posixpath
import re
import tempfile
import unittest
import zipfile
from unittest import mock

import racine  # noqa: F401  -- met backend/ sur le chemin

import olefile  # noqa: E402
from docx import Document  # noqa: E402
from pptx import Presentation  # noqa: E402

from engines import incorpores as I  # noqa: E402
from engines import new_engine, office  # noqa: E402

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
T_PACKAGE = R + "/package"
T_OLE = R + "/oleObject"
CLSID_PAQUET = "0003000C-0000-0000-C000-000000000046"
CT = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "bin": "application/vnd.openxmlformats-officedocument.oleObject",
}
PARTIE = {"pptx": "ppt/slides/slide1.xml", "docx": "word/document.xml",
          "xlsx": "xl/worksheets/sheet1.xml"}
PREFIXE_TRAD = "[EN] "


# --------------------------------------------------------------------------- #
# Fabrication de fichiers réels
# --------------------------------------------------------------------------- #

def reel_xlsx(textes: list[str], onglet: str = "Données") -> bytes:
    """Classeur minimal écrit à la main (openpyxl n'est pas installé)."""
    chaines = "".join("<si><t>%s</t></si>" % t for t in textes)
    lignes = "".join('<row r="%d"><c r="A%d" t="s"><v>%d</v></c></row>' % (i, i, i - 1)
                     for i in range(1, len(textes) + 1))
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ct = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    fichiers = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="%s.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="%s.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="%s.sharedStrings+xml"/>'
            "</Types>" % (ct, ct, ct)),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="%s/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>" % R),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="%s" xmlns:r="%s"><sheets>'
            '<sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>' % (ns, R, onglet)),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="%s/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="%s/sharedStrings" Target="sharedStrings.xml"/>'
            "</Relationships>" % (R, R)),
        "xl/worksheets/sheet1.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="%s" xmlns:r="%s"><sheetData>%s</sheetData></worksheet>'
            % (ns, R, lignes)),
        "xl/sharedStrings.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="%s" count="%d" uniqueCount="%d">%s</sst>'
            % (ns, len(textes), len(textes), chaines)),
    }
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        for nom, contenu in fichiers.items():
            zf.writestr(nom, contenu)
    return tampon.getvalue()


def reel_docx(paragraphes: list[str]) -> bytes:
    doc = Document()
    for p in paragraphes:
        doc.add_paragraph(p)
    tampon = io.BytesIO()
    doc.save(tampon)
    return tampon.getvalue()


def reel_pptx(titre: str) -> bytes:
    prs = Presentation()
    diapo = prs.slides.add_slide(prs.slide_layouts[5])
    diapo.shapes.title.text = titre
    tampon = io.BytesIO()
    prs.save(tampon)
    return tampon.getvalue()


def _xml_objet(partie: str, i: int, rid: str, prog_id: str) -> str:
    if partie.startswith("ppt/"):
        return (
            '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="%d" name="Objet %d"/>'
            "<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>"
            '<p:xfrm><a:off x="0" y="0"/><a:ext cx="3000000" cy="2000000"/></p:xfrm>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
            'presentationml/2006/ole"><p:oleObj xmlns:r="%s" r:id="%s" progId="%s">'
            "<p:embed/></p:oleObj></a:graphicData></a:graphic></p:graphicFrame>"
            % (900 + i, i, R, rid, prog_id))
    if partie.startswith("word/"):
        return (
            '<w:p><w:r><w:object w:dxaOrig="3000" w:dyaOrig="2000">'
            '<v:shape xmlns:v="urn:schemas-microsoft-com:vml" id="_x0000_i%d" '
            'style="width:150pt;height:100pt"/>'
            '<o:OLEObject xmlns:o="urn:schemas-microsoft-com:office:office" '
            'xmlns:r="%s" Type="Embed" ProgID="%s" ShapeID="_x0000_i%d" '
            'DrawAspect="Content" ObjectID="_%d" r:id="%s"/></w:object></w:r></w:p>'
            % (1025 + i, R, prog_id, 1025 + i, i, rid))
    return ('<oleObject xmlns:r="%s" progId="%s" shapeId="%d" r:id="%s"/>'
            % (R, prog_id, 1025 + i, rid))


def greffer(hote: bytes, partie: str, objets: list[tuple]) -> bytes:
    """Hôte réel + objets incorporés à la main.

    `objets` : (nom relatif au dossier `embeddings/`, progId, octets, type de
    relation). L'objet est ajouté à l'archive, à la partie qui l'affiche
    (`partie`), à ses relations et aux types de contenu."""
    racine_ = partie.split("/")[0]
    with zipfile.ZipFile(io.BytesIO(hote)) as zf:
        ordre = zf.namelist()
        contenus = {n: zf.read(n) for n in ordre}
    nom_rels = posixpath.join(posixpath.dirname(partie), "_rels",
                              posixpath.basename(partie) + ".rels")
    rels = contenus.get(nom_rels, (
        '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns='
        '"http://schemas.openxmlformats.org/package/2006/relationships">'
        "</Relationships>").encode()).decode("utf-8")
    xml = contenus[partie].decode("utf-8")
    types = contenus["[Content_Types].xml"].decode("utf-8")
    morceaux = []
    for i, (nom, prog_id, octets, type_rel) in enumerate(objets, 1):
        rid = "rIdObj%d" % i
        cible = posixpath.join(racine_, "embeddings", nom)
        contenus[cible] = octets
        relatif = posixpath.relpath(cible, posixpath.dirname(partie))
        rels = rels.replace("</Relationships>", '<Relationship Id="%s" Type="%s" '
                            'Target="%s"/></Relationships>' % (rid, type_rel, relatif))
        ext = posixpath.splitext(nom)[1][1:]
        if 'Extension="%s"' % ext not in types:
            types = re.sub(r"(<Types[^>]*>)", lambda m: m.group(1) + (
                '<Default Extension="%s" ContentType="%s"/>' % (ext, CT[ext])),
                types, count=1)
        morceaux.append(_xml_objet(partie, i, rid, prog_id))
    bloc = "".join(morceaux)
    if partie.startswith("ppt/"):
        xml = xml.replace("</p:spTree>", bloc + "</p:spTree>")
    elif partie.startswith("word/"):
        i = xml.rfind("<w:sectPr")
        i = i if i >= 0 else xml.rfind("</w:body>")
        xml = xml[:i] + bloc + xml[i:]
    else:
        xml = xml.replace("</worksheet>", "<oleObjects>" + bloc + "</oleObjects></worksheet>")
    contenus[partie] = xml.encode("utf-8")
    contenus[nom_rels] = rels.encode("utf-8")
    contenus["[Content_Types].xml"] = types.encode("utf-8")
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in list(ordre) + [n for n in contenus if n not in ordre]:
            zf.writestr(n, contenus[n])
    return tampon.getvalue()


def ole2(flux: dict[str, bytes], clsid: str = "") -> bytes:
    noeuds = [I._Noeud(nom, I._FLUX, b"\0" * 16, 0, 0, 0, donnees)
              for nom, donnees in flux.items()]
    racine_ = I._Noeud("Root Entry", I._RACINE, I._clsid_octets(clsid), 0, 0, 0,
                       enfants=noeuds)
    return I._ecrire_cfb(racine_)


# --------------------------------------------------------------------------- #
# Traducteur factice et lecture des résultats
# --------------------------------------------------------------------------- #

def marquer(texte: str, id_: str = "") -> str:
    """Traduction factice : « [EN] » devant le texte, APRÈS les balises de runs
    d'ouverture (`[[0]]…`) que le moteur attend en tête, comme un vrai modèle."""
    if "sheetname_" in id_:      # un nom d'onglet ne peut pas contenir de crochets
        return "EN " + texte
    m = re.match(r"(?:\[\[\d+\]\])*", texte)
    return texte[:m.end()] + PREFIXE_TRAD + texte[m.end():]


def traduire(ext: str, octets: bytes, niveau_objets: int = 1):
    """Extrait, « traduit » (préfixe) puis réinjecte avec le vrai moteur.

    Rend (octets traduits, JSON d'extraction avec `translated_text`)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src = os.path.join(tmp, "src." + ext)
        ej, tj, sortie = (os.path.join(tmp, n) for n in ("ext.json", "tr.json", "out." + ext))
        with open(src, "wb") as f:
            f.write(octets)
        moteur = new_engine(ext)
        extraction = moteur.extract_text(src, ej, niveau_objets=niveau_objets)[0]
        assert extraction is not None, "extraction vide"
        with open(ej, encoding="utf-8") as f:
            data = json.load(f)
        for el in I._elements_de(data):
            el["translated_text"] = marquer(el["text"], el["id"])
        with open(tj, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        ok, message = new_engine(ext).inject_translation(
            src, tj, sortie, niveau_objets=niveau_objets)
        assert ok, message
        with open(sortie, "rb") as f:
            return f.read(), data


def partie_de(octets: bytes, nom: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        return zf.read(nom)


def noms_de(octets: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        return zf.namelist()


def cellules(octets: bytes) -> list:
    """Textes des cellules (chaînes partagées et chaînes en ligne)."""
    with zipfile.ZipFile(io.BytesIO(octets)) as zf:
        xml = "".join(zf.read(n).decode("utf-8") for n in zf.namelist()
                      if n == "xl/sharedStrings.xml" or n.startswith("xl/worksheets/sheet"))
    return re.findall(r"<t(?:\s[^>]*)?>([^<]*)</t>", xml)


def onglets(octets: bytes) -> list[str]:
    xml = partie_de(octets, "xl/workbook.xml").decode("utf-8")
    return re.findall(r'<sheet\b[^>]*\bname="([^"]*)"', xml)


def paragraphes(octets: bytes) -> list[str]:
    return [p.text for p in Document(io.BytesIO(octets)).paragraphs if p.text]


def textes_pptx(octets: bytes) -> list[str]:
    return [f.text for diapo in Presentation(io.BytesIO(octets)).slides
            for forme in diapo.shapes if forme.has_text_frame
            for f in forme.text_frame.paragraphs]


def relisible(ext: str, octets: bytes) -> None:
    {"xlsx": cellules, "docx": paragraphes, "pptx": textes_pptx}[ext](octets)


def ids_objets(data: dict) -> list[str]:
    """Ids des blocs d'objets du JSON d'extraction, où qu'ils soient rangés."""
    if "slides" in data:
        return [el["id"] for s in data["slides"] for el in s.get("excel_elements", [])]
    return [el["id"] for el in data.get("objets", [])]


# --------------------------------------------------------------------------- #

class UnNiveau(unittest.TestCase):
    def test_pptx_avec_xlsx(self):
        xlsx = reel_xlsx(["Bonjour", "Merci"], "Données")
        pptx = greffer(reel_pptx("Titre"), PARTIE["pptx"],
                       [("tab.xlsx", "Excel.Sheet.12", xlsx, T_PACKAGE)])
        sortie, data = traduire("pptx", pptx)
        self.assertTrue(ids_objets(data))
        self.assertTrue(all(i.startswith("slide1_excel_tab__") for i in ids_objets(data)))
        self.assertEqual(data["objets_rapport"]["a_traiter"], 1)
        self.assertEqual(data["objets_rapport"]["non_traites"], [])
        inc = partie_de(sortie, "ppt/embeddings/tab.xlsx")
        self.assertEqual(sorted(cellules(inc)), ["[EN] Bonjour", "[EN] Merci"])
        self.assertEqual(onglets(inc), ["EN Données"])
        self.assertIn(PREFIXE_TRAD + "Titre", textes_pptx(sortie))
        relisible("pptx", sortie)

    def test_docx_avec_xlsx_et_docx(self):
        xlsx = reel_xlsx(["Chiffre"], "Budget")
        docx = reel_docx(["Lettre jointe"])
        hote = greffer(reel_docx(["Corps"]), PARTIE["docx"], [
            ("calc.xlsx", "Excel.Sheet.12", xlsx, T_PACKAGE),
            ("lettre.docx", "Word.Document.12", docx, T_PACKAGE)])
        sortie, data = traduire("docx", hote)
        ids = ids_objets(data)
        self.assertTrue(any(i.startswith("excel_calc__") for i in ids), ids)
        self.assertTrue(any(i.startswith("word_lettre__") for i in ids), ids)
        self.assertEqual(data["objets_rapport"]["a_traiter"], 2)
        self.assertEqual(cellules(partie_de(sortie, "word/embeddings/calc.xlsx")),
                         ["[EN] Chiffre"])
        self.assertEqual(paragraphes(partie_de(sortie, "word/embeddings/lettre.docx")),
                         ["[EN] Lettre jointe"])
        self.assertIn("[EN] Corps", paragraphes(sortie))
        relisible("docx", sortie)

    def test_xlsx_avec_docx(self):
        docx = reel_docx(["Note interne"])
        hote = greffer(reel_xlsx(["Total"], "Synthèse"), PARTIE["xlsx"],
                       [("note.docx", "Word.Document.12", docx, T_PACKAGE)])
        sortie, data = traduire("xlsx", hote)
        self.assertTrue(any(i.startswith("word_note__") for i in ids_objets(data)))
        self.assertEqual(data["objets_rapport"]["a_traiter"], 1)
        self.assertEqual(paragraphes(partie_de(sortie, "xl/embeddings/note.docx")),
                         ["[EN] Note interne"])
        self.assertIn("[EN] Total", cellules(sortie))
        relisible("xlsx", sortie)

    def test_pptx_avec_pptx(self):
        interne = reel_pptx("Titre interne")
        hote = greffer(reel_pptx("Titre externe"), PARTIE["pptx"],
                       [("sous.pptx", "PowerPoint.Show.12", interne, T_PACKAGE)])
        sortie, data = traduire("pptx", hote)
        self.assertTrue(any(i.startswith("slide1_ppt_sous__") for i in ids_objets(data)))
        self.assertIn(PREFIXE_TRAD + "Titre interne",
                      textes_pptx(partie_de(sortie, "ppt/embeddings/sous.pptx")))
        self.assertIn(PREFIXE_TRAD + "Titre externe", textes_pptx(sortie))
        relisible("pptx", sortie)


class Profondeur(unittest.TestCase):
    def test_excel_dans_word_dans_powerpoint_et_pas_le_troisieme_niveau(self):
        niveau3 = reel_docx(["TROISIEME NIVEAU"])
        niveau2 = greffer(reel_xlsx(["Deux"], "Calc"), PARTIE["xlsx"],
                          [("niv3.docx", "Word.Document.12", niveau3, T_PACKAGE)])
        niveau1 = greffer(reel_docx(["Un"]), PARTIE["docx"],
                          [("niv2.xlsx", "Excel.Sheet.12", niveau2, T_PACKAGE)])
        hote = greffer(reel_pptx("Zero"), PARTIE["pptx"],
                       [("niv1.docx", "Word.Document.12", niveau1, T_PACKAGE)])
        sortie, data = traduire("pptx", hote)
        textes = [re.sub(r"\[\[/?\d+\]\]", "", el["text"])
                  for s in data["slides"] for el in s["excel_elements"]]
        self.assertIn("Un", textes)
        self.assertIn("Deux", textes)
        self.assertFalse([t for t in textes if "TROISIEME" in t], textes)
        # niveau 1 (Word) et niveau 2 (Excel dans Word) sont traduits
        n1 = partie_de(sortie, "ppt/embeddings/niv1.docx")
        self.assertIn("[EN] Un", paragraphes(n1))
        n2 = partie_de(n1, "word/embeddings/niv2.xlsx")
        self.assertEqual(cellules(n2), ["[EN] Deux"])
        # le troisième niveau est resté tel quel
        n3 = partie_de(n2, "xl/embeddings/niv3.docx")
        self.assertEqual(paragraphes(n3), ["TROISIEME NIVEAU"])
        self.assertEqual(n3, niveau3)
        relisible("pptx", sortie)

    def test_troisieme_niveau_signale_dans_le_rapport_du_moteur(self):
        hote = greffer(reel_xlsx(["x"]), PARTIE["xlsx"],
                       [("n.docx", "Word.Document.12", reel_docx(["y"]), T_PACKAGE)])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src, ej = os.path.join(tmp, "a.xlsx"), os.path.join(tmp, "a.json")
            with open(src, "wb") as f:
                f.write(hote)
            new_engine("xlsx").extract_text(src, ej, niveau_objets=I.PROFONDEUR_MAX + 1)
            with open(ej, encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["objets"], [])
        self.assertEqual([n["raison"] for n in data["objets_rapport"]["non_traites"]],
                         ["profondeur"])


class EnveloppeOle2(unittest.TestCase):
    def test_package_contenant_un_docx(self):
        docx = reel_docx(["Contrat"])
        enveloppe = ole2({"\x01CompObj": b"compobj", "Package": docx}, CLSID_PAQUET)
        hote = greffer(reel_pptx("Titre"), PARTIE["pptx"],
                       [("oleObject1.bin", "Package", enveloppe, T_OLE)])
        sortie, data = traduire("pptx", hote)
        rapport = data["objets_rapport"]
        self.assertEqual(rapport["non_traites"], [])
        self.assertEqual(rapport["natures"], {"document": 1})
        nouveau = partie_de(sortie, "ppt/embeddings/oleObject1.bin")
        with olefile.OleFileIO(io.BytesIO(nouveau)) as ole:
            self.assertEqual(ole.openstream("\x01CompObj").read(), b"compobj")
            self.assertEqual(ole.root.clsid, CLSID_PAQUET)
            interne = ole.openstream("Package").read()
        self.assertEqual(paragraphes(interne), ["[EN] Contrat"])
        relisible("pptx", sortie)


class Binaire97_2003(unittest.TestCase):
    @unittest.skipUnless(office.find_soffice(), "LibreOffice requis")
    def test_xls_converti_en_partie_xlsx(self):
        xls = office.convertir(reel_xlsx(["Bonjour"], "Ventes"), "xlsx", "xls")
        hote = greffer(reel_pptx("Titre"), PARTIE["pptx"],
                       [("oleObject1.bin", "Excel.Sheet.8", xls, T_OLE)])
        sortie, data = traduire("pptx", hote)
        self.assertEqual(data["objets_rapport"]["non_traites"], [])
        noms = noms_de(sortie)
        self.assertIn("ppt/embeddings/oleObject1.xlsx", noms)
        self.assertEqual(cellules(partie_de(sortie, "ppt/embeddings/oleObject1.xlsx")),
                         ["[EN] Bonjour"])
        rels = partie_de(sortie, "ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
        rel = re.search(r'<Relationship[^>]*Id="rIdObj1"[^>]*/>', rels).group(0)
        self.assertIn("oleObject1.xlsx", rel)
        self.assertIn(T_PACKAGE, rel)
        self.assertIn('progId="Excel.Sheet.12"',
                      partie_de(sortie, PARTIE["pptx"]).decode("utf-8"))
        types = partie_de(sortie, "[Content_Types].xml").decode("utf-8")
        self.assertRegex(types, r'Extension="xlsx"')
        self.assertIn(CT["xlsx"], types)
        relisible("pptx", sortie)

    def _hote_ancien(self):
        # Un « Workbook » factice suffit : la conversion est simulée en échec.
        ancien = ole2({"Workbook": b"\x09\x08\x10\x00" + b"\0" * 20})
        hote = greffer(reel_pptx("Titre"), PARTIE["pptx"],
                       [("oleObject1.bin", "Excel.Sheet.8", ancien, T_OLE)])
        return hote, ancien

    def test_conversion_en_echec_objet_intact(self):
        hote, ancien = self._hote_ancien()
        with mock.patch.object(office, "convertir", side_effect=RuntimeError("absent")):
            sortie, data = traduire("pptx", hote)
            direct = I.reinjecter(hote, {"slide1_excel_oleObject1__x": "y"},
                                  lambda o: "slide1_")
        self.assertEqual([n["raison"] for n in data["objets_rapport"]["non_traites"]],
                         ["conversion"])
        self.assertEqual(partie_de(sortie, "ppt/embeddings/oleObject1.bin"), ancien)
        self.assertNotIn("ppt/embeddings/oleObject1.xlsx", noms_de(sortie))
        self.assertIn(PREFIXE_TRAD + "Titre", textes_pptx(sortie))
        self.assertEqual((direct.parties, direct.retouches, direct.cibles), ({}, [], []))
        relisible("pptx", sortie)


class SansObjet(unittest.TestCase):
    def test_octets_egaux(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            for ext, octets in (("pptx", reel_pptx("A")), ("docx", reel_docx(["A"])),
                                ("xlsx", reel_xlsx(["A"]))):
                chemin = os.path.join(tmp, "f." + ext)
                with open(chemin, "wb") as f:
                    f.write(octets)
                modifs = I.reinjecter(chemin, {"slide1_x": "y", "x": "y"})
                self.assertEqual((modifs.parties, modifs.retouches, modifs.cibles),
                                 ({}, [], []))
                I.appliquer_fichier(chemin, modifs)
                with open(chemin, "rb") as f:
                    self.assertEqual(f.read(), octets, ext)
                self.assertFalse(os.path.exists(chemin + ".tmp"))
                self.assertEqual(I.relever(chemin)[0], [])

    def test_objet_sans_traduction_laisse_intact(self):
        hote = greffer(reel_docx(["Corps"]), PARTIE["docx"],
                       [("calc.xlsx", "Excel.Sheet.12", reel_xlsx(["A"]), T_PACKAGE)])
        modifs = I.reinjecter(hote, {"autre__id": "x"})
        self.assertEqual(modifs.cibles, [])
        self.assertEqual(modifs.parties, {})


if __name__ == "__main__":
    unittest.main()
