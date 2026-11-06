"""Remettre l'original d'une image traduite (étude images-documents, étape 6.8.4).

  • `marquer_originale` / `charger_table` / `etat_images` : une image remise à
    l'original sort de la table de rendu, mais ses octets traduits restent
    pour la rétablir ;
  • routes `GET|PATCH /api/documents/{id}/images` : propriétaire seul, copie
    propre au document au premier changement (la traduction partagée reste
    intacte), rendu en cache invalidé, bascule aller-retour.

    cd backend && PYTHONUTF8=1 venv/Scripts/python.exe tests/test_images_retirees.py
Requiert PostgreSQL de test (5433) pour les routes.
"""
from __future__ import annotations
import asyncio
import io
import os
import shutil
import tempfile
import unittest
import uuid

import racine  # noqa: F401

from PIL import Image

from app.services import images_document as module


def _png(couleur) -> bytes:
    sortie = io.BytesIO()
    Image.new("RGB", (60, 40), couleur).save(sortie, "PNG")
    return sortie.getvalue()


ROUGE, BLEU = _png((200, 0, 0)), _png((0, 0, 200))


class Retirees(unittest.TestCase):
    def setUp(self):
        self.racine = tempfile.mkdtemp(prefix="imgret_")
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.trad = os.path.join(self.racine, "translated_fr.json")
        module.ecrire_table(self.trad, {"a": ROUGE, "b": BLEU}, {})

    def test_retiree_hors_du_rendu_mais_gardee(self):
        self.assertTrue(module.marquer_originale(self.trad, "a", True))
        self.assertEqual(set(module.charger_table(self.trad)), {"b"})
        etat = {c: (r, o) for c, r, o in module.etat_images(self.trad)}
        self.assertEqual(etat["a"], (True, ROUGE))
        self.assertEqual(etat["b"], (False, BLEU))

    def test_retablie(self):
        module.marquer_originale(self.trad, "a", True)
        module.marquer_originale(self.trad, "a", True)          # idempotent
        self.assertTrue(module.marquer_originale(self.trad, "a", False))
        self.assertEqual(set(module.charger_table(self.trad)), {"a", "b"})

    def test_cle_inconnue_ou_sans_table(self):
        self.assertFalse(module.marquer_originale(self.trad, "zz", True))
        autre = os.path.join(self.racine, "translated_en.json")
        self.assertFalse(module.marquer_originale(autre, "a", True))
        self.assertEqual(module.etat_images(autre), [])


class Routes(unittest.TestCase):
    """Routes réelles sur la base de test ; fichiers dans le magasin."""

    def test_routes(self):
        asyncio.run(self._run())

    async def _run(self):
        from fastapi.testclient import TestClient
        from sqlalchemy.ext.asyncio import (create_async_engine, async_sessionmaker,
                                            AsyncSession)
        from sqlalchemy.pool import NullPool
        from app import config as cfg, create_app
        from app.api.documents import STORAGE_BASE
        from app.core.database import DATABASE_URL
        from app.core.security import create_access_token
        from app.models import User, Document
        from app.services import render_cache

        eng = create_async_engine(DATABASE_URL, poolclass=NullPool)
        session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        dossier = os.path.join(STORAGE_BASE, f"_test_imgret_{uuid.uuid4().hex[:8]}")
        os.makedirs(dossier)
        orig = os.path.join(dossier, "original.docx")
        open(orig, "wb").write(b"pas un vrai docx")     # vignettes originales absentes
        trad = os.path.join(dossier, "translated_fr.json")
        open(trad, "w", encoding="utf-8").write("{}")
        module.ecrire_table(trad, {"word/media/image1.png": ROUGE}, {})
        cache = render_cache.cache_path_for(trad)

        moi = User(email=f"imgret-{uuid.uuid4().hex[:10]}@example.com",
                   plan="starter", email_verified=True)
        autre = User(email=f"imgret-{uuid.uuid4().hex[:10]}@example.com",
                     plan="starter", email_verified=True)
        async with session() as db:
            db.add_all([moi, autre])
            await db.commit()
            docs = []
            for u in (moi, autre):     # même traduction partagée par deux comptes
                d = Document(user_id=u.id, original_name="r.docx", source_lang="auto",
                             target_lang="fr", original_path=orig, translated_path=trad,
                             size_bytes=1, status="done")
                db.add(d)
                await db.commit()
                docs.append(d.id)

        def h(u):
            return {"X-API-Key": cfg.FRONTEND_API_KEY,
                    "Authorization": f"Bearer {create_access_token(u.id, u.email)}"}

        cle = "word/media/image1.png"
        try:
            with TestClient(create_app()) as c:
                url = f"/api/documents/{docs[0]}/images"
                r = c.get(url, headers=h(moi))
                self.assertEqual(r.status_code, 200, r.text)
                img = r.json()["images"]
                self.assertEqual([(i["cle"], i["originale"]) for i in img], [(cle, False)])
                self.assertTrue(img[0]["vignette_traduite"].startswith("data:image/"))
                self.assertIsNone(img[0]["vignette_originale"])

                self.assertEqual(c.get(url, headers=h(autre)).status_code, 404)
                self.assertEqual(c.patch(url, json={"cle": cle, "originale": True},
                                       headers=h(autre)).status_code, 404)
                self.assertEqual(c.patch(url, json={"cle": "inconnue", "originale": True},
                                       headers=h(moi)).status_code, 404)

                open(cache, "wb").write(b"%PDF ancien rendu")
                r = c.patch(url, json={"cle": cle, "originale": True}, headers=h(moi))
                self.assertEqual(r.status_code, 200, r.text)

                async with session() as db:
                    mien = await db.get(Document, docs[0])
                    sien = await db.get(Document, docs[1])
                copie = mien.translated_path
                self.assertNotEqual(copie, trad)
                self.assertTrue(os.path.basename(copie).startswith("translated_fr"))
                self.assertEqual(sien.translated_path, trad)
                self.assertEqual(set(module.charger_table(trad)), {cle})      # intacte
                self.assertEqual(module.charger_table(copie), {})
                self.assertFalse(render_cache.cache_valid(copie))
                self.assertTrue(c.get(url, headers=h(moi)).json()["images"][0]["originale"])

                # Retour : même copie réutilisée, image traduite rétablie, et le
                # rendu en cache de la copie (plus récent qu'elle) écarté.
                cache_copie = render_cache.cache_path_for(copie)
                open(cache_copie, "wb").write(b"%PDF rendu de la copie")
                self.assertTrue(render_cache.cache_valid(copie))
                r = c.patch(url, json={"cle": cle, "originale": False}, headers=h(moi))
                self.assertEqual(r.status_code, 200, r.text)
                async with session() as db:
                    self.assertEqual((await db.get(Document, docs[0])).translated_path, copie)
                self.assertEqual(module.charger_table(copie), {cle: ROUGE})
                self.assertFalse(render_cache.cache_valid(copie))
        finally:
            async with session() as db:
                for u in (moi, autre):
                    obj = await db.get(User, u.id)
                    if obj:
                        await db.delete(obj)
                await db.commit()
            await eng.dispose()
            shutil.rmtree(dossier, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=1)
