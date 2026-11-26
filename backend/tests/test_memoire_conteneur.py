"""Tenue en mémoire du serveur (étude docs/etude-deconnexion-oom.md).

Mesure de la mémoire libre du conteneur, file d'attente des travaux quand elle
manque, détection par tuiles identique à la détection d'un bloc, plafond de
lecture à la taille affichée dans un document Office.

    backend/venv/Scripts/python.exe backend/tests/test_memoire_conteneur.py
"""
import io
import os
import shutil
import tempfile
import threading
import time
import unittest
import zipfile
from unittest import mock

import racine  # noqa: F401
import numpy as np
from app.services import images_document, memoire
from app.services import scheduler as sched_mod
from app.services.ocr_v2 import ppocr

MO = memoire.MO


class CgroupFactice(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="cgroup_")
        self.addCleanup(shutil.rmtree, self.dossier, True)
        patch = mock.patch.object(memoire, "_CGROUP", self.dossier)
        patch.start()
        self.addCleanup(patch.stop)

    def ecrire(self, limite, courant, inactif=0):
        for nom, val in (("memory.max", limite), ("memory.current", courant),
                         ("memory.stat", f"anon {courant - inactif - 10 * MO}\nkernel {10 * MO}\n"
                                         f"file {inactif}\ninactive_file {inactif}\n")):
            with open(os.path.join(self.dossier, nom), "w", encoding="ascii") as f:
                f.write(f"{val}\n")

    def test_disponible_retire_le_cache_inactif(self):
        self.ecrire(1024 * MO, 900 * MO, inactif=100 * MO)
        self.assertEqual(memoire.disponible(), 224 * MO)

    def test_sans_limite_rien_n_est_bride(self):
        self.ecrire("max", 900 * MO)
        self.assertIsNone(memoire.disponible())
        self.assertTrue(memoire.attendre(10**12, "test"))

    def test_cache_de_fichiers_actif_non_compte(self):
        self.ecrire(1024 * MO, 900 * MO)
        with open(os.path.join(self.dossier, "memory.stat"), "w", encoding="ascii") as f:
            f.write(f"anon {600 * MO}\nfile {290 * MO}\nkernel {10 * MO}\nactive_file {200 * MO}\n")
        self.assertEqual(memoire.disponible(), 414 * MO)

    def test_hors_conteneur(self):
        self.assertIsNone(memoire.disponible())

    def test_attente_puis_reprise(self):
        self.ecrire(1024 * MO, 1000 * MO)
        threading.Timer(0.3, self.ecrire, (1024 * MO, 200 * MO)).start()
        debut = time.monotonic()
        self.assertTrue(memoire.attendre(300 * MO, "test"))
        self.assertGreater(time.monotonic() - debut, 0.25)

    def test_attente_bornee(self):
        self.ecrire(1024 * MO, 1000 * MO)
        with mock.patch.object(memoire, "ATTENTE_MAX_S", 0.2):
            self.assertFalse(memoire.attendre(300 * MO, "test"))

    def test_arret_interrompt_l_attente(self):
        self.ecrire(1024 * MO, 1000 * MO)
        arret = threading.Event()
        arret.set()
        self.assertFalse(memoire.attendre(300 * MO, "test", arret))


class BudgetMemoire(unittest.TestCase):
    """Nombre fixe de travaux simultanés, commun aux deux files."""

    def test_places_a_1_go(self):
        self.assertEqual(memoire.places_pour(1024 * MO, 300, 284, 150), 2)

    def test_places_a_1_go_avec_libreoffice(self):
        # Réglage réel : détection + aperçu LibreOffice réservés d'office.
        reserve = memoire.DETECTION_MO + memoire.LIBREOFFICE_MO
        self.assertEqual(memoire.places_pour(1024 * MO, 300, reserve, 150), 1)
        self.assertEqual(memoire.places_pour(2048 * MO, 300, reserve, 150), 8)

    def test_places_a_768_mo(self):
        self.assertEqual(memoire.places_pour(768 * MO, 300, 284, 150), 1)

    def test_toujours_au_moins_une_place(self):
        self.assertEqual(memoire.places_pour(256 * MO, 300, 284, 150), 1)

    def test_sans_plafond_pas_de_budget(self):
        self.assertIsNone(memoire.places_pour(None, 300, 284, 150))
        self.assertTrue(memoire.Budget(None).prendre_sans_attendre())

    def test_troisieme_travail_attend_en_file(self):
        jobs = sched_mod.jobs
        vus, liberer = {}, threading.Event()
        lances = []
        emit_orig = jobs.emit

        def espion(job_id, event_type, payload):
            vus.setdefault(job_id, []).append(event_type)
            return emit_orig(job_id, event_type, payload)

        def travail(n):
            lances.append(n)
            liberer.wait(5)

        with mock.patch.object(sched_mod, "budget", memoire.Budget(2)), \
                mock.patch.object(jobs, "emit", espion):
            # Deux files distinctes, comme traductions et scans : la 3e attend
            # quand même, le budget est commun.
            a = sched_mod.TranslationScheduler(workers=2)
            b = sched_mod.TranslationScheduler(workers=3)
            ids = [jobs.create() for _ in range(3)]
            a.submit(ids[0], 0, travail, (0,))
            b.submit(ids[1], 0, travail, (1,))
            time.sleep(0.2)
            b.submit(ids[2], 0, travail, (2,))
            time.sleep(0.3)
            self.assertEqual(sorted(lances), [0, 1], "3e lancée sans place")
            self.assertIn("queued", vus[ids[2]])
            liberer.set()
            for _ in range(30):
                if len(lances) == 3:
                    break
                time.sleep(0.1)
            self.assertEqual(sorted(lances), [0, 1, 2], "place jamais rendue")


class ModeleFactice:
    """Détecteur local : la probabilité d'un point ne dépend que de ce point.
    Recoller les centres des tuiles doit donc rendre la carte d'un bloc."""

    def __init__(self):
        self.formes = []

    def run(self, _sorties, entrees, _options=None):
        x = entrees["x"]
        self.formes.append(x.shape[2:])
        return [1 / (1 + np.exp(-x.mean(axis=1, keepdims=True)))]


class Tuiles(unittest.TestCase):
    def test_tuiles_identiques_au_bloc(self):
        rng = np.random.default_rng(0)
        image = rng.integers(0, 256, (1600, 2400, 3), dtype=np.uint8)
        modele = ModeleFactice()
        tuiles = ppocr.PPOCR._probabilites(modele, image)
        self.assertGreater(len(modele.formes), 1)
        self.assertTrue(all(max(f) <= ppocr.TUILE for f in modele.formes))
        with mock.patch.object(ppocr, "TUILE", 4096):
            bloc = ppocr.PPOCR._probabilites(ModeleFactice(), image)
        self.assertEqual(tuiles.shape, bloc.shape)
        self.assertTrue(np.allclose(tuiles, bloc, atol=1e-6))

    def test_peu_de_memoire_petits_morceaux_meme_carte(self):
        rng = np.random.default_rng(1)
        image = rng.integers(0, 256, (1600, 2400, 3), dtype=np.uint8)
        normal = ppocr.PPOCR._probabilites(ModeleFactice(), image)
        modele = ModeleFactice()
        with mock.patch.object(memoire, "disponible", lambda: 150 * MO), \
                mock.patch.object(memoire, "attendre") as attente:
            serre = ppocr.PPOCR._probabilites(modele, image)
        attente.assert_not_called()
        self.assertTrue(all(max(f) <= 512 for f in modele.formes), modele.formes)
        self.assertTrue(np.allclose(normal, serre, atol=1e-6))

    def test_plafond_reduit_la_resolution(self):
        lecteur = ppocr.PPOCR.__new__(ppocr.PPOCR)
        lecteur._rendre = None
        vus = []
        lecteur._probabilites = lambda det, img, opt=None: (
            vus.append(img.shape[:2]), np.zeros(img.shape[:2], np.float32))[1]
        image = np.zeros((2964, 4000, 3), np.uint8)
        lecteur._detecter(None, image)
        with ppocr.plafond(2000):
            lecteur._detecter(None, image)
        with ppocr.plafond(None):
            lecteur._detecter(None, image)
        self.assertEqual(max(vus[0]), 4000)
        self.assertTrue(1984 <= max(vus[1]) <= 2016, vus[1])
        self.assertEqual(max(vus[2]), 4000)
        petite = np.zeros((300, 800, 3), np.uint8)
        with ppocr.plafond(960):
            lecteur._detecter(None, petite)
        self.assertEqual(max(vus[3]), 800, "une petite image ne doit pas changer")


class TailleAffichee(unittest.TestCase):
    """Côté utile = plus grande taille affichée à 150 points par pouce."""

    @staticmethod
    def png(l, h):
        from PIL import Image
        sortie = io.BytesIO()
        Image.new("RGB", (l, h), "white").save(sortie, "PNG")
        return sortie.getvalue()

    def cotes(self, data, ext):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return images_document._cotes_affichees(z, ext)

    def test_pptx_plus_grande_utilisation(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        image = self.png(4000, 3000)
        for largeur in (4, 8):          # même image, affichée 4 puis 8 pouces
            diapo = prs.slides.add_slide(prs.slide_layouts[6])
            diapo.shapes.add_picture(io.BytesIO(image), Inches(1), Inches(1), width=Inches(largeur))
        sortie = io.BytesIO()
        prs.save(sortie)
        cotes = self.cotes(sortie.getvalue(), "pptx")
        self.assertEqual(list(cotes.values()), [1200])     # 8 pouces × 150

    def test_pptx_minimum(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        diapo = prs.slides.add_slide(prs.slide_layouts[6])
        diapo.shapes.add_picture(io.BytesIO(self.png(400, 300)), Inches(1), Inches(1), width=Inches(1))
        sortie = io.BytesIO()
        prs.save(sortie)
        self.assertEqual(list(self.cotes(sortie.getvalue(), "pptx").values()),
                         [images_document.COTE_LECTURE_MIN])

    def test_docx(self):
        from docx import Document
        from docx.shared import Inches
        doc = Document()
        doc.add_picture(io.BytesIO(self.png(3000, 1000)), width=Inches(6))
        sortie = io.BytesIO()
        doc.save(sortie)
        cotes = self.cotes(sortie.getvalue(), "docx")
        self.assertEqual(list(cotes.values()), [images_document.COTE_LECTURE_MIN])   # 6 po × 150 = 900

    def test_docx_grande(self):
        from docx import Document
        from docx.shared import Inches
        doc = Document()
        doc.add_picture(io.BytesIO(self.png(3000, 4000)), height=Inches(9))
        sortie = io.BytesIO()
        doc.save(sortie)
        self.assertEqual(list(self.cotes(sortie.getvalue(), "docx").values()), [1350])

    def test_lister_porte_le_plafond(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        diapo = prs.slides.add_slide(prs.slide_layouts[6])
        diapo.shapes.add_picture(io.BytesIO(self.png(4000, 3000)), 0, 0, width=Inches(10))
        sortie = io.BytesIO()
        prs.save(sortie)
        images = images_document._lister_office(sortie.getvalue(), "pptx")
        self.assertEqual([i.cote_max for i in images if i.cle.endswith(".png")], [1500])


class DisqueLibre(unittest.TestCase):
    """Disque presque plein : nouveaux envois refusés, admins alertés."""

    @staticmethod
    def disque(libre_mo):
        from collections import namedtuple
        usage = namedtuple("usage", "total used free")
        return mock.patch("shutil.disk_usage", lambda _p: usage(0, 0, libre_mo * MO))

    def test_seuil(self):
        from app.services import stockage
        with self.disque(1500):
            self.assertEqual(stockage.disque_insuffisant(2048), 1500)
            self.assertIsNone(stockage.disque_insuffisant(1000))

    def test_sans_seuil_rien_n_est_bloque(self):
        from app.services import stockage
        with self.disque(1), mock.patch.object(stockage, "DISQUE_LIBRE_MIN_MO", None):
            self.assertIsNone(stockage.disque_insuffisant())

    def test_refus_507_et_alerte(self):
        import asyncio
        from fastapi import HTTPException
        from app.services import error_log, stockage
        journal = mock.AsyncMock()
        with self.disque(100), mock.patch.object(stockage, "DISQUE_LIBRE_MIN_MO", 2048),                 mock.patch.object(error_log, "log_error", journal):
            with self.assertRaises(HTTPException) as refus:
                asyncio.run(stockage.refuser_si_disque_plein())
        self.assertEqual(refus.exception.status_code, 507)
        self.assertEqual(journal.await_args.kwargs["level"], "critical")
        journal.reset_mock()
        with self.disque(5000), mock.patch.object(stockage, "DISQUE_LIBRE_MIN_MO", 2048),                 mock.patch.object(error_log, "log_error", journal):
            asyncio.run(stockage.refuser_si_disque_plein())
        journal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
