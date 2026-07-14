"""
Engine SQLAlchemy async + session factory.

Utilisation :
    from backend.database import async_session
    async with async_session() as db:
        user = await db.get(User, user_id)
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/precis")

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dépendance FastAPI : injecte une session async."""
    async with async_session() as session:
        yield session
