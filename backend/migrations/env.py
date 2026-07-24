"""Alembic env — async, lit les modèles depuis backend.models."""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Ajouter backend/ au path pour que `from app.models import Base` fonctionne.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/precis",
)
# configparser interprète les `%` → on les échappe pour éviter ValueError
try:
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
except ValueError:
    pass  # déjà protégé, ou URL sans %

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(DATABASE_URL, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
