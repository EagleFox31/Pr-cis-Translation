# CONTEXTE — pdf_engine_v2 (nouveau moteur PDF « from scratch »)

_Dernière mise à jour : 2026-07-13._

## La traduction PDF v2, en bref

**`pdf_engine_v2` est LE moteur de traduction PDF du produit.** Il a remplacé
l'ancien `backend/pdf_translator_engine.py`, qui n'est plus branché sur les PDF
(il reste en place, intact, pour DOCX/PPTX). Tout ce qui suit décrit ce moteur.

Ce qu'il fait, en une phrase : il **démonte** chaque page en objets (texte, image,
dessin), **traduit** le texte en préservant ses styles, puis **recoule** la
traduction dans la zone exacte de chaque paragraphe d'origine — de sorte que la
page traduite soit géométriquement identique à la source.

Trois propriétés en découlent, et elles gouvernent toutes les décisions du reste
du document :

1. **La mise en page est toujours préservée** — ce n'est pas une option, c'est
   l'invariant. Il n'existe aucun « mode de format » à choisir.
2. **La page traduite est reconstruite, pas retouchée.** Le JSON d'extraction est
   la seule source du rendu, ce qui en fait un vrai test de fidélité.
3. **La traduction est PROGRESSIVE, page par page** ([`stream.py`](pdf_engine_v2/stream.py)) :
   extraction → traduction → rendu, une page à la fois, PDF partiel réécrit après
   chacune. L'utilisateur voit donc la page 1 traduite pendant que la 2 se calcule.

**Deux contraintes structurantes**, à connaître avant toute évolution :

- **Les polices viennent du document source** (repli sur `backend/fonts`, puis
  base-14). Aucune ne porte de glyphe **CJK, arabe ou grec** : ces langues cibles
  sont **hors de portée en PDF** (l'arabe demanderait en plus un reflow
  droite-à-gauche). Écritures rendables : latin et cyrillique.
- **Aucun bloc n'est déplacé.** Le débordement vertical est absorbé sur place
  (grow-into-gap + échelle de groupe + retraduction compacte + force-fit), jamais
  en poussant les blocs suivants — `vertical_flow` reste volontairement à `False`.

> ### ⚠ Le modèle vient de `DEEPSEEK_MODEL`, et de nulle part ailleurs
>
> `translate_pdf_progressive()` ne reçoit **ni modèle ni budget de tokens** : le
> paramètre `quality` de la requête est **ignoré** sur le chemin PDF, et
> `TranslatorAI` lit son modèle dans `backend/.env`. **Cette variable est donc le
> seul réglage qui décide de la vitesse et du coût de toute traduction PDF.**
>
> | Valeur | Effet |
> |---|---|
> | `deepseek-chat` | rapide, économique, non raisonnant — **défaut attendu** |
> | `deepseek-v4-flash` | raisonnement : ~2 min/page, bien plus cher |
>
> Y placer un modèle de raisonnement ralentit et renchérit **chaque page**, sans
> qu'aucune option de l'interface ne le laisse deviner. C'est exactement ce qui
> s'était produit (`.env` basculé sur `deepseek-v4-flash` pendant la campagne de
> tests, puis oublié) — et cela explique les durées observées alors.

**État** — campagne P1-P9 close (voir [`PROBLEMES_PDF_ENGINE_V2.md`](PROBLEMES_PDF_ENGINE_V2.md)) :
césures/justification sans débordement (P2), **expansion v4 par ligne** (encarts
imbriqués respectés, boîtes contenantes, cellules persistées — P1/P5/P9),
**grow-into-gap + échelle de groupe + retraduction compacte** (P3), compensation de
hauteur d'x du repli (P4), gardes de segmentation + folios ancrés (P6), **titres à
lettres espacées reconstruits** (P7), vérification/retry par item de la traduction
(P8).

## Documents liés

| Document | Couvre |
|---|---|
| **`CONTEXTE.md`** (ici) | Le moteur : extraction, analyse de disposition, traduction, reflow, rendu |
| [`PROBLEMES_PDF_ENGINE_V2.md`](PROBLEMES_PDF_ENGINE_V2.md) | Les défauts P1-P9 : cause → correction → vérification |
| [`CONTEXTE_INTERFACE.md`](CONTEXTE_INTERFACE.md) | **L'interface** (React) : formulaire, langues, streaming, hero, pièges CSS |

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
| [`pdf_engine_v2/translate.py`](pdf_engine_v2/translate.py) | Orchestration traduction (→ `backend/translator_ai.py`, DeepSeek) + **support/contexte** de chaque item |
| [`backend/glossary.py`](backend/glossary.py) + [`glossary.json`](backend/glossary.json) | **Expressions pièges** : consigne de terminologie + **filet déterministe** sur la sortie du modèle |
| [`pdf_engine_v2/stream.py`](pdf_engine_v2/stream.py) | **Traduction PROGRESSIVE** page par page (`translate_pdf_progressive`) : extraction→traduction→rendu PAR PAGE, PDF partiel réécrit après chaque page, reprise par cache |
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
saut de colonne (~3–5×).

**Gouttières** (`_column_gutters`, P13) : la largeur seule ne suffit pas. En texte
**justifié**, l'espace entre deux mots enfle jusqu'à rivaliser avec la gouttière
(démo journal : gouttière à 2,33 × la largeur de glyphe, **sous** le seuil, contre
des espaces de mots à 1,75 ×) — les deux colonnes se retrouvaient entrelacées mot
à mot. Ce qui les sépare n'est pas la largeur mais la **PERSISTANCE** : un blanc
de justification se **déplace** d'une ligne à l'autre, une gouttière reste à la
**même abscisse** sur tout le bloc. On cherche donc un **corridor blanc vertical**
(≥ 5 lignes, texte substantiel **des deux côtés** — sans quoi l'indentation d'une
**puce** en forme un) et on coupe les lignes qui l'enjambent, quelle que soit la
largeur du blanc.

**Le vide n'est pas une preuve** (`_gutter_abuts`, P16 — 2026-07-16) : une rangée
traverse **toute la page** (les colonnes voisines partagent leurs lignes de base).
Là où une colonne s'arrête, l'abscisse du corridor tombe dans une vaste zone
**vide** — et cette rangée « confirmait » quand même le corridor, ce qui suffisait
à faire passer le quorum à des corridors **fantômes** qui coupaient le texte.
Désormais une rangée ne prouve un corridor que si du **texte le borde des deux
côtés** (≤ `_GUTTER_ABUT_FACTOR = 4` largeurs de glyphe) ; sinon on l'**enjambe**
— ni preuve, ni réfutation. Seul du texte qui **traverse** réfute. (Démo : 8
corridors → 2 ; la seule gouttière porteuse a 10 rangées bordantes, les 3
fantômes 1-2.)

**Recollage des colonnes justifiées étroites** (`_rejoin_justified`, P15-P17) :
la coupe ci-dessus est **délibérément trop zélée** en colonne étroite justifiée,
où un blanc de mot atteint 4,3 × la largeur de glyphe — plus large que la vraie
gouttière de la page. À l'échelle de la ligne, les deux sont indiscernables ;
une passe de réparation recolle donc **après coup**, en s'appuyant sur les marges
du **BLOC** : une colonne est **avérée** par ≥ 3 lignes **intactes** au même fer
gauche ET droit, et l'on ne recolle une rangée que si ses fragments **remplissent
cette colonne de bord à bord**. Garde-fous : encre (un filet sépare pour de bon),
part d'encre ≥ 50 %, et **priorité à la colonne avérée plus étroite** — sans quoi
un **chapô pleine largeur** soude les colonnes qu'il surplombe (P17). Détail,
limites et contrôles négatifs : `PROBLEMES_PDF_ENGINE_V2.md`.

Le texte **incliné / vertical** (Étape C) est séparé du
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

### Expansion du conteneur (`expand_paragraphs = True`, togglable — Étape D, v4)
Pour absorber des traductions plus longues, chaque paragraphe reçoit une **zone
utilisable élargie vers la droite** (`container_lines` / `container_bbox`, visible
en **orange pointillé**). Expansion **PAR LIGNE** (`_line_target`) : chaque bande
y s'arrête au 1er bloqueur qui commence à sa droite — bloqueurs à granularité
**LIGNE** (les lignes des autres paragraphes, pas leurs bboxes : un encart
imbriqué dans l'empan du paragraphe borne les lignes qui le côtoient, l'escalier
en L est préservé, cf. P1). S'y ajoutent : les **items de dessins** décomposés
(`_drawing_item_boxes` : le mur d'un tableau non détecté borne quand même), les
**cellules `find_tables`** (persistées dans le JSON, `page.cells`, clamp au mur
droit de SA cellule y compris la dernière colonne) et les **boîtes contenantes**
(un paragraphe dessiné DANS une boîte — panneau, cellule en boîte pleine — ne
s'étend jamais au-delà, padding symétrique au padding gauche).

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

### Alignement (P14) — `left` · `center` · `right` · `justify`

**Cadre de référence.** Un alignement n'a de sens que **dans une boîte**.
Hiérarchie, du plus serré au plus lâche : **cellule** `find_tables` → **boîte
contenante** (panneau) → **colonne**. Sans elle, une cellule prend la largeur de
PAGE pour cadre et son texte paraît centré.

**Taxonomie par VARIANCES** (multi-ligne) : le bord le plus **stable** trahit
l'alignement — `vG` minimale → gauche, `vD` → droite, `vC` → centré. Elle est
**sans cadre**, donc immunisée à une colonne polluée (un bandeau pleine largeur
élargit la « colonne » d'un article et ruine tout calcul de marge).

**Ordre de décision** — enroulement (P5) → **droite** → centré → justifié →
gauche. Le fer à droite se juge **avant** le justifié : ses bords droits sont à
fleur, et deux bords gauches proches par hasard suffiraient à le faire passer pour
ferré à gauche. Le vrai discriminant est le bord **GAUCHE** (déchiqueté à droite,
à fleur en justifié).

**Mono-ligne** (pas de variance) : centré par la **symétrie** de ses blancs ;
ferré à droite par sa **PILE** (ses voisines verticales partagent son bord droit,
leurs gauches se dispersent), à condition d'être **adossé au bord droit de son
cadre**. **Texte incliné** : aucune inférence (cette géométrie est mesurée en x,
son axe d'écriture est l'autre).

**Conteneur selon l'alignement** — c'est l'espace RÉELLEMENT disponible :
- `left` / `justify` : bord gauche **figé**, expansion vers la droite ;
- `center` : expansion des **deux** côtés, bornée par le 1er objet de chaque côté
  (`left_block` / `right_block`). Un bloqueur **BORNE**, il n'**annule** pas
  l'alignement — auparavant un objet à droite faisait `centered = False`, donc
  toute légende centrée d'une page multi-colonnes repassait ferrée à gauche ;
- `right` : bord droit **FIGÉ**, expansion vers la **GAUCHE** (jusqu'au
  `left_block`, sinon marge symétrique).

**Garde anti-enroulement (P5)** : un bloc qui chevauche PARTIELLEMENT le bbox du
paragraphe (encart, photo — pas un fond qui l'englobe) explique les bords
variables → jamais centré, jamais à droite. Ne modifie ni le texte ni sa position
d'origine.

### Préparation d'une page traduite (P3 — `_prepare_translated_page`)
Avant de peindre une page traduite : (1) **grow-into-gap** (`grow_into_gap`) —
chaque paragraphe reçoit via `_grow` le blanc RÉELLEMENT disponible sous lui
(borné par le prochain élément, la boîte contenante, 2,5 interlignes ; 30 % du
blanc préservé) — **aucun bloc n'est déplacé** ; (2) reflow à blanc → échelle
nécessaire de chaque paragraphe ; (3) **échelle de groupe** (`group_scale`) —
les fratries (même corps ±0,6 pt, même colonne, chaîne tolérante 4× corps pour
les structures alternées titre/sous-titre) prennent l'échelle du plus contraint
(`_vscale`, plancher 0,88) → page homogène ; (4) les paragraphes sous le
plancher sont marqués `_needs_shorter` → **retraduction compacte**
(`translate.retranslate_overflows`) avec budget de caractères **≥ 0,92× la
longueur source** (en-deçà, le modèle abrège — interdit) ; le force-fit (46 %)
ne reste qu'en garantie ultime anti-chevauchement (`shrink_to_fit`).

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

**Contexte joint à chaque item (P11).** Un fragment partait SEUL — sans voisins,
sans corps de police — alors que le moteur sait qu'un « BREAKING NEWS » de 60 pt
est un **bandeau**, et qu'un bandeau ne se traduit pas comme une phrase. Chaque
item porte donc désormais :
- **`support`** — `titre` ou `corps`, déduit de la **mise en page** (corps ≥ 1,5×
  le corps dominant de la page ET texte court) — signal général, aucune règle liée
  à un document ;
- **`contexte`** — le voisinage textuel de la page (lecture seule).

**Expressions pièges** (`backend/glossary.json` + `glossary.py`) : les tournures
dont le calque est *sémantiquement juste mais pragmatiquement faux*. Pour les
seuls fragments concernés (coût nul ailleurs), une **consigne de terminologie**
est jointe (rendus autorisés, rendus interdits, et le *pourquoi*). Surtout, un
**filet déterministe** relit la sortie : `glossary.enforce` corrige tout rendu
INTERDIT — c'est lui, et non le prompt, qui rend la faute impossible. Ajouter une
expression = ajouter une entrée JSON, aucun code à toucher.
Tests hors ligne : `backend/test_glossary.py`.

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
- **Alignement** : `left` (bord gauche figé) · `center` (recentrage par ligne) ·
  `right` (fer à droite, offset `right − x`) · `justify`.

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
  au texte juste au-dessus. La largeur ne suffit pas à trancher (un titre qui
  **remplit sa colonne** a exactement la largeur du filet de section qui le suit —
  P12). Deux discriminants s'y ajoutent, vérifiés sur les 35 vrais soulignements
  des documents de test : (1) **l'ENCRE** — un soulignement est une décoration du
  TEXTE, donc peint dans SON encre ; un trait d'une autre couleur ne lui
  appartient pas ; (2) **les CLONES** — un filet de la grille du document a des
  jumeaux ailleurs sur la page (même empan, même encre, même épaisseur), là où un
  vrai soulignement est unique. Le run porte `underline` (→ segments → reflow),
  et le soulignement est **redessiné en continu sous le texte reflowé** ; l'ancien
  trait fixe du source est **supprimé** en mode traduit (sinon figé sous le texte
  déplacé).
- Texte **incliné/vertical** : **traduit et reflowé** dans son **repère d'écriture**
  (P10). Le reflow étant purement 2D, on lui passe conteneur et baseline
  transformés par `_to_frame` (X le long de `dir`, Y vers le bas du texte), puis
  `_paint_reflow_rotated` repeint chaque glyphe tourné de `atan2(-dy, dx)`. Un
  titre à **lettres espacées** est re-réparti par son **tracking**
  (`_respread_letterspacing`) pour occuper exactement la bande source — un titre
  espacé se rejustifie par ses blancs, pas en rapetissant son corps. Avant P10,
  la traduction de ces blocs était calculée (et payée) puis **jetée** au rendu.

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
20. **Campagne P1-P9 (2026-07-10/11)** — voir `PROBLEMES_PDF_ENGINE_V2.md` :
    césure+justification sans débordement + coupe des jetons insécables (P2) ;
    expansion v4 par ligne, bloqueurs-lignes, boîtes contenantes, cellules
    persistées (P1/P9) ; garde anti-centrage des enroulements (P5) ;
    grow-into-gap + échelle de groupe + retraduction compacte plafonnée (P3) ;
    compensation de hauteur d'x du repli (P4) ; gardes de segmentation + folios
    ancrés `_split_trailing_numbers` (P6) ; reconstruction des titres à lettres
    espacées avec tracking exact (P7) ; vérification/retry par item + parseur
    robuste + budget de tokens adaptatif (P8).
21. **Intégration dans l'app (2026-07-12)** — moteur v2 branché sur `backend/app.py`
    (l'ancien `pdf_translator_engine` n'est plus branché sur les PDF). Traduction
    **PROGRESSIVE page par page** (`pdf_engine_v2/stream.py`) : `extract_page_data`
    → `translate` → `render_page_into` par page, PDF partiel réécrit
    atomiquement (tmp+rename) après chaque page, cache de reprise `v2_pages.json`.
    API : POST `/api/translate` (PDF → runner v2), SSE `start{total}` +
    `page{page,status,done,total}`, GET `/api/translate/partial/{job}` (PDF des
    pages prêtes), GET `.../result/{job}` (complet). Front : `useStreamingTranslation`
    ouvre l'aperçu au démarrage, vignettes à pastille d'état (attente/en cours/
    prête), panneau traduit avec placeholder par page ; anciens hooks
    (`useTranslation`, `useTranslationProgress`, `TranslationProgress`) supprimés.
22. **Refonte de l'interface (2026-07-13)** — détaillée dans
    [`CONTEXTE_INTERFACE.md`](CONTEXTE_INTERFACE.md). Deux conséquences côté
    **backend** à connaître d'ici : (a) `TranslatorAI.lang_name()` nomme désormais
    chaque **variante régionale** dans le prompt (`en-GB` → « British English (UK
    spelling and conventions) ») et retombe sur la langue de base pour un code
    inconnu — sans ce nommage, `en-GB` et `en-US` produisaient le même texte ;
    (b) le front n'envoie plus `quality` ni `format_options`, que le moteur v2 ne
    lisait pas (`translate_pdf_progressive()` ne reçoit ni modèle ni budget de
    tokens ; la mise en page est toujours préservée). Ces paramètres restent
    acceptés par l'API avec leurs valeurs par défaut.

23. **Texte incliné traduit + registre des bandeaux (2026-07-13)** — voir P10/P11
    dans [`PROBLEMES_PDF_ENGINE_V2.md`](PROBLEMES_PDF_ENGINE_V2.md).
    (a) **P10** : le texte incliné/vertical était traduit puis **jeté au rendu**
    (`_translated_layout` retournait `None`, repli sur les runs SOURCE) → reflow
    dans le **repère d'écriture** + peinture pivotée + tracking re-réparti
    (`_respread_letterspacing`) ; `tagging` mesure enfin l'empan **le long de
    l'axe** (14 pt → 196 pt pour un titre vertical).
    (b) **P11** : chaque item de traduction porte désormais son **support**
    (titre/corps, déduit de la mise en page) et son **contexte de page** ;
    `backend/glossary.*` ajoute les **expressions pièges** (consigne ciblée +
    **filet déterministe** sur la sortie). Le même « BREAKING NEWS » rend
    FLASH INFO / EN DIRECT / ALERTE INFO / « Dernières nouvelles » selon le
    contexte — auparavant les trois cas donnaient le même texte.

## Tests (à rejouer avant toute release)

| Test | Ce qu'il prouve |
|---|---|
| [`backend/test_engine_v2_generic.py`](backend/test_engine_v2_generic.py) | **GÉNÉRICITÉ** : un PDF **synthétique** (autre police, autres corps, autres couleurs, autre format) rejoue les structures de P10-P18 → prouve que les correctifs traitent la **classe** du problème, pas les 3 documents qui l'ont révélé. **31/31** (5 pages). C'est lui qui a débusqué P10-bis, P13-bis, puis **P17** (le chapô pleine largeur qui soudait les colonnes — un bug introduit par P15). |
| [`backend/test_glossary.py`](backend/test_glossary.py) | Expressions pièges : résolution + filet déterministe, hors ligne. **18/18.** |

**Invariants de non-régression** (extraction, 24 pages) : mv21 = **614**
paragraphes · Handbook = **309** · démo = **38** (42 avant P15 : les 4 en moins
sont les fragments **recollés** de la 3ᵉ colonne), **aucun mot perdu**.
Soulignements consommés : mv21 = **27** · Handbook = **6** · démo = **0**.
Toute dérive est une régression jusqu'à preuve du contraire.

> **Un test qui ne tombe jamais ne teste rien.** Chaque règle de P15-P18 a un
> **contrôle négatif** qui la désarme seule ; le check visé doit alors échouer.
> Sans eux, trois assertions passaient **à vide** — dont un contrôle « le piège
> est armé » qui mesurait l'état *après* réparation, donc dépendait du correctif
> qu'il prétendait juger.

> **Règle de conception** (cf. [`PROBLEMES_PDF_ENGINE_V2.md`](PROBLEMES_PDF_ENGINE_V2.md#-audit-de-généricité-2026-07-13--backendtest_engine_v2_genericpy)) :
> **aucune heuristique calée sur un document de test.** Un seuil ne se règle pas
> « pour que mv21 passe » : il doit exprimer une propriété du CONCEPT (un
> soulignement est peint dans l'encre de son texte ; une gouttière persiste, un
> blanc de justification se déplace). Le test synthétique est le juge.

## Toggles (attributs `PDFObjectEngine` + options CLI)

| Attribut | CLI | Étape |
|---|---|---|
| `group_paragraphs` | — | regroupement en paragraphes |
| `para_remaining_space` | `--no-remaining-space` | A (retours volontaires) |
| `expand_paragraphs` | `--no-expand` | D (expansion conteneur) |
| `detect_tables` | `--no-tables` | B (cellules de table) |

## Limites connues (assumées)

**Traduction :**
- **Débordement vertical** : plus de chevauchement possible (grow-into-gap +
  retraduction compacte + force-fit garanti), mais pas de REMONTÉE de blocs
  quand une traduction est plus courte (trous résiduels) — le push-down/pull-up
  reste volontairement désactivé (`vertical_flow=False`).
- **Police sur accents (subsets pauvres)** : repli famille assortie avec
  **compensation de hauteur d'x** (mesure à l'encre) → homogène ; la police
  exacte reste non embarquée (limite fondamentale).
- **Paragraphes trans-pages** : un paragraphe coupé par le bas de page est
  traduit par page → le fragment pendant est traduit isolément (« Votre permis
  étranger », mv p18). Nécessiterait une couture inter-pages.
- Incohérences de traduction ponctuelles du modèle (ex. « PART TWO » conservé
  alors que « PARTIE UN » est traduit) — re-tenté mais non forcé.
- Titres stylisés hors reflow (« Go the extra mile… » mv p3) : rendu original.
- Cas de **segmentation** résiduels (en-tête gras run-in + numéro, acronyme en
  fin de ligne, parenthèse ouverte).
- **Colonne justifiée étroite de ≤ 5 lignes non recollée** (P15, en suspens au
  2026-07-16) : le recollage exige **3 lignes intactes** pour attester la
  colonne ; un bloc court n'en fournit qu'une ou deux, ses mots à gros blanc
  restent donc en îlots. Abaisser le quorum est **exclu** (à 1 témoin, un titre
  pleine largeur soude les 4 colonnes de la démo). 0 occurrence sur les 51 pages
  de référence.

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
