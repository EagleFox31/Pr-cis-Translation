"""Pages illisibles d'un scan : lister, garder l'original, laisser vide ou
traduire quand même (une page débitée seulement si elle est traduite).
L'OCR est simulé ; la base de test (5433) est requise.

    PYTHONUTF8=1 venv/Scripts/python.exe tests/test_ocr_pages_choix.py
"""
import asyncio
import json
import os
import tempfile
import unittest

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import racine  # noqa: F401
import fitz
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api import documents as api
from app.core.database import DATABASE_URL
from app.models import Document, KIND_FREE_OFFER, User, get_plan_monthly_pages
from app.models.beta import BetaCampaign, BetaEnrollment, BetaUsage
from app.models.usage import UsageRecord
from app.services import ocr_pages, translation_runner, usage
from app.services.jobs import jobs
from app.services.ocr import LecturePage
from app.services.translation_runner import render_translation_bytes, run_pdf_v2_job
from test_ocr_moteur_pages import document, page_lue
from test_ocr_pages import pdf_photo

_eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
session = async_sessionmaker(_eng, class_=AsyncSession, expire_on_commit=False)
LIRE = "app.services.translation_runner.ocr.lire_page"


def lancer(coro):
    return asyncio.run(coro)


class Choix(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.beta_ids = []
        self.addCleanup(lambda: lancer(self._nettoyer()))
        self.user_id = self._utilisateur()

    def _utilisateur(self, credits=10):
        async def creer():
            async with session() as db:
                u = User(email=f"ocr-choix-{uuid.uuid4().hex[:10]}@example.com", name="OCR choix",
                         plan="free", email_verified=True, page_credits=credits)
                db.add(u)
                await db.commit()
                return u.id
        ident = lancer(creer())
        self.addCleanup(lambda: lancer(self._supprimer_compte(ident)))
        return ident

    async def _supprimer_compte(self, user_id):
        async with session() as db:
            docs = (await db.execute(select(Document.id).where(Document.user_id == user_id))).scalars().all()
            for model, col in ((BetaUsage, BetaUsage.document_key), (UsageRecord, UsageRecord.document_id)):
                for row in (await db.execute(select(model).where(col.in_(docs or [""])))).scalars():
                    await db.delete(row)
            await db.flush()
            for ident in docs:
                await db.delete(await db.get(Document, ident))
            await db.flush()
            await db.delete(await db.get(User, user_id))
            await db.commit()

    async def _nettoyer(self):
        async with session() as db:
            for ident in self.beta_ids:
                obj = await db.get(BetaEnrollment, ident) or await db.get(BetaCampaign, ident)
                if obj is not None:
                    await db.delete(obj)
                    await db.flush()
            await db.commit()

    # -- Préparation -------------------------------------------------------
    def scan(self, reglages=None):
        """Scan de 3 pages traduit : 1 texte, 2 lue, 3 illisible."""
        dossier = os.path.join(self.dir, uuid.uuid4().hex[:8])
        os.makedirs(dossier)
        self.original = os.path.join(dossier, "original.pdf")
        trad = os.path.join(dossier, "pages_debug_ocrv3.json")
        octets = document("texte", pdf_photo(), pdf_photo())
        lectures = {2: LecturePage("ok", None, page_lue()), 3: LecturePage("illisible", "lecture")}
        job = jobs.create()
        with patch(LIRE, lambda _src, page: lectures[page]):
            run_pdf_v2_job(job, octets, self.original, os.path.join(dossier, "out.pdf"), "scan.pdf",
                           os.path.join(dossier, "partial.pdf"), trad, "en", None, True)
        jobs.forget(job)
        self.assertEqual(ocr_pages.pages_illisibles(trad), {3: "lecture"})

        async def creer():
            async with session() as db:
                doc = Document(user_id=self.user_id, original_name="scan.pdf", source_lang="fr",
                               target_lang="en", original_path=self.original, translated_path=trad,
                               size_bytes=1, status="done", page_count=3,
                               reglages=json.dumps(reglages or {}))
                db.add(doc)
                await db.commit()
                return doc.id
        return lancer(creer()), trad

    def beta(self, doc_id, unites=2):
        async def creer():
            async with session() as db:
                user = await db.get(User, self.user_id)
                campagne = BetaCampaign(name="test choix", limits={})
                db.add(campagne)
                await db.flush()
                maintenant = datetime.now(timezone.utc)
                inscription = BetaEnrollment(campaign_id=campagne.id, email=user.email,
                                             user_id=self.user_id, limits={},
                                             activated_at=maintenant,
                                             expires_at=maintenant + timedelta(days=7))
                db.add(inscription)
                await db.flush()
                self.beta_ids += [inscription.id, campagne.id]
                db.add(BetaUsage(enrollment_id=inscription.id, document_id=doc_id,
                                 document_key=doc_id, format="pdf", units=unites))
                await db.commit()
        lancer(creer())

    # -- Appels ------------------------------------------------------------
    def appel(self, route, doc_id, *args, user_id=None):
        async def faire():
            async with session() as db:
                user = await db.get(User, user_id or self.user_id)
                return await route(doc_id, *args, user=user, db=db)
        return lancer(faire())

    def lister(self, doc_id, **kw):
        return self.appel(api.pages_illisibles, doc_id, **kw)

    def choisir(self, doc_id, pages, choix, **kw):
        """PATCH ; les travaux soumis sont rendus (sans les lancer)."""
        soumis = []
        with patch.object(api.scheduler_scans, "submit", side_effect=lambda *a: soumis.append(a)):
            reponse = self.appel(api.choisir_pages_illisibles, doc_id,
                                 api.ChoixPages(pages=pages, choix=choix), **kw)
        return reponse, soumis

    def executer(self, soumis, lecture):
        for _job, _prio, cible, args in soumis:
            with patch(LIRE, lambda _src, _page, forcee=False: lecture):
                cible(*args)

    def doc(self, doc_id):
        async def lire():
            async with session() as db:
                return await db.get(Document, doc_id)
        return lancer(lire())

    def debits(self, doc_id):
        async def lire():
            async with session() as db:
                pages = (await db.execute(select(func.coalesce(func.sum(UsageRecord.pages), 0)).where(
                    UsageRecord.document_id == doc_id, UsageRecord.refunded.is_(False)))).scalar()
                beta = (await db.execute(select(func.coalesce(func.sum(BetaUsage.units), 0)).where(
                    BetaUsage.document_key == doc_id, BetaUsage.refunded.is_(False)))).scalar()
                return int(pages), int(beta)
        return lancer(lire())

    # -- Cas ---------------------------------------------------------------
    def test_liste_par_defaut_sans_choix(self):
        doc, _ = self.scan()
        self.assertEqual(self.lister(doc), {"pages": [{"page": 3, "motif": "lecture",
                                                       "choix": None}], "en_cours": [],
                                             "provisoire": False, "blanches": []})

    def test_pages_blanches_listees_a_part(self):
        """Une page blanche n'est pas à décider : elle sort dans `blanches`,
        jamais dans `pages`."""
        doc, trad = self.scan()
        ocr_pages.ecrire(trad, 2, "blanche")
        reponse = self.lister(doc)
        self.assertEqual(([p["page"] for p in reponse["pages"]], reponse["blanches"]), ([3], [2]))

    def test_pendant_la_traduction_liste_provisoire_sans_choix(self):
        """Traduction en cours : `translated_path` est encore NULL. Les pages
        déjà lues se listent (la carte s'affiche sur la page), sans choix
        possible tant que la copie du document n'existe pas."""
        doc, trad = self.scan()

        async def en_cours(status):
            async with session() as db:
                d = await db.get(Document, doc)
                d.translated_path, d.status = None, status
                await db.commit()
        lancer(en_cours("translating"))
        with patch.object(api, "chemin_traduction_du_document", lambda _d: trad):
            self.assertEqual(self.lister(doc), {"pages": [{"page": 3, "motif": "lecture",
                                                           "choix": None}],
                                                "en_cours": [], "provisoire": True, "blanches": []})
            with self.assertRaises(api.HTTPException) as refus:
                self.choisir(doc, [3], "vide")
            self.assertEqual(refus.exception.status_code, 404)
            self.assertFalse(ocr_pages.lire_choix(trad))
            lancer(en_cours("error"))
            with self.assertRaises(api.HTTPException) as fini:
                self.lister(doc)
            self.assertEqual(fini.exception.status_code, 404)

    def test_vide_puis_original_sur_une_copie_propre(self):
        doc, trad = self.scan()
        reponse, soumis = self.choisir(doc, [3], "vide")
        self.assertEqual((reponse["pages"][0]["choix"], soumis), ("vide", []))
        copie = self.doc(doc).translated_path
        self.assertNotEqual(copie, trad, "la traduction partagée n'est pas modifiée")
        self.assertEqual(ocr_pages.lire_choix(trad), {})
        with fitz.open(stream=render_translation_bytes(self.original, copie, "pdf", "en"),
                       filetype="pdf") as rendu:
            self.assertEqual(rendu[2].get_images(), [])
        reponse, _ = self.choisir(doc, [3], "original")
        self.assertEqual(reponse["pages"][0]["choix"], "original")
        with fitz.open(stream=render_translation_bytes(self.original, copie, "pdf", "en"),
                       filetype="pdf") as rendu:
            self.assertGreaterEqual(len(rendu[2].get_images()), 1)
        self.assertEqual(self.debits(doc), (0, 0))

    def test_traduire_reussi_une_page_debitee_et_rendue(self):
        doc, _ = self.scan()
        reponse, soumis = self.choisir(doc, [3], "traduire")
        self.assertEqual((reponse["en_cours"], len(soumis)), ([3], 1))
        copie = self.doc(doc).translated_path
        self.executer(soumis, LecturePage("ok", None, page_lue("Second reading text")))
        self.assertEqual(self.debits(doc), (1, 0))
        self.assertEqual(self.lister(doc), {"pages": [], "en_cours": [], "provisoire": False, "blanches": []})
        self.assertEqual(ocr_pages.lire(copie, 3)["statut"], "ok")
        with fitz.open(stream=render_translation_bytes(self.original, copie, "pdf", "en"),
                       filetype="pdf") as rendu:
            self.assertIn("Second reading text", rendu[2].get_text())
            self.assertIn("Recognized scan text", rendu[1].get_text())

    def _offre_epuisee(self):
        async def consommer():
            async with session() as db:
                usage.record(db, self.user_id, None, KIND_FREE_OFFER, get_plan_monthly_pages("free"))
                await db.commit()
        lancer(consommer())

    def test_suivi_de_la_bibliotheque(self):
        """La carte de la bibliothèque suit les pages : à décider, puis en
        relecture, puis plus rien une fois la page relue."""
        doc, _ = self.scan()
        suivi = lambda: api._suivi_scan(self.doc(doc))
        self.assertEqual(suivi(), {"pages_a_decider": 1, "pages_relues": 0})
        _, soumis = self.choisir(doc, [3], "traduire")
        self.assertEqual(suivi(), {"pages_a_decider": 0, "pages_relues": 1})
        self.executer(soumis, LecturePage("ok", None, page_lue("Second reading text")))
        self.assertEqual(suivi(), {"pages_a_decider": 0, "pages_relues": 0})

    def test_essai_sur_pages_offertes_reste_en_apercu(self):
        doc, _ = self.scan()
        _, soumis = self.choisir(doc, [3], "traduire")
        self.executer(soumis, LecturePage("ok", None, page_lue("Second reading text")))
        self.assertEqual(self.debits(doc), (1, 0))
        self.assertFalse(self.doc(doc).paid)

    def test_essai_paye_en_credits_devient_telechargeable(self):
        """Même règle qu'au lancement : une page achetée rend le document téléchargeable."""
        doc, _ = self.scan()
        self._offre_epuisee()
        _, soumis = self.choisir(doc, [3], "traduire")
        self.executer(soumis, LecturePage("ok", None, page_lue("Second reading text")))
        self.assertEqual(self.debits(doc), (1, 0))
        self.assertTrue(self.doc(doc).paid)

    def test_traduire_sans_texte_rien_debite(self):
        doc, _ = self.scan()
        _, soumis = self.choisir(doc, [3], "traduire")
        self.executer(soumis, LecturePage("illisible", "lecture"))
        self.assertEqual(self.debits(doc), (0, 0))
        self.assertEqual([p["page"] for p in self.lister(doc)["pages"]], [3])

    def test_solde_epuise_pendant_le_travail(self):
        doc, _ = self.scan()
        _, soumis = self.choisir(doc, [3], "traduire")
        copie = self.doc(doc).translated_path
        with open(copie, "rb") as f:
            avant = f.read()
        with patch.object(translation_runner.ext_service, "debiter", return_value=False) as debit:
            async def refus(*_a, **_k):
                return False
            debit.side_effect = refus
            self.executer(soumis, LecturePage("ok", None, page_lue()))
        self.assertEqual(self.debits(doc), (0, 0))
        with open(copie, "rb") as f:
            self.assertEqual(f.read(), avant, "la traduction est remise comme avant")
        self.assertEqual(ocr_pages.lire(copie, 3)["statut"], "illisible")
        with open(copie, encoding="utf-8") as f:
            page3 = [p for p in json.load(f)["pages"] if p.get("page_num") == 3]
        self.assertFalse(any(e.get("tr_tagged") for p in page3 for e in p.get("elements", [])),
                         "la page 3 n'apparaît pas traduite")
        self.assertEqual(self.lister(doc)["pages"], [{"page": 3, "motif": "solde", "choix": None}])

    def test_402_sans_couverture_rien_lance(self):
        doc, trad = self.scan()

        async def rien(*_a):
            return 0, 0, False
        with patch.object(api.extension, "couverture", rien):
            reponse, soumis = self.choisir(doc, [3], "traduire")
        self.assertEqual((reponse.status_code, soumis), (402, []))
        corps = json.loads(bytes(reponse.body))
        self.assertEqual((corps["reason"], corps["required"]), ("insufficient_credits", 1))
        self.assertEqual(self.doc(doc).translated_path, trad, "rien n'est copié sur un refus")

    def test_deux_demandes_un_seul_travail(self):
        doc, _ = self.scan()
        _, premier = self.choisir(doc, [3], "traduire")
        reponse, second = self.choisir(doc, [3], "traduire")
        self.assertEqual((len(premier), second, reponse["en_cours"]), (1, [], [3]))
        self.executer(premier, LecturePage("ok", None, page_lue()))
        self.assertEqual(self.debits(doc), (1, 0))
        self.assertEqual(translation_runner.pages_en_cours(self.doc(doc).translated_path), set())

    def test_beta_page_traduite_comptee(self):
        doc, _ = self.scan(reglages={"beta": True})
        self.beta(doc, unites=2)
        _, soumis = self.choisir(doc, [3], "traduire")
        self.assertEqual(len(soumis), 1)
        self.assertIs(soumis[0][3][-1], True)
        self.executer(soumis, LecturePage("ok", None, page_lue()))
        self.assertEqual(self.debits(doc), (0, 3))

    def test_document_d_un_autre_compte(self):
        doc, _ = self.scan()
        autre = self._utilisateur()
        for appel in (lambda: self.lister(doc, user_id=autre),
                      lambda: self.choisir(doc, [3], "vide", user_id=autre)):
            with self.assertRaises(HTTPException) as err:
                appel()
            self.assertEqual(err.exception.status_code, 404)

    def test_page_non_illisible_409(self):
        doc, trad = self.scan()
        for pages in ([2], [1, 3]):
            with self.assertRaises(HTTPException) as err:
                self.choisir(doc, pages, "traduire")
            self.assertEqual(err.exception.status_code, 409)
        self.assertEqual(self.doc(doc).translated_path, trad)


if __name__ == "__main__":
    unittest.main()
