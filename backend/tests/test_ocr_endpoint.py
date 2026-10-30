"""Parcours accepte : OCR reel avant inscription de la consommation et mise en file."""
import asyncio
import io
import json
import os
import shutil
import uuid
from unittest.mock import patch

import racine  # noqa: F401
from fastapi import Response, UploadFile
from sqlalchemy import select
from app.api.translate import translate_endpoint
from app import config
from app.core.database import async_session, engine
from app.models import User, Document, UsageRecord
from app.services.jobs import jobs
from test_ocr import scanned_pdf


async def main():
    email = f"ocr-{uuid.uuid4().hex}@example.com"
    data = scanned_pdf()
    job_id = None
    original_path = None
    try:
        async with async_session() as db:
            user = User(email=email, name="OCR test", plan="admin", email_verified=True)
            db.add(user)
            await db.commit()
            with patch("app.api.translate.scheduler.submit") as submit:
                response = await translate_endpoint(request=racine.requete_test(), response=Response(),
                    file=UploadFile(filename="scan.pdf", file=io.BytesIO(data)), target_lang="en",
                    format_options="{}", quality="fast", precise="", pages="1", debug="",
                    x_api_key=config.FRONTEND_API_KEY, current_user=user, db=db)
            body = json.loads(bytes(response.body))
            assert response.status_code == 200, body
            assert body["ocr_pages"] == 1 and body["ocr_review_required"] is True
            job_id = body["job_id"]
            submit.assert_called_once()
            args = submit.call_args.args[-1]
            assert args[1] == data, "Original bytes must stay intact"
            assert args[-1] is not None and args[-1] != data
            assert "_ocrv1" in args[6], "OCR translations need a distinct cache key"
            document = (await db.execute(select(Document).where(Document.user_id == user.id))).scalar_one()
            original_path = document.original_path
            assert document.page_count == 1
            records = (await db.execute(select(UsageRecord).where(UsageRecord.user_id == user.id))).scalars().all()
            assert len(records) == 1, "Only the recognized selected page may be recorded"
        print("PASS: scan accepted after real OCR; original retained; review notice; distinct cache; one selected page recorded")
    finally:
        if job_id:
            jobs.forget(job_id)
        async with async_session() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user:
                for doc in (await db.execute(select(Document).where(Document.user_id == user.id))).scalars().all():
                    await db.delete(doc)
                for record in (await db.execute(select(UsageRecord).where(UsageRecord.user_id == user.id))).scalars().all():
                    await db.delete(record)
                await db.delete(user)
                await db.commit()
        if original_path:
            shutil.rmtree(os.path.dirname(original_path), ignore_errors=True)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
