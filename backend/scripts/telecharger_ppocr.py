"""Télécharge les poids PP-OCRv6 small (ONNX) dans `backend/models/ppocr`.

Les poids ne sont pas versionnés (30 Mo). Révision Hugging Face figée et
empreinte SHA-256 vérifiée : un fichier différent de celui qui a été mesuré
sur le banc est refusé. Licence des poids : Apache-2.0 (fiches officielles
PaddlePaddle).

Bloquant dans l'image Docker : sans ces fichiers, la lecture des images de
l'extension serait indisponible sans que rien ne le signale à la construction.

    python backend/scripts/telecharger_ppocr.py [--dossier CHEMIN]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER = os.path.join(_BACKEND, "models", "ppocr")
BASE = "https://huggingface.co/PaddlePaddle/{depot}/resolve/{rev}/{nom}"

# (fichier local, dépôt, révision, fichier distant, SHA-256)
FICHIERS = (
    ("det.onnx", "PP-OCRv6_small_det_onnx", "28fe5895c24fd108c19eb3e8479f4ab385fbfc62", "inference.onnx",
     "d73e0058b7a8086bbd57f3d10b8bcd4ff95363f67e06e2762b5e814fe9c9410e"),
    ("rec.onnx", "PP-OCRv6_small_rec_onnx", "b8f84f0b80c529de40b4fbb3544b84fa7233a513", "inference.onnx",
     "5435fd747c9e0efe15a96d0b378d5bd157e9492ed8fd80edf08f30d02fa24634"),
    ("rec.yml", "PP-OCRv6_small_rec_onnx", "b8f84f0b80c529de40b4fbb3544b84fa7233a513", "inference.yml",
     "ab078671bb49f06228eadccd34f1bb501e157f7a047095ffb943ba81512c77d1"),
)


def _empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dossier", default=DOSSIER)
    dossier = parser.parse_args().dossier
    os.makedirs(dossier, exist_ok=True)
    for local, depot, rev, nom, sha in FICHIERS:
        chemin = os.path.join(dossier, local)
        if os.path.isfile(chemin) and _empreinte(chemin) == sha:
            print(f"{local} : déjà présent")
            continue
        provisoire = chemin + ".part"
        for essai in range(3):
            try:
                # Délai par lecture : un serveur muet fait échouer le build au lieu de le bloquer.
                with (urllib.request.urlopen(BASE.format(depot=depot, rev=rev, nom=nom), timeout=60) as r,
                      open(provisoire, "wb") as f):
                    shutil.copyfileobj(r, f, 1 << 20)
                break
            except OSError as exc:
                if essai == 2:
                    if os.path.exists(provisoire):
                        os.remove(provisoire)
                    sys.exit(f"{local} : téléchargement impossible ({exc})")
        if _empreinte(provisoire) != sha:
            os.remove(provisoire)
            sys.exit(f"{local} : empreinte SHA-256 inattendue, fichier refusé")
        os.replace(provisoire, chemin)
        print(f"{local} : téléchargé")


if __name__ == "__main__":
    main()
