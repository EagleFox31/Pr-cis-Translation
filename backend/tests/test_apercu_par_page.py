"""Aperçu PPTX page par page, sans socle (docs/etude-apercu-par-page.md, lot 1).

Conversion simulée : `extraire` écrit la liste des pages demandées, `convertir`
en fait un PDF dont chaque page porte « page N ». On vérifie :
- une conversion par diapositive au plus (`par_conversion=1`) ;
- les pages rendues sont sur disque, les autres « en attente » (blanches) ;
- l'ordre et l'appariement ;
- les gardes (page hors document, rendu décalé) ;
- la reprise d'un dossier existant sans reconversion ;
- le balayage du magasin efface le dossier de pages d'un partiel.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz                                                     # noqa: E402

from app.services.progressive_preview import (ApercuParPage,    # noqa: E402
                                              taille_diapositive)

ECHECS: list[str] = []


def ok(cond: bool, nom: str, detail: str = "") -> None:
    print(("OK   " if cond else "ECHEC") + f" {nom}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        ECHECS.append(nom)


def _fabrique(appels: list[list[int]], decaler: bool = False):
    def extraire(chemin: str, pages: set[int]) -> None:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(sorted(pages), f)

    def convertir(octets: bytes) -> bytes:
        pages = json.loads(octets)
        appels.append(pages)
        doc = fitz.open()
        for n in pages + ([0] if decaler else []):
            p = doc.new_page(width=720, height=405)
            p.insert_text((50, 50), f"page {n}")
        return doc.tobytes()

    return extraire, convertir


def _textes(pdf: bytes) -> list[str]:
    with fitz.open(stream=pdf, filetype="pdf") as d:
        return [p.get_text().strip() for p in d]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        dossier = os.path.join(td, "partial_ab12cd34.pdf.pages")
        appels: list[list[int]] = []
        extraire, convertir = _fabrique(appels)
        a = ApercuParPage(extraire, convertir, dossier, total=5,
                          taille=(720, 405))

        pdf = a.assembler()
        ok(_textes(pdf) == [""] * 5, "partiel initial : 5 pages en attente")
        with fitz.open(stream=pdf, filetype="pdf") as d:
            ok(tuple(round(v) for v in d[0].rect[2:]) == (720, 405),
               "page en attente au format de la diapositive")
        ok(appels == [], "aucune conversion pour le partiel initial")

        pdf = a.greffer([4, 2])
        ok(appels == [[2], [4]], "une conversion par diapositive", str(appels))
        ok(_textes(pdf) == ["", "page 2", "", "page 4", ""],
           "pages rendues à leur place", str(_textes(pdf)))
        ok(a.liste_pages == [2, 4], "liste des pages prêtes")
        ok(sorted(os.listdir(dossier)) == ["2.pdf", "4.pdf"],
           "pages rangées sur disque", str(os.listdir(dossier)))

        try:
            a.greffer([6])
            ok(False, "page hors document refusée")
        except ValueError:
            ok(True, "page hors document refusée")

        appels2: list[list[int]] = []
        e2, c2 = _fabrique(appels2, decaler=True)
        b = ApercuParPage(e2, c2, dossier, total=5, taille=(720, 405))
        try:
            b.greffer([1])
            ok(False, "rendu décalé refusé")
        except ValueError:
            ok(True, "rendu décalé refusé")
        ok(not os.path.exists(os.path.join(dossier, "1.pdf")),
           "rien écrit pour un lot refusé")

        appels3: list[list[int]] = []
        e3, c3 = _fabrique(appels3)
        r = ApercuParPage(e3, c3, dossier, total=5, taille=(720, 405))
        manquent = r.reprendre([1, 2, 3, 4, 5])
        ok(manquent == [1, 3, 5] and r.liste_pages == [2, 4],
           "reprise : pages déjà rendues retrouvées", str(manquent))
        ok(_textes(r.assembler()) == ["", "page 2", "", "page 4", ""],
           "reprise : partiel sans reconversion")
        ok(appels3 == [], "reprise : aucune conversion")

        lot = ApercuParPage(e3, c3, os.path.join(td, "lot"), total=5,
                            taille=(720, 405), par_conversion=2)
        lot.greffer([1, 2, 3])
        ok(appels3 == [[1, 2], [3]], "par_conversion borne la taille du lot",
           str(appels3))

        # Format lu dans le PPTX ; repli 16:9 sur un fichier illisible.
        ok(taille_diapositive(os.path.join(td, "absent.pptx")) == (960.0, 540.0),
           "format par défaut")

    # Balayage du magasin : le dossier de pages d'un partiel est une sortie de job.
    from app.services import stockage
    with tempfile.TemporaryDirectory() as mag:
        racine_job = os.path.join(mag, "0123456789abcdef")
        langue = os.path.join(racine_job, "fr")
        pages = os.path.join(langue, "partial_q_ab12cd34.pdf.pages")
        os.makedirs(pages)
        original = os.path.join(racine_job, "original.pptx")
        open(original, "wb").close()
        open(os.path.join(pages, "1.pdf"), "wb").close()
        stockage.balayer_magasin({original}, "v0", magasin=mag)
        ok(not os.path.exists(pages), "balayage : dossier de pages effacé")
        ok(os.path.exists(original), "balayage : original gardé")

    print(f"\n{len(ECHECS)} échec(s)")
    return 1 if ECHECS else 0


if __name__ == "__main__":
    sys.exit(main())
