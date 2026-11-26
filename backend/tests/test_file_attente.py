"""File d'attente affichée : position juste, durée estimée, mise à jour.

Cas de l'étude (docs/etude-file-attente.md) : une seule place mémoire, trois
travaux lancés presque ensemble sur deux files.
"""
import os
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import memoire  # noqa: E402
from app.services import scheduler as sched_mod  # noqa: E402


def _attendre(cond, delai=5.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.02)
    return False


class BudgetOrdreArrivee(unittest.TestCase):
    def test_places_donnees_dans_l_ordre_d_arrivee(self):
        b = memoire.Budget(1)
        self.assertFalse(b.prendre("A"))          # place libre : pas d'attente
        servis = []

        def attendre(cle):
            self.assertTrue(b.prendre(cle))
            servis.append(cle)

        fils = []
        for cle in ("B", "C", "D"):
            t = threading.Thread(target=attendre, args=(cle,), daemon=True)
            t.start()
            fils.append(t)
            _attendre(lambda c=cle: c in b.attente)
        self.assertEqual(b.attente, ["B", "C", "D"])
        for attendu in ("B", "C", "D"):
            b.rendre()
            self.assertTrue(_attendre(lambda a=attendu: a in servis))
            self.assertEqual(servis[-1], attendu)
        b.rendre()
        self.assertEqual((b.occupees, b.attente), (0, []))

    def test_sans_plafond_jamais_d_attente(self):
        b = memoire.Budget(None)
        self.assertFalse(any(b.prendre(str(i)) for i in range(5)))


class Estimation(unittest.TestCase):
    def test_mediane_et_surestimation(self):
        with mock.patch.object(sched_mod, "budget", memoire.Budget(1)), \
                mock.patch.object(sched_mod, "_durees", sched_mod.deque(maxlen=10)):
            self.assertEqual(sched_mod.duree_type(), 150)     # défaut
            sched_mod._durees.extend([100, 120, 3000])         # un géant
            self.assertEqual(sched_mod.duree_type(), 120)
            sched_mod.budget.occupees = 1
            self.assertEqual(sched_mod.estimer_attente(0), 120)   # après l'en-cours
            self.assertEqual(sched_mod.estimer_attente(2), 360)


class FileCommune(unittest.TestCase):
    """A démarre ; B attend la place mémoire ; C attend un worker. Avant le
    correctif, B et C voyaient tous deux « démarrage imminent »."""

    def test_position_juste_et_mise_a_jour(self):
        jobs = sched_mod.jobs
        vus: dict[str, list] = {}
        emit_orig = jobs.emit
        verrou = threading.Lock()

        def espion(job_id, event_type, payload):
            with verrou:
                vus.setdefault(job_id, []).append((event_type, dict(payload)))
            return emit_orig(job_id, event_type, payload)

        liberer = {}

        def travail(jid):
            jobs.emit(jid, "page", {})            # premier vrai événement
            liberer[jid].wait(5)

        with mock.patch.object(sched_mod, "budget", memoire.Budget(1)), \
                mock.patch.object(sched_mod, "_durees", sched_mod.deque(maxlen=10)), \
                mock.patch.object(sched_mod, "_dernier_signal", {}), \
                mock.patch.object(sched_mod, "_files", []), \
                mock.patch.object(jobs, "emit", espion):
            trad = sched_mod.TranslationScheduler(workers=2)
            sched_mod.TranslationScheduler(workers=3)          # file des scans
            a, b, c, d = (jobs.create() for _ in range(4))
            for j in (a, b, c, d):
                liberer[j] = threading.Event()
            trad.submit(a, 0, travail, (a,))
            _attendre(lambda: ("page", {}) in vus.get(a, []))
            trad.submit(b, 0, travail, (b,))
            _attendre(lambda: b in sched_mod.budget.attente)
            trad.submit(c, 0, travail, (c,))
            trad.submit(d, 0, travail, (d,))
            time.sleep(0.2)

            def dernier_queued(j):
                q = [p for t, p in vus.get(j, []) if t == "queued"]
                return q[-1] if q else None

            self.assertIsNone(dernier_queued(a), "A ne doit jamais être en file")
            self.assertEqual(dernier_queued(b)["ahead"], 0)
            self.assertEqual(dernier_queued(b)["attente_s"], 150)
            self.assertEqual(dernier_queued(c)["ahead"], 1)
            self.assertEqual(dernier_queued(c)["attente_s"], 300)
            self.assertEqual(dernier_queued(c)["seuil_s"], 15 * 60)

            # D annulé pendant l'attente : il ne compte plus pour personne.
            jobs.demander_arret(d, "cancelled")
            # A finit : chacun avance d'un rang, sans recharger la page.
            liberer[a].set()
            self.assertTrue(_attendre(lambda: ("page", {}) in vus.get(b, [])))
            self.assertTrue(_attendre(lambda: (dernier_queued(c) or {}).get("ahead") == 0))

            for j in (b, c, d):
                liberer[j].set()
            self.assertTrue(_attendre(lambda: ("page", {}) in vus.get(c, [])))
            time.sleep(0.2)
            # Aucun « en file » après le démarrage réel d'un travail.
            for j in (a, b, c):
                types = [t for t, _ in vus.get(j, [])]
                debut = types.index("page")
                self.assertNotIn("queued", types[debut:], f"en file après démarrage : {j}")


if __name__ == "__main__":
    unittest.main()
