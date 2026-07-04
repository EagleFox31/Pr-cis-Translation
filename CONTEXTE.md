# CONTEXTE — pdf_engine_v2 (nouveau moteur PDF « from scratch »)

_Dernière mise à jour : 2026-07-04 — **Traduction bout-en-bout** (balisage →
reflow → rendu), expansion horizontale v3 (colonne / centrage), soulignements
suivant le texte, ancrage vertical des baselines, règles d'orthographe de
segmentation. Restant : **flux vertical / push-down** (étape 2)._

## But

Nouveau moteur PDF **isolé** dans [`pdf_engine_v2/`](pdf_engine_v2/), **indépendant**
de l'ancien moteur [`backend/pdf_translator_engine.py`](backend/pdf_translator_engine.py)
(qui reste **intact**). Deux usages construits l'un sur l'autre :

1. **Fidélité** (base) — extraction de **chaque objet** (texte, image, dessin) en
   JSON, puis réinjection sur une feuille **vierge** à la position/mise en forme
   d'origine. Le JSON est la **seule source** du rendu → vrai test de fidélité.
2. **Traduction** (but final) — à partir de la même extraction : balisage du texte
   par style, traduction (DeepSeek), puis **reflow** du texte traduit dans la zone
   réutilisable de chaque paragraphe, en préservant la mise en forme. Voir la
   section [Traduction](#traduction).

## Fichiers

| Fichier | Rôle |
|---|---|
| [`pdf_engine_v2/engine.py`](pdf_engine_v2/engine.py) | Cœur : `extract()` / `reinject()` (+ `reinject(translated=True)`) |
| [`pdf_engine_v2/tagging.py`](pdf_engine_v2/tagging.py) | Balisage `[[n]]` par **segment de style** (méthode Word) |
| [`pdf_engine_v2/reflow.py`](pdf_engine_v2/reflow.py) | **Coulée** du texte traduit dans `container_lines` (cascade + césure + centrage) |
| [`pdf_engine_v2/translate.py`](pdf_engine_v2/translate.py) | Orchestration traduction (→ `backend/translator_ai.py`, DeepSeek) |
| [`pdf_engine_v2/cli.py`](pdf_engine_v2/cli.py) | CLI : `extract` / `reinject` / `roundtrip` |
| [`pdf_engine_v2/__init__.py`](pdf_engine_v2/__init__.py) | Export `PDFObjectEngine` |
| [`pdf_engine_v2/README.md`](pdf_engine_v2/README.md) | Doc détaillée (schéma JSON, seuils, limites) |

Dépendances ajoutées (venv) : **`pyphen`** (césure syllabique). Clé DeepSeek dans
`backend/.env` (`DEEPSEEK_API_KEY`).

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
(`_group_rotated_lines`) — ex. « TABLE OF CONTENTS » vertical devient **une** ligne.

Deux garde-fous récents :
- **Tolérance de clustering** basée sur la **plus petite** taille des deux spans
  (au lieu de max) : un glyphe géant (numéro décoratif « 1 » taille 62) n'avale
  plus une petite ligne voisine de baseline différente (« & VEHICLE OWNERS »).
- **Caractères de contrôle** (BEL `\x07`, etc.) purgés à l'extraction
  (`_CTRL_RE`) : ils créaient des spans/lignes parasites (« Note: » séparé de son
  corps).

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

1. **DUR** : item de liste · changement de graisse ou de taille (`> 0.20×`) ·
   gros saut `g > 1.8` (`_PARA_GAP_FACTOR`).
2. **Flot continu** : `g < 1.35` (`_PARA_MODERATE_FACTOR`) → **fusion** (x0
   ignoré) ; ligne suivante en **minuscule** → fusion.
3. **Modéré** : indentation d'alinéa `> 1.2× taille` ; ponctuation `.?!` +
   majuscule si `g > 1.6` (`_PARA_PUNCT_FACTOR`) et hors conjonction.

**Règles d'ORTHOGRAPHE (continuation)** — évitent les fausses coupes :
- **Puce** (`_BULLET_RE`) → coupe DURE. **Numéro/lettre** en tête (`_NUMITEM_RE` :
  « 16. », « 44) ») → item de liste **seulement si la ligne précédente finit une
  phrase** ; sinon c'est un nombre du texte (« age is 16. », « (MV-44) ») → pas
  de coupe.
- La ligne précédente finit par un **mot NON TERMINAL** (article/préposition/
  conjonction/auxiliaire, EN+FR, `_NON_TERMINAL`) ou un **tiret** → la suivante
  est une **continuation** → inhibe coupe « espace restant » et ponctuation
  (« …from the / U.S. », « …The / REAL ID Act »).
- Ligne démarrant par une **conjonction de coordination** ou son symbole
  (« & » = and, « + ») → continuation (`_starts_coord`) — ex. titre 2 lignes
  « INFORMATION FOR DRIVERS / & VEHICLE OWNERS » = **un** paragraphe.

Cas non couverts (assumés) : en-tête gras « run-in » suivi d'un numéro
(« Class MJ … / 16. »), acronyme en fin de ligne (« …a DMV / Office »),
parenthèse ouverte non fermée.

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

### Expansion du conteneur (`expand_paragraphs = True`, togglable — Étape D, v3)
Pour absorber des traductions plus longues, chaque paragraphe reçoit une **zone
utilisable élargie vers la droite** (`container_lines` / `container_bbox`, visible
en **orange pointillé**). Expansion **au PARAGRAPHE ENTIER** : bord droit
**uniforme** = minimum disponible sur toute la hauteur (aucune ligne ne dépasse).

**Colonne** d'un paragraphe = paragraphes qui le **chevauchent horizontalement**
(pas seulement de même marge gauche) → une ligne indentée/centrée référence la
vraie marge de sa colonne. Sécurité multi-colonnes par la **règle de côté** :
seuls les voisins qui **commencent à gauche** de `p` définissent sa marge droite
(la colonne voisine, qui démarre à droite, borne via `right_block`, jamais comme
référence).

Bord droit cible :
- **objet/colonne à droite** dans la bande → `bord − gouttière de sécurité`
  (`_safe_gutter`, normalisée ~1,5× le corps, plancher 12 pt) ;
- sinon **marge droite de sa colonne** (bord droit max des voisins) ;
- sinon (**vraiment seul**, `has_col_sibling` faux) → **marge symétrique**
  (`page − marge gauche`).

**Texte CENTRÉ** détecté (multi-ligne : chaque ligne a une gauche différente,
donc **pas de marge gauche dominante** — un simple alinéa de 1re ligne ne compte
pas ; mono-ligne : marges gauche/droite substantielles et ~égales) → conteneur =
**colonne entière** et rendu **recentré** (`align=center`), sinon bord gauche figé
et rendu ferré à gauche. `align` est mémorisé sur le paragraphe pour le reflow.
Ne modifie ni le texte ni sa position d'origine.

### Rendu de texte : mise à l'échelle horizontale (anti-chevauchement)
Chaque run est rendu **mis à l'échelle en x** pour occuper exactement sa largeur
d'origine (`sx = largeur_bbox / font.text_length(...)`, via `write_text(morph=…)`).
Sans cela, les avances de glyphe du sous-ensemble embarqué diffèrent (~2 %) du
placement réel du PDF : la dérive cumulée fait **déborder un run sur le suivant**
(texte collé / superposé, ex. liens soulignés). Garde-fou : correction bornée à
`0.5 ≤ sx ≤ 2.0`. Le repli base-14 passe aussi par ce rendu (objet `fitz.Font`).

## Traduction

Pipeline bout-en-bout, construit sur l'extraction ci-dessus. Chaîne :
**extraction → balisage → traduction → reflow → rendu**.

### 1. Balisage par segment de style (`tagging.py`)
Chaque paragraphe devient un texte balisé `[[0]]…[[/0]][[1]]…[[/1]]…` (méthode
DOCX de `backend/docx_translator_engine.py`). Une balise = un **groupe de runs
consécutifs de MÊME style** (police, gras, italique, taille, couleur,
**soulignement**) — car un mot à lettres espacées est éclaté en un run par
lettre ; les tagger séparément serait absurde. Le texte reconstruit dans les
balises est **identique** au champ `paragraph.text` (mêmes espaces, dé-césure)
→ retirer les balises redonne le texte source (0 divergence sur ~5 300
paragraphes des 2 docs de test). `style_sig` inclut le soulignement, donc un
lien devient son propre segment.

### 2. Traduction (`translate.py` → `backend/translator_ai.py`)
Collecte les paragraphes, envoie le texte balisé par lots à **DeepSeek**
(compatible OpenAI, clé `backend/.env`), qui **préserve les balises `[[n]]`**.
Résultat stocké par paragraphe : `tr_tagged` (texte traduit balisé) + `tr_segments`
(style de chaque balise). Décision produit : **compression par reformulation
seulement**, jamais d'abréviations (le document reste irréprochable).

### 3. Reflow (`reflow.py`)
Coule les segments traduits dans le polygone `container_lines` :
- **Découpe en lignes** gloutonne, chaque ligne clippée à `[gauche(y), droite(y)]`
  du contour en escalier (gère l'enroulement en L). **Césure** syllabique
  (`pyphen`, langue cible).
- **Ancrage vertical** : les lignes sont posées aux **baselines d'origine**
  (`first_baseline + i·pitch`, `first_baseline` = baseline de la 1re ligne
  source) → le texte garde sa position verticale (corrige la dérive qui décalait
  le texte sous ses soulignements).
- **Cascade d'ajustement** (hauteur fixe) du moins au plus intrusif :
  **tracking → taille → interligne** (marges infimes), pour faire tenir une
  traduction plus longue. Si rien ne tient au niveau max → `fitted=False`
  (à signaler / re-traduire plus court).
- **Alignement** : `left` (bord gauche figé) ou `center` (recentrage par ligne).

### 4. Rendu traduit (`engine.reinject(translated=True)`)
Peint la version traduite via reflow au lieu du rendu run-par-run.
- **Police glyphe-par-glyphe** : les sous-ensembles embarqués sont subsettés pour
  le texte SOURCE (anglais) → ils n'ont pas forcément les glyphes accentués FR.
  `has_glyph` / `valid_codepoints` / `glyph_bbox` **sur-déclarent tous** la
  couverture. **Seul test fiable** : rendre le glyphe sur un pixmap et détecter
  l'encre (`_renders_glyph`, en cache). On garde le typeface embarqué là où il
  rend vraiment, sinon **repli base-14** assorti (Times/Helvetica/Courier +
  gras/italique). NB : mv21 (ProximaNova) rend déjà tout ; le Handbook
  (Avenir/PTSerif) subit le repli sur accents.
- **Soulignements de liens** : `_mark_underlines` associe le trait fin horizontal
  au texte juste au-dessus (largeur comparable ; les **filets pleine largeur** =
  règles de section sont ignorés). Le run porte `underline` (→ segments → reflow),
  et le soulignement est **redessiné en continu sous le texte reflowé** ; l'ancien
  trait fixe du source est **supprimé** en mode traduit (sinon figé sous le texte
  déplacé).
- Texte **incliné/vertical** : laissé en rendu original (pas de reflow).

### Utilisation (traduction, 10 pages, via script de test)
Le pilote `scratchpad/run_translate10.py` : charge l'extraction, traduit N pages
(cache `<json>_trN.json` réutilisé au re-rendu), **recalcule l'expansion** avec le
code courant, puis `reinject(translated=True)`. Sorties `*_traduit_p1-10.pdf`
(+ `_debug` avec cadres conteneurs).

## Bordures (debug)

Vert = texte, rouge = image, bleu = dessin. Un paragraphe multi-lignes est cadré
par un **contour rectilinéaire en escalier** (`_draw_stair_outline`) passant par
les sommets de chaque ligne → épouse bords irréguliers, retraits, et forme un
**L** autour d'une image/encart (pas un rectangle englobant).

## Schéma JSON (résumé)

```
pages[] → { page_num, width, height, elements[] }
elements[] (ordre de peinture) :
  { type:"drawing", draw_type, bbox, items[], stroke_color, fill_color,
                    _underline_consumed? }
  { type:"image",   bbox, xref, ext, asset_b64 | asset_file }
  { type:"paragraph", bbox, container_bbox, container_lines[], align, text,
                      lines[] → { text_line, bbox,
                                  runs[] → {text,origin,font,size,color,bold,italic,dir,underline?} },
                      tr_tagged?, tr_segments?[] }   ← champs de TRADUCTION
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
14. Fix rendu titres à lettres espacées (gaps de mots via runs à espace de tête).
15. **Traduction bout-en-bout** — balisage par style (`tagging`) → DeepSeek →
    reflow (`reflow`) → rendu traduit (`reinject(translated=True)`).
16. **Polices traduites** — couverture fiable par test de rendu (`_renders_glyph`)
    + repli base-14 assorti (les subsets embarqués mentent sur la couverture).
17. **Soulignements** suivant le texte reflowé + **ancrage vertical** des baselines.
18. **Expansion horizontale v3** — au paragraphe (min), colonne par chevauchement,
    gouttière normalisée, marge symétrique en dernier recours, **détection et
    rendu du centrage** (vs alinéa de 1re ligne).
19. **Segmentation** — clustering par plus petite taille, purge des caractères de
    contrôle, règles d'orthographe (numéro/mot non terminal/`&` = continuation).

## Toggles (attributs `PDFObjectEngine` + options CLI)

| Attribut | CLI | Étape |
|---|---|---|
| `group_paragraphs` | — | regroupement en paragraphes |
| `para_remaining_space` | `--no-remaining-space` | A (retours volontaires) |
| `expand_paragraphs` | `--no-expand` | D (expansion conteneur) |
| `detect_tables` | `--no-tables` | B (cellules de table) |

## Limites connues (assumées)

**Traduction :**
- **Débordement VERTICAL** (le plus important) : les conteneurs ont une hauteur
  FIXE (expansion vers la droite seulement). Un paragraphe dont la traduction est
  plus longue que ne l'absorbe la cascade **empiète sur le suivant** (ex. titres
  de sommaire passant à 2 lignes, bas de pages denses). → **étape 2 : flux
  vertical / push-down** (à faire).
- **Police sur accents (subsets pauvres)** : les sous-ensembles Avenir/PTSerif du
  Handbook n'ont pas les glyphes accentués FR → repli base-14 pour CES glyphes.
  **Limite fondamentale** (la police complète n'est pas embarquée) ; mv21 rend
  déjà tout.
- **Titres à lettres espacées** (couverture) : extraits « A D V I C E … » (espace
  entre chaque lettre) → charabia pour la traduction. Reconstruction des mots
  tentée puis reverté (incohérente à cause des spans à espace de tête). À reprendre.
- Reflow **ferré à gauche/centré**, pas **justifié** (l'original l'est souvent).
- Cas de **segmentation** résiduels (en-tête gras run-in + numéro, acronyme en
  fin de ligne, parenthèse ouverte).

**Fidélité (base) :**
- Dégradés / shadings purs non captés ; **images** pivotées sans rotation ;
  clips / groupes vectoriels ignorés ; tables **sans bordures** non cloisonnées ;
  ordre de lecture **inter-colonnes global** non implémenté.

## Pistes suivantes possibles

1. **Étape 2 — flux vertical / push-down** (priorité) : récupérer le blanc du bas
   de page, décaler les blocs suivants en conservant leurs écarts, borné par les
   objets ancrés (images/pieds de page) + distance de sécurité, **column-aware**.
2. **Justification** du texte reflowé (répartition d'espace par ligne).
3. Reprise propre des **titres à lettres espacées** (reconstruction des mots).
4. Chargement/embarquement de **polices complètes** (ex. PT Serif, libre) pour
   éliminer le repli sur accents du Handbook.
5. Rotation des **images** pivotées ; tables sans bordures (stratégie `text`).
