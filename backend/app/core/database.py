"""
Engine SQLAlchemy async + session factory.

Utilisation :
    from backend.database import async_session
    async with async_session() as db:
        user = await db.get(User, user_id)
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# L'URL vient de `app.config`, seul endroit qui lit l'environnement. Ce module
# appelait `load_dotenv` sur `app/core/.env` — un chemin qui n'existe pas : le
# `.env` n'était vu que par l'effet de bord de l'import de `config`, et à défaut
# l'application se connectait SILENCIEUSEMENT à la base de démonstration.
from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dépendance FastAPI : injecte une session async."""
    async with async_session() as session:
        yield session
