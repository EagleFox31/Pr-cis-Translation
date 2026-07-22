"""Aperçu des objets Excel incorporés — ne rien perdre, ne rien déformer.

LE DÉFAUT. Un classeur incorporé porte couramment un tableau ET un graphique
posés côte à côte. LibreOffice imprime cette feuille sur du A4 : trop étroit, il
PAGINE — tableau page 1, graphique page 2. On ne rendait que la première page.

Résultat mesuré sur une diapositive réelle : le graphique disparaissait, et
l'image restante — bien plus étroite que le cadre — s'y affichait ÉTIRÉE sur
toute la largeur. Deux défauts d'un seul geste, l'un de CONTENU, l'autre de
FORME.

Ce que ce fichier verrouille :
  1. `_forcer_fit_to_page` pose bien le réglage qui tient la feuille sur une
     page, sans casser le classeur ni en perdre une partie ;
  2. `_crop_xlsx_pdf_to_png` rend TOUTES les pages (l'ancienne version en jetait
     — c'est là que le graphique se perdait) ;
  3. l'image produite prend les proportions du CADRE d'affichage, par ajout de
     blanc et JAMAIS par rognage : PowerPoint étire l'image sur le cadre, une
     image mal proportionnée y apparaît déformée.

Tout est SYNTHÉTIQUE : un PDF fabriqué à la volée, un classeur minimal fabriqué
à la volée. Aucun document de test, aucun LibreOffice, aucun réseau.

Exécution :  backend/venv/Scripts/python.exe backend/test_ole_apercu.py
"""
from __future__ import annotations
import io
import os
import sys
import tempfile
import zipfile

import racine  # noqa: F401  -- met backend/ sur le chemin

import fitz                                               # noqa: E402
from lxml import etree                                    # noqa: E402
from PIL import Image                                     # noqa: E402

from engines.pptx.engine import PPTXTranslatorEngine, NAMESPACES  # noqa: E402

S = NAMESPACES['s']


def _pdf_deux_pages(path: str) -> None:
    """Un PDF de deux pages, chacune avec une marque à un endroit différent.

    C'est la forme exacte que LibreOffice donne à un classeur paginé : le
    tableau sur une page, le graphique sur la suivante.
    """
    doc = fitz.open()
    p1 = doc.new_page(width=595, height=842)
    p1.draw_rect(fitz.Rect(50, 50, 300, 150), color=(0, 0, 0), fill=(0, 0, 0))
    p2 = doc.new_page(width=595, height=842)
    p2.draw_circle(fitz.Point(150, 400), 60, color=(0, 0, 0), fill=(0, 0, 0))
    doc.save(path)
    doc.close()


def _xlsx_minimal(path: str, avec_pagesetup: bool) -> None:
    """Un classeur réduit à ce que la fonction touche, plus des parts témoins
    dont on vérifie qu'elles SURVIVENT à la copie."""
    feuille = ('<worksheet xmlns="%s"><sheetData/>%s</worksheet>'
               % (S, '<pageSetup orientation="portrait"/>'
                  if avec_pagesetup else ''))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/worksheets/sheet1.xml", feuille)
        z.writestr("xl/charts/chart1.xml", "<chart/>")     # témoin
        z.writestr("xl/sharedStrings.xml", "<sst/>")       # témoin


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def ok(nom, cond, detail=""):
        checks.append((nom, bool(cond), detail))

    eng = PPTXTranslatorEngine()

    # ── 1. Le réglage « une seule page » ─────────────────────────────────
    for avec in (False, True):
        etiquette = "avec pageSetup" if avec else "sans pageSetup"
        brut = ('<worksheet xmlns="%s"><sheetData/>%s</worksheet>'
                % (S, '<pageSetup orientation="portrait"/>' if avec else ''))
        sortie = eng._forcer_fit_to_page(brut.encode(), S)
        root = etree.fromstring(sortie)
        pu = root.find("{%s}sheetPr/{%s}pageSetUpPr" % (S, S))
        ps = root.find("{%s}pageSetup" % S)
        ok(f"FIT ({etiquette})  fitToPage est posé",
           pu is not None and pu.get("fitToPage") == "1")
        ok(f"FIT ({etiquette})  la feuille tient en largeur ET en hauteur",
           ps is not None and ps.get("fitToWidth") == "1"
           and ps.get("fitToHeight") == "1")
        # L'ORDRE compte dans le schéma : sheetPr en tête, pageSetup à la fin.
        enfants = [etree.QName(e).localname for e in root]
        ok(f"FIT ({etiquette})  sheetPr est le premier élément",
           enfants and enfants[0] == "sheetPr", str(enfants))
        ok(f"FIT ({etiquette})  pageSetup est le dernier",
           enfants and enfants[-1] == "pageSetup", str(enfants))
        ok(f"FIT ({etiquette})  un seul pageSetup",
           enfants.count("pageSetup") == 1, str(enfants))

    # ── 2. La copie de rendu ne perd aucune part ─────────────────────────
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "src.xlsx")
        dst = os.path.join(td, "dst.xlsx")
        _xlsx_minimal(src, avec_pagesetup=False)
        ok("COPIE  la copie ajustée est produite",
           eng._xlsx_ajuste_une_page(src, dst) and os.path.isfile(dst))
        with zipfile.ZipFile(src) as a, zipfile.ZipFile(dst) as b:
            ok("COPIE  toutes les parts sont conservées",
               set(a.namelist()) == set(b.namelist()),
               f"{set(a.namelist()) ^ set(b.namelist())}")
            ok("COPIE  le graphique du classeur survit",
               b.read("xl/charts/chart1.xml") == a.read("xl/charts/chart1.xml"))
            ok("COPIE  la feuille porte désormais fitToPage",
               b"fitToPage" in b.read("xl/worksheets/sheet1.xml"))
        # L'ORIGINAL n'est pas touché : c'est le classeur qu'on LIVRE.
        with zipfile.ZipFile(src) as a:
            ok("COPIE  le classeur d'origine reste intact",
               b"fitToPage" not in a.read("xl/worksheets/sheet1.xml"))

    # ── 3. Aucune page n'est jetée ───────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        pdf = os.path.join(td, "deux.pdf")
        _pdf_deux_pages(pdf)
        png = eng._crop_xlsx_pdf_to_png(pdf)
        ok("PAGES  une image est produite", png is not None)
        if png:
            im = Image.open(io.BytesIO(png))
            # Les deux marques sont à des hauteurs différentes : si une seule
            # page avait été rendue, l'image serait bien plus courte. On compare
            # à la page seule pour ne pas dépendre d'une taille en dur.
            une_page = fitz.open()
            une_page.insert_pdf(fitz.open(pdf), from_page=0, to_page=0)
            solo = os.path.join(td, "une.pdf")
            une_page.save(solo)
            une_page.close()
            png1 = eng._crop_xlsx_pdf_to_png(solo)
            im1 = Image.open(io.BytesIO(png1))
            ok("PAGES  la 2e page n'est PAS jetée (image plus haute)",
               im.height > im1.height,
               f"deux pages={im.size} une page={im1.size}")

        # ── 4. Proportions du cadre : on complète, on ne rogne pas ───────
        for ratio in (2.33, 0.5):
            png = eng._crop_xlsx_pdf_to_png(pdf, ratio_cible=ratio)
            im = Image.open(io.BytesIO(png))
            obtenu = im.width / im.height
            ok(f"RATIO {ratio}  l'image prend les proportions du cadre",
               abs(obtenu - ratio) < 0.02, f"obtenu={obtenu:.3f}")

        brut = Image.open(io.BytesIO(eng._crop_xlsx_pdf_to_png(pdf)))
        cible = Image.open(io.BytesIO(
            eng._crop_xlsx_pdf_to_png(pdf, ratio_cible=2.33)))
        ok("RATIO  le complément AGRANDIT le cadre, ne rogne jamais",
           cible.width >= brut.width and cible.height >= brut.height,
           f"brut={brut.size} complete={cible.size}")

        # ── 5. Rien n'est peint là où la source ne peint rien ────────────
        # Un aperçu OLE remplace une image VECTORIELLE : ce qui est posé sous
        # le cadre dans la diapositive doit rester visible au travers. Un
        # aplat opaque masquait la flèche « Groupe 13 ».
        ok("FOND  l'image porte un canal alpha", brut.mode == "RGBA",
           f"mode={brut.mode}")
        px = brut.load()
        ok("FOND  un coin jamais peint est TOTALEMENT transparent",
           px[0, 0][3] == 0, f"coin={px[0, 0]}")
        # Le contenu, lui, reste plein : la transparence ne doit pas manger
        # le dessin. Le rectangle noir occupe le haut de la première page.
        import numpy as np
        a = np.asarray(brut.getchannel("A"))
        ok("FOND  le contenu peint reste opaque",
           int((a == 255).sum()) > 0.05 * a.size,
           f"opaques={int((a == 255).sum())}/{a.size}")
        # Entre les deux pages empilées, la marge de recadrage est du VIDE :
        # elle ne doit pas non plus être blanchie.
        ok("FOND  la majorité de la surface reste traversable",
           int((a == 0).sum()) > 0, f"alpha0={int((a == 0).sum())}")
        # Le complément au ratio est de la marge d'échelle, pas un fond.
        ac = np.asarray(cible.getchannel("A"))
        ok("FOND  le complément au ratio est transparent",
           cible.mode == "RGBA"
           and int((ac == 0).sum()) > int((a == 0).sum()),
           f"mode={cible.mode} avant={int((a==0).sum())} "
           f"apres={int((ac==0).sum())}")

    print()
    n_ok = sum(1 for _, c, _ in checks if c)
    for nom, cond, detail in checks:
        etat = "  OK  " if cond else " FAIL "
        ligne = f"{etat}  {nom}"
        if not cond and detail:
            ligne += f"   [{detail}]"
        print(ligne)
    print(f"\n{n_ok}/{len(checks)}")
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
