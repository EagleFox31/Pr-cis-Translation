"""Forfait Gratuit avec pages achetees : l'OCR vise tout le document, pas la seule page d'essai."""
import asyncio
import io
import json
import uuid
import os
import tempfile
from unittest.mock import patch

import fitz

import racine  # noqa: F401
from fastapi import Response, UploadFile
from sqlalchemy import select
from app.api.translate import translate_endpoint
from app import config
from app.core.database import async_session, engine
from app.models import Document, User
from app.services.jobs import jobs


def scanned_pages(count):
    """PDF de `count` pages image seule : aucun caractere extractible."""
    with fitz.open() as source, fitz.open() as output:
        page = source.new_page(width=595, height=842)
        page.insert_text((60, 80), "Scanned page", fontsize=20)
        png = page.get_pixmap(dpi=72).tobytes("png")
        for _ in range(count):
            output.new_page(width=595, height=842).insert_image(fitz.Rect(0, 0, 595, 842), stream=png)
        return output.tobytes()


async def _nettoyer(email):
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user:
            for doc in (await db.execute(select(Document).where(Document.user_id == user.id))).scalars():
                await db.delete(doc)
            await db.delete(user)
            await db.commit()


async def _envoyer(user, db, dossier, covered_only):
    def chemins(digest, langue):
        return os.path.join(dossier, digest), os.path.join(dossier, digest, langue)

    soumis = []
    with patch("app.api.translate.Tesseract.manquant", return_value=None), \
            patch("app.api.translate.build_job_paths", side_effect=chemins), \
            patch("app.api.translate.scheduler_scans.submit",
                  side_effect=lambda *args: soumis.append(args)):
        response = await translate_endpoint(request=racine.requete_test(), response=Response(),
            file=UploadFile(filename="scan.pdf", file=io.BytesIO(scanned_pages(7))),
            target_lang="en", format_options="{}", quality="fast", precise="", pages="",
            debug="", covered_only=covered_only, x_api_key=config.FRONTEND_API_KEY,
            current_user=user, db=db)
    return response, soumis


async def recognized_pages(page_credits):
    """Pages de scan visees par le travail lance (couvert seulement)."""
    email = f"ocr-credits-{uuid.uuid4().hex}@example.com"
    try:
        with tempfile.TemporaryDirectory() as dossier:
            async with async_session() as db:
                user = User(email=email, name="OCR credits", plan="free", email_verified=True,
                            page_credits=page_credits, created_at=racine.compte_ancien())
                db.add(user)
                await db.commit()
                response, soumis = await _envoyer(user, db, dossier, "1")
                body = json.loads(bytes(response.body))
                assert response.status_code == 200 and len(soumis) == 1, body
                job_id, _priorite, _cible, job_args = soumis[0]
                jobs.forget(job_id)
                visees = job_args[8] or set(range(1, 8))
                assert body["ocr_pages"] == len(visees), body
                return set(visees), job_args[12]
    finally:
        await _nettoyer(email)


async def trial_offer_on_scan():
    """Essai sur un scan de 7 pages : le 402 compte tout le document, rien n'est lance."""
    email = f"ocr-trial-{uuid.uuid4().hex}@example.com"
    try:
        with tempfile.TemporaryDirectory() as dossier:
            async with async_session() as db:
                user = User(email=email, name="OCR trial", plan="free", email_verified=True, page_credits=0,
                            created_at=racine.compte_ancien())
                db.add(user)
                await db.commit()
                response, soumis = await _envoyer(user, db, dossier, "")
                assert soumis == []
                return response.status_code, json.loads(bytes(response.body))
    finally:
        await _nettoyer(email)


async def main():
    try:
        status, body = await trial_offer_on_scan()
        assert status == 402 and body.get("reason") == "need_credits" and body.get("pages_needed") == 7, (status, body)
        print("PASS: trial on a scan still offers to buy the missing pages")
        # Solde partiel sur un scan : toutes les pages sont parcourues dans
        # l'ordre, la traduction s'arrête après 5 pages lues (budget).
        assert await recognized_pages(0) == ({1, 2, 3, 4, 5, 6, 7}, 5), "Free trial must stop after five read pages"
        print("PASS: free trial without purchased pages translates at most five read pages")
        assert await recognized_pages(5) == ({1, 2, 3, 4, 5, 6, 7}, None), "Purchased pages must open the whole document"
        print("PASS: purchased pages make OCR cover the whole document")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
