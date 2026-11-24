"""Deux traductions lancées en même temps sur un solde qui ne couvre pas les deux.

20 pages achetées, documents de 15 et 30 pages envoyés simultanément.
Le moteur est remplacé ; admission, verrou et consommation sont réels.
"""
import asyncio
import io
import json
import sys
import unittest
from unittest.mock import patch
import uuid

import racine  # noqa: F401
import test_beta_program as fixtures
from fastapi import Response
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.api import translate as translation
from app.core.database import DATABASE_URL
from app.models import User, UsageRecord, Document


class CourseSolde(unittest.IsolatedAsyncioTestCase):
    async def test_15_et_30_pages_sur_20(self):
        engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        fx = fixtures.BetaTests()
        await fx.asyncSetUp()
        async with sessions() as db:
            user = User(email=f"course-{uuid.uuid4().hex}@example.com", email_verified=True,
                        plan="free", page_credits=20, created_at=racine.compte_ancien())
            db.add(user)
            await db.commit()

        async def envoi(n, covered=""):
            async with sessions() as db:
                compte = await db.get(User, user.id)
                rep = await translation.translate_endpoint(
                    request=racine.requete_test(), response=Response(),
                    file=fixtures.translation.UploadFile(filename=f"doc{n}.pdf", file=io.BytesIO(fixtures.pdf(n))),
                    target_lang="en", format_options="{}", quality="fast", precise="", pages="",
                    debug="", covered_only=covered, use_beta="0",
                    x_api_key=fixtures.config.FRONTEND_API_KEY, current_user=compte, db=db)
                code = getattr(rep, "status_code", 200)
                corps = json.loads(rep.body) if hasattr(rep, "body") else rep
                return n, code, corps

        async def etat():
            async with sessions() as db:
                u = await db.get(User, user.id, populate_existing=True)
                recs = (await db.execute(select(UsageRecord.kind, UsageRecord.pages)
                        .where(UsageRecord.user_id == user.id))).all()
                docs = (await db.execute(select(Document.original_name, Document.pages_libres)
                        .where(Document.user_id == user.id))).all()
                print("  documents (nom, pages en aperçu) :", docs)
                return u.page_credits, recs

        try:
            for essai in range(3):
                async with sessions() as db:
                    await db.execute(delete(UsageRecord).where(UsageRecord.user_id == user.id))
                    u = await db.get(User, user.id); u.page_credits = 20
                    await db.commit()
                res = await asyncio.gather(envoi(15), envoi(30))
                solde, recs = await etat()
                print(f"\n--- essai {essai+1} ---")
                for n, code, corps in res:
                    resume = {k: corps.get(k) for k in ("reason", "pages_needed", "pages_available",
                              "partial_possible", "libre_limit")} if code != 200 else "accepté"
                    print(f"  doc {n} p. -> {code} {resume}")
                print(f"  solde après : {solde} ; consommations : {recs}")
                self.assertGreaterEqual(solde, 0)
                self.assertLessEqual(sum(p for k, p in recs if k == "credits"), 20)
            # Suite logique côté client : traduire seulement les pages couvertes du 30 p.
            n, code, corps = await envoi(30, covered="1")
            solde, recs = await etat()
            print(f"\n--- puis 30 p. « pages couvertes seulement » -> {code} ; solde {solde} ; {recs}")
        finally:
            async with sessions() as db:
                await db.execute(delete(UsageRecord).where(UsageRecord.user_id == user.id))
                await db.execute(delete(User).where(User.id == user.id))
                await db.commit()
            await fx.asyncTearDown()
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
