# CONTEXTE — pdf_engine_v2 (nouveau moteur PDF « from scratch »)

_Dernière mise à jour : 2026-07-02_

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
saut de colonne (~3–5×).

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

Étape 8 (texte lisible seulement) : **dé-césure** + espaces écrasés.

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
  { type:"paragraph", bbox, text, lines[] → { text_line, bbox, runs[] → {text,origin,font,size,color,bold,italic,dir} } }
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

## Limites connues (assumées)

- Dégradés / shadings PDF purs non captés (seuls fonds/traits vectoriels et
  images raster).
- Images pivotées / texte pivoté : placés sans matrice de rotation.
- Clips / groupes vectoriels ignorés.
- Ordre de lecture **inter-colonnes global** (étape 6) non implémenté : chaque
  paragraphe est correct et boxé, mais la concaténation d'une page multi-colonnes
  suit haut→bas/gauche→droite (utile surtout pour l'extraction de texte continu).

## Pistes suivantes possibles

- Ordre de lecture colonne par colonne (étape 6) pour un flux texte continu.
- Rotation (images/texte pivotés).
- Contours de paragraphe : lissage / fusion des micro-marches.
