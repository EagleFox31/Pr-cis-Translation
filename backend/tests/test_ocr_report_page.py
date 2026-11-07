"""Report d'une page lue après coup : ordre pose / débit / retour arrière,
pages lues sans traduction, verrou lecture-écriture, délai de lecture d'image
et copie propre au document.

    PYTHONUTF8=1 venv/Scripts/python.exe tests/test_ocr_report_page.py
"""
import contextlib
import io
import json
import os
import tempfile
import threading
import time
import types
import unittest

import racine  # noqa: F401
from PIL import Image

from app.api import documents as api
from app.services import ocr_pages, render_cache, translation_runner
from app.services.ocr_v2 import image as image_ocr
from app.services.translation_runner import _reporter_page, pages_lues_sans_traduction

PDF = b"%PDF-1.4 page lue"


def page_json(numero, tagged=None):
    """Page de traduction : un paragraphe, traduit si `tagged` est donné."""
    paragraphe = {"type": "paragraph", "text": "texte"}
    if tagged is not None:
        paragraphe["tr_tagged"] = tagged
    return {"page_num": numero, "elements": [paragraphe]}


class Dossier(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def ecrire_json(self, nom, pages):
        chemin = os.path.join(self.dir, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"pages": pages}, f)
        return chemin

    def octets(self, chemin):
        with open(chemin, "rb") as f:
            return f.read()


class Report(Dossier):
    def setUp(self):
        super().setUp()
        self.trad = self.ecrire_json("pages_ocrv3.json", [page_json(1, "Hello"), page_json(2)])
        ocr_pages.ecrire(self.trad, 3, "illisible", "lecture")
        ocr_pages.ecrire_choix(self.trad, [3], "vide")
        self.avant = self.octets(self.trad)
        self.nouvelle = page_json(3, "Third page")

    def numeros(self):
        with open(self.trad, encoding="utf-8") as f:
            return [p["page_num"] for p in json.load(f)["pages"]]

    def test_debit_en_erreur_tout_est_remis(self):
        def debiter():
            raise RuntimeError("base indisponible")
        with self.assertRaises(RuntimeError):
            _reporter_page(self.trad, 3, self.nouvelle, PDF, debiter)
        self.assertEqual(self.octets(self.trad), self.avant)
        self.assertEqual(ocr_pages.lire(self.trad, 3), {"statut": "illisible", "motif": "lecture"})
        self.assertIsNone(ocr_pages.pdf_de(self.trad, 3))
        self.assertEqual(ocr_pages.lire_choix(self.trad), {3: "vide"})

    def test_debit_refuse_tout_est_remis(self):
        appels = []

        def debiter():
            appels.append(1)
            return False
        self.assertIs(_reporter_page(self.trad, 3, self.nouvelle, PDF, debiter), False)
        self.assertEqual(appels, [1])
        self.assertEqual(self.octets(self.trad), self.avant)
        self.assertEqual(ocr_pages.lire(self.trad, 3), {"statut": "illisible", "motif": "lecture"})
        self.assertIsNone(ocr_pages.pdf_de(self.trad, 3))

    def test_page_deja_ok_ni_reposee_ni_debitee(self):
        ocr_pages.ecrire(self.trad, 3, "ok", None, b"%PDF-deja")
        appels = []
        self.assertIs(_reporter_page(self.trad, 3, self.nouvelle, PDF,
                                     lambda: appels.append(1) or True), True)
        self.assertEqual(appels, [])
        self.assertEqual(self.octets(self.trad), self.avant)
        self.assertEqual(ocr_pages.pdf_de(self.trad, 3), b"%PDF-deja")

    def test_succes_page_posee_statut_ok_choix_efface(self):
        self.assertIs(_reporter_page(self.trad, 3, self.nouvelle, PDF, lambda: True), True)
        self.assertEqual(self.numeros(), [1, 2, 3])
        with open(self.trad, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["pages"][2], self.nouvelle)
        self.assertEqual(ocr_pages.lire(self.trad, 3), {"statut": "ok", "motif": None})
        self.assertEqual(ocr_pages.pdf_de(self.trad, 3), PDF)
        self.assertEqual(ocr_pages.lire_choix(self.trad), {})

    def test_page_posee_avant_le_debit(self):
        vu = {}

        def debiter():
            vu["statut"] = ocr_pages.lire(self.trad, 3)["statut"]
            vu["pages"] = self.numeros()
            return True
        _reporter_page(self.trad, 3, self.nouvelle, PDF, debiter)
        self.assertEqual(vu, {"statut": "ok", "pages": [1, 2, 3]})


class LuesSansTraduction(Dossier):
    def test_page_ok_sans_tr_tagged_comptee(self):
        trad = self.ecrire_json("pages_ocrv3.json", [page_json(1, "Hello"), page_json(2)])
        ocr_pages.ecrire(trad, 1, "ok", None, PDF)
        ocr_pages.ecrire(trad, 2, "ok", None, PDF)
        self.assertEqual(pages_lues_sans_traduction(trad), {2})

    def test_page_ok_avec_tr_tagged_non_comptee(self):
        trad = self.ecrire_json("pages_ocrv3.json", [page_json(1, "Hello")])
        ocr_pages.ecrire(trad, 1, "ok", None, PDF)
        self.assertEqual(pages_lues_sans_traduction(trad), set())

    def test_page_ok_absente_du_json_comptee_et_autres_statuts_ignores(self):
        trad = self.ecrire_json("pages_ocrv3.json", [page_json(1, "Hello")])
        ocr_pages.ecrire(trad, 4, "ok", None, PDF)
        ocr_pages.ecrire(trad, 5, "illisible", "lecture")
        ocr_pages.ecrire(trad, 6, "blanche")
        self.assertEqual(pages_lues_sans_traduction(trad), {4})

    def test_mode_structure_paragraphe_non_tague_non_compte(self):
        trad = self.ecrire_json("pages_debug_ocrv3.json", [page_json(2)])
        ocr_pages.ecrire(trad, 2, "ok", None, PDF)
        self.assertTrue(translation_runner.mode_structure(trad))
        self.assertEqual(pages_lues_sans_traduction(trad), set())


class VerrouEcrivainPrioritaire(unittest.TestCase):
    def test_un_nouveau_lecteur_attend_l_ecrivain_en_attente(self):
        chemin = os.path.join(tempfile.gettempdir(), f"verrou-{os.getpid()}-{time.monotonic_ns()}.json")
        verrou = render_cache.verrou_traduction(chemin)
        journal = []
        ecrivain_attend = threading.Event()
        lecteur2_tente = threading.Event()
        liberer_lecteur1 = threading.Event()

        def ecrivain():
            ecrivain_attend.set()
            with verrou.ecrire():
                journal.append("ecrivain")

        def lecteur2():
            lecteur2_tente.set()
            with verrou.lire():
                journal.append("lecteur2")

        t_ecr = threading.Thread(target=ecrivain)
        t_lec2 = threading.Thread(target=lecteur2)
        with verrou.lire():  # premier lecteur
            t_ecr.start()
            self.assertTrue(ecrivain_attend.wait(1))
            time.sleep(0.2)  # l'écrivain est bien entré en attente
            t_lec2.start()
            self.assertTrue(lecteur2_tente.wait(1))
            time.sleep(0.2)
            self.assertEqual(journal, [], "ni l'écrivain ni le second lecteur ne passent")
        liberer_lecteur1.set()
        t_ecr.join(2)
        t_lec2.join(2)
        self.assertEqual(journal, ["ecrivain", "lecteur2"])


class _Lecteur:
    """Lecteur factice : retient le délai reçu, ne lit rien."""
    def __init__(self):
        self.delais = []

    def manquant(self):
        return None

    def lire(self, _chemin, delai):
        self.delais.append(delai)
        return []


class DelaiApresLeGuichet(unittest.TestCase):
    def test_attente_au_guichet_ne_reduit_pas_le_delai(self):
        tampon = io.BytesIO()
        Image.new("RGB", (60, 40), (255, 255, 255)).save(tampon, format="PNG")
        lecteur = _Lecteur()

        @contextlib.contextmanager
        def tour():
            time.sleep(1.7)  # attente au guichet plus longue que le délai
            yield

        image_ocr.traduire_image(tampon.getvalue(), lambda textes: textes, lecteur,
                                 delai_s=1.5, tour=tour)
        self.assertEqual(len(lecteur.delais), 1)
        # Mesuré depuis l'entrée dans le tour : ~1,5 s (le plancher d'1 s
        # donnerait 1,0 si l'attente était décomptée).
        self.assertGreater(lecteur.delais[0], 1.3)
        self.assertLessEqual(lecteur.delais[0], 1.5)


class CopieReutilisee(Dossier):
    def test_copie_existante_renvoyee_sans_etre_reecrite(self):
        trad = self.ecrire_json("pages_ocrv3.json", [page_json(1, "Hello")])
        doc = types.SimpleNamespace(id="abc-123", translated_path=trad)
        copie = api._copie_prevue(doc)
        self.assertNotEqual(copie, trad)
        with open(copie, "w", encoding="utf-8") as f:
            f.write('{"pages": [{"page_num": 9}]}')
        avant = self.octets(copie)
        self.assertEqual(api._copie_du_document(doc), copie)
        self.assertEqual(self.octets(copie), avant)
        self.assertNotEqual(self.octets(copie), self.octets(trad))


if __name__ == "__main__":
    unittest.main()
