"""Le mode précis (modèle de raisonnement) est réservé aux admins côté serveur.

L'interface ne propose `precise=1` qu'aux admins ; cette suite vérifie que le
serveur ne s'y fie pas : tout autre compte retombe sur le mode rapide.
"""
import unittest
from types import SimpleNamespace

import racine  # noqa: F401
from app.api.translate import qualite_autorisee


def compte(plan):
    return SimpleNamespace(plan=plan)


class ModePrecis(unittest.TestCase):
    def test_admin_obtient_le_mode_precis(self):
        self.assertEqual(qualite_autorisee("fast", "1", compte("admin")), "precise")
        self.assertEqual(qualite_autorisee("precise", "", compte("admin")), "precise")

    def test_autres_comptes_retombent_sur_rapide(self):
        for plan in ("free", "starter", "pro", "business"):
            self.assertEqual(qualite_autorisee("fast", "1", compte(plan)), "fast", plan)
            self.assertEqual(qualite_autorisee("precise", "", compte(plan)), "fast", plan)

    def test_valeur_inconnue_donne_rapide(self):
        self.assertEqual(qualite_autorisee("ultra", "", compte("admin")), "fast")
        self.assertEqual(qualite_autorisee("fast", "", compte("admin")), "fast")


if __name__ == "__main__":
    unittest.main()
