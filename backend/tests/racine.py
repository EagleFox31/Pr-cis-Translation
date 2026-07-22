"""Met `backend/` sur le chemin d'import.

Chaque suite est un SCRIPT autonome (`python backend/tests/test_x.py`), pas un
module de paquet : Python ajoute alors `backend/tests/` au chemin, jamais
`backend/`. Sans cette ligne, `import app` ou `import engines` echoue.

Importer ce module suffit -- l'effet a lieu au chargement :

    import racine  # noqa: F401
"""
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
