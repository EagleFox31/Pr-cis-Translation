# CONTEXTE — pdf_engine_v2 (nouveau moteur PDF « from scratch »)

_Dernière mise à jour : 2026-07-02 — Étapes A (retours volontaires), D (expansion),
B (tables), C (texte incliné/vertical) + rendu mis à l'échelle._

## But

Nouveau moteur PDF **isolé** dans [`pdf_engine_v2/`](pdf_engine_v2/), **indépendant**
de l'ancien moteur [`backend/pdf_translator_engine.py`](backend/pdf_translator_engine.py)
(qui reste **intact**). Il fait **une seule chose**, en deux temps :

1. **Extraction** — lit chaque page et sérialise **chaque objet détectable**
   (texte, image, dessin vectoriel) en JSON, dans l'ordre de peinture.
2. **Réinjection** — reconstruit chaque page sur une feuille **vierge** (mêmes
   dimensions) en redessinant chaque objet **à sa position et mise en forme
   d'origine**, puis trace une **bordure** autour de chaque objet.

Le JSON est la **seule source** du rendu reconstruit (rien n'est copié depuis le
PDF d'origine) → c'est un vrai test de fidélité de l'extraction.

## Fichiers

| Fichier | Rôle |
|---|---|
| [`pdf_engine_v2/engine.py`](pdf_engine_v2/engine.py) | Cœur : `PDFObjectEngine.extract()` / `.reinject()` |
| [`pdf_engine_v2/cli.py`](pdf_engine_v2/cli.py) | CLI : `extract` / `reinject` / `roundtrip` |
| [`pdf_engine_v2/__init__.py`](pdf_engine_v2/__init__.py) | Export `PDFObjectEngine` |
| [`pdf_engine_v2/README.md`](pdf_engine_v2/README.md) | Doc détaillée (schéma JSON, seuils, limites) |

## Utilisation

```bash
# Aller-retour complet (extraire puis reconstruire) — test de fidélité
backend/venv/Scripts/python.exe -m pdf_engine_v2.cli roundtrip "mon.pdf" "sortie.pdf"

# Extraction seule -> <pdf>_objects.json (images en base64 dans le JSON)
backend/venv/Scripts/python.exe -m pdf_engine_v2.cli extract "mon.pdf"

# Réinjection seule (avec bordures ; --no-borders pour désactiver)
backend/venv/Scripts/python.exe -m pdf_engine_v2.cli reinject "mon_objects.json" "sortie.pdf"
```

PDF de test : `backend/tests files/The Data Science Handbook.pdf` (285 pages).
Sortie de référence régénérée : `backend/tests files/The Data Science Handbook_reconstitue.pdf`.

## Ce qui est capté et réinjecté

- **Texte** — spans PyMuPDF, regroupés en **lignes** puis **paragraphes** par
  analyse de disposition (voir plus bas). Rendu run par run à la position/police
  exacte.
- **Polices** — les polices embarquées du PDF sont extraites et réutilisées
  (glyphes exacts). Les polices **CID / Type0 (Identity-H)** n'ont pas de cmap
  Unicode : elle est **reconstruite** via `get_texttrace()` (couples
  Unicode↔glyph-id) + **fontTools**. Repli base-14 sinon.
- **Images** — composées avec leur masque de transparence (**SMask**) en PNG à
  alpha (zones transparentes préservées).
- **Dessins vectoriels** — tracés (lignes, rectangles, béziers, quads) rejoués.
- **Ordre de peinture** : dessins/fonds → images → texte.

## Analyse de disposition (façon « sélection de texte », sans OCR)

### Lignes
Spans → lignes visuelles : clustering par ligne de base, puis **coupe aux
colonnes** aux grands écarts horizontaux mesurés **relativement à la largeur de
glyphe** (`_COL_SPLIT_FACTOR = 2.5`) — distingue un letter-spacing (~1–2×) d'un
saut de colonne (~3–5×). Le texte **incliné / vertical** (Étape C) est séparé du
texte horizontal et regroupé **le long de son axe d'écriture**
(`_group_rotated_lines` : projection origine sur l'axe d'avancée `o·dir` et
transverse `o·perp`) — ex. « TABLE OF CONTENTS » vertical devient **une** ligne.

### Tableaux (`detect_tables = True`, togglable — Étape B)
Tables **bordées** détectées par `find_tables(strategy="lines")` (faible
faux-positif). Chaque ligne est **taguée par sa cellule** ; deux lignes de
cellules différentes ne fusionnent jamais (cloisonnement). Les murs de cellule
sont ajoutés aux **obstacles** (bornent l'expansion et l'« espace restant »).

### Paragraphes (`group_paragraphs = True`)
Column-aware : deux lignes ne fusionnent que si elles se chevauchent
horizontalement ; le parent d'une ligne est la ligne au-dessus la **plus proche
verticalement** (flot de lecture → gère l'enroulement autour d'une image/encart).
Hiérarchie de coupe (`g` = saut de ligne de base / taille) :

1. **DUR** : item de liste (puce/numéro) · changement de graisse ou de taille
   (`> 0.20×`) · gros saut `g > 1.8` (`_PARA_GAP_FACTOR`).
2. **Flot continu** : `g < 1.35` (`_PARA_MODERATE_FACTOR`) → **fusion** (x0
   ignoré) ; ligne suivante en **minuscule** → fusion.
3. **Modéré** : indentation d'alinéa `> 1.2× taille` (distinction du **centrage**
   par axe central, pas par bord droit) ; ponctuation `.?!` + majuscule si
   `g > 1.6` (`_PARA_PUNCT_FACTOR`) et hors **conjonction de coordination**.

**Règle « espace restant »** (`para_remaining_space = True`, togglable — Étape A) :
tie-breaker géométrique évalué **avant** le flot continu (mais après les signaux
DURS et la continuation minuscule). Si le **premier mot** de la ligne suivante
aurait pu tenir dans l'espace libre à droite de la dernière ligne, c'est un
**retour à la ligne volontaire** → coupe ; sinon fusion.

La marge droite de référence est la **marge de COLONNE** de la ligne
(`col_margin`, cf. `_assign_column_margins`). On calcule, dans une fenêtre
verticale (`_RS_WINDOW_FACTOR × taille`) restreinte aux lignes qui chevauchent
horizontalement (même colonne) : le bord droit max partagé, et l'**espace ouvert**
à droite (`_open_right` : 1er obstacle/colonne voisine, sinon **bord de page** —
une colonne seule a donc tout l'espace à sa droite). Deux régimes :
- **texte qui coule** — ≥ 2 lignes alignées au même bord droit **ET** contenu de
  la ligne **≥** espace restant (le reliquat n'est qu'une gouttière) → `col_margin`
  = ce bord → le mot suivant n'y rentre pas → **pas de fausse coupe** ;
- **item court** — sinon (sommaire, liste, **numéros de page** de largeur
  identique, entrées longues d'un sommaire à colonne unique) → `col_margin` =
  espace ouvert → coupe du retour volontaire.

Le test « contenu ≥ reliquat » distingue une vraie colonne justifiée (ligne large,
gouttière étroite → fusion) d'items courts alignés (numéros → coupe), là où le
seul « même bord droit » les confondait. Plafonné par le 1er obstacle non-texte.
Contexte (dimensions, **obstacles**) fourni par `_build_page_ctx()`.

### Rendu du texte incliné / vertical (Étape C)
Chaque run porte son vecteur `dir` ; à la réinjection (`_write_scaled`), un run
non horizontal est tourné par la **matrice de rotation** d'angle
`atan2(dy, dx)` autour de l'origine (via `write_text(morph=…)`). Le texte
horizontal garde la **mise à l'échelle en x** (anti-chevauchement). Rendu vérifié
conforme à l'original (« TABLE OF CONTENTS » vertical).

Étape 8 (texte lisible seulement) : **dé-césure** + espaces écrasés.

### Expansion du conteneur (`expand_paragraphs = True`, togglable — Étape D)
Pour absorber des traductions plus longues/courtes, chaque paragraphe reçoit une
**zone utilisable élargie vers la droite uniquement** (bord gauche figé),
calculée **ligne par ligne** (`container_lines`) — donc un contour en escalier
qui **contourne un encart** (L) au lieu d'un rectangle qui le traverse. Règle
**unique** : on étend chaque ligne **seulement jusqu'à la plus grande ligne du
paragraphe** (`right_max`) — on aligne toutes les fins de ligne sur la ligne la
plus longue (« équilibrage vers la fin la plus éloignée »). **JAMAIS jusqu'à la
marge de page** : une colonne reste dans sa largeur, sans déborder sur le bloc de
droite. On n'étend que si `right_max` est atteignable en gardant l'espace de
sécurité (`_EXPAND_GAP`) face au 1er objet/colonne à droite ; sinon la ligne est
**laissée telle quelle** (enroulement autour d'un encart). Ne modifie ni le texte
ni sa position ; visible en **orange pointillé** à la réinjection.

### Rendu de texte : mise à l'échelle horizontale (anti-chevauchement)
Chaque run est rendu **mis à l'échelle en x** pour occuper exactement sa largeur
d'origine (`sx = largeur_bbox / font.text_length(...)`, via `write_text(morph=…)`).
Sans cela, les avances de glyphe du sous-ensemble embarqué diffèrent (~2 %) du
placement réel du PDF : la dérive cumulée fait **déborder un run sur le suivant**
(texte collé / superposé, ex. liens soulignés). Garde-fou : correction bornée à
`0.5 ≤ sx ≤ 2.0`. Le repli base-14 passe aussi par ce rendu (objet `fitz.Font`).

## Bordures (debug)

Vert = texte, rouge = image, bleu = dessin. Un paragraphe multi-lignes est cadré
par un **contour rectilinéaire en escalier** (`_draw_stair_outline`) passant par
les sommets de chaque ligne → épouse bords irréguliers, retraits, et forme un
**L** autour d'une image/encart (pas un rectangle englobant).

## Schéma JSON (résumé)

```
pages[] → { page_num, width, height, elements[] }
elements[] (ordre de peinture) :
  { type:"drawing", draw_type, bbox, items[], stroke_color, fill_color, ... }
  { type:"image",   bbox, xref, ext, asset_b64 | asset_file }
  { type:"paragraph", bbox, container_bbox, container_lines[], text,
                       lines[] → { text_line, bbox, runs[] → {text,origin,font,size,color,bold,italic,dir} } }
fonts{} : nom → [ {ext, b64}, ... ]   (polices embarquées, cmap patchée si CID)
```

## Historique des corrections (chronologie de la session)

1. v1 : extraction/réinjection géométrique + bordures par objet ; base-14.
2. Embarquement des **polices source** (+ reconstruction cmap CID) → glyphes exacts.
3. **SMask** images (transparence) + ordre de peinture corrigé.
4. Bordures par **ligne visuelle** (fin du 1 cadre/lettre sur letter-spacing).
5. **Détection de lignes** column-aware (seuil relatif largeur de glyphe).
6. **Regroupement en paragraphes** (étapes 7–8).
7. Corrections de 3 cas : titre/sous-titre sommaire séparés · faux découpages ·
   **texte enroulé** autour image/encart en un seul paragraphe (parent = plus
   proche vertical ; indentation conditionnée au gap ; `.?!` seuls coupent).
8. Cohérence sommaire (garde-fou centrage par **axe central**) + **contours en
   escalier** exacts.
9. **Étape A** — coupe « espace restant » (retours à la ligne volontaires) :
   marge de **colonne** avec régime justifié/liste + test « contenu ≥ reliquat »
   (gère numéros de page, entrées longues de sommaire, colonne unique).
10. **Rendu texte** — mise à l'échelle horizontale par run (anti-chevauchement
    dû à la dérive des métriques du sous-ensemble embarqué).
11. **Étape D** — expansion du conteneur vers la droite (jusqu'à la plus grande
    ligne du paragraphe uniquement ; contour en escalier ; jamais vers la gauche).
12. **Étape B** — cloisonnement des cellules de tableau (`find_tables` lignes).
13. **Étape C** — texte incliné / vertical : regroupement le long de l'axe +
    rendu pivoté (matrice de rotation).

## Toggles (attributs `PDFObjectEngine` + options CLI)

| Attribut | CLI | Étape |
|---|---|---|
| `group_paragraphs` | — | regroupement en paragraphes |
| `para_remaining_space` | `--no-remaining-space` | A (retours volontaires) |
| `expand_paragraphs` | `--no-expand` | D (expansion conteneur) |
| `detect_tables` | `--no-tables` | B (cellules de table) |

## Limites connues (assumées)

- Dégradés / shadings PDF purs non captés (seuls fonds/traits vectoriels et
  images raster).
- **Images** pivotées : placées sans matrice de rotation (le **texte** pivoté,
  lui, est géré — Étape C).
- Clips / groupes vectoriels ignorés.
- Tables **sans bordures** (détectées par alignement seul) non cloisonnées
  (stratégie `lines` uniquement, pour éviter les faux positifs).
- Ordre de lecture **inter-colonnes global** (étape 6) non implémenté : chaque
  paragraphe est correct et boxé, mais la concaténation d'une page multi-colonnes
  suit haut→bas/gauche→droite (utile surtout pour l'extraction de texte continu).

## Pistes suivantes possibles

- Ordre de lecture colonne par colonne (étape 6) pour un flux texte continu.
- Rotation des **images** pivotées.
- Tables sans bordures (stratégie `text`) avec garde-fous anti-faux-positifs.
- Contours de paragraphe : lissage / fusion des micro-marches.
