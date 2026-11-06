"""Clôture d'un scan : les pages illisibles ou blanches réservées au lancement
reviennent au client (crédits achetés d'abord), une seule fois même si la
clôture est rejouée ; sélection, reprise et bêta comptent juste.

    PYTHONUTF8=1 venv/Scripts/python.exe tests/test_ocr_facturation_pages.py
"""
import asyncio
import json
import os
import tempfile
import unittest
import uuid

import racine  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import DATABASE_URL
from app.models import Document, User
from app.models.beta import BetaCampaign, BetaEnrollment, BetaUsage
from app.models.usage import KIND_CREDITS, KIND_PLAN, UsageRecord
from app.services import ocr_pages
from app.services.jobs import jobs

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)


def lancer(coro):
    return asyncio.run(coro)


class Cloture(unittest.TestCase):
    CREDITS = 10

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.email = f"ocr-fact-{uuid.uuid4().hex[:10]}@example.com"
        self.beta_ids = []

        async def creer():
            async with session() as db:
                u = User(email=self.email, name="OCR facturation", plan="free",
                         email_verified=True, page_credits=self.CREDITS)
                db.add(u)
                await db.commit()
                return u.id
        self.user_id = lancer(creer())
        self.addCleanup(lambda: lancer(self._nettoyer()))

    async def _nettoyer(self):
        async with session() as db:
            docs = (await db.execute(select(Document.id).where(
                Document.user_id == self.user_id))).scalars().all()
            for model, col in ((BetaUsage, BetaUsage.document_key),
                               (UsageRecord, UsageRecord.document_id)):
                for row in (await db.execute(select(model).where(col.in_(docs or [""])))).scalars():
                    await db.delete(row)
            await db.flush()
            for ident in self.beta_ids:
                obj = await db.get(BetaEnrollment, ident) or await db.get(BetaCampaign, ident)
                if obj is not None:
                    await db.delete(obj)
                    await db.flush()
            for ident in docs:
                await db.delete(await db.get(Document, ident))
            await db.delete(await db.get(User, self.user_id))
            await db.commit()

    # -- Préparation -------------------------------------------------------
    def document(self, page_count, lignes=(), reglages=None, beta_units=0, statuts=None):
        """Document traduit, ses consommations réservées et le statut OCR des pages."""
        dossier = os.path.join(self.dir, uuid.uuid4().hex[:8])
        os.makedirs(dossier)
        trad = os.path.join(dossier, "pages_ocrv3.json")
        for page, statut in (statuts or {}).items():
            ocr_pages.ecrire(trad, page, statut, "lecture" if statut == "illisible" else None)

        async def creer():
            async with session() as db:
                doc = Document(user_id=self.user_id, original_name="scan.pdf", source_lang="fr",
                               target_lang="en", original_path=os.path.join(dossier, "original.pdf"),
                               size_bytes=1, status="translating", page_count=page_count,
                               reglages=json.dumps(reglages or {}))
                db.add(doc)
                await db.flush()
                for kind, pages in lignes:
                    db.add(UsageRecord(user_id=self.user_id, document_id=doc.id, kind=kind, pages=pages))
                if beta_units:
                    campagne = BetaCampaign(name="test ocr", limits={})
                    db.add(campagne)
                    await db.flush()
                    inscription = BetaEnrollment(campaign_id=campagne.id, email=self.email,
                                                 user_id=self.user_id, limits={})
                    db.add(inscription)
                    await db.flush()
                    self.beta_ids += [inscription.id, campagne.id]
                    db.add(BetaUsage(enrollment_id=inscription.id, document_id=doc.id,
                                     document_key=doc.id, format="pdf", units=beta_units))
                await db.commit()
                return doc.id
        return lancer(creer()), trad

    def cloturer(self, doc_id, trad):
        job = jobs.create()
        jobs.get(job)["document_id"] = doc_id
        try:
            jobs.sync_status(job, "done", translated_path=trad)
        finally:
            jobs.forget(job)

    def etat(self, doc_id):
        async def lire():
            async with session() as db:
                par_titre = dict((await db.execute(
                    select(UsageRecord.kind, func.sum(UsageRecord.pages))
                    .where(UsageRecord.document_id == doc_id, UsageRecord.refunded.is_(False))
                    .group_by(UsageRecord.kind))).all())
                credits = (await db.get(User, self.user_id)).page_credits
                beta = (await db.execute(select(func.coalesce(func.sum(BetaUsage.units), 0)).where(
                    BetaUsage.document_key == doc_id, BetaUsage.refunded.is_(False)))).scalar()
                statut = (await db.get(Document, doc_id)).status
                return {k: int(v) for k, v in par_titre.items()}, credits, int(beta), statut
        return lancer(lire())

    # -- Cas ---------------------------------------------------------------
    def test_illisibles_et_blanches_rendues_credits_d_abord(self):
        doc, trad = self.document(5, [(KIND_CREDITS, 2), (KIND_PLAN, 3)],
                                  statuts={2: "illisible", 4: "illisible", 5: "blanche"})
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({KIND_PLAN: 2}, self.CREDITS + 2, 0, "done"))

    def test_cloture_rejouee_ne_rend_pas_deux_fois(self):
        doc, trad = self.document(5, [(KIND_CREDITS, 2), (KIND_PLAN, 3)],
                                  statuts={2: "illisible", 4: "illisible", 5: "blanche"})
        self.cloturer(doc, trad)
        premier = self.etat(doc)
        self.cloturer(doc, trad)
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), premier)

    def test_credits_partiellement_rendus_puis_rejoue(self):
        doc, trad = self.document(4, [(KIND_CREDITS, 4)], statuts={1: "illisible"})
        self.cloturer(doc, trad)
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 3}, self.CREDITS + 1, 0, "done"))

    def test_document_entierement_illisible_rien_n_est_du(self):
        doc, trad = self.document(2, [(KIND_CREDITS, 1), (KIND_PLAN, 1)],
                                  statuts={1: "illisible", 2: "blanche"})
        self.cloturer(doc, trad)
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({}, self.CREDITS + 1, 0, "done"))

    def test_hors_selection_non_compte(self):
        doc, trad = self.document(2, [(KIND_PLAN, 2)], reglages={"pages": "2,3"},
                                  statuts={1: "illisible", 3: "illisible", 4: "blanche"})
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc)[0], {KIND_PLAN: 1})

    def test_reprise_ne_compte_que_le_reste(self):
        # 2 pages payées par le document repris ; celui-ci réserve les 3 autres.
        doc, trad = self.document(5, [(KIND_PLAN, 3)], reglages={"deja": 2},
                                  statuts={5: "illisible"})
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc)[0], {KIND_PLAN: 2})

    def test_beta_pages_rendues(self):
        doc, trad = self.document(3, reglages={"beta": True}, beta_units=3,
                                  statuts={3: "illisible"})
        self.cloturer(doc, trad)
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({}, self.CREDITS, 2, "done"))

    def test_beta_entierement_illisible(self):
        doc, trad = self.document(2, reglages={"beta": True}, beta_units=2,
                                  statuts={1: "illisible", 2: "illisible"})
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc)[2], 0)

    # -- Solde partiel (budget à la page) -------------------------------------
    def document_budget(self, traduites, lues_vides=()):
        """Scan de 6 pages, solde de 3 : pages 1-4 parcourues (2 illisible),
        5-6 hors budget. `traduites` sortent traduites, `lues_vides` lues sans
        paragraphe traduit."""
        doc, trad = self.document(6, [(KIND_CREDITS, 3)], reglages={"budget": 3},
                                  statuts={2: "illisible"})
        for n in (1, 3, 4):
            ocr_pages.ecrire(trad, n, "ok", pdf=b"%PDF-1.4")
        pages = [{"page_num": n, "elements": [{"type": "paragraph", "tr_tagged": n in traduites}]}
                 for n in range(1, 7)]
        with open(trad, "w", encoding="utf-8") as f:
            json.dump({"pages": pages}, f)
        return doc, trad

    def cloturer_budget(self, doc_id, trad, consommees):
        job = jobs.create()
        jobs.get(job)["document_id"] = doc_id
        ocr_pages.ecrire_budget(trad, job, [1, 2, 3, 4], consommees)
        try:
            jobs.sync_status(job, "done", translated_path=trad)
            jobs.sync_status(job, "done", translated_path=trad)
        finally:
            jobs.forget(job)

    def chemin(self, doc_id):
        async def lire():
            async with session() as db:
                return (await db.get(Document, doc_id)).translated_path
        return lancer(lire())

    def test_budget_tout_consomme_copie_propre_filtree(self):
        doc, trad = self.document_budget(traduites={1, 3, 4})
        self.cloturer_budget(doc, trad, [1, 3, 4])
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 3}, self.CREDITS, 0, "done"))
        copie = self.chemin(doc)
        self.assertNotEqual(copie, trad, "la traduction partagée reste intacte")
        with open(copie, encoding="utf-8") as f:
            self.assertEqual([p["page_num"] for p in json.load(f)["pages"]], [1, 2, 3, 4])
        with open(trad, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["pages"]), 6)
        self.assertEqual(ocr_pages.lire_selection(copie), {1, 2, 3, 4})

    def test_budget_page_lue_sans_traduction_rendue_une_fois(self):
        doc, trad = self.document_budget(traduites={1, 3})
        self.cloturer_budget(doc, trad, [1, 3, 4])
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 2}, self.CREDITS + 1, 0, "done"))

    def test_budget_copie_purge_les_lectures_etrangeres(self):
        doc, trad = self.document_budget(traduites={1, 3, 4})
        ocr_pages.ecrire(trad, 6, "ok", pdf=b"%PDF-1.4")   # lue par un autre compte
        ocr_pages.ecrire_choix(trad, [5], "original")
        self.cloturer_budget(doc, trad, [1, 3, 4])
        copie = self.chemin(doc)
        self.assertEqual(set(ocr_pages.lister(copie)), {1, 2, 3, 4})
        self.assertEqual(ocr_pages.lire_choix(copie), {})
        self.assertIn(6, ocr_pages.lister(trad), "la traduction partagée reste intacte")

    def test_budget_releve_perdu_tout_rendu_rien_livre(self):
        doc, trad = self.document_budget(traduites={1, 3, 4})
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({}, self.CREDITS + 3, 0, "error"))
        self.assertIsNone(self.chemin(doc))

    def test_budget_rien_de_traduit_tout_rendu(self):
        doc, trad = self.document_budget(traduites=set())
        self.cloturer_budget(doc, trad, [])
        self.assertEqual(self.etat(doc), ({}, self.CREDITS + 3, 0, "done"))

    def rejouer_apres_tqm(self, chemin_passe):
        """Clôture budget, « traduire quand même » de la page 2 dans la copie
        (débitée à part), puis clôture rejouée du même job."""
        doc, trad = self.document_budget(traduites={1, 3, 4})
        job = jobs.create()
        jobs.get(job)["document_id"] = doc
        ocr_pages.ecrire_budget(trad, job, [1, 2, 3, 4], [1, 3, 4])
        try:
            jobs.sync_status(job, "done", translated_path=trad)
            copie = self.chemin(doc)
            ocr_pages.ecrire(copie, 2, "ok", pdf=b"%PDF-1.4")
            with open(copie, encoding="utf-8") as f:
                data = json.load(f)
            for p in data["pages"]:
                if p["page_num"] == 2:
                    p["elements"][0]["tr_tagged"] = True
            with open(copie, "w", encoding="utf-8") as f:
                json.dump(data, f)

            async def debiter():
                async with session() as db:
                    db.add(UsageRecord(user_id=self.user_id, document_id=doc,
                                       kind=KIND_CREDITS, pages=1))
                    await db.commit()
            lancer(debiter())
            jobs.sync_status(job, "done", translated_path=trad if chemin_passe else None)
        finally:
            jobs.forget(job)
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 4}, self.CREDITS, 0, "done"))
        self.assertEqual(self.chemin(doc), copie)
        with open(copie, encoding="utf-8") as f:
            self.assertEqual([p["page_num"] for p in json.load(f)["pages"]], [1, 2, 3, 4])

    def test_budget_rejoue_sans_chemin_garde_la_page_traduite_quand_meme(self):
        self.rejouer_apres_tqm(chemin_passe=False)

    def test_budget_rejoue_avec_chemin_garde_la_page_traduite_quand_meme(self):
        self.rejouer_apres_tqm(chemin_passe=True)

    def test_rejoue_hors_budget_garde_la_page_traduite_quand_meme(self):
        doc, trad = self.document(3, [(KIND_CREDITS, 3)], statuts={2: "illisible"})
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 2}, self.CREDITS + 1, 0, "done"))
        ocr_pages.ecrire(trad, 2, "ok", pdf=b"%PDF-1.4")

        async def debiter():
            async with session() as db:
                db.add(UsageRecord(user_id=self.user_id, document_id=doc,
                                   kind=KIND_CREDITS, pages=1))
                (await db.get(User, self.user_id)).page_credits -= 1
                await db.commit()
        lancer(debiter())
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 3}, self.CREDITS, 0, "done"))

    def test_sans_page_illisible_rien_ne_change(self):
        doc, trad = self.document(3, [(KIND_CREDITS, 3)])
        self.cloturer(doc, trad)
        self.assertEqual(self.etat(doc), ({KIND_CREDITS: 3}, self.CREDITS, 0, "done"))


if __name__ == "__main__":
    unittest.main()
