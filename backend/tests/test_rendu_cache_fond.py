"""La construction du rendu en arrière-plan trouve bien ses fonctions de rendu."""
import json
import os
import tempfile
import threading
import time

import racine  # noqa: F401
from app.api import documents
from app.services import render_cache


def main():
    vrai = documents.render_translation_bytes
    appels = []
    documents.render_translation_bytes = lambda *a, **k: appels.append(a) or b"%PDF-1.4 rendu"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            trad = os.path.join(tmp, "pages.json")
            with open(trad, "w", encoding="utf-8") as f:
                json.dump({"pages": []}, f)
            render_cache.ensure_background_build(os.path.join(tmp, "o.pdf"), trad, "pdf", "en")
            fin = time.monotonic() + 10
            while time.monotonic() < fin and any(
                    t.name.startswith("render-cache-") for t in threading.enumerate()):
                time.sleep(0.05)
            assert appels, "Le rendu d'arrière-plan doit appeler render_translation_bytes"
            assert render_cache.cache_valid(trad), "Le rendu complet doit être mis en cache"
    finally:
        documents.render_translation_bytes = vrai
    print("PASS: rendu d'arrière-plan construit et mis en cache")


if __name__ == "__main__":
    main()
