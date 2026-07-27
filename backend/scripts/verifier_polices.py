"""Contrôle des polices de repli. Sort en erreur s'il en manque une.

POURQUOI CE SCRIPT EXISTE
-------------------------
`_load_matched_font()` (engines/pdf/engine.py) retombe SANS UN MOT sur la
base-14 — Helvetica — quand le fichier attendu est absent. C'est le bon
comportement à l'exécution : mieux vaut un PDF en Helvetica qu'une exception au
milieu d'une traduction payée. Mais c'est un désastre silencieux à la
construction : le service tourne, rend des documents, et perd la fidélité
typographique qui est son objet même, sans qu'aucune erreur ne le signale.

Ce contrôle transforme donc un défaut invisible en échec de BUILD. Il est appelé
depuis le Dockerfile : une image qui n'a pas ses polices n'existe pas.

Il ne vérifie pas que les fichiers sont BEAUX — seulement qu'ils sont là,
lisibles par le moteur de rendu, et non vides. (Une police assortie a déjà été
livrée corrompue une fois : PT Serif. `fitz.Font()` refuse un fichier illisible,
ce qui attrape ce cas-là aussi.)

    python backend/scripts/verifier_polices.py
"""
from __future__ import annotations

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

FONTS_DIR = os.path.join(_BACKEND, "fonts")

# Ce que le moteur peut réclamer. Les familles viennent de `_matched_family()`,
# les variantes de `_WEIGHT_VARIANTS` : toute famille citée là-bas doit au
# minimum offrir Regular et Bold, sans quoi la classe de graisse correspondante
# n'a aucun fichier à charger.
#
# Les variantes OPTIONNELLES (SemiBold, Medium, italiques) ont un repli explicite
# dans le moteur — leur absence est une perte de finesse, pas une panne. Elles
# sont donc signalées, sans faire échouer.
REQUISES = {
    "ptserif":      ("Regular", "Bold"),
    "merriweather": ("Regular", "Bold"),
    "montserrat":   ("Regular", "Bold"),
    "opensans":     ("Regular", "Bold"),
    "roboto":       ("Regular", "Bold"),
    "oswald":       ("Regular", "Bold"),
}
SOUHAITEES = {
    "ptserif":      ("Italic", "BoldItalic"),
    "merriweather": ("Italic", "BoldItalic"),
    "montserrat":   ("Italic", "BoldItalic", "SemiBold", "SemiBoldItalic"),
    "opensans":     ("Italic", "BoldItalic", "SemiBold", "SemiBoldItalic"),
    "roboto":       ("Italic", "BoldItalic", "Medium"),
    "oswald":       ("SemiBold",),
}


def main() -> int:
    try:
        import fitz  # PyMuPDF — le moteur de rendu lui-même
    except ImportError:
        print("ERREUR : PyMuPDF absent, contrôle impossible.")
        return 1

    manquantes: list[str] = []
    illisibles: list[str] = []
    absentes_souhaitees: list[str] = []

    for famille, variantes in REQUISES.items():
        for v in variantes:
            nom = f"{famille}-{v}.ttf"
            chemin = os.path.join(FONTS_DIR, nom)
            if not os.path.exists(chemin) or os.path.getsize(chemin) == 0:
                manquantes.append(nom)
                continue
            # Le moteur charge la police EXACTEMENT ainsi. Un fichier tronqué ou
            # corrompu passe l'existence et échoue ici — c'est déjà arrivé.
            try:
                fitz.Font(fontfile=chemin)
            except Exception as exc:
                illisibles.append(f"{nom} ({type(exc).__name__})")

    for famille, variantes in SOUHAITEES.items():
        for v in variantes:
            nom = f"{famille}-{v}.ttf"
            if not os.path.exists(os.path.join(FONTS_DIR, nom)):
                absentes_souhaitees.append(nom)

    total = len([f for f in os.listdir(FONTS_DIR)
                 if f.lower().endswith(".ttf")]) if os.path.isdir(FONTS_DIR) else 0
    print(f"Polices de repli : {total} fichier(s) dans {FONTS_DIR}")

    if absentes_souhaitees:
        print("  variantes fines absentes (repli prevu, sans gravite) : "
              + ", ".join(absentes_souhaitees))

    if manquantes or illisibles:
        if manquantes:
            print("  MANQUANTES : " + ", ".join(manquantes))
        if illisibles:
            print("  ILLISIBLES : " + ", ".join(illisibles))
        print("\nEchec : sans ces fichiers, le moteur retombe SILENCIEUSEMENT "
              "sur Helvetica et la fidelite typographique est perdue.")
        return 1

    print("OK - toutes les familles de repli sont completes et lisibles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
