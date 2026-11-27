"""Tenue en charge, lot 1 (docs/etude-tenue-en-charge.md).

  (a) le flux SSE ne bloque pas la boucle asyncio ;
  (b) `refus_admission` : None sous les plafonds, délai borné au-delà, None si
      les plafonds sont désactivés ;
  (c) la route refuse en 503 + Retry-After sans rien débiter (sauf admin) ;
  (d) la file ne retient plus d'octets de fichier ; la relecture au démarrage
      rend l'original, et un original illisible ferme le job en erreur ;
  (e) `/health` n'est plus limité en débit ;
  (f) l'envoi est écrit en flux sur le disque, identique au fichier envoyé,
      et ne laisse rien derrière lui s'il est refusé.

Exécution :  cd backend && venv/Scripts/python.exe -m pytest tests/test_tenue_en_charge.py -q
Ne touche pas à la base : les sessions et les comptes sont simulés.
"""
from __future__ import annotations

import asyncio
import os
import queue
import shutil
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import racine  # noqa: F401  -- met backend/ sur le chemin

from fastapi import HTTPException, Response            # noqa: E402
from fastapi.testclient import TestClient              # noqa: E402

from app import rate_limit                             # noqa: E402
from app import create_app                             # noqa: E402
from app.api import translate as tr                    # noqa: E402
from app.core.security import create_access_token, require_auth  # noqa: E402
from app.services import depots                        # noqa: E402
from app.services import scheduler as sched_mod        # noqa: E402
from app.services.jobs import jobs                     # noqa: E402

# Clé d'API fixe, posée dans `app.rate_limit` : le test ne dépend pas du `.env`
# de la machine (absent d'un clone neuf).
CLE_TEST = "cle-test"
CLE = {"X-API-Key": CLE_TEST}


class _CleApi(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(rate_limit, "FRONTEND_API_KEY", CLE_TEST)
        p.start()
        self.addCleanup(p.stop)


def _attendre(cond, delai=5.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.02)
    return False


# ── (a) flux SSE non bloquant ────────────────────────────────────────────────
class FluxSseNonBloquant(unittest.TestCase):
    def test_la_boucle_reste_reactive_pendant_l_attente(self):
        job_id = jobs.create()
        jobs.set(job_id, user_id="42", state="running")
        jeton = create_access_token("42", "sse@example.com")

        async def scenario():
            reponse = await tr.translation_events(job_id, token=jeton)
            flux = reponse.body_iterator
            ecarts: list[float] = []
            fini = asyncio.Event()

            async def pouls():
                # Si le flux bloquait la boucle, ce battement serait en retard.
                dernier = time.monotonic()
                while not fini.is_set():
                    await asyncio.sleep(0.01)
                    now = time.monotonic()
                    ecarts.append(now - dernier - 0.01)
                    dernier = now

            async def lecteur():
                recu = []
                async for morceau in flux:
                    recu.append(morceau)
                return recu

            tache_pouls = asyncio.create_task(pouls())
            tache_flux = asyncio.create_task(lecteur())
            await asyncio.sleep(1.0)              # file vide, job en cours
            jobs.get(job_id)["q"].put({"type": "progress", "pct": 50})
            jobs.get(job_id)["q"].put({"type": "done", "filename": "x.pdf"})
            recu = await asyncio.wait_for(tache_flux, 3)
            fini.set()
            await tache_pouls
            return ecarts, recu

        try:
            ecarts, recu = asyncio.run(scenario())
        finally:
            jobs.forget(job_id)
        self.assertGreater(len(ecarts), 20)
        self.assertLess(max(ecarts), 0.05, f"boucle bloquée {max(ecarts):.3f} s")
        texte = "".join(recu)
        self.assertIn('"progress"', texte)
        self.assertIn('"done"', texte)


# ── (b) admission bornée ─────────────────────────────────────────────────────
class _FileFactice:
    """Même forme que `TranslationScheduler` pour ce que lit `refus_admission`."""

    def __init__(self):
        self._pq: queue.PriorityQueue = queue.PriorityQueue()
        self._running = 0
        self._workers = 1
        self._seq = 0

    def mettre(self, job_id):
        self._seq += 1
        self._pq.put((0, self._seq, job_id, lambda: None, ()))


class RefusAdmission(unittest.TestCase):
    def setUp(self):
        self.file = _FileFactice()
        self.ids: list[str] = []
        p = mock.patch.object(sched_mod, "_files", [self.file])
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        for j in self.ids:
            jobs.forget(j)

    def _attendre_job(self, user_id, demarre=False):
        job_id = jobs.create()
        jobs.set(job_id, user_id=user_id, demarre=demarre)
        self.ids.append(job_id)
        self.file.mettre(job_id)

    def _limites(self, total, par_compte):
        for nom, val in (("FILE_ATTENTE_MAX", total),
                         ("FILE_ATTENTE_MAX_PAR_COMPTE", par_compte)):
            p = mock.patch.object(sched_mod, nom, val)
            p.start()
            self.addCleanup(p.stop)

    def test_sous_les_plafonds_rien_n_est_refuse(self):
        self._limites(20, 3)
        for _ in range(2):
            self._attendre_job(1)
        self.assertIsNone(sched_mod.refus_admission(1))

    def test_plafond_par_compte(self):
        self._limites(20, 3)
        for _ in range(3):
            self._attendre_job(1)
        delai = sched_mod.refus_admission(1)
        self.assertIsInstance(delai, int)
        self.assertTrue(30 <= delai <= 600, delai)
        self.assertIsNone(sched_mod.refus_admission(2))     # un autre compte passe

    def test_plafond_total(self):
        self._limites(4, 3)
        for uid in (1, 2, 3, 4):
            self._attendre_job(uid)
        delai = sched_mod.refus_admission(9)
        self.assertTrue(30 <= delai <= 600, delai)

    def test_les_travaux_demarres_ne_comptent_pas(self):
        self._limites(2, 2)
        for _ in range(3):
            self._attendre_job(1, demarre=True)
        self.assertIsNone(sched_mod.refus_admission(1))

    def test_plafonds_a_none_aucune_limite(self):
        self._limites(None, None)
        for _ in range(50):
            self._attendre_job(1)
        self.assertIsNone(sched_mod.refus_admission(1))


# ── (c) route : 503 avant toute lecture et tout débit ────────────────────────
class RouteSaturee(_CleApi):
    def _appel(self, user, db):
        return tr.translate_endpoint(
            request=racine.requete_test(), response=Response(), file=None,
            upload_id="", target_lang="en", format_options="{}", quality="fast",
            precise="", pages="", debug="", x_api_key=CLE_TEST,
            current_user=user, db=db)

    def test_503_retry_after_sans_debit(self):
        user = SimpleNamespace(id=5, plan="free", email="x@example.com")
        db = mock.MagicMock()
        with mock.patch.object(tr, "refus_admission", return_value=90), \
             mock.patch.object(tr, "_fichier_recu",
                               side_effect=AssertionError("fichier lu")) as lu:
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(self._appel(user, db))
        self.assertEqual(cm.exception.status_code, 503)
        self.assertEqual(cm.exception.detail, "service_sature")
        self.assertEqual(cm.exception.headers["Retry-After"], "90")
        lu.assert_not_called()
        self.assertEqual(db.method_calls, [])           # ni Document ni débit

    def test_l_admin_n_est_jamais_refuse(self):
        class Atteint(Exception):
            pass
        user = SimpleNamespace(id=1, plan="admin", email="a@example.com")
        with mock.patch.object(tr, "refus_admission", return_value=90) as ref, \
             mock.patch.object(tr, "_fichier_recu", side_effect=Atteint):
            with self.assertRaises(Atteint):
                asyncio.run(self._appel(user, mock.MagicMock()))
        ref.assert_not_called()


# ── (d) la file ne retient plus d'octets ─────────────────────────────────────
class OriginalRelu(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="orig-")
        self.addCleanup(shutil.rmtree, self.dossier, True)

    def test_la_cible_enveloppee_relit_l_original(self):
        chemin = os.path.join(self.dossier, "o.pdf")
        contenu = os.urandom(200_000)
        with open(chemin, "wb") as f:
            f.write(contenu)
        arg = tr.OriginalSurDisque(chemin)
        # Rien de volumineux dans ce que la file garde.
        for a in ("job", arg, chemin):
            self.assertFalse(isinstance(a, (bytes, bytearray)) and len(a) > 1024)
        recu = {}

        def cible(job_id, octets, *reste):
            recu["octets"] = octets
            recu["reste"] = reste

        tr._relire_original(cible)("job", arg, "suite", 3)
        self.assertEqual(recu["octets"], contenu)
        self.assertEqual(recu["reste"], ("suite", 3))

    def test_original_illisible_ferme_le_job_en_erreur(self):
        job_id = jobs.create()
        jobs.set(job_id, user_id="1")
        appele = []
        file = sched_mod.TranslationScheduler(1)
        try:
            with mock.patch("app.services.solde_ia.verifier_depuis_un_thread"), \
                 mock.patch.object(jobs, "sync_status") as sync:
                file.submit(job_id, 1,
                            tr._relire_original(lambda *a: appele.append(a)),
                            (job_id, tr.OriginalSurDisque(
                                os.path.join(self.dossier, "absent.pdf"))))
                self.assertTrue(_attendre(
                    lambda: (jobs.get(job_id) or {}).get("state") == "error"))
                # Même chemin que l'échec d'un runner : `jobs.error` puis le
                # report en base, qui rembourse les pages du Document.
                sync.assert_any_call(job_id, "error")
            self.assertEqual(appele, [])                 # le runner n'a pas tourné
        finally:
            sched_mod._files.remove(file)
            jobs.forget(job_id)


# ── (e) /health sans limite de débit ─────────────────────────────────────────
class SanteSansLimite(unittest.TestCase):
    def test_quinze_appels_repondent_200(self):
        client = TestClient(create_app())
        for i in range(15):
            r = client.get("/health")
            self.assertEqual(r.status_code, 200, (i, r.text))


# ── (f) envoi écrit en flux ──────────────────────────────────────────────────
class EnvoiEnFlux(_CleApi):
    def setUp(self):
        super().setUp()
        self.dossier = tempfile.mkdtemp(prefix="depots-")
        self.addCleanup(shutil.rmtree, self.dossier, True)
        app = create_app()
        app.dependency_overrides[require_auth] = lambda: SimpleNamespace(id=101)
        self.client = TestClient(app)
        p = mock.patch.object(depots, "DOSSIER", self.dossier)
        p.start()
        self.addCleanup(p.stop)
        # L'espace libre de la machine ne doit pas décider du résultat.
        p = mock.patch("app.services.stockage.disque_insuffisant", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_le_depot_est_identique_au_fichier_envoye(self):
        contenu = b"%PDF-1.4 " + os.urandom(3 * 1024 * 1024 + 123)
        r = self.client.post("/api/upload?nom=gros.pdf", content=contenu,
                             headers={**CLE, "Content-Type": "application/octet-stream"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(set(r.json()), {"upload_id", "taille"})
        self.assertEqual(r.json()["taille"], len(contenu))
        upload_id = r.json()["upload_id"]
        with open(os.path.join(self.dossier, upload_id, "fichier"), "rb") as f:
            self.assertEqual(f.read(), contenu)
        self.assertEqual(os.listdir(self.dossier), [upload_id])
        self.assertEqual(depots.lire(upload_id, 101), ("gros.pdf", contenu))

    def test_trop_gros_sans_annonce_ne_laisse_rien(self):
        def morceaux():
            for _ in range(3):
                yield b"%PDF" + os.urandom(1024 * 1024)

        with mock.patch.object(tr, "MAX_FILE_SIZE", 2 * 1024 * 1024):
            r = self.client.post("/api/upload?nom=gros.pdf", content=morceaux(),
                                 headers={**CLE, "Content-Type": "application/octet-stream"})
        self.assertEqual(r.status_code, 413, r.text)
        self.assertEqual(os.listdir(self.dossier), [])

    def test_fichier_vide_ne_laisse_rien(self):
        r = self.client.post("/api/upload?nom=vide.pdf", content=b"", headers=CLE)
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(os.listdir(self.dossier), [])

    def test_la_purge_garde_les_envois_en_cours_et_efface_les_restes(self):
        recent = os.path.join(self.dossier, depots.PREFIXE_RECU + "a")
        vieux = os.path.join(self.dossier, depots.PREFIXE_RECU + "b")
        for p in (recent, vieux):
            with open(p, "wb") as f:
                f.write(b"x")
        ancien = time.time() - depots.RECU_CONSERVATION_S - 60
        os.utime(vieux, (ancien, ancien))
        depots.purger()
        self.assertTrue(os.path.exists(recent))
        self.assertFalse(os.path.exists(vieux))


if __name__ == "__main__":
    unittest.main()
