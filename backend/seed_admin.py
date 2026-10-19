r"""Amorcage du compte administrateur : le cree, ou le promeut s'il existe.

Idempotent : lance a chaque demarrage du conteneur (docker-entrypoint.sh),
apres les migrations. Une base neuve en production a donc son admin des le
premier demarrage, sans console ni requete SQL a la main.

Les adresses viennent de ADMIN_EMAIL, separees par des virgules
(defaut : mbowouibrah@gmail.com). Chaque compte n'a
pas de mot de passe : il se connecte par code envoye par e-mail, ou par Google.

A la main :
    backend\venv\Scripts\python.exe backend\seed_admin.py
    docker compose exec backend python seed_admin.py

Sans accents ni emoji dans les sorties : la console Windows est en cp1252, et
un caractere hors de cette page fait planter le script APRES que la base a ete
modifiee -- une erreur qui ment alors sur ce qui s'est reellement passe.
"""
import os
import asyncio

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from sqlalchemy import func, select
from app.models import User
from app.core.database import async_session as _asm, engine

DEFAULT_ADMIN_EMAIL = "mbowouibrah@gmail.com"
ADMIN_NAME = "Ibrahim Mbowou"


def admin_name(email: str) -> str:
    """Un nom propre a l'adresse ; jamais l'identite d'un autre compte."""
    return email.partition("@")[0]


def admin_emails() -> list[str]:
    """Normalise la liste et ignore les entrees vides et les doublons."""
    value = os.getenv("ADMIN_EMAIL") or DEFAULT_ADMIN_EMAIL
    emails = list(dict.fromkeys(part.strip().lower() for part in value.split(",")
                                if part.strip()))
    if not emails:
        raise ValueError("ADMIN_EMAIL doit contenir au moins une adresse.")
    return emails


def admin_email() -> str:
    """Compatibilite avec les appelants qui demandent un seul compte."""
    return admin_emails()[0]


async def ensure_admin(email: str | None = None) -> User:
    email = (email or admin_email()).strip().lower()
    async with _asm() as db:
        user = (await db.execute(
            select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
        created = user is None
        if created:
            user = User(email=email, name=admin_name(email))
            db.add(user)
        user.plan = "admin"
        user.email_verified = True
        user.storage_limit = 0  # 0 = illimite
        # Plan attribue, pas achete : sans echeance.
        user.plan_expires_at = None
        user.plan_started_at = None
        # Repare uniquement le nom historique attribue par erreur par ce script.
        # Un nom personnalise reste intact aux redemarrages suivants.
        if not user.name or (user.name == ADMIN_NAME and email != DEFAULT_ADMIN_EMAIL
                             and not user.google_id):
            user.name = admin_name(email)
        await db.commit()
        await db.refresh(user)
    print(f"OK  Compte admin {'cree' if created else 'a jour'} : {user.email}")
    return user


async def main() -> None:
    try:
        for email in admin_emails():
            await ensure_admin(email)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
