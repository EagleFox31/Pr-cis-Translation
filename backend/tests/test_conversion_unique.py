"""Aperçu : un même document demandé plusieurs fois en même temps n'est
converti qu'UNE fois. Les demandes suivantes attendent la première et
repartent avec son résultat.

La conversion LibreOffice est remplacée par une fonction lente qui compte
ses appels ; le cache vit dans un dossier temporaire.

Exécution :  cd backend && venv/Scripts/python.exe tests/test_conversion_unique.py
"""
from __future__ import annotations
import os
import shutil
import sys
import tempfile
import threading
import time

import racine  # noqa: F401  -- met backend/ sur le chemin

import engines.office as moteur                                # noqa: E402
import app.services.office as office                           # noqa: E402
import app.services.stockage as stockage                       # noqa: E402


def run() -> int:
    checks = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))
        print(f"  {'OK   ' if cond else 'ÉCHEC'} {nom}" + (f"  ({detail})" if detail and not cond else ""))

    appels = []

    def conversion_lente(data: bytes, ext: str) -> bytes:
        appels.append(data)
        time.sleep(0.3)
        return b"%PDF-" + data

    dossier = tempfile.mkdtemp(prefix="apercu_")
    anciens = (moteur.convert_to_pdf, office.PREVIEW_CACHE_DIR, stockage.limiter_apercus)
    moteur.convert_to_pdf = conversion_lente
    office.PREVIEW_CACHE_DIR = dossier
    stockage.limiter_apercus = lambda *a, **k: 0
    try:
        # 1) Trois demandes simultanées du même document
        res = []
        fils = [threading.Thread(target=lambda: res.append(office.convert_to_pdf_bytes(b"doc-A", "pptx")))
                for _ in range(3)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        ok("MÊME DOC  3 demandes simultanées -> 1 conversion", len(appels) == 1, f"{len(appels)} conversions")
        ok("MÊME DOC  les 3 reçoivent le même PDF", res == [b"%PDF-doc-A"] * 3, str(res))

        # 2) Documents différents : chacun sa conversion, en parallèle possible
        appels.clear()
        fils = [threading.Thread(target=office.convert_to_pdf_bytes, args=(f"doc-{i}".encode(), "docx"))
                for i in range(3)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        ok("DOCS DIFFÉRENTS  une conversion chacun", len(appels) == 3, f"{len(appels)} conversions")

        # 3) Déjà en cache : aucune conversion
        appels.clear()
        office.convert_to_pdf_bytes(b"doc-A", "pptx")
        ok("CACHE  document déjà converti -> 0 conversion", not appels)

        # 4) PDF : rendu tel quel, sans conversion ni cache
        ok("PDF  rendu tel quel", office.convert_to_pdf_bytes(b"%PDF-x", "pdf") == b"%PDF-x" and not appels)

        # 5) Pas de fichier temporaire oublié, pas de verrou qui traîne
        restes = [n for n in os.listdir(dossier) if n.endswith(".tmp")]
        ok("CACHE  aucun fichier .tmp laissé", not restes, str(restes))
        ok("VERROUS  tous libérés", not office._verrous, str(office._verrous))
    finally:
        moteur.convert_to_pdf, office.PREVIEW_CACHE_DIR, stockage.limiter_apercus = anciens
        shutil.rmtree(dossier, ignore_errors=True)

    bons = sum(1 for _, c, _ in checks if c)
    print(f"{bons}/{len(checks)}")
    return 0 if bons == len(checks) else 1


if __name__ == "__main__":
    sys.exit(run())
