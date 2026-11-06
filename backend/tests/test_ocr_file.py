"""Guichet de l'OCR : une lecture à la fois, priorité, anti-famine, délai, arrêt."""
import threading
import time
import unittest

import racine  # noqa: F401
from app.services.ocr_file import Guichet, OCROccupe, definir_priorite, priorite_du_fil


class Arret(Exception):
    pass


def attendre(condition, delai=5.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.005)
    return False


class TestGuichet(unittest.TestCase):
    def _files(self, g, tickets, pause_entre=0.0):
        """Le fil principal tient le tour ; lance `tickets` [(nom, priorité)]
        dans cet ordre, libère, et rend l'ordre de passage."""
        ordre, garde = [], threading.Lock()

        def passer(nom, prio):
            with g.tour(priorite=prio):
                with garde:
                    ordre.append(nom)

        g.acquerir(priorite=0)
        fils = []
        for i, (nom, prio) in enumerate(tickets):
            fil = threading.Thread(target=passer, args=(nom, prio))
            fil.start()
            fils.append(fil)
            self.assertTrue(attendre(lambda n=i + 1: g.en_attente() == n))
            if pause_entre:
                time.sleep(pause_entre)
        g.liberer()
        for fil in fils:
            fil.join(5)
            self.assertFalse(fil.is_alive())
        return ordre

    def test_jamais_deux_lectures_simultanees(self):
        g = Guichet(anti_famine_s=60)
        en_cours, maximum, garde = [0], [0], threading.Lock()

        def lecture():
            with g.tour(priorite=0):
                with garde:
                    en_cours[0] += 1
                    maximum[0] = max(maximum[0], en_cours[0])
                time.sleep(0.01)
                with garde:
                    en_cours[0] -= 1

        fils = [threading.Thread(target=lecture) for _ in range(12)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(10)
        self.assertEqual(maximum[0], 1)
        self.assertFalse(g.occupe())
        self.assertEqual(g.en_attente(), 0)

    def test_le_plus_prioritaire_passe_d_abord(self):
        g = Guichet(anti_famine_s=60)
        ordre = self._files(g, [("gratuit", 0), ("pro", 3), ("standard", 1)])
        self.assertEqual(ordre, ["pro", "standard", "gratuit"])

    def test_meme_priorite_ordre_d_arrivee(self):
        g = Guichet(anti_famine_s=60)
        ordre = self._files(g, [("a", 2), ("b", 2), ("c", 2)])
        self.assertEqual(ordre, ["a", "b", "c"])

    def test_anti_famine_le_moins_prioritaire_finit_par_passer(self):
        g = Guichet(anti_famine_s=0.2)
        ordre = self._files(g, [("gratuit", 0), ("pro", 3)], pause_entre=0.15)
        # À la libération, « gratuit » attend depuis plus de 0,2 s : il passe
        # devant, même si « pro » attend aussi.
        self.assertEqual(ordre[0], "gratuit")

    def test_anti_famine_sert_le_plus_ancien_des_affames(self):
        g = Guichet(anti_famine_s=0.1)
        ordre = self._files(g, [("ancien", 0), ("moins_ancien", 0), ("pro", 3)],
                            pause_entre=0.15)
        self.assertEqual(ordre[0], "ancien")

    def test_delai_depasse_ticket_retire(self):
        g = Guichet(anti_famine_s=60)
        g.acquerir(priorite=0)
        erreurs = []

        def essayer():
            try:
                g.acquerir(priorite=5, delai=0.05)
            except OCROccupe as e:
                erreurs.append(e)

        fil = threading.Thread(target=essayer)
        fil.start()
        fil.join(5)
        self.assertEqual(len(erreurs), 1)
        self.assertEqual(g.en_attente(), 0)
        g.liberer()
        # Le ticket abandonné ne bloque pas le suivant.
        with g.tour(priorite=0, delai=1):
            self.assertTrue(g.occupe())

    def test_arret_pendant_l_attente_ticket_retire(self):
        g = Guichet(anti_famine_s=60)
        g.acquerir(priorite=0)
        demande = threading.Event()
        leve = []

        def arret():
            if demande.is_set():
                raise Arret()

        def attendre_son_tour():
            try:
                g.acquerir(priorite=9, arret=arret)
            except Arret:
                leve.append(True)

        fil = threading.Thread(target=attendre_son_tour)
        fil.start()
        self.assertTrue(attendre(lambda: g.en_attente() == 1))
        demande.set()
        fil.join(5)
        self.assertEqual(leve, [True])
        self.assertEqual(g.en_attente(), 0)
        g.liberer()
        with g.tour(priorite=0, delai=1):
            pass

    def test_exception_pendant_la_lecture_libere_le_tour(self):
        g = Guichet(anti_famine_s=60)
        with self.assertRaises(ValueError):
            with g.tour(priorite=0):
                raise ValueError()
        self.assertFalse(g.occupe())
        with g.tour(priorite=0, delai=1):
            pass

    def test_non_reentrant(self):
        g = Guichet(anti_famine_s=60)
        with g.tour(priorite=0):
            with self.assertRaises(RuntimeError):
                g.acquerir(priorite=0)
        self.assertFalse(g.occupe())

    def test_priorite_du_fil(self):
        resultat = []

        def fil():
            resultat.append(priorite_du_fil())
            definir_priorite(4)
            resultat.append(priorite_du_fil())

        t = threading.Thread(target=fil)
        t.start()
        t.join()
        self.assertEqual(resultat, [0, 4])
        self.assertEqual(priorite_du_fil(), 0)


if __name__ == "__main__":
    unittest.main()
