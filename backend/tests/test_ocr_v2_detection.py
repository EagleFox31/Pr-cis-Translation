"""Lecteur PP-OCRv6 (OCR v2, étude §4 et §8).

Deux fonds du banc d'effacement lus en entier, boîtes proches de la vérité,
dictionnaire et délai. Sauté sans onnxruntime ni poids
(`backend/scripts/telecharger_ppocr.py`). Banc complet (48 images, japonais) :
`backend/tests/banc_detection.py`.

    backend/venv/Scripts/python.exe backend/tests/test_ocr_v2_detection.py
"""
import os
import tempfile
import time

import racine  # noqa: F401
import cv2
from app.services.ocr_v2.detect import LectureEchouee
from app.services.ocr_v2.ppocr import PPOCR, lire_dictionnaire
from banc_effacement import ETIQUETTES, generer


def lire_cas(lecteur, nom, dossier, delai=60):
    cas = generer(nom, 0, (0, 0))
    chemin = os.path.join(dossier, f"{nom}.png")
    cv2.imwrite(chemin, cas["image"])
    return cas, [m for m in lecteur.lire(chemin, delai) if m.conf >= 40]


def cas_dictionnaire():
    with tempfile.TemporaryDirectory() as dossier:
        chemin = os.path.join(dossier, "rec.yml")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("PostProcess:\n  name: CTCLabelDecode\n  character_dict:\n"
                    "  - a\n  - '1'\n  - ''''\n  - 安\n  - ' '\nPreProcess:\n  - x\n")
        assert lire_dictionnaire(chemin) == ["a", "1", "'", "安", " "], lire_dictionnaire(chemin)
    print("  dictionnaire : apostrophes et scalaires nus")


def cas_lecture(lecteur, dossier):
    for nom in ("uni", "brique"):
        cas, mots = lire_cas(lecteur, nom, dossier)
        attendus = sorted(w for t, *_ in ETIQUETTES[nom] for w in t.split())
        lus = sorted(m.texte for m in mots)
        assert lus == attendus, (nom, lus, attendus)
        # Chaque mot tombe dans la boîte de son étiquette (marge de 6 px).
        for m in mots:
            x, y, w, h = m.boite
            assert any(bx - 6 <= x and by - 6 <= y and x + w <= bx + bw + 6 and y + h <= by + bh + 6
                       for bx, by, bw, bh in cas["boites"]), (nom, m)
        print(f"  {nom} : {len(mots)} mots lus, boîtes dans les étiquettes")


def cas_delai(lecteur, dossier):
    try:
        lire_cas(lecteur, "papier_scan", dossier, delai=0)
    except LectureEchouee:
        print("  délai dépassé : LectureEchouee")
        return
    raise AssertionError("délai nul accepté")


def main():
    debut = time.monotonic()
    cas_dictionnaire()
    lecteur = PPOCR()
    if lecteur.manquant():
        print("SAUTÉ lecture PP-OCRv6 : onnxruntime ou poids absents (scripts/telecharger_ppocr.py)")
        return
    with tempfile.TemporaryDirectory(prefix="test-det-") as dossier:
        cas_lecture(lecteur, dossier)
        cas_delai(lecteur, dossier)
    print(f"OK détection ({time.monotonic() - debut:.1f} s)")


if __name__ == "__main__":
    main()
