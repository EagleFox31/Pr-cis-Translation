"""P15 — la colonne justifiée COURTE : mesurer avant de toucher à quoi que ce soit.

LE DÉFAUT, TEL QU'IL EST DOCUMENTÉ
----------------------------------
`_rejoin_justified` répare les colonnes justifiées étroites, où les blancs de
mots enflent au-delà du seuil de coupe et font arracher les mots à leur phrase.
Il ne le fait que sur une colonne AVÉRÉE, et une colonne s'avère par ses lignes
TÉMOINS : celles qui courent d'un bord à l'autre sans blanc assez large pour
être coupées. Il en faut `_JUST_MIN_LINES` (3).

Limite connue : une colonne de ≤5 lignes n'a souvent que 1 ou 2 lignes
intactes (≈55 % de lignes intactes observé) — donc pas de quorum, donc pas de
réparation.

CE QUE CE SCRIPT ÉTABLIT, ET DANS CET ORDRE
-------------------------------------------
1. Le défaut est-il REPRODUCTIBLE sur un document synthétique ? Sans cela on ne
   peut ni le mesurer ni prouver un correctif.
2. Combien de lignes intactes une colonne courte porte-t-elle RÉELLEMENT, en
   fonction de sa hauteur ? C'est ce chiffre qui dit si le quorum de 3 est
   atteignable, ou si le remède doit être ailleurs.
3. Que coûterait un quorum abaissé ? On le mesure au lieu de le supposer — la
   mémoire du projet dit que `_JUST_MIN_LINES=1` fait souder les 4 colonnes du
   journal par un titre pleine largeur, et que 2 == 3 sur 51 pages.

Aucun correctif ici. On mesure.

    python scripts/mesurer_colonne_courte.py
"""
from __future__ import annotations

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import fitz  # noqa: E402

from engines.pdf.engine import PDFObjectEngine  # noqa: E402

# Un texte quelconque, découpé en colonnes étroites justifiées. Le contenu n'a
# aucune importance : ce qui compte est la LARGEUR de la colonne, qui force les
# blancs de mots à enfler.
_MOTS = ("La circulation des véhicules lourds obéit à des règles strictes "
         "que tout conducteur doit connaître avant de prendre la route "
         "car la sécurité de chacun en dépend directement et sans réserve "
         "dans toutes les situations rencontrées au quotidien").split()


def _page_colonne(doc, n_lignes: int, largeur_col: float = 108.0,
                  corps: float = 9.0):
    """Une page portant UNE colonne justifiée de `n_lignes` lignes.

    Le texte est justifié À LA MAIN : on pose chaque mot à une abscisse
    calculée pour que la ligne touche EXACTEMENT les deux bords. C'est ce que
    fait un fondeur, et c'est ce qui crée le défaut — les blancs inter-mots
    deviennent plus larges que le seuil de coupe du moteur.
    """
    page = doc.new_page(width=595, height=842)
    x0, y = 72.0, 120.0
    police = fitz.Font("helv")
    i = 0
    for _ in range(n_lignes):
        # Remplir la ligne au plus près de la largeur cible.
        ligne, larg = [], 0.0
        while i < len(_MOTS):
            w = police.text_length(_MOTS[i], corps)
            esp = police.text_length(" ", corps) if ligne else 0.0
            if ligne and larg + esp + w > largeur_col:
                break
            ligne.append(_MOTS[i])
            larg += esp + w
            i += 1
        if not ligne:
            i = 0
            continue
        # Répartir le blanc restant entre les mots : c'est la justification.
        encre = sum(police.text_length(m, corps) for m in ligne)
        blanc = (largeur_col - encre) / max(1, len(ligne) - 1)
        x = x0
        for m in ligne:
            page.insert_text((x, y), m, fontsize=corps, fontname="helv")
            x += police.text_length(m, corps) + blanc
        y += corps * 1.6
    return page


def _diagnostic(doc, eng):
    """Ce que le moteur fait de la page.

    On passe par `extract_page_data` — l'API publique, celle qu'emprunte une
    vraie traduction — et non par les fonctions internes : c'est le seul moyen
    d'observer ce que le document subit RÉELLEMENT, garde-fous compris.
    """
    els = eng.extract_page_data(doc, 0, doc[0], embed_images=True)["elements"]
    return [e for e in els if e.get("type") in ("text_line", "paragraph")]


def run():
    eng = PDFObjectEngine()
    print("hauteur de colonne -> lignes rendues par le moteur")
    print("(une colonne SAINE rend autant de lignes qu'elle en compte ;")
    print(" une colonne ÉCLATÉE en rend DAVANTAGE — les fragments)\n")
    print(f"{'lignes posées':>14}{'lignes rendues':>16}{'éclatement':>13}")
    for n in (3, 4, 5, 6, 8, 12):
        doc = fitz.open()
        _page_colonne(doc, n)
        lignes = _diagnostic(doc, eng)
        doc.close()
        etat = "OK" if len(lignes) <= n else f"+{len(lignes) - n}"
        print(f"{n:>14}{len(lignes):>16}{etat:>13}")

    # Combien de lignes INTACTES (à fleur des deux bords) une colonne porte-t-elle ?
    print("\nlignes TÉMOINS disponibles (à fleur des DEUX bords) :")
    for n in (3, 4, 5, 6, 8, 12):
        doc = fitz.open()
        _page_colonne(doc, n)
        lignes = _diagnostic(doc, eng)
        boxes = []
        for ln in lignes:
            bb = ln.get("bbox")
            if bb:
                boxes.append((bb[0], bb[1], bb[2], bb[3],
                              ln.get("size") or 9.0))
        cols = eng._justified_columns(boxes)
        doc.close()
        print(f"  {n:>2} lignes -> {len(cols)} colonne(s) avérée(s)"
              f"   {'RÉPARABLE' if cols else 'NON réparable'}")


if __name__ == "__main__":
    run()
