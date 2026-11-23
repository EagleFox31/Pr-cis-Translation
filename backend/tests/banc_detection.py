"""Banc de détection : part des mots retrouvés par le lecteur (étude §8).

Reprend les 12 fonds du banc d'effacement, aux 4 positions, et y ajoute des
lignes japonaises (erreur par caractère). Seuils : 100 % des mots sur fond
propre ; fond chargé au-dessus de Tesseract (0 %) ; japonais ≤ 10 %
d'erreur par caractère. Les poids doivent être présents
(`scripts/telecharger_ppocr.py`).

    cd backend && PYTHONUTF8=1 venv/Scripts/python.exe tests/banc_detection.py [--tesseract]
"""
import os
import sys
import tempfile
import time

import racine  # noqa: F401
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr_v2.detect import Tesseract
from app.services.ocr_v2.ppocr import PPOCR
from banc_effacement import ETIQUETTES, FONDS, NOMS, VARIANTES, H, W, generer

PROPRES = ("uni", "sombre", "degrade_lin", "papier_scan", "tableau")
CHARGES = ("brique", "herbe", "photo", "quadrillage", "degrade_radial", "schema_fleche", "schema_boite")
CER_MAX_JA = 0.10
CONF_MIN = 40  # comme `ocr.py` : un mot moins sûr n'est pas remplacé

POLICES_JA = (os.environ.get("BANC_POLICE_JA", ""),
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "C:/Windows/Fonts/YuGothM.ttc")
# (fond, texte, x, y, taille, couleur BGR)
JAPONAIS = [
    ("uni", "安全確認を行ってください", 30, 60, 26, (40, 40, 40)),
    ("degrade_lin", "電源を切ってから点検する", 30, 200, 26, (255, 255, 255)),
    ("photo", "圧力計の値を記録", 60, 120, 30, (255, 255, 255)),
    ("brique", "非常口", 150, 90, 40, (255, 255, 255)),
    ("quadrillage", "温度センサー", 80, 200, 28, (150, 40, 20)),
]


def levenshtein(a, b):
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cour = [i]
        for j, cb in enumerate(b, 1):
            cour.append(min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (ca != cb)))
        prec = cour
    return prec[-1]


def lire(lecteur, image, dossier):
    chemin = os.path.join(dossier, "cas.png")
    cv2.imwrite(chemin, image)
    debut = time.monotonic()
    mots = [m for m in lecteur.lire(chemin, 60) if m.conf >= CONF_MIN]
    return mots, time.monotonic() - debut


def mesurer_mots(lecteur, dossier):
    """{cas: (trouvés, attendus, inventés, durée)} sur les 4 positions."""
    res = {}
    for nom in NOMS:
        attendus = [w for t, *_ in ETIQUETTES[nom] for w in t.split()]
        trouves = inventes = 0
        duree = 0.0
        for graine, dec in enumerate(VARIANTES):
            mots, dt = lire(lecteur, generer(nom, graine, dec)["image"], dossier)
            lus = [m.texte for m in mots]
            for w in attendus:
                if w in lus:
                    lus.remove(w)
                    trouves += 1
            inventes += len(lus)
            duree += dt
        res[nom] = (trouves, 4 * len(attendus), inventes, duree / 4)
    return res


def mesurer_japonais(lecteur, dossier, police):
    res = []
    for fond_nom, texte, x, y, taille, col in JAPONAIS:
        fond = np.ascontiguousarray(FONDS[fond_nom](np.random.default_rng(0)).astype(np.float32))
        c = Image.new("L", (W, H), 0)
        ImageDraw.Draw(c).text((x, y), texte, font=ImageFont.truetype(police, taille), fill=255)
        a = np.asarray(c, np.float32)[..., None] / 255.0
        image = np.clip(fond * (1 - a) + np.array(col, np.float32) * a, 0, 255).astype(np.uint8)
        mots, dt = lire(lecteur, image, dossier)
        lu = "".join(m.texte for m in mots)
        res.append((fond_nom, texte, lu, levenshtein(texte, lu) / len(texte), dt))
    return res


def main():
    lecteurs = {"PP-OCRv6": PPOCR()}
    if "--tesseract" in sys.argv:
        lecteurs["Tesseract"] = Tesseract()
    echecs = []
    with tempfile.TemporaryDirectory(prefix="banc-det-") as dossier:
        for nom_l, lecteur in lecteurs.items():
            manque = lecteur.manquant()
            if manque:
                print(f"{nom_l} indisponible ({manque})")
                echecs.append(f"{nom_l} indisponible")
                continue
            debut = time.monotonic()
            res = mesurer_mots(lecteur, dossier)
            print(f"\n{nom_l}\n{'cas':<15}{'mots':>9}{'part':>7}{'inventés':>10}{'s/image':>9}")
            for nom, (t, n, inv, dt) in res.items():
                print(f"{nom:<15}{f'{t}/{n}':>9}{100 * t / n:6.0f} %{inv:>10}{dt:9.2f}")
            total = sum(r[0] for r in res.values()), sum(r[1] for r in res.values())
            charges = [res[n][0] / res[n][1] for n in CHARGES]
            print(f"total {total[0]}/{total[1]} ({100 * total[0] / total[1]:.0f} %), "
                  f"fond chargé {100 * np.mean(charges):.0f} %, {time.monotonic() - debut:.0f} s")
            if nom_l != "PP-OCRv6":
                continue
            for n in PROPRES:
                if res[n][0] < res[n][1]:
                    echecs.append(f"{n} : {res[n][0]}/{res[n][1]} mots sur fond propre")
            if np.mean(charges) == 0:
                echecs.append("aucun mot trouvé sur fond chargé")

            police = next((p for p in POLICES_JA if p and os.path.isfile(p)), None)
            if not police:
                print("japonais : aucune police japonaise trouvée (BANC_POLICE_JA), cas sautés")
                continue
            ja = mesurer_japonais(lecteur, dossier, police)
            print(f"\njaponais ({os.path.basename(police)})")
            for fond_nom, texte, lu, cer, dt in ja:
                print(f"{fond_nom:<13}{100 * cer:5.0f} %  {dt:5.2f} s  {texte} → {lu}")
            cer = sum(levenshtein(t, l) for _, t, l, _, _ in ja) / sum(len(t) for _, t, *_ in ja)
            print(f"erreur par caractère {100 * cer:.1f} %")
            if cer > CER_MAX_JA:
                echecs.append(f"japonais {100 * cer:.1f} % > {100 * CER_MAX_JA:.0f} %")
    print("ÉCHEC : " + " ; ".join(echecs) if echecs else "OK banc de détection")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
