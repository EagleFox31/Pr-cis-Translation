"""Forfait Gratuit avec pages achetees : l'OCR vise tout le document, pas la seule page d'essai."""
import asyncio
import io
import json
import uuid
from unittest.mock import patch

import fitz

import racine  # noqa: F401
from fastapi import UploadFile
from sqlalchemy import select
from app.api.translate import translate_endpoint
from app import config
from app.core.database import async_session, engine
from app.models import User
from app.services.ocr import OCRError


def scanned_pages(count):
    """PDF de `count` pages image seule : aucun caractere extractible."""
    with fitz.open() as source, fitz.open() as output:
        page = source.new_page(width=595, height=842)
        page.insert_text((60, 80), "Scanned page", fontsize=20)
        png = page.get_pixmap(dpi=72).tobytes("png")
        for _ in range(count):
            output.new_page(width=595, height=842).insert_image(fitz.Rect(0, 0, 595, 842), stream=png)
        return output.tobytes()


async def recognized_pages(page_credits):
    email = f"ocr-credits-{uuid.uuid4().hex}@example.com"
    seen = {}

    def fake_ocr(_data, scans):
        seen["scans"] = set(scans)
        raise OCRError("stop before translation")

    try:
        async with async_session() as db:
            user = User(email=email, name="OCR credits", plan="free", email_verified=True,
                        page_credits=page_credits)
            db.add(user)
            await db.commit()
            with patch("app.api.translate.prepare_scanned_pdf", side_effect=fake_ocr):
                response = await translate_endpoint(request=None,
                    file=UploadFile(filename="scan.pdf", file=io.BytesIO(scanned_pages(3))),
                    target_lang="en", format_options="{}", quality="fast", precise="", pages="",
                    debug="", covered_only="", x_api_key=config.FRONTEND_API_KEY,
                    current_user=user, db=db)
            body = json.loads(bytes(response.body))
            assert response.status_code == 422 and body["reason"] == "scanned_document", body
        return seen["scans"]
    finally:
        async with async_session() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user:
                await db.delete(user)
                await db.commit()


async def trial_offer_on_scan():
    """Essai sur un scan de 3 pages : la page 1 reconnue, le 402 compte tout le document."""
    email = f"ocr-trial-{uuid.uuid4().hex}@example.com"

    def fake_ocr(data, scans):
        with fitz.open(stream=data, filetype="pdf") as doc:
            for number in scans:
                doc[number - 1].insert_text((60, 120), "Recognized text", fontsize=12)
            return doc.tobytes(), len(scans)

    try:
        async with async_session() as db:
            user = User(email=email, name="OCR trial", plan="free", email_verified=True, page_credits=0)
            db.add(user)
            await db.commit()
            with patch("app.api.translate.prepare_scanned_pdf", side_effect=fake_ocr):
                response = await translate_endpoint(request=None,
                    file=UploadFile(filename="scan.pdf", file=io.BytesIO(scanned_pages(3))),
                    target_lang="en", format_options="{}", quality="fast", precise="", pages="",
                    debug="", covered_only="", x_api_key=config.FRONTEND_API_KEY,
                    current_user=user, db=db)
            return response.status_code, json.loads(bytes(response.body))
    finally:
        async with async_session() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user:
                await db.delete(user)
                await db.commit()


async def main():
    try:
        status, body = await trial_offer_on_scan()
        assert status == 402 and body.get("reason") == "need_credits" and body.get("pages_needed") == 3, (status, body)
        print("PASS: trial on a scan still offers to buy the missing pages")
        assert await recognized_pages(0) == {1}, "Free trial must only recognize its single page"
        print("PASS: free trial without purchased pages recognizes one page")
        assert await recognized_pages(5) == {1, 2, 3}, "Purchased pages must open the whole document"
        print("PASS: purchased pages make OCR cover the whole document")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
