"""Purge à 30 jours des traductions en aperçu sans aucune page payée, avec un
rappel par e-mail 5 jours avant (docs/etude-traduction-libre.md, étape 5.5)."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import AsyncMock, patch

import racine  # noqa: F401
import test_beta_program as fixtures

from app.core import email as courriel
from app.models import Document, User
from app.services import purge_libres

NOW = datetime(2026, 12, 1, 3, 0, tzinfo=timezone.utc)


class PurgeLibresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fx = fixtures.BetaTests()
        await self.fx.asyncSetUp()
        self.user = self.fx.other

    async def asyncTearDown(self):
        await self.fx.asyncTearDown()

    async def doc(self, *, jours, paid=False, libres=3, rappel=None, **champs):
        reglages = {"rappel_purge": (NOW - timedelta(days=rappel)).isoformat()} if rappel is not None else {}
        async with self.fx.sessions() as db:
            d = Document(user_id=self.user.id, original_name=f"doc-{jours}-{paid}-{libres}.pdf",
                         source_lang="fr", target_lang="en", original_path="hors-magasin.pdf",
                         size_bytes=10, storage_charged=champs.pop("storage_charged", 0),
                         status=champs.pop("status", "completed"), paid=paid, pages_libres=libres,
                         page_count=3, reglages=json.dumps(reglages),
                         created_at=NOW - timedelta(days=jours), **champs)
            db.add(d)
            await db.commit()
            return d.id

    async def run_purge(self, envoi=None):
        envoi = envoi or AsyncMock()
        with patch.object(courriel, "send_rappel_libres_email", envoi):
            async with self.fx.sessions() as db:
                bilan = await purge_libres.rappeler_et_purger(db, now=NOW)
        return bilan, envoi

    async def get(self, doc_id):
        async with self.fx.sessions() as db:
            return await db.get(Document, doc_id)

    async def test_one_reminder_per_account_lists_its_documents_once(self):
        a = await self.doc(jours=26)
        b = await self.doc(jours=25)
        recent = await self.doc(jours=10)
        bilan, envoi = await self.run_purge()
        self.assertEqual(bilan, {"rappels": 1, "supprimes": 0})
        destinataire, langue, liste = envoi.await_args.args
        self.assertEqual(destinataire, self.user.email)
        self.assertEqual(len(liste), 2)
        # Créé il y a 25 jours : supprimé dans 5 jours, à la date annoncée.
        self.assertIn(((NOW + timedelta(days=5)).date().isoformat()), [d for _, d in liste])
        for i in (a, b):
            self.assertIn("rappel_purge", json.loads((await self.get(i)).reglages))
        self.assertNotIn("rappel_purge", json.loads((await self.get(recent)).reglages))
        bilan, envoi = await self.run_purge()
        self.assertEqual(bilan, {"rappels": 0, "supprimes": 0})
        envoi.assert_not_awaited()

    async def test_document_is_deleted_five_days_after_the_reminder(self):
        async with self.fx.sessions() as db:
            user = await db.get(User, self.user.id)
            user.storage_used = 100
            await db.commit()
        echu = await self.doc(jours=31, rappel=5, storage_charged=40)
        trop_tot = await self.doc(jours=31, rappel=2)
        bilan, envoi = await self.run_purge()
        self.assertEqual(bilan, {"rappels": 0, "supprimes": 1})
        self.assertIsNone(await self.get(echu))
        self.assertIsNotNone(await self.get(trop_tot))
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).storage_used, 60)

    async def test_late_reminder_postpones_the_deletion(self):
        # Rappel jamais parti (serveur arrêté) : on prévient d'abord, avec 5 jours de délai.
        vieux = await self.doc(jours=40)
        bilan, envoi = await self.run_purge()
        self.assertEqual(bilan, {"rappels": 1, "supprimes": 0})
        self.assertEqual(envoi.await_args.args[2][0][1], (NOW + timedelta(days=5)).date().isoformat())
        self.assertIsNotNone(await self.get(vieux))

    async def test_paid_pages_protect_the_document(self):
        partiel = await self.doc(jours=60, paid=True, libres=2, rappel=30)
        debloque = await self.doc(jours=60, paid=True, libres=0, rappel=30)
        copie = await self.doc(jours=60, rappel=30, copie_de="abc")
        en_cours = await self.doc(jours=60, rappel=30, status="translating")
        bilan, envoi = await self.run_purge()
        self.assertEqual(bilan, {"rappels": 0, "supprimes": 0})
        envoi.assert_not_awaited()
        for i in (partiel, debloque, copie, en_cours):
            self.assertIsNotNone(await self.get(i))

    async def test_failed_reminder_is_retried_and_blocks_the_deletion(self):
        d = await self.doc(jours=31)
        refus = AsyncMock(side_effect=courriel.EmailIndisponible("refus"))
        bilan, _ = await self.run_purge(refus)
        self.assertEqual(bilan, {"rappels": 0, "supprimes": 0})
        self.assertNotIn("rappel_purge", json.loads((await self.get(d)).reglages))
        bilan, envoi = await self.run_purge()
        self.assertEqual(bilan["rappels"], 1)

    def test_reminder_email_escapes_names_in_both_languages(self):
        for langue, mot in (("fr", "Supprimé le"), ("en", "Deleted on")):
            msg = courriel._message_rappel_libres(
                "a@example.com", langue, [("<b>rapport</b>.pdf", "2026-12-06")])
            html = msg.get_payload()[0].get_payload()[1].get_payload(decode=True).decode()
            texte = msg.get_payload()[0].get_payload()[0].get_payload(decode=True).decode()
            self.assertIn(mot, html)
            self.assertIn("&lt;b&gt;rapport&lt;/b&gt;.pdf", html)
            self.assertNotIn("<b>rapport", html)
            self.assertIn("<b>rapport</b>.pdf", texte)
            self.assertEqual(msg["Auto-Submitted"], "auto-generated")


if __name__ == "__main__":
    unittest.main()
