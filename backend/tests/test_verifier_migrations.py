"""Garde-fou des migrations : deux fins de suite ou base inconnue sont signalées."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from alembic.script import ScriptDirectory  # noqa: E402

import verifier_migrations as vm  # noqa: E402


def _migration(dossier: str, revision: str, parente: str | None) -> None:
    with open(os.path.join(dossier, "versions", f"{revision}.py"), "w", encoding="utf-8") as f:
        f.write(f"revision = {revision!r}\ndown_revision = {parente!r}\n"
                "branch_labels = None\ndepends_on = None\n"
                "def upgrade(): pass\ndef downgrade(): pass\n")


def _suite(dossier: str) -> ScriptDirectory:
    return ScriptDirectory(dossier, version_locations=[os.path.join(dossier, "versions")])


def _sortie(code: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], code, out, err)


class SuiteTests(unittest.TestCase):
    def test_le_depot_a_une_seule_fin(self):
        self.assertEqual(vm.verifier_suite(), [])

    def test_une_suite_lineaire_passe(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "versions"))
            _migration(d, "a", None)
            _migration(d, "b", "a")
            with mock.patch.object(vm, "_scripts", return_value=_suite(d)):
                self.assertEqual(vm.verifier_suite(), [])

    def test_deux_fins_sont_signalees_avec_leurs_noms(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "versions"))
            _migration(d, "a", None)
            _migration(d, "b", "a")
            _migration(d, "c", "a")
            with mock.patch.object(vm, "_scripts", return_value=_suite(d)):
                problemes = vm.verifier_suite()
        self.assertIn("b, c", problemes[0])
        self.assertIn("down_revision", problemes[1])


class BaseTests(unittest.TestCase):
    def test_migration_inconnue_expliquee_et_aucune_mise_a_jour(self):
        err = "Can't locate revision identified by '0018_document_reglages'\n"
        with mock.patch.object(vm, "_alembic", return_value=_sortie(1, err=err)) as alembic:
            problemes = vm.verifier_base()
        self.assertIn("0018_document_reglages", problemes[0])
        self.assertEqual(alembic.call_count, 1)

    def test_base_connue_mise_a_jour(self):
        with mock.patch.object(vm, "_alembic", return_value=_sortie()) as alembic:
            self.assertEqual(vm.verifier_base(), [])
        self.assertEqual(alembic.call_args_list[-1].args, ("upgrade", "head"))

    def test_base_injoignable(self):
        with mock.patch.object(vm, "_alembic", return_value=_sortie(1, err="connexion refusee\n")):
            self.assertIn("injoignable", vm.verifier_base()[0])


if __name__ == "__main__":
    unittest.main()
