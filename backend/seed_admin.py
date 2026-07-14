"""Seed : promeut mbowouibrah@gmail.com en admin (compte existant ou création).

Usage unique :
    backend\venv\Scripts\python.exe backend\seed_admin.py
"""
import os, sys, asyncio

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from sqlalchemy import select
from models import User
from database import async_session as _asm, engine

ADMIN_EMAIL = "mbowouibrah@gmail.com"
ADMIN_NAME = "Ibrahim Mbowou"

async def main():
    async with _asm() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=ADMIN_EMAIL,
                name=ADMIN_NAME,
                email_verified=True,
                plan="admin",
                storage_limit=0,  # 0 = illimité (traité spécialement)
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"✅ Compte admin créé : {user.email}")
        else:
            user.plan = "admin"
            user.email_verified = True
            user.storage_limit = 0  # 0 = illimité
            user.name = user.name or ADMIN_NAME
            await db.commit()
            await db.refresh(user)
            print(f"✅ Compte promu admin : {user.email}")

        print(f"   Plan    : {user.plan}")
        print(f"   Stockage: {'Illimité' if user.storage_limit == 0 else f'{user.storage_limit / 1024 / 1024:.0f} Mo'}")
        print(f"   Vérifié : {user.email_verified}")

    await engine.dispose()

asyncio.run(main())
