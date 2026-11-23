# Étude : lettre cachée sous une forme, étiquettes dans deux cadres (moteur PDF)

## Besoin
Document 4S (EN → FR) :
- **Page 2** : le « S » rouge de « Seiri » réapparaît en gris. Dans l'original, le texte gris « Seiri » est recouvert, sur son « S », par une lettre rouge **dessinée** (forme vectorielle) peinte après lui. Au rendu, la page est repeinte (dessins, puis texte), et le « S » gris repasse au-dessus du rouge.
- **Page 3** : « Necessary » et « Unnecessary », chacun dans son cadre et séparés de 8 pt, sont lus comme une même ligne. La traduction mêle les deux : « Articles inutiles néces-saires ».

## Existant
- `_opaque_covers` / `_hidden_chars` (`engine.py`) : un caractère est caché seulement s'il se trouve sous un **rectangle** plein et opaque peint après lui. Toute autre forme est ignorée, par prudence.
- `_group_horizontal_lines` : une rangée est coupée sur un grand écart (`_COL_SPLIT_FACTOR`), sur une gouttière ou sur un marqueur de liste. Les cadres ne comptent pas, sauf au recollage (`_rejoin_justified`, murs d'encre).

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Forme quelconque peinte après le caractère → caché, **vérifié à l'image** | Ciblé, prouvé par l'original ; prolonge la règle des rectangles | Un rendu de pixels par caractère candidat (rare) |
| B. Repeindre texte et dessins dans l'ordre exact de l'original | Général | Touche tout le rendu : risque élevé |
| C. Coupe de rangée quand deux textes sont chacun dans un cadre distinct | Règle géométrique simple | Aucun |

Retenu : **A + C**.

## Règles
- **A** :
  - Forme candidate : pleine, opaque, peinte après le texte, et qui n'est pas un simple rectangle (les rectangles restent traités par `_opaque_covers`).
  - Elle doit couvrir au moins 40 % de la boîte du caractère (`_MASK_OVERLAP`).
  - Elle masque le caractère si l'original, rendu à ×4 sur cette boîte, ne montre presque plus aucun pixel de la couleur du texte (≤ 0,5 %, `_MASK_VISIBLE`).
  - Exclus : les espaces, les couleurs non RVB ou gris, le texte transparent.
- **C** :
  - Un cadre est une boîte d'encre (item de dessin ou image) de plus de 1 pt dans chaque sens.
  - On coupe entre deux textes voisins si l'un est dans un cadre qui ne contient pas l'autre, et inversement.
  - Deux mots dans le même cadre restent ensemble.

## Risques
- A : si un trait de surligneur est dessiné en mode « produit » sur un texte coloré, la couleur visible change et le texte pourrait être jugé caché. Ce cas n'apparaît pas dans le corpus.
- C : deux mots surlignés chacun par son propre rectangle, collés l'un à l'autre, seraient séparés. Ce cas est rare et sans perte de texte.

## Vérification
- `tests/test_engine_v2_generic.py` P36 : 5 contrôles, dont 2 échouent sans le correctif. Résultat : 108/108.
- `test_coherence_pdf` 10/10 ; `test_rendu_cache_fond` OK.
- Corpus de 124 pages (mv21, Code de la route, Data Science Handbook, CD…, démo) : extraction identique avant et après.
- Document 4S : la page 2 donne « eiri / eiton / eiso / eiketsu » (le S rouge reste visible) ; la page 3 donne « Necessary items » et « Unnecessary items » séparés.
- Moteur passé en version 1.0.13, ce qui invalide les rendus en cache.
