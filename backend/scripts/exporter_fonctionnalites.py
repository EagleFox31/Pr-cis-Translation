"""Instantané du catalogue des fonctionnalités pour le prérendu SEO.

Le prérendu du site (frontend/scripts/prerender.mjs) n'importe pas le code
Python : il lit `frontend/seo/fonctionnalites.json`, écrit par ce script à
partir du catalogue français. Le fichier est versionné ; un test du catalogue
vérifie qu'il est à jour.

Exécution (après toute modification de app/content/nouveautes.py) :
  cd backend && venv/Scripts/python.exe scripts/exporter_fonctionnalites.py
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.content import nouveautes as cat  # noqa: E402

CIBLE = BACKEND.parent / "frontend" / "seo" / "fonctionnalites.json"
CHAMPS = ("id", "date", "type", "domaine", "titre", "resume", "detail")


def instantane() -> str:
    """Contenu exact du fichier : version, date de version, éléments en français."""
    donnees = {
        "version": cat.VERSION,
        "date_version": cat.DATE_VERSION,
        "elements": [{c: e[c] for c in CHAMPS} for e in cat.elements("fr")],
    }
    return json.dumps(donnees, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    CIBLE.write_text(instantane(), encoding="utf-8", newline="\n")
    print(f"{CIBLE} écrit ({len(cat.FONCTIONNALITES)} éléments).")
