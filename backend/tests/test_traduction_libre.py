"""Mode libre : un solde insuffisant n'empêche plus de traduire, en aperçu.

Les pages non couvertes sont des pages libres : traduites, mais ni en clair ni
téléchargeables tant qu'elles ne sont pas payées. Plafond de 20 pages libres par
24 h, par compte et par appareil. Seul le worker est remplacé ; extraction,
admission, persistance et droits de lecture s'exécutent pour de bon.
"""
import asyncio
import os
from datetime import timedelta
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

import racine  # noqa: F401
import test_beta_program as fixtures
from sqlalchemy import select

from app.api.documents import _apercu_filigrane, _may_read_clear, pages_filigranees
from app.models import Document, LibreGrant, UsageRecord, User
from app.services import anti_abus
from app.services.documents import pages_libres_du_document, reglages_de
from app.services.jobs import jobs


class TraductionLibreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Ces cas testent la limite journalière, désactivée en production.
        self._plafond = anti_abus.LIBRE_MAX_PAGES
        anti_abus.LIBRE_MAX_PAGES = 20
        self.fx = fixtures.BetaTests()
        await self.fx.asyncSetUp()
        self.client = self.fx.client
        self.user = self.fx.other
        self.headers = self.fx.headers(self.user)

    async def asyncTearDown(self):
        await self.fx.asyncTearDown()
        anti_abus.LIBRE_MAX_PAGES = self._plafond

    async def upload(self, data=None, headers=None, **options):
        return await self.client.post("/api/translate", headers=headers or self.headers,
            files={"file": ("document.pdf", data if data is not None else fixtures.pdf(),
                            "application/octet-stream")},
            data={"target_lang": "en", "use_beta": "0", **options})

    async def document(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        identifier = jobs.get(response.json()["job_id"])["document_id"]
        async with self.fx.sessions() as db:
            return await db.get(Document, identifier)

    async def records(self, document):
        async with self.fx.sessions() as db:
            return (await db.execute(select(UsageRecord).where(
                UsageRecord.document_id == document.id))).scalars().all()

    async def test_mixed_document_translates_the_whole_selection_but_stays_locked(self):
        response = await self.upload(fixtures.pdf(7))
        document = await self.document(response)
        body = response.json()
        self.assertFalse(body["can_download"])
        self.assertEqual(body["pages_libres"], 2)
        self.assertEqual(document.pages_libres, 2)
        # Les DERNIÈRES pages sont libres : l'aperçu les voile une à une,
        # en direct comme à la réouverture depuis « Mes documents ».
        self.assertEqual(body["pages_libres_numeros"], [6, 7])
        self.assertEqual(body["libre_restant"], 18)
        listed = await self.client.get("/api/documents", headers=self.headers)
        entry = next(d for d in listed.json() if d["id"] == document.id)
        self.assertEqual(entry["pages_libres_numeros"], [6, 7])
        self.assertTrue(document.paid)
        self.assertEqual(document.page_count, 7)
        pages = jobs.get(body["job_id"])["pages"]
        self.assertTrue(pages is None or len(pages) == 7)
        self.assertEqual(sum(row.pages for row in await self.records(document)), 5)
        # Aucun téléchargement tant que les pages libres ne sont pas payées.
        result = Path(self.fx.temp.name) / "libre.pdf"
        result.write_bytes(fixtures.pdf(7))
        jobs.set(body["job_id"], state="done", result_path=str(result), result_filename="libre.pdf")
        download = await self.client.get("/api/translate/result/" + body["job_id"], headers=self.headers)
        self.assertEqual(download.status_code, 402)
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 2)

    async def test_without_daily_cap_every_page_is_translated_in_preview(self):
        anti_abus.LIBRE_MAX_PAGES = None
        async with self.fx.sessions() as db:
            anti_abus.record_libre(db, self.user, None, 40)
            await db.commit()
        response = await self.upload(fixtures.pdf(25))
        body = response.json()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(body["can_download"])
        self.assertNotIn("libre_restant", body)
        self.assertNotIn("plafond", body)
        self.assertEqual(body["pages_libres"], 20)   # 5 pages payées, 20 en aperçu

    async def test_cap_counts_only_free_pages_left_by_the_plan_limit(self):
        # La limite du forfait coupe la sélection à 6 pages : une seule page libre.
        with patch("app.api.translate.cap_pages_for_plan",
                   side_effect=lambda pages, ext, limit: set(range(1, 7))):
            document = await self.document(await self.upload(fixtures.pdf(7)))
        self.assertEqual(document.pages_libres, 1)
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 1)

    async def test_empty_balance_gives_a_fully_free_unpaid_document(self):
        first = await self.upload(fixtures.pdf(5))
        self.assertTrue((await self.document(first)).paid)
        response = await self.upload(fixtures.pdf(3))
        document = await self.document(response)
        self.assertFalse(document.paid)
        self.assertEqual(document.pages_libres, 3)
        self.assertEqual(document.page_count, 3)
        self.assertFalse(response.json()["can_download"])
        self.assertEqual(await self.records(document), [])

    async def test_cap_is_per_account_and_per_device(self):
        self.assertEqual((await self.upload(fixtures.pdf(5))).status_code, 200)   # pages offertes
        full = await self.upload(fixtures.pdf(20))
        self.assertEqual((await self.document(full)).pages_libres, 20)
        over = await self.upload(fixtures.pdf(1))
        self.assertEqual(over.status_code, 402)
        body = over.json()
        self.assertEqual((body["reason"], body["libre_limit"]), ("need_credits", True))
        # Le refus dit la limite, ce qui est déjà pris, et quand l'aperçu revient.
        self.assertEqual((body["libre_used"], body["libre_max"], body["libre_needed"]), (20, 20, 1))
        async with self.fx.sessions() as db:
            accordee = (await db.execute(select(LibreGrant.created_at))).scalars().first()
        self.assertEqual(anti_abus.aware(anti_abus.datetime.fromisoformat(body["libre_reprise"])),
                         anti_abus.aware(accordee) + anti_abus.LIBRE_WINDOW)
        # Même appareil (même cookie), autre compte : la limite de l'appareil s'applique.
        async with self.fx.sessions() as db:
            other = User(email=f"libre-{uuid.uuid4().hex}@example.com", plan="free", email_verified=True,
                         created_at=racine.compte_ancien())
            db.add(other)
            await db.commit()
        refused = await self.upload(fixtures.pdf(7), headers=self.fx.headers(other))
        self.assertEqual(refused.status_code, 402, refused.text)
        self.assertTrue(refused.json()["libre_limit"])
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, other.id, None), 0)
            machine = (await db.execute(select(LibreGrant.machine_id))).scalars().first()
            self.assertEqual(await anti_abus.libre_used(db, other.id, machine), 20)
            later = anti_abus.utcnow() + timedelta(hours=25)
            self.assertEqual(await anti_abus.libre_used(db, other.id, machine, now=later), 0)

    async def test_reprise_waits_for_enough_old_grants_to_leave_the_window(self):
        maintenant = anti_abus.utcnow()
        async with self.fx.sessions() as db:
            for heures, pages in ((20, 6), (10, 8), (2, 5)):
                db.add(LibreGrant(user_id=self.user.id, machine_id=None, pages=pages,
                                  created_at=maintenant - timedelta(hours=heures)))
            await db.commit()
            # 19 pages prises : 1 page tient, 10 pages attendent la sortie des 6 + 8.
            self.assertIsNone(await anti_abus.libre_reprise(db, self.user.id, None, 1, now=maintenant))
            reprise = await anti_abus.libre_reprise(db, self.user.id, None, 10, now=maintenant)
            self.assertEqual(anti_abus.aware(reprise), anti_abus.aware(maintenant) + timedelta(hours=14))
            # Plus grand que la limite à lui seul : aucune heure de reprise.
            self.assertIsNone(await anti_abus.libre_reprise(db, self.user.id, None, 21, now=maintenant))

    async def test_document_larger_than_the_cap_gets_the_next_slice_time(self):
        # Traduit par tranches (jusqu'à la limite, puis pause) : l'heure dit
        # quand une tranche pleine redevient disponible.
        await self.seed_libres(16)
        refused = await self.upload(fixtures.pdf(25))
        self.assertEqual(refused.status_code, 402, refused.text)
        body = refused.json()
        self.assertEqual((body["libre_needed"], body["pause_possible"]), (20, True))
        self.assertIsNotNone(body["libre_reprise"])

    async def test_document_larger_than_the_cap_has_no_reprise(self):
        self.assertEqual((await self.upload(fixtures.pdf(5))).status_code, 200)   # pages offertes
        refused = await self.upload(fixtures.pdf(21))
        self.assertEqual(refused.status_code, 402, refused.text)
        body = refused.json()
        self.assertEqual((body["libre_limit"], body["libre_needed"], body["libre_reprise"]), (True, 21, None))

    async def test_covered_only_translates_the_covered_pages_without_free_pages(self):
        response = await self.upload(fixtures.pdf(7), covered_only="1")
        document = await self.document(response)
        self.assertEqual((document.page_count, document.pages_libres or 0), (5, 0))
        self.assertTrue(response.json()["can_download"])
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 0)

    async def test_free_pages_lock_the_clear_reading_even_for_a_paying_plan(self):
        subscriber = User(email="abonne@example.com", plan="starter")
        locked = Document(user_id="x", paid=True, pages_libres=3)
        clear = Document(user_id="x", paid=True, pages_libres=0)
        unset = Document(user_id="x", paid=False, pages_libres=None)
        self.assertFalse(_may_read_clear(subscriber, locked))
        self.assertTrue(_may_read_clear(subscriber, clear))
        self.assertTrue(_may_read_clear(subscriber, unset))
        free = User(email="gratuit@example.com", plan="free")
        self.assertFalse(_may_read_clear(free, locked))
        self.assertTrue(_may_read_clear(free, clear))
        self.assertFalse(_may_read_clear(free, unset))

    async def test_free_pages_are_the_last_of_the_selection(self):
        whole = Document(user_id="x", paid=True, pages_libres=2, page_count=7)
        self.assertEqual(pages_libres_du_document(whole), {6, 7})
        chosen = Document(user_id="x", paid=True, pages_libres=2, page_count=4,
                          original_path="/x/doc.pdf", target_lang="en", reglages='{"pages": "2,3,4,9"}')
        self.assertEqual(pages_libres_du_document(chosen), {4, 9})
        self.assertEqual(pages_libres_du_document(Document(user_id="x", pages_libres=0)), set())

    async def test_watermark_targets_only_the_free_pages(self):
        subscriber = User(email="abonne@example.com", plan="starter")
        free = User(email="gratuit@example.com", plan="free")
        mixed = Document(user_id="x", paid=True, pages_libres=2, page_count=7)
        paid = Document(user_id="x", paid=True, pages_libres=0, page_count=7)
        unpaid = Document(user_id="x", paid=False, pages_libres=3, page_count=3)
        self.assertEqual(pages_filigranees(free, mixed), (True, {6, 7}))
        self.assertEqual(pages_filigranees(free, mixed, [1, 2, 7]), (True, {7}))
        self.assertEqual(pages_filigranees(free, mixed, [1, 2]), (False, None))
        self.assertEqual(pages_filigranees(subscriber, paid), (False, None))
        self.assertEqual(pages_filigranees(free, unpaid, [1]), (True, [1]))
        self.assertEqual(pages_filigranees(free, unpaid), (True, None))
        # Crédit bêta (gratuit ou abonné) ou pages offertes : aperçu net, la
        # liste des documents comme l'aperçu en cours de traduction.
        beta_doc = Document(user_id="x", paid=True, pages_libres=0, page_count=2,
                            reglages='{"beta": true}')
        for user in (free, subscriber):
            self.assertEqual(pages_filigranees(user, beta_doc), (False, None))
            self.assertEqual(pages_filigranees(user, beta_doc, [1]), (False, None))
            self.assertFalse(_apercu_filigrane(user, beta_doc))
        self.assertFalse(_apercu_filigrane(free, paid))
        self.assertTrue(_apercu_filigrane(free, unpaid))

    async def test_purge_removes_old_libre_grants_only(self):
        now = anti_abus.utcnow()
        async with self.fx.sessions() as db:
            db.add_all([
                LibreGrant(user_id=self.user.id, machine_id="m", pages=4, created_at=now - timedelta(days=3)),
                LibreGrant(user_id=self.user.id, machine_id="m", pages=2, created_at=now - timedelta(hours=1)),
            ])
            await db.commit()
            await anti_abus.purge(db, now)
            await db.commit()
            rows = (await db.execute(select(LibreGrant))).scalars().all()
            self.assertEqual([row.pages for row in rows], [2])


    async def mixed_document(self):
        """Document de 7 pages : 5 offertes, 2 libres (pages 6 et 7)."""
        document = await self.document(await self.upload(fixtures.pdf(7)))
        self.assertEqual(document.pages_libres, 2)
        # Le worker est remplacé : la traduction est déclarée terminée ici.
        async with self.fx.sessions() as db:
            stored = await db.get(Document, document.id)
            stored.status, stored.translated_path = "done", "trad.json"
            await db.commit()
        return document

    async def set_user(self, **fields):
        async with self.fx.sessions() as db:
            user = await db.get(User, self.user.id)
            for key, value in fields.items():
                setattr(user, key, value)
            await db.commit()

    def rendu(self, pdf, retirees=frozenset()):
        """Traduction terminée rendue en `pdf` ; `retirees` : pages que le
        client a retirées, numérotées comme l'original."""
        from contextlib import ExitStack
        pile = ExitStack()
        for cible, kw in (("app.api.documents._traduction", {"return_value": ("trad.json", None)}),
                          ("app.api.documents._render_or_404", {"return_value": pdf}),
                          ("app.api.documents.render_cache.cache_valid", {"return_value": None}),
                          ("app.api.documents.render_cache.store_render", {}),
                          ("app.api.documents.ocr_pages.pages_retirees", {"return_value": set(retirees)})):
            pile.enter_context(patch(cible, **kw))
        return pile

    async def test_settlement_pays_what_the_purchased_balance_covers(self):
        document = await self.mixed_document()
        await self.set_user(page_credits=1)
        url = f"/api/documents/{document.id}/regler-libres"
        first = await self.client.post(url, headers=self.headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), {"pages_debitees": 1, "pages_libres": 1, "paid": True})
        again = await self.client.post(url, headers=self.headers)
        self.assertEqual(again.json()["pages_debitees"], 0)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).page_credits, 0)
            reloaded = await db.get(Document, document.id)
            self.assertEqual(pages_libres_du_document(reloaded), {7})
        self.assertEqual(sum(row.pages for row in await self.records(document)), 6)

    async def test_settlement_uses_the_monthly_quota_of_a_paying_plan(self):
        document = await self.mixed_document()
        await self.set_user(plan="starter", page_credits=0)
        body = (await self.client.post(f"/api/documents/{document.id}/regler-libres",
                                       headers=self.headers)).json()
        self.assertEqual((body["pages_debitees"], body["pages_libres"]), (2, 0))
        kinds = {row.kind for row in await self.records(document)}
        self.assertIn("plan", kinds)
        async with self.fx.sessions() as db:
            reloaded = await db.get(Document, document.id)
            self.assertTrue(_may_read_clear(await db.get(User, self.user.id), reloaded))

    async def test_settlement_never_takes_the_free_offer_nor_another_account(self):
        document = await self.mixed_document()
        refused = await self.client.post(f"/api/documents/{document.id}/regler-libres",
                                         headers=self.fx.headers(self.fx.tester))
        self.assertEqual(refused.status_code, 404)
        body = (await self.client.post(f"/api/documents/{document.id}/regler-libres",
                                       headers=self.headers)).json()
        self.assertEqual((body["pages_debitees"], body["pages_libres"]), (0, 2))

    async def test_download_offers_the_choice_then_keeps_only_paid_pages(self):
        document = await self.mixed_document()
        url = f"/api/documents/{document.id}/download"
        with self.rendu(fixtures.pdf(7)):
            refused = await self.client.get(url, headers=self.headers)
            self.assertEqual(refused.status_code, 402)
            self.assertEqual(refused.json()["reason"], "pages_libres")
            self.assertEqual(refused.json()["pages_libres"], 2)
            partial = await self.client.get(url + "?sans_libres=1", headers=self.headers)
        self.assertEqual(partial.status_code, 200, partial.text)
        self.assertIn("_PARTIEL", partial.headers["content-disposition"])
        import fitz
        with fitz.open(stream=partial.content, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 5)

    async def test_fully_free_document_is_unlocked_by_purchased_pages(self):
        await self.upload(fixtures.pdf(5))          # épuise les pages offertes
        document = await self.document(await self.upload(fixtures.pdf(3)))
        self.assertEqual((document.paid, document.pages_libres), (False, 3))
        async with self.fx.sessions() as db:
            stored = await db.get(Document, document.id)
            stored.status, stored.translated_path = "done", "trad.json"
            await db.commit()
        await self.set_user(page_credits=4)         # achat : 3 pages + 1 de surplus
        body = (await self.client.post(f"/api/documents/{document.id}/regler-libres",
                                       headers=self.headers)).json()
        self.assertEqual(body, {"pages_debitees": 3, "pages_libres": 0, "paid": True})
        with self.rendu(fixtures.pdf(3)):
            full = await self.client.get(f"/api/documents/{document.id}/download",
                                         headers=self.headers)
        self.assertEqual(full.status_code, 200, full.text)
        self.assertNotIn("_PARTIEL", full.headers["content-disposition"])
        import fitz
        with fitz.open(stream=full.content, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 3)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).page_credits, 1)

    async def test_continue_is_refused_when_no_page_is_paid(self):
        await self.upload(fixtures.pdf(5))          # épuise les pages offertes
        document = await self.document(await self.upload(fixtures.pdf(3)))
        self.assertFalse(document.paid)
        with (patch("app.api.documents._traduction", return_value=("trad.json", None)),
              patch("app.api.documents._render_or_404", return_value=fixtures.pdf(3))):
            refused = await self.client.get(f"/api/documents/{document.id}/download?sans_libres=1",
                                            headers=self.headers)
        self.assertEqual(refused.status_code, 402)

    async def test_settlement_rereads_the_balance_under_the_lock(self):
        """Un solde déjà chargé dans la session (authentification) ne doit pas
        servir au débit : un autre règlement a pu le vider entre-temps."""
        from app.services import usage
        document = await self.mixed_document()
        await self.set_user(page_credits=5)
        async with self.fx.sessions() as db:
            stale = await db.get(User, self.user.id)
            self.assertEqual(stale.page_credits, 5)
            await self.set_user(page_credits=0)      # dépensé par une autre requête
            doc = await db.get(Document, document.id)
            self.assertEqual(await usage.regler_pages_libres(db, self.user.id, doc), 0)
            await db.commit()
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).page_credits, 0)

    async def test_unfinished_translation_is_not_settled(self):
        document = await self.mixed_document()
        await self.set_user(page_credits=5)
        async with self.fx.sessions() as db:
            stored = await db.get(Document, document.id)
            stored.status, stored.translated_path = "cancelled", None
            await db.commit()
        refused = await self.client.post(f"/api/documents/{document.id}/regler-libres",
                                         headers=self.headers)
        self.assertEqual(refused.status_code, 409)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).page_credits, 5)

    async def test_continue_cuts_libre_and_removed_pages_in_one_pass(self):
        """Libres 6-7, pages retirées 2-3 : un seul découpage, numéros de
        l'original (couper en deux fois décalait la seconde coupe)."""
        document = await self.mixed_document()
        with self.rendu(fixtures.pdf(7), retirees={2, 3}):
            partial = await self.client.get(f"/api/documents/{document.id}/download?sans_libres=1",
                                            headers=self.headers)
        self.assertEqual(partial.status_code, 200, partial.text)
        import fitz
        with fitz.open(stream=partial.content, filetype="pdf") as pdf:
            texts = [page.get_text() for page in pdf]
        self.assertEqual(len(texts), 3)
        for kept, number in zip(texts, (0, 3, 4)):
            self.assertIn(f"page {number}", kept)

    async def test_targeted_payment_clears_the_libre_pages(self):
        from app.api.payments import _apply_credit
        from app.models import Payment
        await self.upload(fixtures.pdf(5))          # épuise les pages offertes
        document = await self.document(await self.upload(fixtures.pdf(3)))
        self.assertEqual((document.paid, document.pages_libres), (False, 3))
        async with self.fx.sessions() as db:
            payment = Payment(user_id=self.user.id, document_id=document.id, pages=3,
                              amount=1, currency="XAF", zone="A", status="SUCCESSFUL",
                              provider_ref="ref-" + uuid.uuid4().hex)
            db.add(payment)
            await db.commit()
            await _apply_credit(db, payment)
        async with self.fx.sessions() as db:
            reloaded = await db.get(Document, document.id)
            self.assertEqual((reloaded.paid, reloaded.pages_libres), (True, 0))

    async def test_stopped_document_delivers_its_paid_pages_without_settling(self):
        """Arrêt après 7 pages : seules les 5 payées sont livrées, sans
        fenêtre ni débit (les pages libres d'un arrêt ne se règlent pas)."""
        document = await self.mixed_document()
        await self.set_user(page_credits=5)
        with (patch("app.api.documents._traduction",
                    return_value=("trad.json", set(range(1, 8)))),
              patch("app.api.documents._render_or_404", return_value=fixtures.pdf(7))):
            delivered = await self.client.get(f"/api/documents/{document.id}/download",
                                              headers=self.headers)
        self.assertEqual(delivered.status_code, 200, delivered.text)
        self.assertIn("_PARTIEL", delivered.headers["content-disposition"])
        import fitz
        with fitz.open(stream=delivered.content, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 5)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).page_credits, 5)


    # Retour 4 : traduire jusqu'à la limite, pause, reprise.

    async def seed_libres(self, pages, heures=1):
        async with self.fx.sessions() as db:
            db.add(LibreGrant(user_id=self.user.id, machine_id=None, pages=pages,
                              created_at=anti_abus.utcnow() - timedelta(hours=heures)))
            await db.commit()

    async def traduit_sur_disque(self, document, pages):
        import json
        from app.services.documents import _selection_du_document
        chemin = _selection_du_document(document)[0]
        Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        Path(chemin).write_text(json.dumps({"pages": [
            {"page_num": n, "elements": [{"type": "paragraph", "tr_tagged": "<s1>x</s1>"}]}
            for n in pages]}), encoding="utf-8")

    async def pause(self, response, limite=False, status="paused"):
        # La clôture tourne d'ordinaire dans une boucle à part, sur la base
        # du serveur : ici, sur la base du test. `limite` : pause posée par
        # la limite d'aperçu (et non par l'utilisateur).
        travaux = []
        if limite:
            jobs.marquer_pause_limite(response.json()["job_id"])
        with patch("app.services.jobs._dans_une_boucle_jetable", side_effect=travaux.append):
            jobs.sync_status(response.json()["job_id"], status)
        async with self.fx.sessions() as db:
            await travaux[0](db)
            await db.commit()
        async with self.fx.sessions() as db:
            return await db.get(Document, jobs.get(response.json()["job_id"])["document_id"])

    async def vieillir_libres(self):
        async with self.fx.sessions() as db:
            for g in (await db.execute(select(LibreGrant))).scalars():
                g.created_at -= timedelta(hours=25)
            await db.commit()

    async def document_a_la_limite(self, limite=True, status="paused"):
        """12 pages, 5 offertes, 16 pages d'aperçu déjà prises : la traduction
        s'arrête après la page 9 (4 pages d'aperçu), puis pause."""
        await self.seed_libres(16)
        self.donnees = fixtures.pdf(12)    # mêmes octets pour la reprise
        refused = await self.upload(self.donnees)
        self.assertEqual(refused.status_code, 402, refused.text)
        body = refused.json()
        self.assertTrue(body["libre_limit"])
        self.assertEqual((body["libre_needed"], body["pause_possible"]), (7, True))
        response = await self.upload(self.donnees, jusqu_limite="1")
        document = await self.document(response)
        body = response.json()
        self.assertEqual((body["plafond"], body["pages_libres"], body["libre_restant"]), (9, 4, 0))
        self.assertEqual(body["pages_libres_numeros"], [6, 7, 8, 9])
        self.assertIsNotNone(body["reprise_apercu"])
        self.assertEqual(pages_libres_du_document(document), {6, 7, 8, 9})
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 20)
        await self.traduit_sur_disque(document, range(1, 10))
        paused = await self.pause(response, limite=limite, status=status)
        self.assertEqual((paused.status, paused.pages_done, paused.pages_libres), ("paused", 9, 4))
        return paused

    async def test_a_capped_job_ending_done_stays_paused_at_the_limit(self):
        # Clôture « done » d'un job plafonné en deçà de sa sélection (moteur
        # qui n'aurait pas posé la pause) : le document reste à la limite.
        paused = await self.document_a_la_limite(limite=False, status="done")
        from app.api.documents import _pause_apercu
        self.assertTrue(_pause_apercu(paused)["limite_apercu"])

    async def test_an_empty_preview_page_does_not_give_back_the_pages_after_it(self):
        await self.upload(fixtures.pdf(5))          # épuise les pages offertes
        response = await self.upload(fixtures.pdf(3))
        document = await self.document(response)
        await self.traduit_sur_disque(document, [2])   # page 1 vide, page 2 traduite
        paused = await self.pause(response)
        self.assertEqual(pages_libres_du_document(paused), {1, 2})
        self.assertEqual(reglages_de(paused).get("plafond"), 2)

    async def test_a_manual_pause_before_any_preview_page_keeps_no_zero_cap(self):
        await self.upload(fixtures.pdf(5))          # épuise les pages offertes
        response = await self.upload(fixtures.pdf(3))
        document = await self.document(response)
        paused = await self.pause(response)
        self.assertNotIn("plafond", reglages_de(paused))   # 0 se lirait « sans plafond »
        self.assertEqual(paused.pages_libres, 0)

    async def test_no_partial_offer_on_a_paused_document_with_preview_pages(self):
        await self.upload(fixtures.pdf(5))          # épuise les pages offertes
        await self.seed_libres(17)
        donnees = fixtures.pdf(4)
        response = await self.upload(donnees, jusqu_limite="1")   # pages 1 à 3 en aperçu
        document = await self.document(response)
        await self.traduit_sur_disque(document, [1])
        paused = await self.pause(response)
        self.assertEqual(paused.pages_libres, 1)
        await self.set_user(page_credits=1)
        refused = await self.upload(donnees, resume_of=paused.id)
        self.assertEqual(refused.status_code, 402, refused.text)
        self.assertFalse(refused.json()["partial_possible"])

    async def test_resume_with_another_page_selection_starts_a_new_document(self):
        import json
        from app.services.documents import translation_path_for
        paused = await self.document_a_la_limite()
        await self.vieillir_libres()
        # Un autre compte a traduit la sélection 1-6 : ce cache ne prouve rien
        # de ce que le document en pause a payé.
        dossier = os.path.join(os.path.dirname(paused.original_path), paused.target_lang)
        autre = translation_path_for(dossier, "pdf", set(range(1, 7)),
                                     reglages_de(paused).get("qsuffix") or "")
        Path(autre).parent.mkdir(parents=True, exist_ok=True)
        Path(autre).write_text(json.dumps({"pages": [
            {"page_num": n, "elements": [{"type": "paragraph", "tr_tagged": "<s1>x</s1>"}]}
            for n in range(1, 7)]}), encoding="utf-8")
        response = await self.upload(self.donnees, resume_of=paused.id, pages="1-6")
        self.assertEqual(response.status_code, 200, response.text)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(Document, paused.id)).status, "paused")

    async def test_a_manual_pause_of_a_capped_document_is_not_shown_as_the_limit(self):
        paused = await self.document_a_la_limite(limite=False)
        from app.api.documents import _pause_apercu
        self.assertEqual(_pause_apercu(paused), {})

    async def test_preview_of_a_paused_document_shows_its_preview_pages(self):
        from app.api.documents import _traduction
        paused = await self.document_a_la_limite()
        async with self.fx.sessions() as db:
            _, apercu = await _traduction(db, paused, avec_libres=True)
            _, telechargement = await _traduction(db, paused)
        self.assertEqual(apercu, set(range(1, 10)))         # pages 6 à 9 filigranées
        self.assertEqual(telechargement, set(range(1, 6)))  # payées seulement

    async def test_capped_job_done_with_only_empty_pages_left_stays_done(self):
        from app.services import ocr_pages
        from app.services.documents import _selection_du_document
        await self.seed_libres(16)
        donnees = fixtures.pdf(12)
        response = await self.upload(donnees, jusqu_limite="1")   # plafond 9
        document = await self.document(response)
        ocr_pages.ecrire_choix(_selection_du_document(document)[0], [10, 11, 12], "vide")
        await self.traduit_sur_disque(document, range(1, 10))
        travaux = []
        with patch("app.services.jobs._dans_une_boucle_jetable", side_effect=travaux.append):
            jobs.sync_status(response.json()["job_id"], "done")
        async with self.fx.sessions() as db:
            await travaux[0](db)
            await db.commit()
        async with self.fx.sessions() as db:
            self.assertNotEqual((await db.get(Document, document.id)).status, "paused")

    async def test_launch_up_to_the_limit_then_pause(self):
        paused = await self.document_a_la_limite()
        # Seules les 5 pages offertes sont débitées ; la pause n'en rend aucune.
        self.assertEqual(sum(r.pages for r in await self.records(paused) if not r.refunded), 5)
        # « Mes documents » dit pourquoi il est en pause et quand reprendre.
        from app.api.documents import _pause_apercu
        carte = _pause_apercu(paused)
        self.assertTrue(carte["limite_apercu"])
        self.assertIsNotNone(carte["reprise_apercu"])

    async def test_resume_next_day_keeps_the_preview_pages_without_recounting(self):
        paused = await self.document_a_la_limite()
        # Le jour même : l'aperçu est épuisé, la reprise n'avancerait pas.
        same_day = await self.upload(self.donnees, resume_of=paused.id, jusqu_limite="1")
        self.assertEqual(same_day.status_code, 402, same_day.text)
        self.assertEqual((same_day.json()["libre_needed"], same_day.json()["pause_possible"]), (3, False))
        await self.vieillir_libres()
        response = await self.upload(self.donnees, resume_of=paused.id)
        document = await self.document(response)
        body = response.json()
        self.assertNotIn("plafond", body)
        self.assertEqual((body["pages_libres"], body["libre_restant"]), (7, 17))
        self.assertEqual(body["pages_libres_numeros"], list(range(6, 13)))
        self.assertEqual(sum(r.pages for r in await self.records(document)), 0)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(Document, paused.id)).status, "resumed")
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 3)

    async def test_resume_after_purchase_pays_the_preview_pages_already_done(self):
        paused = await self.document_a_la_limite()
        await self.set_user(page_credits=7)
        response = await self.upload(self.donnees, resume_of=paused.id)
        document = await self.document(response)
        body = response.json()
        self.assertTrue(body["can_download"])
        self.assertNotIn("pages_libres", body)
        self.assertEqual(sum(r.pages for r in await self.records(document)), 7)
        async with self.fx.sessions() as db:
            self.assertEqual((await db.get(User, self.user.id)).page_credits, 0)

    async def test_manual_pause_gives_back_the_untranslated_preview_pages(self):
        donnees = fixtures.pdf(7)
        response = await self.upload(donnees)      # 5 offertes, pages 6 et 7 en aperçu
        document = await self.document(response)
        await self.traduit_sur_disque(document, range(1, 7))
        paused = await self.pause(response)
        self.assertEqual(paused.pages_libres, 1)
        self.assertEqual(pages_libres_du_document(paused), {6})
        from app.api.documents import _pause_apercu
        self.assertEqual(_pause_apercu(paused), {})     # pause manuelle
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 1)
        # La reprise retrouve la page 6 en aperçu et ne compte que la 7.
        resumed = await self.upload(donnees, resume_of=paused.id)
        body = resumed.json()
        self.assertEqual((body["pages_libres"], body["pages_libres_numeros"]), (2, [6, 7]), resumed.text)
        async with self.fx.sessions() as db:
            self.assertEqual(await anti_abus.libre_used(db, self.user.id, None), 2)


if __name__ == "__main__":
    unittest.main()


class PauseAuPlafondTests(unittest.TestCase):
    """Moteur : la page hors plafond pose la pause « limite » ; une pause
    manuelle déjà demandée prime et n'est pas lue comme la limite."""

    def setUp(self):
        from app.services.translation_runner import _pause_au_plafond
        self.job_id = jobs.create()
        jobs.demarrer(self.job_id)
        self.avant_page = _pause_au_plafond(self.job_id, "inutile.pdf", {1, 2, 3, 4}, 2)

    def test_page_beyond_the_cap_pauses_at_the_limit(self):
        from app.services.jobs import ArretDemande
        self.avant_page(1)
        self.avant_page(2)
        with self.assertRaises(ArretDemande):
            self.avant_page(3)
        job = jobs.get(self.job_id)
        self.assertEqual((job["arret"], job.get("pause_limite")), ("paused", True))

    def test_manual_pause_already_requested_is_not_the_limit(self):
        from app.services.jobs import ArretDemande
        jobs.demander_arret(self.job_id, "paused")
        with self.assertRaises(ArretDemande):
            self.avant_page(3)
        self.assertFalse(jobs.get(self.job_id).get("pause_limite"))
