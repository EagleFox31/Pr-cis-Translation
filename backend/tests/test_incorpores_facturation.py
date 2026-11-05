"""6.11.6 — facturation et compte rendu des objets incorporés.

- le devis compte le texte des objets incorporés (D1) ;
- l'aperçu d'un objet n'est ni lu par l'OCR ni facturé en image ;
- un objet non traité dans un objet est nommé « parent › enfant » ;
- le moteur PPTX progressif cumule les objets non traités, liés compris ;
- ce qui échoue à la réinjection ou au redessin est signalé (`Modifs.restes`) ;
- une archive aux octets abîmés est refusée proprement ;
- les trois jobs émettent l'événement `objets` (rien si la liste est vide).
"""
from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import os
import posixpath
import re
import shutil
import tempfile
import time
import unittest
import zipfile
from unittest import mock

import racine  # noqa: F401  -- met backend/ sur le chemin

from lxml import etree  # noqa: E402
from PIL import Image  # noqa: E402

from app.services import beta_meter, images_document, translation_runner  # noqa: E402
from app.services.jobs import jobs  # noqa: E402
from engines import incorpores as I, new_engine  # noqa: E402
from engines.pptx.engine import PPTXTranslatorEngine  # noqa: E402
from test_incorpores_recursion import (  # noqa: E402
    CT, R, T_PACKAGE, greffer, marquer, reel_docx, reel_pptx, reel_xlsx)
from test_ole_apercu import pptx_avec_apercu  # noqa: E402

CT.setdefault("vsdx", "application/vnd.ms-visio.drawing")
MOTS_OBJET = ["Chiffre", "affaires", "trimestriel", "consolidé", "Région", "Nord"]
T_IMAGE = R + "/image"


def png(couleur=(200, 30, 30)) -> bytes:
    sortie = io.BytesIO()
    Image.new("RGB", (400, 400), couleur).save(sortie, "PNG")
    return sortie.getvalue()


def reecrire(octets: bytes, change) -> bytes:
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        ordre = z.namelist()
        p = {n: z.read(n) for n in ordre}
    change(p)
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for n in list(ordre) + [n for n in p if n not in ordre]:
            if n in p:
                z.writestr(n, p[n])
    return sortie.getvalue()


def pptx_apercu_png() -> bytes:
    """Aperçu de l'objet en PNG (et non EMF) + une image ordinaire."""
    def change(p):
        p["ppt/media/image9.png"] = png()
        del p["ppt/media/image9.emf"]
        for n in list(p):
            if n.endswith(".rels"):
                p[n] = p[n].replace(b"image9.emf", b"image9.png")
        types = p["[Content_Types].xml"].decode()
        if 'Extension="png"' not in types:
            types = re.sub(r"(<Types[^>]*>)",
                           r'\1<Default Extension="png" ContentType="image/png"/>', types, count=1)
        p["[Content_Types].xml"] = types.encode()
        p["ppt/media/image1.png"] = png((30, 30, 200))
    return reecrire(pptx_avec_apercu(), change)


def visio() -> tuple:
    return ("schema.vsdx", "Visio.Drawing.15", reel_docx(["Schéma"]), T_PACKAGE)


def classeur(nom: str = "Feuille1.xlsx", octets: bytes | None = None) -> tuple:
    return (nom, "Excel.Sheet.12", octets or reel_xlsx(MOTS_OBJET), T_PACKAGE)


def poser_apercu(p: dict, partie: str, media: str) -> None:
    """Ajoute l'image `media` et sa relation rIdImg à `partie`."""
    p[media] = png()
    dossier, _, nom = partie.rpartition("/")
    rels = f"{dossier}/_rels/{nom}.rels"
    p[rels] = p[rels].replace(
        b"</Relationships>",
        (f'<Relationship Id="rIdImg" Type="{T_IMAGE}" '
         f'Target="{posixpath.relpath(media, dossier)}"/></Relationships>').encode())
    types = p["[Content_Types].xml"].decode()
    if 'Extension="png"' not in types:
        types = re.sub(r"(<Types[^>]*>)",
                       r'\1<Default Extension="png" ContentType="image/png"/>', types, count=1)
    p["[Content_Types].xml"] = types.encode()


def docx_apercu_png() -> bytes:
    def change(p):
        p["word/document.xml"] = re.sub(
            rb'(<v:shape [^>]*?)/>',
            (r'\1><v:imagedata xmlns:r="%s" r:id="rIdImg"/></v:shape>' % R).encode(),
            p["word/document.xml"], count=1)
        poser_apercu(p, "word/document.xml", "word/media/image9.png")
    return reecrire(greffer(reel_docx(["Texte"]), "word/document.xml", [classeur()]), change)


def xlsx_apercu_png() -> bytes:
    partie = "xl/worksheets/sheet1.xml"

    def change(p):
        p[partie] = p[partie].replace(
            b'r:id="rIdObj1"/>',
            b'r:id="rIdObj1"><objectPr r:id="rIdImg"><anchor/></objectPr></oleObject>')
        poser_apercu(p, partie, "xl/media/image9.png")
    return reecrire(greffer(reel_xlsx(["Texte"]), partie, [classeur()]), change)


def abimer(octets: bytes) -> bytes:
    """Garde le répertoire du zip intact mais rend les données compressées fausses."""
    brut = bytearray(octets)
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        for info in z.infolist():
            if info.filename == "[Content_Types].xml" or not info.compress_size:
                continue
            nom_l, extra_l = (int.from_bytes(brut[info.header_offset + d:info.header_offset + d + 2],
                                             "little") for d in (26, 28))
            debut = info.header_offset + 30 + nom_l + extra_l
            brut[debut:debut + info.compress_size] = b"\xff" * info.compress_size
    return bytes(brut)


def pptx_deux_diapos() -> bytes:
    """Deux diapositives qui affichent le même objet."""
    from pptx import Presentation
    prs = Presentation()
    for _ in range(2):
        prs.slides.add_slide(prs.slide_layouts[6])
    sortie = io.BytesIO()
    prs.save(sortie)
    octets = sortie.getvalue()
    for n in (1, 2):
        octets = greffer(octets, f"ppt/slides/slide{n}.xml", [visio()])
    return octets


def pptx_objet_lie() -> bytes:
    """Objet lié seul sur la diapositive : aucune partie embeddings ni charts."""
    def change(p):
        del p["ppt/embeddings/Lien.xlsx"]
        rels = "ppt/slides/_rels/slide1.xml.rels"
        p[rels] = re.sub(
            rb'Type="[^"]*/package" Target="[^"]*Lien\.xlsx"',
            (f'Type="{R}/oleObject" Target="file:///C:/Lien.xlsx" '
             'TargetMode="External"').encode(), p[rels])
        partie = "ppt/slides/slide1.xml"
        p[partie] = p[partie].replace(b"<p:embed/>", b"<p:link/>")
    return reecrire(greffer(reel_pptx("Titre"), "ppt/slides/slide1.xml",
                            [classeur("Lien.xlsx")]), change)


def pptx_apercu_partage() -> bytes:
    """Un classeur et un objet Visio (non traduit) affichent la même image."""
    def change(p):
        partie = "ppt/slides/slide1.xml"
        cadre = re.search(rb"<p:graphicFrame>.*?</p:graphicFrame>", p[partie], re.S).group(0)
        second = re.sub(rb'r:id="rIdObj1" progId="[^"]+"',
                        b'r:id="rIdVisio" progId="Visio.Drawing.15"', cadre)
        p[partie] = p[partie].replace(cadre, cadre + second)
        p["ppt/embeddings/schema.vsdx"] = visio()[2]
        rels = "ppt/slides/_rels/slide1.xml.rels"
        p[rels] = p[rels].replace(
            b"</Relationships>",
            (f'<Relationship Id="rIdVisio" Type="{T_PACKAGE}" '
             'Target="../embeddings/schema.vsdx"/></Relationships>').encode())
        p["[Content_Types].xml"] = re.sub(
            rb"(<Types[^>]*>)",
            rb'\1<Default Extension="vsdx" ContentType="application/vnd.ms-visio.drawing"/>',
            p["[Content_Types].xml"], count=1)
    return reecrire(pptx_avec_apercu(), change)


def hote_imbrique() -> bytes:
    """Un Word contenant Budget.xlsx, qui contient lui-même Interne.xlsx."""
    parent = greffer(reel_xlsx(["Ventes"]), "xl/worksheets/sheet1.xml",
                     [classeur("Interne.xlsx")])
    return greffer(reel_docx(["Texte"]), "word/document.xml", [classeur("Budget.xlsx", parent)])


def injecter(ext: str, octets: bytes, panne=None):
    """Extrait, « traduit », réinjecte (sous `panne`, un contexte qui ne couvre pas
    l'extraction) ; rend le moteur d'injection."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        src = os.path.join(tmp, "src." + ext)
        ej, tj, sortie = (os.path.join(tmp, n) for n in ("e.json", "t.json", "s." + ext))
        with open(src, "wb") as f:
            f.write(octets)
        assert new_engine(ext).extract_text(src, ej)[0] is not None
        with open(ej, encoding="utf-8") as f:
            data = json.load(f)
        for el in I._elements_de(data):
            el["translated_text"] = marquer(el["text"], el["id"])
        with open(tj, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        moteur = new_engine(ext)
        with panne or contextlib.nullcontext():
            ok, message = moteur.inject_translation(src, tj, sortie)
        assert ok, message
        return moteur


class Traducteur:
    """Préfixe tout : assez pour que les jobs réinjectent les objets."""

    def fiche_document(self, *_a, **_k):
        return ""

    def _translate_batch(self, *_a, **_k):
        return None

    def translate_json(self, chemin, target_lang=None, progress_callback=None, **_):
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
        for el in I._elements_de(data):
            el["translated_text"] = marquer(el["text"], el["id"])
        sortie = chemin + ".out.json"
        with open(sortie, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return True, sortie


def lancer_job(ext: str, octets: bytes, progressif: bool, reinjection_cassee: bool = False) -> list:
    """Vrai job, faux traducteur : rend les listes émises dans l'événement `objets`."""
    recus = []
    vrai_emit = jobs.emit

    def emit(job_id, evenement, donnees=None):
        if evenement == "objets":
            recus.append(donnees["non_traites"])
        return vrai_emit(job_id, evenement, donnees)

    dossier = tempfile.mkdtemp(prefix="fact_job_")
    job_id = jobs.create()
    try:
        chemins = {n: os.path.join(dossier, n) for n in
                   ("original." + ext, "e.json", "t.json", "s." + ext, "p.pdf")}
        with mock.patch.object(translation_runner.jobs, "emit", emit), \
                mock.patch.object(translation_runner, "ai_translator", Traducteur(), create=True), \
                mock.patch.object(translation_runner, "ai_active", True, create=True), \
                (mock.patch.object(I, "reinjecter", side_effect=RuntimeError("cassé"))
                 if reinjection_cassee else contextlib.nullcontext()):
            if not progressif:
                translation_runner.run_translation_job(
                    job_id, octets, "s." + ext, ext, "en", {}, dossier, dossier,
                    chemins["original." + ext], chemins["e.json"], chemins["t.json"],
                    chemins["s." + ext], "s." + ext, None, None)
            elif ext == "pptx":
                translation_runner.run_pptx_progressive_job(
                    job_id, octets, chemins["original.pptx"], chemins["s.pptx"], "s.pptx",
                    chemins["p.pdf"], chemins["t.json"], "en")
            else:
                translation_runner.run_xlsx_progressive_job(
                    job_id, octets, chemins["original.xlsx"], chemins["s.xlsx"], "s.xlsx",
                    chemins["p.pdf"], chemins["t.json"], "en")
        etat = jobs.get(job_id) or {}
        assert etat.get("state") != "error", etat.get("error")
    finally:
        jobs.forget(job_id)
        shutil.rmtree(dossier, ignore_errors=True)
    return recus


class Devis(unittest.TestCase):
    def test_le_texte_de_l_objet_est_compte(self):
        seul = reel_docx(["Rapport annuel de la société"])
        avec = greffer(seul, "word/document.xml",
                       [("Feuille1.xlsx", "Excel.Sheet.12", reel_xlsx(MOTS_OBJET), T_PACKAGE)])
        sans_objet = beta_meter.office_cost(seul, "docx").units
        avec_objet = beta_meter.office_cost(avec, "docx").units
        self.assertGreaterEqual(avec_objet - sans_objet, len(MOTS_OBJET))


class ExclusionOCR(unittest.TestCase):
    def test_casse_differente_entre_relation_et_archive(self):
        def change(p):
            for n in list(p):
                if n.endswith(".rels"):
                    p[n] = p[n].replace(b"image9.png", b"IMAGE9.PNG")
        images = {i.cle: i for i in images_document.lister(reecrire(pptx_apercu_png(), change), "pptx")}
        self.assertEqual(images["ppt/media/image9.png"].exclusion, "apercu_objet")

    def test_apercu_png_exclu_image_ordinaire_proposee(self):
        images = {i.cle: i for i in images_document.lister(pptx_apercu_png(), "pptx")}
        self.assertEqual(images["ppt/media/image9.png"].exclusion, "apercu_objet")
        self.assertIsNone(images["ppt/media/image1.png"].exclusion)

    def test_l_ocr_n_analyse_jamais_l_apercu(self):
        lues = []

        class Lecteur:
            def manquant(self):
                return False

            def detecter_image(self, image):
                lues.append(image.shape)
                return [1]

        analyse = images_document.detecter(images_document.lister(pptx_apercu_png(), "pptx"),
                                           lecteur=Lecteur())
        self.assertEqual([i.cle for i in analyse.a_texte], ["ppt/media/image1.png"])
        self.assertEqual((analyse.analysees, len(lues)), (1, 1))

    def test_docx_et_xlsx(self):
        for ext, octets, media in (("docx", docx_apercu_png(), "word/media/image9.png"),
                                   ("xlsx", xlsx_apercu_png(), "xl/media/image9.png")):
            with self.subTest(ext):
                images = {i.cle: i for i in images_document.lister(octets, ext)}
                self.assertEqual(images[media].exclusion, "apercu_objet")


class ArchiveAbimee(unittest.TestCase):
    def test_refus_propre(self):
        for ext, octets in (("pptx", pptx_apercu_png()), ("docx", docx_apercu_png()),
                            ("xlsx", xlsx_apercu_png())):
            with self.subTest(ext):
                abimee = abimer(octets)
                self.assertEqual(I.reperer(abimee), [])
                if ext == "pptx":
                    with self.assertRaises(ValueError):
                        images_document.lister(abimee, ext)
                else:
                    self.assertTrue(all(i.octets is None
                                        for i in images_document.lister(abimee, ext)))

    def test_le_garde_fou_passe_avant_la_decompression(self):
        with mock.patch.object(images_document, "_ouvrir_zip",
                               side_effect=ValueError("trop gros")), \
                mock.patch.object(images_document.incorpores, "reperer") as reperer:
            with self.assertRaises(ValueError):
                images_document.lister(pptx_apercu_png(), "pptx")
        reperer.assert_not_called()


class RapportImbrique(unittest.TestCase):
    def test_parent_et_enfant(self):
        classeur = greffer(reel_xlsx(["Ventes"]), "xl/worksheets/sheet1.xml", [visio()])
        hote = greffer(reel_docx(["Texte"]), "word/document.xml",
                       [("Budget.xlsx", "Excel.Sheet.12", classeur, T_PACKAGE)])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = os.path.join(tmp, "src.docx")
            with open(src, "wb") as f:
                f.write(hote)
            _, rapport = I.relever(src, niveau=1)
        cibles = [o["cible"] for o in rapport["non_traites"]]
        self.assertTrue(any(c.startswith("Budget.xlsx › ") and c.endswith("schema.vsdx")
                            for c in cibles), cibles)
        sous = next(o for o in rapport["non_traites"] if "›" in o["cible"])
        self.assertEqual(sous["raison"], "visio")


class PPTXProgressif(unittest.TestCase):
    def test_non_traites_cumules_sans_doublon(self):
        octets = greffer(reel_pptx("Titre"), "ppt/slides/slide1.xml", [visio()])
        dossier = tempfile.mkdtemp(prefix="fact_pptx_")
        try:
            src = os.path.join(dossier, "src.pptx")
            with open(src, "wb") as f:
                f.write(octets)
            eng = PPTXTranslatorEngine()
            try:
                eng._cleanup_temp()
                eng._extract_zip(src)
                eng.extract_slide(1)
                eng.extract_slide(1)
                raisons = [o["raison"] for o in eng.objets_non_traites]
            finally:
                eng._cleanup_temp()
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
        self.assertEqual(raisons, ["visio"])

    def extraire(self, octets, diapos):
        dossier = tempfile.mkdtemp(prefix="fact_pptx_")
        try:
            src = os.path.join(dossier, "src.pptx")
            with open(src, "wb") as f:
                f.write(octets)
            eng = PPTXTranslatorEngine()
            try:
                eng._cleanup_temp()
                eng._extract_zip(src)
                for n in diapos:
                    eng.extract_slide(n)
                return list(eng.objets_non_traites)
            finally:
                eng._cleanup_temp()
        finally:
            shutil.rmtree(dossier, ignore_errors=True)

    def test_objet_partage_par_deux_diapositives_une_seule_fois(self):
        self.assertEqual([o["raison"] for o in self.extraire(pptx_deux_diapos(), (1, 2))],
                         ["visio"])

    def test_objet_lie_seul_sur_la_diapositive(self):
        self.assertEqual([o["raison"] for o in self.extraire(pptx_objet_lie(), (1,))], ["lie"])

    def test_lien_hypertexte_n_ouvre_pas_le_paquet(self):
        def change(p):
            rels = "ppt/slides/_rels/slide1.xml.rels"
            p[rels] = p[rels].replace(
                b"</Relationships>",
                (f'<Relationship Id="rIdL" Type="{R}/hyperlink" Target="https://exemple.org" '
                 'TargetMode="External"/></Relationships>').encode())
        with mock.patch.object(I, "reperer", wraps=I.reperer) as reperer:
            self.assertEqual(self.extraire(reecrire(reel_pptx("Titre"), change), (1,)), [])
        reperer.assert_not_called()


class Cumul(unittest.TestCase):
    def test_sans_doublon_sur_cible_et_raison(self):
        liste = []
        I.cumuler(liste, [{"cible": "a", "raison": "visio", "partie": "p1"}])
        I.cumuler(liste, [{"cible": "a", "raison": "visio", "partie": "p2"},
                          {"cible": "a", "raison": "apercu"}])
        self.assertEqual([(o["cible"], o["raison"]) for o in liste],
                         [("a", "visio"), ("a", "apercu")])


class Restes(unittest.TestCase):
    """Ce qui rate après l'extraction doit arriver jusqu'au client."""

    def test_redessin_en_panne(self):
        with mock.patch("engines.apercus.redessiner", side_effect=RuntimeError("panne")):
            moteur = injecter("pptx", pptx_avec_apercu())
        self.assertEqual(moteur.objets_restes, [{"cible": "Feuille1.xlsx", "raison": "apercu"}])

    def test_redessin_partiel(self):
        with mock.patch("engines.apercus.redessiner", return_value={}):
            moteur = injecter("pptx", pptx_avec_apercu())
        self.assertEqual(moteur.objets_restes, [{"cible": "Feuille1.xlsx", "raison": "apercu"}])

    def test_redessin_reussi_rien_a_signaler(self):
        with mock.patch("engines.apercus.redessiner",
                        side_effect=lambda ds: {d.cle: png() for d in ds}):
            moteur = injecter("pptx", pptx_avec_apercu())
        self.assertEqual(moteur.objets_restes, [])

    def test_image_partagee_avec_un_objet_non_traduit(self):
        with mock.patch("engines.apercus.redessiner", return_value={}) as redessiner:
            moteur = injecter("pptx", pptx_apercu_partage())
        self.assertIn({"cible": "Feuille1.xlsx", "raison": "apercu"}, moteur.objets_restes)
        self.assertEqual(redessiner.call_count, 0)

    def test_objet_impossible_a_remettre(self):
        hote = greffer(reel_docx(["Texte"]), "word/document.xml", [classeur()])
        moteur = injecter("docx", hote,
                          mock.patch.object(I, "_moderne", side_effect=RuntimeError("panne")))
        self.assertEqual(moteur.objets_restes, [{"cible": "Feuille1.xlsx", "raison": "reinjection"}])

    @staticmethod
    def panne_de_l_interne():
        vrai = I._moderne
        appels = []

        def casse_l_interne(ex):
            # Le 1er appel relit le parent ; le 2e remet l'objet interne en place.
            if ex.objet.cible.endswith("Interne.xlsx"):
                appels.append(ex)
                if len(appels) > 1:
                    raise RuntimeError("panne")
            return vrai(ex)

        return mock.patch.object(I, "_moderne", casse_l_interne)

    def test_objet_dans_un_objet(self):
        moteur = injecter("docx", hote_imbrique(), self.panne_de_l_interne())
        self.assertEqual(moteur.objets_restes,
                         [{"cible": "Budget.xlsx › Interne.xlsx", "raison": "reinjection"}])

    def test_parent_perdu_seul_signale(self):
        vrai = I.reecrire

        def casse_le_parent(ex, nouveaux):
            if ex.objet.cible.endswith("Budget.xlsx"):
                raise RuntimeError("panne")
            return vrai(ex, nouveaux)

        with self.panne_de_l_interne(), mock.patch.object(I, "reecrire", casse_le_parent):
            moteur = injecter("docx", hote_imbrique())
        self.assertEqual(moteur.objets_restes, [{"cible": "Budget.xlsx", "raison": "reinjection"}])

    def test_objet_illisible_a_la_reinjection(self):
        hote = greffer(reel_docx(["Texte"]), "word/document.xml", [classeur()])
        moteur = injecter("docx", hote, mock.patch.object(I, "extraire", return_value=None))
        self.assertEqual(moteur.objets_restes, [{"cible": "Feuille1.xlsx", "raison": "reinjection"}])

    def test_traduction_sans_element_a_la_relecture(self):
        hote = greffer(reel_docx(["Texte"]), "word/document.xml", [classeur()])
        vrai = I._elements_de
        moteur = injecter("docx", hote,
                          mock.patch.object(I, "_elements_de", lambda d: list(vrai(d))[1:]))
        self.assertEqual(moteur.objets_restes, [{"cible": "Feuille1.xlsx", "raison": "reinjection"}])


class BudgetReinjection(unittest.TestCase):
    def test_le_budget_de_l_extraction_suffit(self):
        hote = hote_imbrique()
        budget = I.Budget(10 ** 9)
        elements, _ = I.relever(hote, budget=budget)
        consomme = 10 ** 9 - budget.reste
        traductions = {e["id"]: "XX " + e["text"] for e in elements}
        modifs = I.reinjecter(hote, traductions, budget=I.Budget(consomme))
        self.assertEqual(modifs.restes, [])
        self.assertTrue(modifs.cibles)


class FichiersForges(unittest.TestCase):
    NS_X = I.NS["x"]
    NS_XDR = I.NS["xdr"]

    def ratio(self, attributs_col, a_col=3, a_ligne=3, decalage=0):
        feuille = etree.fromstring(
            f'<worksheet xmlns="{self.NS_X}"><cols><col {attributs_col}/></cols></worksheet>')

        def marque(nom, col, off, ligne):
            return (f"<{nom}><xdr:col>{col}</xdr:col><xdr:colOff>{off}</xdr:colOff>"
                    f"<xdr:row>{ligne}</xdr:row><xdr:rowOff>0</xdr:rowOff></{nom}>")

        ancre = etree.fromstring(
            f'<anchor xmlns="{self.NS_X}" xmlns:xdr="{self.NS_XDR}">'
            + marque("from", 0, 0, 0) + marque("to", a_col, decalage, a_ligne) + "</anchor>")
        return I._ratio_ancre(feuille, ancre)

    def test_valeurs_non_finies(self):
        self.assertIsNotNone(self.ratio('min="1e999" max="1e999" width="1e999"'))

    def test_entier_demesure(self):
        self.assertIsNone(self.ratio('min="1" max="1" width="9"', decalage="9" * 400))

    def test_ancre_demesuree_vite_traitee(self):
        debut = time.monotonic()
        self.ratio('min="1" max="1" width="9"', a_col=50_000_000, a_ligne=50_000_000)
        self.assertLess(time.monotonic() - debut, 1.5)

    def test_colonnes_repetees_bornees(self):
        cols = "".join('<col min="1" max="16384" width="9"/>' for _ in range(5000))
        feuille = etree.fromstring(f'<worksheet xmlns="{self.NS_X}"><cols>{cols}</cols></worksheet>')
        ancre = etree.fromstring(
            f'<anchor xmlns="{self.NS_X}" xmlns:xdr="{self.NS_XDR}">'
            '<from><xdr:col>0</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>0</xdr:row>'
            '<xdr:rowOff>0</xdr:rowOff></from><to><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff>'
            '<xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff></to></anchor>')
        debut = time.monotonic()
        self.assertIsNotNone(I._ratio_ancre(feuille, ancre))
        self.assertLess(time.monotonic() - debut, 1.5)


class RapportDoublons(unittest.TestCase):
    def test_meme_nom_meme_raison_une_seule_ligne(self):
        o = I.reperer(greffer(reel_docx(["T"]), "word/document.xml", [visio()]))[0]
        nom = posixpath.basename(o.cible)
        autre = dataclasses.replace(o, cible="word/autre/" + nom)
        self.assertEqual(len(I.rapport([o, autre])["non_traites"]), 1)


class HorsDiapositives(unittest.TestCase):
    DISPOSITION = "ppt/slideLayouts/slideLayout1.xml"

    def moteur(self, octets):
        m = PPTXTranslatorEngine()
        m._source = octets
        return m

    def test_objet_sur_une_disposition(self):
        hote = greffer(reel_pptx("Titre"), self.DISPOSITION, [classeur()])
        self.assertEqual(self.moteur(hote).objets_hors_diapositives(),
                         [{"cible": "Feuille1.xlsx", "raison": "hors_diapo"}])

    def test_raison_propre_conservee(self):
        hote = greffer(reel_pptx("Titre"), self.DISPOSITION, [visio()])
        self.assertEqual([o["raison"] for o in self.moteur(hote).objets_hors_diapositives()],
                         ["visio"])

    def test_aussi_sur_une_diapositive(self):
        hote = greffer(greffer(reel_pptx("Titre"), self.DISPOSITION, [classeur()]),
                       "ppt/slides/slide1.xml", [classeur()])
        self.assertEqual(self.moteur(hote).objets_hors_diapositives(), [])

    def test_panne_generale_objet_inconnu(self):
        for ext, hote in (
                ("docx", greffer(reel_docx(["Texte"]), "word/document.xml", [classeur()])),
                ("xlsx", greffer(reel_xlsx(["Texte"]), "xl/worksheets/sheet1.xml", [classeur()])),
                ("pptx", greffer(reel_pptx("Titre"), "ppt/slides/slide1.xml", [classeur()]))):
            with self.subTest(ext):
                panne = mock.patch.object(I, "reinjecter", side_effect=RuntimeError("x"))
                self.assertEqual(injecter(ext, hote, panne).objets_restes,
                                 [{"cible": None, "raison": "reinjection"}])


class Evenement(unittest.TestCase):
    def test_emis_depuis_l_extraction(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            chemin = os.path.join(tmp, "ext.json")
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump({"objets_rapport": {"non_traites": [
                    {"cible": "a.vsdx", "partie": "p", "nature": "visio", "raison": "visio"}]}}, f)
            with mock.patch.object(translation_runner, "jobs") as faux_jobs:
                translation_runner._signaler_objets("j1", extraction_path=chemin)
        attendu = [{"cible": "a.vsdx", "raison": "visio"}]
        faux_jobs.emit.assert_called_once_with("j1", "objets", {"non_traites": attendu})

    def test_rien_si_vide_ou_illisible(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            casse = os.path.join(tmp, "casse.json")
            with open(casse, "w", encoding="utf-8") as f:
                f.write("{pas du json")
            scalaire = os.path.join(tmp, "scalaire.json")
            with open(scalaire, "w", encoding="utf-8") as f:
                json.dump({"objets_rapport": {"non_traites": "n'importe quoi"}}, f)
            with mock.patch.object(translation_runner, "jobs") as faux_jobs:
                translation_runner._signaler_objets("j1", [])
                translation_runner._signaler_objets("j1", ["pas un objet"])
                translation_runner._signaler_objets("j1", extraction_path="/nexiste/pas.json")
                translation_runner._signaler_objets("j1", extraction_path=casse)
                translation_runner._signaler_objets("j1", extraction_path=scalaire)
        faux_jobs.emit.assert_not_called()


class Jobs(unittest.TestCase):
    """Les trois parcours, de bout en bout : extraction puis réinjection."""

    def verifier(self, ext, partie, hote, progressif):
        objets_visio = greffer(hote, partie, [visio()])
        raisons = [o["raison"] for liste in lancer_job(ext, objets_visio, progressif) for o in liste]
        self.assertEqual(raisons, ["visio"])
        avec_texte = greffer(hote, partie, [classeur()])
        recus = lancer_job(ext, avec_texte, progressif, reinjection_cassee=True)
        self.assertEqual(recus, [[{"cible": None, "raison": "reinjection"}]])

    def test_docx(self):
        self.verifier("docx", "word/document.xml", reel_docx(["Rapport annuel"]), False)

    def test_xlsx_progressif(self):
        self.verifier("xlsx", "xl/worksheets/sheet1.xml", reel_xlsx(["Ventes"]), True)

    def test_pptx_progressif(self):
        self.verifier("pptx", "ppt/slides/slide1.xml", reel_pptx("Titre"), True)

    def test_xlsx(self):
        self.verifier("xlsx", "xl/worksheets/sheet1.xml", reel_xlsx(["Ventes"]), False)

    def test_pptx(self):
        self.verifier("pptx", "ppt/slides/slide1.xml", reel_pptx("Titre"), False)

    def test_pptx_progressif_objet_sur_une_disposition(self):
        hote = greffer(reel_pptx("Titre"), HorsDiapositives.DISPOSITION, [classeur()])
        self.assertEqual(lancer_job("pptx", hote, True),
                         [[{"cible": "Feuille1.xlsx", "raison": "hors_diapo"}]])


if __name__ == "__main__":
    unittest.main()
