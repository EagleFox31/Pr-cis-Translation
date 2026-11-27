"""Tenue en charge, lot 2 : cloisons (docs/etude-tenue-en-charge.md §4 C3, C4,
G3, G4, M4).

  (a) au plus N rendus simultanés (compartiment « rendus »), et la mémoire
      estimée est retenue puis rendue ;
  (b) une attente de place n'occupe aucun thread ;
  (c) deux téléchargements simultanés du même document = un seul rendu ;
  (d) file LibreOffice : une conversion urgente ajoutée après trois
      conversions « à l'avance » passe juste après celle en cours ;
  (e) file pleine : la conversion à l'avance est ignorée, l'urgente passe ;
      une conversion à l'avance dont le fichier est remplacé est abandonnée ;
  (f) plus de démarrage sans marge après le délai d'attente de la mémoire ;
  (g) rendus de fond : après les demandeurs interactifs, le plus récent d'abord ;
  (h) détection d'image : attente de mémoire sans verrou, arrêtable, bornée ;
  (i) `tour_async` : mêmes priorités que `tour`, annulation = file libérée ;
  (j) fil d'exécution saturé de préparations : l'aperçu urgent passe d'abord ;
  (k) un rendu de fond ne prend pas la priorité urgente ;
  (l) une place de compartiment attend la marge mémoire ;
  (m) rendus de fond en attente bornés : le plus ancien est écarté.

Exécution :  cd backend && venv/Scripts/python.exe -m pytest tests/test_tenue_en_charge_lot2.py -q
Ne touche ni au réseau ni à la base.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import racine  # noqa: F401  -- met backend/ sur le chemin

from app.api import documents as docs                  # noqa: E402
from app.services import office, render_cache          # noqa: E402
from app.services.jobs import ArretDemande             # noqa: E402
from app.services.ocr_v2 import ppocr                  # noqa: E402
from app.services.ocr_v2.detect import LectureEchouee  # noqa: E402
from app.services import memoire                       # noqa: E402
from app.services.file_libreoffice import ConversionAbandonnee, FileConversions  # noqa: E402


def _attendre(cond, delai=5.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return False


# ── (a) au plus N rendus simultanés ──────────────────────────────────────────
class CompartimentBorne(unittest.TestCase):
    def test_au_plus_n_rendus_a_la_fois(self):
        comp = memoire.Compartiment("t", 2, 10)
        actifs, pic = [0], [0]

        async def rendu():
            async with comp.place_async():
                actifs[0] += 1
                pic[0] = max(pic[0], actifs[0])
                await asyncio.sleep(0.05)
                actifs[0] -= 1

        async def scenario():
            await asyncio.gather(*(rendu() for _ in range(8)))

        asyncio.run(scenario())
        self.assertEqual(pic[0], 2)
        self.assertEqual(comp.occupees, 0)
        self.assertEqual(comp.en_attente, 0)

    def test_memoire_estimee_retenue_puis_rendue(self):
        comp = memoire.Compartiment("t", 2, 10)
        avant = memoire.reserve()

        async def scenario():
            async with comp.place_async():
                self.assertEqual(memoire.reserve(), avant + 10 * memoire.MO)

        asyncio.run(scenario())
        self.assertEqual(memoire.reserve(), avant)

    def test_place_rendue_si_le_travail_echoue(self):
        comp = memoire.Compartiment("t", 1, 10)
        avant = memoire.reserve()

        async def scenario():
            with self.assertRaises(ValueError):
                async with comp.place_async():
                    raise ValueError("boom")
            async with comp.place_async():
                pass

        asyncio.run(scenario())
        self.assertEqual(comp.occupees, 0)
        self.assertEqual(memoire.reserve(), avant)

    def test_sans_limite(self):
        comp = memoire.Compartiment("t", None, 10)

        async def scenario():
            async with comp.place_async(), comp.place_async(), comp.place_async():
                self.assertEqual(comp.en_attente, 0)

        asyncio.run(scenario())
        self.assertEqual(comp.occupees, 0)

    def test_attente_annulee_ne_perd_pas_la_place(self):
        comp = memoire.Compartiment("t", 1, 10)

        async def scenario():
            async with comp.place_async():
                tache = asyncio.create_task(comp.prendre_async())
                await asyncio.sleep(0.05)
                self.assertEqual(comp.en_attente, 1)
                tache.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await tache
                self.assertEqual(comp.en_attente, 0)
            self.assertEqual(comp.occupees, 0)

        asyncio.run(scenario())


# ── (b) l'attente n'occupe pas de thread ─────────────────────────────────────
class AttenteSansThread(unittest.TestCase):
    def test_vingt_attentes_n_ajoutent_aucun_thread(self):
        comp = memoire.Compartiment("t", 1, 10)

        async def scenario():
            threads_avant = threading.active_count()
            async with comp.place_async():
                attentes = [asyncio.create_task(comp.prendre_async()) for _ in range(20)]
                await asyncio.sleep(0.1)
                self.assertEqual(comp.en_attente, 20)
                # Aucun thread pris, ni par nous ni par le réservoir par défaut.
                self.assertEqual(threading.active_count(), threads_avant)
                self.assertIsNone(asyncio.get_running_loop()._default_executor)
                for t in attentes:
                    t.cancel()
                await asyncio.gather(*attentes, return_exceptions=True)
            self.assertEqual(comp.occupees, 0)

        asyncio.run(scenario())

    def test_la_boucle_reste_reactive_pendant_l_attente(self):
        comp = memoire.Compartiment("t", 1, 10)

        async def scenario():
            async with comp.place_async():
                attente = asyncio.create_task(comp.prendre_async())
                t0 = time.monotonic()
                for _ in range(5):
                    await asyncio.sleep(0.01)
                self.assertLess(time.monotonic() - t0, 0.5)
                attente.cancel()
                await asyncio.gather(attente, return_exceptions=True)

        asyncio.run(scenario())


# ── (g) rendus de fond : interactifs d'abord, puis le plus récent ────────────
class RendusDeFond(unittest.TestCase):
    def test_ordre_des_places(self):
        comp = memoire.Compartiment("t", 1, 10)
        ordre: list[str] = []
        comp.prendre()                       # place tenue par un rendu en cours

        def demandeur(nom: str, fond: bool):
            with comp.place(fond=fond):
                ordre.append(nom)

        threads = []
        for nom, fond in (("fond1", True), ("fond2", True), ("fond3", True),
                          ("ecran", False)):
            t = threading.Thread(target=demandeur, args=(nom, fond))
            t.start()
            threads.append(t)
            self.assertTrue(_attendre(lambda n=len(threads): comp.en_attente == n))
        comp._rendre_place()                 # le rendu en cours finit
        for t in threads:
            t.join(5)
        self.assertEqual(ordre, ["ecran", "fond3", "fond2", "fond1"])
        self.assertEqual(comp.occupees, 0)


# ── (c) deux téléchargements simultanés = un seul rendu ──────────────────────
class TelechargementsSimultanes(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.trad = os.path.join(self.dossier, "doc.json")
        with open(self.trad, "w") as f:
            f.write("{}")
        self.rendus = 0

    def _telecharger(self):
        doc = SimpleNamespace(
            id="d1", user_id=1, original_name="a.pdf", original_path="",
            translated_path=self.trad, paid=True, pages_libres=None,
            page_count=3, status="done")
        user = SimpleNamespace(id=1, plan="pro")

        async def traduction(db, d, avec_libres=False):
            return self.trad, None

        async def get(*_a):
            return doc

        def rendu(*_a, **_k):
            self.rendus += 1
            time.sleep(0.4)
            return b"%PDF-1.4 fake"

        db = SimpleNamespace(get=get)
        with mock.patch.object(docs, "_exiger_acces", lambda *_: None), \
             mock.patch.object(docs, "_traduction", traduction), \
             mock.patch.object(docs, "pages_libres_du_document", lambda d: set()), \
             mock.patch.object(docs, "_may_read_clear", lambda *_: True), \
             mock.patch.object(docs, "_sans_pages_retirees", lambda data, *_a: data), \
             mock.patch.object(docs, "_render_or_404", rendu):
            async def deux():
                return await asyncio.gather(
                    docs.download_document("d1", user, db, None),
                    docs.download_document("d1", user, db, None))
            return asyncio.run(deux())

    def test_un_seul_rendu_pour_deux_telechargements(self):
        reponses = self._telecharger()
        self.assertEqual(self.rendus, 1)
        self.assertTrue(all(r.body == b"%PDF-1.4 fake" for r in reponses))


# ── (d)(e) file LibreOffice ──────────────────────────────────────────────────
class FileLibreOffice(unittest.TestCase):
    def _lancer(self, file, nom, ordre, a_l_avance, tenue=None, abandon=None):
        def run():
            try:
                with file.tour(a_l_avance=a_l_avance, abandon=abandon):
                    ordre.append(nom)
                    if tenue is not None:
                        tenue.wait(5)
            except ConversionAbandonnee:
                ordre.append(f"ignore:{nom}")

        t = threading.Thread(target=run)
        t.start()
        return t

    def test_l_urgente_passe_juste_apres_celle_en_cours(self):
        file = FileConversions(20)
        ordre: list[str] = []
        tenue = threading.Event()
        threads = [self._lancer(file, "en_cours", ordre, True, tenue)]
        self.assertTrue(_attendre(lambda: ordre == ["en_cours"]))
        for nom in ("avance1", "avance2", "avance3"):
            threads.append(self._lancer(file, nom, ordre, True))
            self.assertTrue(_attendre(lambda n=len(threads) - 1: file.en_attente == n))
        threads.append(self._lancer(file, "urgente", ordre, False))
        self.assertTrue(_attendre(lambda: file.en_attente == 4))
        tenue.set()
        for t in threads:
            t.join(5)
        self.assertEqual(ordre, ["en_cours", "urgente", "avance1", "avance2", "avance3"])

    def test_file_pleine_l_avance_est_ignoree_l_urgente_passe(self):
        file = FileConversions(2)
        ordre: list[str] = []
        tenue = threading.Event()
        threads = [self._lancer(file, "en_cours", ordre, False, tenue)]
        self.assertTrue(_attendre(lambda: ordre == ["en_cours"]))
        for nom in ("a1", "a2"):
            threads.append(self._lancer(file, nom, ordre, True))
            self.assertTrue(_attendre(lambda n=len(threads) - 1: file.en_attente == n))
        with self.assertRaises(ConversionAbandonnee):
            with file.tour(a_l_avance=True):
                self.fail("ne devait pas démarrer")
        threads.append(self._lancer(file, "urgente", ordre, False))
        self.assertTrue(_attendre(lambda: file.en_attente == 3))
        tenue.set()
        for t in threads:
            t.join(5)
        self.assertEqual(ordre, ["en_cours", "urgente", "a1", "a2"])

    def test_fichier_remplace_avant_son_tour_abandonne(self):
        file = FileConversions(20)
        ordre: list[str] = []
        tenue = threading.Event()
        remplace = threading.Event()
        threads = [self._lancer(file, "en_cours", ordre, False, tenue)]
        self.assertTrue(_attendre(lambda: ordre == ["en_cours"]))
        threads.append(self._lancer(file, "ancien", ordre, True, abandon=remplace.is_set))
        self.assertTrue(_attendre(lambda: file.en_attente == 1))
        remplace.set()
        # Abandonnée sans attendre son tour : la place de file est libérée.
        self.assertTrue(_attendre(lambda: "ignore:ancien" in ordre, 3))
        self.assertEqual(file.en_attente, 0)
        tenue.set()
        for t in threads:
            t.join(5)
        self.assertEqual(ordre, ["en_cours", "ignore:ancien"])


# ── (f) plus de démarrage sans marge ─────────────────────────────────────────
class PasDeDemarrageSansMarge(unittest.TestCase):
    def test_apres_le_delai_le_travail_reste_en_attente(self):
        resultat: list[bool] = []
        arret = threading.Event()
        with mock.patch.object(memoire, "disponible", return_value=10 * memoire.MO), \
             mock.patch.object(memoire, "ATTENTE_MAX_S", 0.1), \
             mock.patch.object(memoire, "_PAS_S", 0.02):
            t = threading.Thread(target=lambda: resultat.append(
                memoire.attendre(300 * memoire.MO, "traduction", arret, jusqu_a_marge=True)))
            t.start()
            time.sleep(0.5)                  # 5 fois le délai
            self.assertTrue(t.is_alive(), "le travail est parti sans marge")
            self.assertEqual(resultat, [])
            arret.set()                      # seul l'arrêt le libère
            t.join(2)
            self.assertEqual(resultat, [False])

    def test_reprise_des_que_la_marge_revient(self):
        libre = [10 * memoire.MO]
        resultat: list[bool] = []
        with mock.patch.object(memoire, "disponible", side_effect=lambda: libre[0]), \
             mock.patch.object(memoire, "ATTENTE_MAX_S", 0.1), \
             mock.patch.object(memoire, "_PAS_S", 0.02):
            t = threading.Thread(target=lambda: resultat.append(
                memoire.attendre(300 * memoire.MO, "traduction", jusqu_a_marge=True)))
            t.start()
            time.sleep(0.3)
            self.assertTrue(t.is_alive())
            libre[0] = 400 * memoire.MO
            t.join(2)
            self.assertEqual(resultat, [True])

    def test_les_autres_attentes_gardent_leur_borne(self):
        with mock.patch.object(memoire, "disponible", return_value=10 * memoire.MO), \
             mock.patch.object(memoire, "ATTENTE_MAX_S", 0.1), \
             mock.patch.object(memoire, "_PAS_S", 0.02):
            self.assertFalse(memoire.attendre(300 * memoire.MO, "rendu"))


# ── (h) détection d'image : attente de mémoire sans verrou, arrêtable, bornée ─
class DetectionAttendMemoire(unittest.TestCase):
    @staticmethod
    def _besoin(t):
        return t * memoire.MO

    def _lancer(self, resultat, verifier=None):
        def run():
            try:
                with ppocr.arret(verifier):
                    with ppocr._creneau_detection([2, 1], self._besoin) as tuile:
                        resultat.append(("tuile", tuile))
            except BaseException as e:               # noqa: BLE001
                resultat.append(("erreur", type(e)))
        t = threading.Thread(target=run)
        t.start()
        return t

    def test_arret_du_job_pendant_l_attente_sans_tenir_le_verrou(self):
        arret = threading.Event()

        def verifier():
            if arret.is_set():
                raise ArretDemande("stop")

        resultat: list = []
        with mock.patch.object(memoire, "disponible", return_value=0), \
             mock.patch.object(memoire, "_PAS_S", 0.02), \
             mock.patch.object(ppocr, "ATTENTE_DETECTION_S", None):
            t = self._lancer(resultat, verifier)
            time.sleep(0.3)
            self.assertTrue(t.is_alive())
            # Pendant l'attente, le verrou de détection est libre.
            self.assertTrue(ppocr._VERROU_DETECTION.acquire(blocking=False))
            ppocr._VERROU_DETECTION.release()
            arret.set()
            t.join(3)
        self.assertFalse(t.is_alive())
        self.assertEqual(resultat, [("erreur", ArretDemande)])
        self.assertFalse(ppocr._VERROU_DETECTION.locked())

    def test_delai_depasse_la_page_echoue_proprement(self):
        resultat: list = []
        with mock.patch.object(memoire, "disponible", return_value=0), \
             mock.patch.object(memoire, "_PAS_S", 0.02), \
             mock.patch.object(ppocr, "ATTENTE_DETECTION_S", 0.2):
            t = self._lancer(resultat)
            t.join(3)
        self.assertFalse(t.is_alive())
        self.assertEqual(resultat, [("erreur", LectureEchouee)])
        self.assertFalse(ppocr._VERROU_DETECTION.locked())

    def test_la_memoire_revenue_la_detection_passe_et_rend_le_verrou(self):
        libre = [0]
        resultat: list = []
        with mock.patch.object(memoire, "disponible", side_effect=lambda: libre[0]), \
             mock.patch.object(memoire, "_PAS_S", 0.02), \
             mock.patch.object(ppocr, "ATTENTE_DETECTION_S", None):
            t = self._lancer(resultat)
            time.sleep(0.2)
            self.assertTrue(t.is_alive())
            libre[0] = 10 * memoire.MO
            t.join(3)
        self.assertEqual(resultat, [("tuile", 2)])
        self.assertFalse(ppocr._VERROU_DETECTION.locked())


# ── (i) file LibreOffice sans thread (`tour_async`) ──────────────────────────
class FileLibreOfficeAsync(unittest.TestCase):
    def test_l_urgente_passe_avant_celles_a_l_avance(self):
        file = FileConversions(20)
        ordre: list[str] = []

        async def conv(nom, a_l_avance, tenue=None):
            async with file.tour_async(a_l_avance=a_l_avance):
                ordre.append(nom)
                if tenue is not None:
                    await tenue.wait()

        async def scenario():
            tenue = asyncio.Event()
            taches = [asyncio.create_task(conv("en_cours", True, tenue))]
            while ordre != ["en_cours"]:
                await asyncio.sleep(0.01)
            for nom in ("a1", "a2", "a3"):
                taches.append(asyncio.create_task(conv(nom, True)))
            await asyncio.sleep(0.1)
            taches.append(asyncio.create_task(conv("urgente", False)))
            await asyncio.sleep(0.1)
            tenue.set()
            await asyncio.gather(*taches)

        asyncio.run(scenario())
        self.assertEqual(ordre, ["en_cours", "urgente", "a1", "a2", "a3"])

    def test_file_pleine_l_avance_est_refusee(self):
        file = FileConversions(1)

        async def scenario():
            tenue = asyncio.Event()

            async def occupe():
                async with file.tour_async():
                    await tenue.wait()

            async def en_file():
                async with file.tour_async(a_l_avance=True):
                    pass

            t1 = asyncio.create_task(occupe())
            await asyncio.sleep(0.1)
            t2 = asyncio.create_task(en_file())     # prend l'unique place de file
            await asyncio.sleep(0.1)
            with self.assertRaises(ConversionAbandonnee):
                async with file.tour_async(a_l_avance=True):
                    self.fail("ne devait pas démarrer")
            tenue.set()
            await asyncio.gather(t1, t2)

        asyncio.run(scenario())

    def test_l_annulation_libere_la_file(self):
        file = FileConversions(20)

        async def scenario():
            tenue = asyncio.Event()

            async def occupe():
                async with file.tour_async():
                    await tenue.wait()

            async def attend():
                async with file.tour_async(a_l_avance=True):
                    pass

            t1 = asyncio.create_task(occupe())
            await asyncio.sleep(0.1)
            t2 = asyncio.create_task(attend())
            await asyncio.sleep(0.1)
            self.assertEqual(file.en_attente, 1)
            t2.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t2
            self.assertEqual(file.en_attente, 0)
            tenue.set()
            await t1
            # Le tour est rendu : une nouvelle conversion démarre aussitôt.
            async with file.tour_async():
                pass

        asyncio.run(scenario())
        self.assertEqual(file._en_cours, 0)


# ── (j) fil d'exécution saturé par des préparations : l'urgente passe d'abord ─
class ApercuUrgentSurFilSature(unittest.TestCase):
    def test_apercu_urgent_avant_les_preparations(self):
        rep = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rep, True)
        chemin = os.path.join(rep, "a.docx")
        with open(chemin, "wb") as f:
            f.write(b"x")
        file = FileConversions(500)
        ordre: list[str] = []
        libere = threading.Event()

        def fausse_conversion(donnees, ext, **k):
            ordre.append("prep")
            libere.wait(10)
            return b"%PDF"

        async def scenario():
            n = 40                               # plus que les fils du pool par défaut
            preps = [asyncio.create_task(office.preparer_apercu_async(chemin, "docx"))
                     for _ in range(n)]
            while len(ordre) < 1:
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.2)             # les 39 autres attendent, sans fil

            async def urgente():
                async with office.tour_conversion(b"y", "docx", use_cache=False):
                    ordre.append("urgente")

            tache = asyncio.create_task(urgente())
            await asyncio.sleep(0.2)
            libere.set()
            await asyncio.wait_for(tache, 10)
            self.assertEqual(ordre[:2], ["prep", "urgente"])
            await asyncio.gather(*preps)

        with mock.patch.object(office, "file_conversions", file), \
             mock.patch.object(office, "convert_to_pdf_bytes", fausse_conversion):
            asyncio.run(scenario())
        self.assertEqual(ordre.count("prep"), 40)


# ── (k) un rendu de fond ne prend pas la priorité urgente ────────────────────
class RenduDeFondSansPriorite(unittest.TestCase):
    def test_le_rendu_de_fond_demande_la_priorite_a_l_avance(self):
        rep = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rep, True)
        orig = os.path.join(rep, "o.docx")
        trad = os.path.join(rep, "t.json")
        for c in (orig, trad):
            with open(c, "wb") as f:
                f.write(b"x")
        appels: list[dict] = []

        def conv(data, ext, **k):
            appels.append(k)
            return b"%PDF-1.4"

        with mock.patch.object(docs, "render_translation_bytes", lambda *a, **k: b"docx"), \
             mock.patch.object(docs, "convert_to_pdf_bytes", conv):
            render_cache.ensure_background_build(orig, trad, "docx", "fr")
            self.assertTrue(_attendre(lambda: appels))
            self.assertTrue(_attendre(lambda: not render_cache._building))
        self.assertEqual(appels[0].get("priorite"), FileConversions.A_L_AVANCE)


# ── (l) compartiment : la place attend la marge mémoire ──────────────────────
class PlaceAttendLaMarge(unittest.TestCase):
    def test_la_deuxieme_place_attend_la_marge(self):
        comp = memoire.Compartiment("t", 2, 100)
        libre = [0]
        etat: list[str] = []
        with mock.patch.object(memoire, "disponible", side_effect=lambda: libre[0]), \
             mock.patch.object(memoire, "_PAS_S", 0.02):
            with comp.place():                      # seule en cours : part sans attendre
                def second():
                    with comp.place():
                        etat.append("parti")
                t = threading.Thread(target=second)
                t.start()
                time.sleep(0.3)
                self.assertEqual(etat, [], "parti sans marge mémoire")
                libre[0] = 1000 * memoire.MO
                t.join(3)
        self.assertEqual(etat, ["parti"])
        self.assertEqual(comp.occupees, 0)

    def test_place_async_attend_aussi_et_se_libere_si_annulee(self):
        comp = memoire.Compartiment("t", 2, 100)

        async def scenario():
            with mock.patch.object(memoire, "disponible", return_value=0), \
                 mock.patch.object(memoire, "_PAS_S", 0.02):
                async with comp.place_async():
                    async def second():
                        async with comp.place_async():
                            self.fail("parti sans marge mémoire")
                    t = asyncio.create_task(second())
                    await asyncio.sleep(0.3)
                    self.assertFalse(t.done())
                    t.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await t
                    self.assertEqual(comp.occupees, 1)   # sa place est rendue

        asyncio.run(scenario())
        self.assertEqual(comp.occupees, 0)


# ── (m) rendus de fond en attente : bornés, le plus ancien est écarté ────────
class AttenteDeFondBornee(unittest.TestCase):
    def test_le_plus_ancien_est_ecarte(self):
        comp = memoire.Compartiment("t", 1, 10, fond_attente_max=2)
        comp.prendre()                              # place tenue
        resultat: dict[str, str] = {}

        def fond(nom):
            try:
                with comp.place(fond=True):
                    resultat[nom] = "fait"
            except memoire.PlaceEcartee:
                resultat[nom] = "ecarte"

        threads = []
        for nom in ("f1", "f2", "f3"):
            t = threading.Thread(target=fond, args=(nom,))
            t.start()
            threads.append(t)
            time.sleep(0.05)
        self.assertTrue(_attendre(lambda: resultat.get("f1") == "ecarte"))
        self.assertEqual(comp.en_attente, 2)
        comp._rendre_place()
        for t in threads:
            t.join(5)
        self.assertEqual(resultat, {"f1": "ecarte", "f2": "fait", "f3": "fait"})
        self.assertEqual(comp.occupees, 0)


if __name__ == "__main__":
    unittest.main()
