"""Socle commun des modèles : la base déclarative et les deux fabriques de
valeurs par défaut.

Isolé de tout modèle concret pour qu'aucun d'eux n'ait à en importer un autre
seulement pour obtenir `Base`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Horodatage UTC conscient du fuseau.

    Toujours `timezone.utc`, jamais `datetime.now()` : une date naïve comparée à
    une date aware lève `TypeError`, et le plantage arrive des mois plus tard,
    dans la requête qui compare.
    """
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Identifiant primaire : UUID4 en hexadécimal sans tirets (32 caractères)."""
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Base déclarative de tous les modèles.

    `alembic/env.py` lit `Base.metadata` pour l'autogénération : un modèle
    absent de cet import n'apparaîtra dans AUCUNE migration.
    """
