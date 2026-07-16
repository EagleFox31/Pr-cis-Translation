# Problèmes identifiés — pdf_engine_v2

_Campagne 20 pages du 2026-07-10 (corrigés les 2026-07-10/11), puis P12-P14
(07-13/14) et **P15-P18 (2026-07-16)**._

> Constats issus de 20 pages traduites (FR) + debug pour `mv21.pdf` et
> `The Data Science Handbook.pdf` (`backend/tests files/`), causes établies dans
> le code, **corrections appliquées et vérifiées** (repro + checker automatique
> + revérification visuelle page par page). Objectif produit : mise en forme
> **fiable et 100 % conforme**.

## ✅ Corrigés & vérifiés

| # | Problème | Cause | Correction | Vérification |
|---|----------|-------|------------|--------------|
| **P2** 🔴 | Césures + justification/centrage débordent la marge droite (jusqu'à sortir de page/cellule) | `reflow._layout` n'avançait pas `x` après la pose du préfixe césuré → slack de justification surestimé (repro : +14 à +33 pt) ; jetons insécables (URL) plus larges que la ligne | Avance de `x` ; `_hard_split` des jetons insécables (séparateurs `/.-_` puis caractère) | Repro à 0 ; **checker : 0 violation** sur les 2 docs entiers ; visuel p6/p7 hb au fer à droite exact |
| **P1** 🔴 | Paragraphes enroulés reflowés pleine largeur → **écrasent les encarts** (hb p13/16/18/20) | `right_block` exigeait `qb[0] ≥ pright` (encart imbriqué invisible) ; `_set_container` aplatissait l'escalier (bord droit uniforme) ; bboxes de paragraphes trop grossiers | Bord droit **par ligne** (`_line_target`), bloqueurs à granularité **ligne** (`blocker_lines`), **boîtes contenantes** (panneau/cellule dessinée : jamais au-delà de sa boîte), cellules `find_tables` **persistées** dans le JSON (`page.cells`) + clamp | hb p13/16/18/20 : citations intactes entre leurs filets, enroulement respecté ; mv p16 : 6 cellules sur 6 propres |
| **P5** 🟠 | Faux centrage des paragraphes enroulés (hb p20) | Gauches variables causées par l'obstacle → détection « centré » → `left_edge=col_left` écrasait les gauches | Garde `wrapped` : un bloc qui chevauche **partiellement** le bbox (sans l'englober — un bandeau de fond ne compte pas) ⇒ jamais centré | hb p20 ferré à gauche correct |
| **P3** 🟠 | Tailles hétérogènes (sommaires, listes à ~50-60 %), sauts de taille en pleine phrase | `shrink_to_fit` force-fit 46 % par paragraphe isolé ; conteneurs à hauteur fixe ; hook « re-traduire plus court » jamais câblé | **3 volets** : (1) `grow_into_gap` — le conteneur reçoit le blanc réel sous le bloc (`_grow`, aucun déplacement) ; (2) `group_scale` — fratries (même corps, même colonne, chaîne tolérante 4×corps) → échelle commune `_vscale`, plancher 0,88 ; (3) **retraduction compacte** (`translate.retranslate_overflows`) avec budget de caractères, **plancher ≥ 0,92× la longueur source** (en-deçà le modèle abrégeait : « Ch7 », « RMSE » — interdit) + passe de réparation des sur-abréviations | Sommaire hb homogène sans abréviations ; listes hb p9 uniformes ; hb : 19 → 0 paragraphes trop longs après compact |
| **P4** 🟠 | Lignes accentuées dans une police de repli visuellement plus grosse (mv21 « bicolore ») | Segment entier basculé sur la famille assortie (subset sans accents) ; hauteur d'x Montserrat ≫ ProximaNova | **Compensation de hauteur d'x** : mesure à l'encre (`_font_xheight`, même infra que `_renders_glyph`) → corps ajusté `× xh_src/xh_assortie` (borné 0,85–1,12) ; 22 polices `backend/fonts` vérifiées saines (encre + accents) | Sommaire mv21 p4 homogène ; corps mv21 cohérent |
| **P6** 🟠 | Duplications (« Relevé », fragments), folio « 64 » avalé, lignes centrées fusionnées, scission « …ou âge / 17 ans » | Fausses coupes/fusions de la segmentation | 4 gardes : « / » final = continuation ; **nombre nu + minuscule** = continuation de mesure ; le **wrap d'un item** à puce/numéro n'est pas jugé sur l'« espace ouvert » ; lignes **individuellement centrées auto-suffisantes** (fin d'unité : `.!?)»`, nombre, domaine) = une entrée par ligne. + `_split_trailing_numbers` : folio final aligné avec ≥ 2 autres folios → ligne ancrée séparée | Extraction : items 2 lignes fusionnés, « 64 » autonome et ferré à droite au rendu, 5 organismes mv p3 chacun sur leur ligne, « 18 ans, ou âge 17 avec… » d'un seul tenant |
| **P7** 🟠 | Titres à lettres espacées : mots collés (« CONSEILSETIDEESDE ») | Frontières de mots détruites : double espace écrasé (`\s{2,}`) pour la forme mono-run ; espace de tête des runs ignoré pour la forme run-par-lettre | `tagging._letterspaced_segments` : reconstruction des mots (double espace / espace de tête / saut géométrique en repli), changement de style = frontière de mot ; meta `letter_spaced{width,text}` → le moteur calcule le **tracking exact** avec les vraies polices, ré-appliqué au rendu (mesure + peinture cohérentes, espace de mot = espace + 2×tracking) | hb p1 : « CONSEILS ET ENSEIGNEMENTS DE », « PRÉFACE DE JAKE KLAMKA », « L E » — quasi identique à l'original |
| **P8** 🟡 | Texte resté en anglais / styles perdus, en silence | id absents de la réponse jamais re-tentés ; balises mutilées → « style dominant » ; réponse « objet nu » non parsée ; bloc unique tronqué sans extension de budget | Vérification **par item** (id + intégrité des balises) + retry individuel (2 essais) + journalisation des replis ; parseur : objet nu accepté ; budget de sortie doublé (jusqu'à 32 768) sur bloc unique tronqué | mv21 : 5 items récupérés au retry ; « PARTIE UN »/« Règles de la route » traduits |
| **P9** 🟡 | Filets d'encart orphelins | Conséquence de P1 (débordement du voisin) | Aucun mécanisme nouveau : disparu avec P1 (le texte de la citation reste ancré dans sa boîte) | hb p13/16/18/20 : filets exactement autour des citations |

## ✅ Corrigés & vérifiés — campagne du 2026-07-13

| # | Problème | Cause | Correction | Vérification |
|---|----------|-------|------------|--------------|
| **P10** 🔴 | **Texte incliné/vertical jamais traduit** (« TABLE OF CONTENTS » de mv21 reste en anglais) | La traduction était bien faite (`tr_tagged` rempli — l'appel était payé), mais le RENDU la jetait : `_translated_layout` retournait `None` dès qu'un run n'était pas horizontal → repli sur `_draw_paragraph`, c.-à-d. les runs SOURCE. Second défaut : `tagging` mesurait la largeur d'un titre à lettres espacées **en x**, donc 14 pt (la largeur du fût) au lieu des 196 pt de l'empan vertical → tracking nul | Le reflow est **purement 2D** : on lui donne conteneur et baseline dans le **repère d'écriture** du paragraphe (`_to_frame`/`_to_page`, X le long de `dir`), il coule normalement, puis `_paint_reflow_rotated` repeint chaque glyphe tourné de `atan2(-dy,dx)`. `tagging._axis_extent` mesure désormais **le long de l'axe**. `_respread_letterspacing` re-répartit le tracking sur le texte TRADUIT (un titre espacé se rejustifie par son tracking, pas par son corps → pas de force-fit qui rapetisse) | mv21 p4/p5/p6 : « TABLE DES MATIÈRES » et « PARTIE » rendus verticaux, `dir` conservé, occupant **exactement** la bande source (215,3→411,8 pt). **Non-régression : 12 pages rendues, seules les lignes inclinées changent** (tout le texte horizontal est identique au bit près) |
| **P11** 🟠 | Registre inadapté sur les **titres/bandeaux** : le même « BREAKING NEWS » rendu à l'identique quel que soit le contexte (direct, alerte, phrase) | Chaque paragraphe partait SEUL (`{"id":…, "text":"[[0]]BREAKING NEWS[[/0]]"}`) : ni voisins, ni corps de police — alors que le moteur SAIT que c'est un titre de 60 pt. Le prompt se déclarait en plus « traducteur **technique** ». Le modèle n'avait donc aucun moyen de distinguer les cas | (1) `translate.py` joint à chaque item son **support** (`titre`/`corps`, déduit de la mise en page : corps ≥ 1,5× le corps dominant de la page **et** texte court) et un **contexte de page** ; (2) `backend/glossary.json` + `glossary.py` : base d'expressions pièges → consigne de terminologie jointe **aux seuls fragments concernés** (coût nul ailleurs) ; (3) **filet déterministe** `glossary.enforce` : un rendu INTERDIT (« dernières minutes ») est corrigé après coup, quoi qu'ait produit le modèle | `backend/test_glossary.py` : **18/18** hors ligne. Bout-en-bout DeepSeek : le même « BREAKING NEWS » donne **FLASH INFO** (affiche) · **EN DIRECT** (contexte « live ») · **ALERTE INFO** (évacuation/attentat) · « Dernières nouvelles » (dans une phrase). **Avant : les 3 cas donnaient le même rendu** |

> ### ⚠ P11 — portée EXACTE de la correction (à lire avant d'y toucher)
>
> **Le problème général n'est PAS résolu, et il ne peut pas l'être par ce moyen.**
> Deux couches, aux garanties très inégales :
>
> | Couche | Portée | Garantie |
> |---|---|---|
> | `support` + contexte + règle de registre du prompt | **toute** expression | **aucune** — probabiliste. Mesurée : effet ~nul sur les libellés isolés (le modèle rendait déjà « Save » → « Enregistrer », « Home » → « Accueil » sans elle). Assurance bon marché, à ne pas survendre. |
> | `glossary.json` + `enforce` | **seulement** les 16 entrées listées | **totale** — le rendu interdit est impossible à émettre, quel que soit le modèle |
>
> Contre-exemple mesuré : **« DEVELOPING STORY » → « EN DIRECT »** (contresens :
> une affaire qui *évolue* n'est pas une *diffusion en direct*). La couche
> générale ne l'attrape pas. L'entrée `developing-story` (8 lignes de JSON) le
> corrige et le verrouille → « SITUATION ÉVOLUTIVE ». **C'est le mode d'emploi :
> un piège constaté = une entrée, pas une modification de code.**
>
> ### 🔬 Banc d'essai des entrées (2026-07-13) — `hint: false`
>
> Chaque entrée a été rejouée **sans sa consigne et sans le filet** (mais avec le
> `support`), **3 essais**. Verdict :
>
> - **14 entrées sur 16 sont MUETTES** : le modèle les traduit seul, correctement
>   et **3/3 à l'identique** (*library* → bibliothèque, *supports* → prend en
>   charge, *sensible* → judicieux, *ISSUE 42* → NUMÉRO 42 vs *the issue* → le
>   problème…). Leur consigne ne faisait que **payer des jetons pour un conseil
>   déjà suivi** → `hint: false`, elles ne parlent plus.
> - **`breaking-news` PARLE** : seul, le modèle rend **« FLASH INFO » dans les 3
>   contextes** (affiche, direct, alerte) — il ne fait **aucune** distinction. Et
>   en *corps* il dérape (« Le flash info a été diffusé à 18h » : l'idiome du
>   bandeau appliqué dans une phrase). C'est elle qui produit EN DIRECT /
>   ALERTE INFO / « Dernières nouvelles ».
> - **`developing-story` PARLE** : contresens « EN DIRECT » **2 fois sur 3**, de
>   façon **non déterministe** (3e essai : « ENQUÊTE EN COURS »).
>
> **Règle d'architecture qui en découle** — une entrée a deux fonctions au coût
> très inégal, à ne PAS confondre :
>
> | Fonction | Coût | Portée |
> |---|---|---|
> | **consigne** (`options`, `note`) injectée dans le prompt | des jetons à **chaque** fragment qui matche | réservée aux entrées qui changent la sortie (`hint: true`) |
> | **filet** (`never`) testé sur la sortie | **zéro jeton** | **toutes** les entrées — assurance gratuite contre un changement de modèle |
>
> Vérifié : « librairie », « éventuellement », « supporte » sont toujours corrigés
> alors que leurs entrées ne coûtent plus un seul jeton de prompt.
>
> **⚠ L'erreur signalée (« dernières minutes ») n'a PAS été reproduite.**
> Testé sur `deepseek-chat`, `deepseek-v4-flash` et `deepseek-reasoner`, seul ou
> noyé dans un lot : tous rendent « FLASH INFO ». L'occurrence observée venait
> donc d'un autre chemin (prompt antérieur, tirage à `temperature=0.1`, ou autre
> support). **C'est précisément pourquoi la correction ne repose pas sur le
> prompt** : un prompt ne garantit rien contre une faute intermittente. Le filet
> `enforce` rend le rendu interdit **impossible à émettre**, quelle qu'en soit la
> cause. Ce qui est en revanche mesuré et corrigé, c'est l'**aveuglement au
> contexte** : le moteur ne distinguait structurellement pas les trois situations.

| **P12** 🔴 | **Filet de section pris pour un SOULIGNEMENT** (démo journal : le titre « Tech Giants Report… » n'est pas souligné — c'est un filet de séparation qui le suit) — et le faux soulignement était de surcroît **redessiné dans la couleur du TEXTE** (rouge) au lieu de celle du trait (gris) | Le seul garde-fou comparait la largeur du trait à celle du **run** (`> 1.4 × rw` ⇒ rejet). Un titre qui **remplit sa colonne** a exactement la largeur du filet (531,3 pt dans les deux cas) → ratio 1,0, garde-fou inopérant. Le seuil vertical cédait aussi de justesse (trait à 8,0 pt sous la ligne de base, seuil `0.35 × 15,1 + 3 = 8,29`) | Deux discriminants **généraux**, mesurés sur les **35 vrais soulignements** de mv21 + Handbook : (1) **l'ENCRE** — un soulignement est une décoration du TEXTE, donc peint dans SON encre (les 35 vrais : trait et texte de couleur **identique**) ; un trait d'une autre couleur ne lui appartient pas (`_same_ink`, tolérance 0,25/canal) ; (2) **les CLONES** — un filet de la grille du document a des jumeaux ailleurs sur la page (même empan, même encre, même épaisseur) ; un vrai soulignement est unique (`_rule_key` + `_RULE_FAMILY_MIN = 3`). **Corollaire** : puisque l'encre du trait doit désormais égaler celle du texte, le redessiner dans l'encre du texte est exact **par construction** — le bug de couleur disparaît avec le faux positif | Démo : **0** soulignement détecté, le filet gris est **conservé** à sa place (visuel identique à la source). Handbook : 6 → **6** (inchangé). mv21 : 29 → **27** — les 2 « perdus » étaient eux aussi des **faux positifs** (filets de séparation de lignes du tableau p22 : 6 et 15 clones gris `0,39` sous un texte noir `0,13`), que l'ancienne règle **supprimait du tableau** pour les redessiner en noir sous le texte |

| **P13** 🟠 | **Deux colonnes voisines ENTRELACÉES mot à mot** (démo journal : « Among the standout performers, *Software* / several leading semiconductor *delivered upbeat results, with* … ») → les deux encadrés fusionnés en un seul paragraphe, traduits ensemble, rendus l'un sur l'autre | La coupe en colonnes (`_COL_SPLIT_FACTOR`) juge un blanc **ligne par ligne**, donc sur sa seule LARGEUR. Or en texte **justifié**, l'espace entre deux mots enfle jusqu'à rivaliser avec la gouttière : ici la gouttière fait **8,0 pt = 2,33 × la largeur de glyphe** (sous le seuil de 2,5) alors que des espaces de mots de la même ligne atteignent **1,75 ×**. **Aucun seuil de largeur ne sépare les deux** (vérifié : relever le facteur à 3,0 déplace déjà 2 paragraphes du Handbook) | **Corridor blanc VERTICAL** (`_column_gutters`) : ce qui distingue une gouttière d'un blanc de justification n'est pas sa largeur mais sa **PERSISTANCE** — un blanc de justification se DÉPLACE d'une ligne à l'autre, une gouttière reste à la MÊME abscisse. Depuis chaque blanc candidat on remonte/descend le bloc ; le corridor meurt dès qu'une ligne le TRAVERSE. Deux garde-fous indispensables : `_GUTTER_MIN_SIDE` (texte substantiel **des deux côtés** — sinon l'indentation d'une **PUCE** forme un corridor parfait et le « • » du Handbook se détache de son texte) et `_GUTTER_MIN_LINES = 5` (sinon deux blancs de justification alignés par hasard feignent une colonne) | **mv21 : 614 → 614** et **Handbook : 309 → 309 paragraphes, au bit près.** Démo : les 2 encadrés enfin **séparés**, l'encadré gauche parfaitement rendu. **Aucun mot perdu** sur les 3 documents (631 / 10 671 / 8 615 mots identiques) |

> ### ⚠ P13 — la moitié qui RESTE, et pourquoi je ne l'ai pas forcée
>
> L'encadré **droit** de la démo demeure en miettes (« Les résul- / tats du
> logiciel », fragments superposés). Cause **distincte et antérieure** : sa
> justification est si lâche (« reshaped ␣␣␣ how ␣␣␣ businesses ») que ses blancs
> de mots dépassent `_COL_SPLIT_FACTOR` et **découpent la ligne elle-même**.
>
> Deux remèdes essayés, **tous deux rejetés par la mesure** :
> 1. **Relever `_COL_SPLIT_FACTOR`** → déplace le Handbook dès 3,0 (309 → 307,
>    puis 302 à 4,0). Refusé : on n'échange pas une régression sur un document de
>    référence contre un encadré de démo.
> 2. **Neutraliser la coupe quand la ligne porte PLUSIEURS grands blancs de taille
>    voisine** (signature d'une justification lâche) → **FAUX** : une rangée de
>    tableau à 3 cellules a exactement la même signature. mv21 p12/p16 fusionnait
>    « New York City | Long Island | Upstate » en un seul paragraphe.
>
> **Conclusion : à l'échelle de la LIGNE, une justification lâche et une rangée de
> tableau sont géométriquement indiscernables.** Il faut un signal d'un autre
> ordre (cellules `find_tables`, régularité inter-lignes des blancs) — c'est un
> chantier à part entière, pas un réglage de seuil.

## ✅ P14 — ALIGNEMENTS (2026-07-14) : centré · ferré à droite · cadre de référence

> **Constat de départ.** Le justifié était traité, le centrage l'était mal, le
> **fer à droite n'existait pas** (`reflow` ne connaissait même pas `align="right"`).

| # | Problème | Cause (mesurée) | Correction |
|---|----------|-----------------|------------|
| **P14a** 🔴 | **Un bloqueur à droite ANNULAIT le centrage** — dans une page multi-colonnes tout est borné à droite, donc **toute** légende, tout bandeau centré repassait ferré à gauche (démo : « Trading floor at the New York Stock Exchange », blancs de **201 pt de chaque côté**, rendu à gauche) | `if centered and right_block != inf: centered = False` — l'objet ne bornait pas le conteneur, il **détruisait l'alignement** | Un bloqueur **BORNE**, il n'annule pas. Ajout de `left_block` (**symétrique** du `right_block` : il n'existait aucun bloqueur gauche). Le conteneur d'un bloc centré s'étend des **deux** côtés, jusqu'au 1er objet de chaque côté |
| **P14b** 🟠 | Bloc **parfaitement symétrique** non centré (démo : « BREAKING NEWS », blancs de **92,8 pt de chaque côté**) | Le seuil mono-ligne exigeait des marges `> 0.18 × col_w` = 95,6 pt → **raté de 2,8 pt** | On assouplit la TAILLE exigée (`0.10 × col_w`) et on **durcit la SYMÉTRIE** en échange : le vrai signal n'est pas la taille des blancs, c'est leur égalité |
| **P14c** 🔴 | **Cadre de référence faux** : une cellule de tableau prenait la **largeur de PAGE** pour cadre → son texte paraissait centré (démo : « Fiches produits et avis clients », blancs de 219 / 227 pt vers les bords de la page) | Aucune hiérarchie de cadres — `col_left`/`col_right` venaient des voisins, pollués par les blocs pleine largeur | **Hiérarchie** : cellule `find_tables` → boîte contenante (panneau) → colonne. Un alignement n'a de sens que **dans une boîte** |
| **P14d** 🟠 | Détection multi-ligne par un signal **indirect** (variance des bords gauches), qui manquait des cas | — | **Taxonomie par VARIANCES** : le bord le plus STABLE trahit l'alignement (`vG` min → gauche, `vD` min → droite, `vC` min → centré). **Sans cadre**, donc immunisée à une colonne polluée — c'est ce qui fait échouer toute mesure par les blancs |
| **P14e** 🔴 | **`align="right"` inexistant** : détection ET rendu | — | `reflow` : offset `right − x` (symétrique exact du centrage). Conteneur : bord droit **FIGÉ**, expansion **vers la GAUCHE** (le CONTEXTE disait « jamais vers la gauche » — ce n'est plus vrai) |
| **P14f** 🟠 | Un bloc ferré à droite (adresse, date) était **fusionné** par l'Étape A puis recoulé en une seule ligne | La règle « espace restant » protège le « texte qui coule » dès que **≥ 2 lignes partagent le bord droit** — or c'est aussi la signature d'un fer à droite | Une colonne qui coule est à fleur des **DEUX** bords. Si les gauches sont déchiquetées et les droites alignées, les retours sont **VOLONTAIRES** → coupe |

### Ordre de décision (le fer à droite se juge EN PREMIER)

1. **Garde d'ENROULEMENT** (P5) — un bloc qui chevauche partiellement le paragraphe explique des bords variables : **ni centré, ni droite**.
2. **DROITE** — `vD ≤ tol` **et** `vG ≥ franc`. *Avant justify* : un bloc ferré à droite a ses bords droits à fleur, et il suffit que deux de ses bords gauches tombent près l'un de l'autre par hasard (adresse du test : **438 / 440 / 467**) pour qu'il paraisse ferré à gauche. Le vrai discriminant est le bord **GAUCHE**.
3. **CENTRÉ** — `vC ≤ tol` et les **deux** bords francs.
4. **JUSTIFIÉ** — inchangé (ferré à gauche + lignes intérieures au même bord droit).
5. **GAUCHE** — défaut.

**Mono-ligne** (pas de variance) : centré par la **symétrie** de ses blancs dans son cadre ; ferré à droite par sa **PILE** — une ligne seule ne peut rien dire d'elle-même, ce sont ses voisines verticales qui parlent (elles partagent son bord droit, leurs gauches se dispersent). Garde-fou : **adossé au bord droit de son cadre** — sans lui, l'en-tête courant de mv21 (« 6 | Driver's Manual », collé à la marge **gauche**) passait pour ferré à droite.

**Texte incliné** : aucune inférence — cette géométrie est mesurée en x, or son axe d'écriture est l'autre (les en-têtes pivotés de la démo ressortaient « centrés »).

### Vérification

| | Avant | Après |
|---|---|---|
| **mv21** | left 576 · justify 34 · center 4 | left 560 · justify **34** · center **20** |
| **Handbook** | left 211 · justify 94 · center 4 | left 194 · justify **94** · center 4 · **right 17** |
| **démo** | left 37 · justify 5 · center **0** | left 35 · justify **5** · center **2** |

- **`justify` strictement inchangé** sur les 3 documents · **segmentation au sha1 près** (614 / 309 / 42).
- mv21 p3 (affiche du don d'organes) : **entièrement centrée à la traduction** — elle était intégralement rendue au fer à gauche. Démo : « FLASH INFO » centré dans son bandeau, légende de photo centrée.
- Handbook : les 17 « droite » sont les **folios de page** et une ligne de filigrane — tous légitimes.
- **Aucun** bloc multi-ligne ferré à droite dans les 3 documents → `align="right"` est validé sur le **document synthétique** (`test_engine_v2_generic.py`, **19/19**).

## ✅ P15-P17 — COLONNE JUSTIFIÉE ÉTROITE : le mot arraché à sa phrase (2026-07-16)

> **Le symptôme.** Démo journal, 3ᵉ colonne : « Software providers also » sortait
> en **trois paragraphes** (« Software » soudé au bloc, « providers » et « also »
> en îlots), et « reshaped how businesses » de même. Envoyés seuls au traducteur,
> hors contexte, ces mots ressortaient faux.
>
> **La cause.** Justifier une colonne étroite, c'est étirer ses blancs de mots
> jusqu'aux deux bords. Étroite, la colonne offre peu de blancs : chacun enfle
> énormément — **13,9 pt** pour une largeur de glyphe de 3,4 (**4,3 ×**, très
> au-delà du seuil de coupe de 2,5 ×), soit **plus large que la vraie gouttière
> de la page** (13,7 pt). À l'échelle de la LIGNE, un blanc de mot et une
> frontière de colonne sont **géométriquement indiscernables**. Aucun seuil ne
> les sépare.

**Pourquoi un veto de persistance ne marche pas** (piste explorée, abandonnée —
ne pas la reprendre) : « pas de corridor vertical → pas de coupe » fait du
corridor l'**unique juge**, or il lui faut `_GUTTER_MIN_LINES` (5) lignes pour se
prononcer. Handbook p20 : une citation encadrée de **4 lignes**, enjambée par le
corps voisin (leurs lignes de base se touchent), est trop courte pour former un
corridor → absoute à tort → **absorbée par le corps**. *L'absence de preuve de
colonne n'est pas la preuve de son absence.*

| # | Problème | Cause | Correction | Vérification |
|---|----------|-------|------------|--------------|
| **P15** 🔴 | Colonne justifiée étroite : les mots à gros blanc **arrachés à leur phrase** | Le blanc de justification dépasse `_COL_SPLIT_FACTOR` ; indiscernable d'une gouttière à l'échelle de la ligne | **On ne disculpe plus le blanc, on PROUVE la justification** — par les marges du BLOC, que la ligne seule ignore. `_justified_columns` : une colonne est **avérée** par ≥ 3 lignes **intactes** au même fer gauche ET droit ; `_rejoin_justified` ne recolle une rangée que si ses fragments **remplissent cette colonne de bord à bord**. Itère jusqu'au point fixe (une rangée recollée devient un témoin de plus) | Démo 42 → 38 paragraphes, bloc reconstitué mot pour mot. hb p20 recollerait [63,5 → 561,2] : ne correspond à **aucune** colonne (63,5 = fer de la citation, 561,2 = fer du corps) → coupe maintenue ✅ |
| **P16** 🟠 | `_column_gutters` fabrique des **corridors FANTÔMES** qui coupent le texte | **Le VIDE était compté comme preuve.** Les rangées traversent toute la page (4 colonnes partagent leurs lignes de base) ; là où une colonne s'arrête, l'abscisse du corridor tombe dans une vaste zone vide et la rangée « confirmait » quand même. `_gutter_sides_ok` (page-entière) passait toujours | `_gutter_abuts` (`_GUTTER_ABUT_FACTOR = 4.0` gw) : une rangée ne prouve un corridor que si du **texte le BORDE des deux côtés** ; sinon on l'**enjambe** — ni preuve, ni réfutation. Seul du texte qui **traverse** réfute | Démo : **8 corridors → 2**. La gouttière porteuse col2/col3 (8,0 pt — la seule utile des 51 pages) a **10** rangées bordantes et survit ; les 3 fantômes n'en avaient que **1-2**. Sortie inchangée (P15 masquait déjà les dégâts) → prouvé **en boîte blanche** |
| **P17** 🔴 | Un **CHAPÔ justifié pleine largeur** soude les 4 colonnes en charabia | **Bug introduit par P15**, trouvé en sondant ses limites. L'auto-cohérence de P15 (« aucune ligne ne traverse une gouttière, donc aucun témoin ne peut nuire ») ne vaut **que pour le bloc qui fournit la preuve** : un chapô pleine largeur atteste à lui seul le couple (fer gauche de col1, fer droit de la dernière), et les rangées des colonnes sont bel et bien à fleur de ces deux fers | **Priorité à la colonne avérée PLUS ÉTROITE** : un fragment qui remplit exactement une colonne plus étroite **EST une ligne de cette colonne** — le recoller reviendrait à traverser une gouttière | Prototype chapô : soudure (« Regional plants raised output Regional plants raised… ») → 5 blocs distincts ✅ |

### Garde-fous de `_rejoin_justified` (chacun payé cash)

- **`_JUST_EDGE_FACTOR = 0.05`** (tolérance de fer). À 0,25 × corps (3,75 pt au
  corps 15), le **folio** du Handbook (x1 = 558,0) passait pour le fer droit du
  corps (561,16) → **« DJ PATIL » soudé à « 15 » sur 21 pages**. La justification
  est exacte au centième de point : rester serré ne coûte rien.
- **`_JUST_MIN_INK = 0.5`** — une ligne justifiée est faite de mots que le blanc
  écarte, pas de blanc que deux mots bordent (démo : 71 % d'encre ; ligne
  synthétique la plus lâche : 73 % ; titre courant + folio : **18 %**).
- **Encre** (`_ink_walls`) — un filet, un cadre ou une image qui s'intercale
  sépare pour de bon, quoi que dise la géométrie (mur de cellule de tableau).
- **`_JUST_MIN_LINES = 3`** — **mesuré, pas arbitraire** : à **1**, le *titre*
  pleine largeur de la démo (une seule ligne) atteste à lui seul une colonne
  32 → 563 et **soude les 4 colonnes** (14 lignes d'inventaire ravagées). À **2**,
  identique à 3 sur les 51 pages. On garde **3** (marge).

## ✅ P18 — LÉGENDE : centrage manqué + débordement sur la colonne (2026-07-16)

> **Le symptôme** (démo journal, signalé sur le rendu) : la légende
> « Les consommateurs retournent dans les centres-villes… » n'est pas centrée
> sous sa photo et **déborde sur la colonne voisine**. Deux symptômes, **une
> seule cause**.
>
> **La cause.** Une légende se pose **SOUS** sa photo, jamais dedans : la « boîte
> contenante » (P14) ne la voit donc pas, et elle retombe sur sa *colonne*. Or
> la colonne se déduit des paragraphes qui chevauchent le bloc, **sans aucune
> fenêtre verticale** : le titre pleine largeur « Tech Giants Report… »
> [32 ; 563], à **480 pt au-dessus**, chevauche la légende [87 ; 232] et commence
> à sa gauche → il lui impose `col_right = 563`. **La « colonne » d'une légende,
> c'était la PAGE.**

| Légende | Cadre retenu | lg / rg | Verdict |
|---|---|---|---|
| Trading floor | page [32 ; 563] | 201 / 201 | ✅ centrée… **par pur hasard** (son panneau est centré sur la page) |
| Shoppers return | page [32 ; 563] | 55 / **331** | ❌ `left`, conteneur [87 ; **351,9**] → déborde (photo : [32 ; 287,6]) |
| Federal Reserve | page [32 ; 563] | **332** / 56 | ❌ `left` |

**Correction** — `_overhead_frame` : l'**illustration collée au-dessus** révèle la
colonne de la légende (elle en occupe la largeur). L'objet doit être un **BLOC**
(≥ 1 corps de haut *et* de large — un filet n'est pas une illustration),
**toucher** la légende (≤ `_CAPTION_GAP_FACTOR = 1.5 × corps`), la **contenir**
horizontalement, et **SERRER** le cadre courant. Ce dernier point est le
garde-fou : la règle ne peut que resserrer — elle prolonge la hiérarchie
existante (cellule → boîte → colonne), où le plus serré gagne ; un bandeau
pleine largeur n'y gagne rien. Le cadre borne **aussi `ref_right`** : un cadre ne
vaut que si ses **deux** bords tiennent, sinon la légende se recentre de travers
(191,9 au lieu de 159,8) et déborde quand même.

### 🔴 Piste ÉCARTÉE : corriger l'estimation de colonne (fenêtre verticale)

C'est la cause *racine*, et c'était tentant. **Mesuré : trop large.** Ajouter une
fenêtre verticale (+ les objets) au balayage de colonne touche **410 conteneurs
sur 886** (écart médian 5,7 pt, max 345,7) et **casse des cas déjà réglés** :
privé de ses voisins, l'en-tête courant de mv21 « 6 | Driver's Manual » repassait
**ferré à droite** — le bug même qu'un commentaire du code documente comme
corrigé — et son conteneur doublait (190,8 → 377,8) ; « Sold to » (hb p1) perdait
son fer à droite. Le correctif retenu, lui, touche **exactement 3 paragraphes sur
886** : les 3 légendes. Ne pas rouvrir sans un plan pour l'en-tête courant.

**Vérification** : 3 paragraphes changent sur 51 pages (les 3 légendes) ; au
rendu, avec les vraies légendes françaises (plus longues), les 3 tombent sur
l'axe de leur photo à **±0,0 pt**. Test P18 (page 5 synthétique) : photo
**décentrée** dans la page (axe 180 vs 306) pour qu'un centrage-page ne puisse
pas passer par hasard, + titre pleine largeur qui empoisonne la colonne.

## 🧪 AUDIT DE GÉNÉRICITÉ (2026-07-13) — `backend/test_engine_v2_generic.py`

> **Le problème de fond.** P10-P13 ont été trouvés sur mv21, le Handbook et la
> démo journal. **Rien ne prouvait qu'ils traitaient la CLASSE du problème plutôt
> que ces trois fichiers.** Un correctif calé sur ses documents de découverte
> laisse le défaut ressortir au premier PDF venu — exactement ce qu'on veut éviter.
>
> **La preuve.** Un PDF **synthétique**, que le moteur n'a jamais vu (autre police
> — Times ; autres corps, autres couleurs, autre format — Letter ; autres
> coordonnées), rejoue les MÊMES STRUCTURES : titre pleine colonne + filet de
> section · vrai soulignement · deux colonnes à gouttière plus étroite que leurs
> propres blancs de justification · liste à puces · titre vertical à lettres
> espacées · en-têtes de tableau pivotés serrés. **13 contrôles, 13 verts.**
>
> _Étendu le 2026-07-16 à **5 pages / 31 contrôles** (P15-P18) : colonne étroite
> justifiée · citation enjambée par le corps voisin (contre-épreuve hb p20) ·
> filet vertical dans le blanc · corridor fantôme nourri par le vide · chapô
> pleine largeur au-dessus de 4 colonnes · légende sous une photo décentrée.
> Le texte justifié y est **composé**
> (coupe au plus juste puis étirement des blancs), et non posé à la main : les
> lignes lâches apparaissent d'elles-mêmes, comme dans un vrai document._

**Le test a débusqué deux trous que les 3 documents réels masquaient** — c'est
précisément ce qu'on lui demandait :

| # | Trou | Pourquoi les vrais documents le masquaient | Correction |
|---|------|--------------------------------------------|------------|
| **P10-bis** 🔴 | Titre vertical rendu **collé** (« APPENDIXSECTION ») → le traducteur recevait un mot inexistant | `_make_rotated_line` **concaténait brutalement** les runs. mv21 s'en sortait par chance : ses runs PORTAIENT l'espace dans leur texte (« ␣O »). Un titre dont la frontière de mot est purement **géométrique** sortait collé | `_compose_rotated_text` : espace insérée là où l'écart, mesuré **le long de l'axe**, dépasse franchement le pas médian entre lettres (signal général : le pas entre MOTS est nettement plus grand que le pas entre LETTRES). `_axis_gw` mesure aussi la largeur de glyphe sur l'axe |
| **P13-bis** 🟠 | **Puce détachée de son texte** dès que le retrait dépasse `_COL_SPLIT_FACTOR` | Le Handbook y échappait **de justesse** (son retrait est un peu plus serré que le seuil). J'avais protégé le CORRIDOR contre les puces, mais **pas la coupe de largeur** | Même garde-fou sur la coupe de largeur. Réserve indispensable : le marqueur doit être une **PUCE** ou un **numéro ponctué** (`_BULLET_RE` / `_NUMITEM_RE`) — un **nombre nu** n'en est pas un, c'est une donnée. Sans cette réserve, le sommaire de mv21 fusionnait « 6 » avec « Chapter 1 – Driver Licenses » (−31 paragraphes) |

### Verdict par correctif

| # | Le signal est-il générique ? | Limite connue |
|---|------------------------------|---------------|
| **P10** | ✅ **Oui** — transformation de repère (mathématique pure, toute direction) ; empan et pas mesurés **le long de l'axe** ; conteneur ancré sur la bbox (l'expansion page est *perpendiculaire* pour un vertical). Aucun seuil calé sur un document | Validé sur des rotations à **90°**. Un angle quelconque (45°) passerait par le même code, mais la bbox du conteneur dans le repère tourné serait une **sur-approximation** |
| **P11** | ✅ **Oui** pour le `support` (corps dominant de la page, ratio 1,5 — aucune constante de document). ⚠️ **Non** par nature pour le glossaire : il est **énumératif**, et c'est assumé (cf. l'encadré P11 — une garantie exige un ensemble décidable) | Les 14 entrées muettes ne garantissent plus que par leur filet ; rejouer le banc à tout changement de modèle |
| **P12** | ✅ **Oui** — l'encre (un soulignement est peint dans l'encre de SON texte) et les clones (un filet de grille se répète) sont des propriétés **du concept**, pas des documents. Vérifié sur 35 vrais soulignements + le synthétique | Un soulignement d'une couleur **différente** de son texte serait rejeté ; un filet **isolé** de la **même** couleur passerait encore. Levier connu : les annotations `/Link` |
| **P13** | ✅ **Oui** sur le principe — la **persistance** du corridor est une propriété du concept (un blanc de justification se déplace, une gouttière non). ⚠️ **Mais la mise en œuvre comptait le VIDE comme preuve** : corrigé par P16 (cf. ci-dessus). Le verdict « garde-fous génériques » était **trop optimiste** — `_gutter_sides_ok` est inopérant sur une rangée page-entière (il y a toujours du texte des deux côtés, très loin) | `_GUTTER_MIN_LINES = 5` : un bloc à **deux colonnes de moins de 5 lignes** ne sera pas détecté (plancher conservateur). Depuis P16, le quorum se compte sur les rangées **bordantes** : une gouttière dont les deux colonnes se croisent sur < 5 lignes de base (interlignes différents) n'est plus détectée — inoffensif tant que la coupe de largeur la rattrape (vérifié : 0 régression sur 51 pages) |
| **P15** | ✅ **Oui** — la preuve est une propriété du **concept** de justification (le fer aux deux bords), pas d'un document. Le témoin est la **ligne intacte**, qui ne peut pas exister à travers une gouttière. Aucun seuil calé sur un document ; `_JUST_MIN_LINES` mesuré (cf. ci-dessus) | 🔴 **Colonne justifiée de ≤ 5 lignes non réparée** : il faut ≥ 3 lignes intactes pour attester la colonne, or une colonne étroite en a ≈ 55 % (démo : 6/11). Un bloc de 4 lignes n'en a qu'**1** → reste éclaté. Vérifié sur cas construit. **Ne PAS attester la colonne par les FRAGMENTS** (leurs fers) : c'est exactement ce qui rouvre P17 et hb p20 |
| **P16** | ✅ **Oui** — « le vide n'est pas une preuve » est une règle de raisonnement, pas un réglage. Une rangée sans texte bordant est **enjambée**, comme une ligne trop courte | Le corridor reste jugé sur des rangées **page-entière** : la cause structurelle (pas de notion de bloc dans `_column_gutters`) n'est pas traitée, seul son amplificateur l'est |
| **P17** | ✅ **Oui** — « la colonne la plus étroite gagne » découle de la définition d'une gouttière. **Leçon** : l'auto-cohérence d'une preuve ne vaut que pour **le bloc qui la fournit** ; un témoin venu d'un autre bloc n'autorise rien | Repose sur le fait que les colonnes voisines soient elles-mêmes **avérées** (≥ 3 lignes intactes chacune). Des colonnes courtes surmontées d'un chapô pleine largeur resteraient exposées |

### Batterie de vérification (à rejouer avant toute release)

```bash
backend/venv/Scripts/python.exe backend/test_glossary.py            # 18/18
backend/venv/Scripts/python.exe backend/test_engine_v2_generic.py   # 31/31
```
Invariants de non-régression sur les documents réels (24 pages chacun) :
**mv21 = 614 paragraphes · Handbook = 309 · démo = 38** (42 avant P15 : les 4
paragraphes en moins sont les **fragments recollés** de la 3ᵉ colonne — c'est le
correctif, pas une perte), et **aucun mot perdu** (631 / 10 671 / 8 615).
Soulignements consommés : **mv21 = 27 · Handbook = 6 · démo = 0**. Toute dérive
de ces nombres est une régression jusqu'à preuve du contraire.

> **Les contrôles négatifs sont la moitié du test** (2026-07-16). Chaque règle de
> P15-P17 a son script qui la **désarme seule** ; le check visé DOIT alors tomber :
> recollage 28/31 · encre 30/31 · bordant 30/31 · colonne-étroite 30/31 ·
> cadre-légende 28/31. Sans eux,
> **trois assertions passaient à vide** (elles ne prouvaient rien) — dont le
> contrôle « le piège est armé », qui mesurait les lignes *après* réparation et
> dépendait donc du correctif qu'il devait juger. Un test qui ne tombe jamais ne
> teste rien.

## ⏳ Résiduels (documentés, non bloquants)

- 🔴 **EN SUSPENS (décidé le 2026-07-16) — colonne justifiée étroite de ≤ 5
  lignes non recollée.** `_rejoin_justified` exige **3 lignes intactes** pour
  attester la colonne ; un bloc court n'en fournit qu'une ou deux. Exemple
  mesuré (même texte, même largeur, seule la longueur change) :

  | Bloc | Lignes intactes | Résultat |
  |---|---|---|
  | 11 lignes | 8 | ✅ 1 paragraphe |
  | 4 lignes | 1 | ❌ 3 morceaux (`'providers how'`, `'also regional'`…) |

  **Abaisser le quorum n'est PAS la solution** : à 1 témoin, le titre pleine
  largeur de la démo soude les 4 colonnes. Le compromis est assumé — *exigence
  stricte → quelques blocs courts restent cassés ; exigence relâchée → des pages
  entières deviennent illisibles.* C'est aussi l'**état d'avant P15** (aucune
  régression). Conditions cumulatives (colonne étroite **+** justifiée **+**
  ≤ 5 lignes) : **0 occurrence** sur les 51 pages de référence. Traiter ce cas
  demanderait une preuve d'une **autre nature** (cellules de tableau détectées,
  interligne du bloc) — chantier, pas réglage.
- **Retraduction compacte mv21 partielle** : la phase compacte a été interrompue
  (erreurs de connexion API en série) — la traduction principale est complète et
  saine ; certains items de listes denses restent compressés (force-fit) au lieu
  d'être reformulés. Relance en une commande : `run_translate20.py` (le cache
  `*_tr20.json` est réutilisé, seuls les paragraphes trop longs repartent).
- **« PART TWO »** (mv p4) : la ligne est bien traduite (« – Règles de la
  route ») mais le modèle a conservé « PART TWO » (incohérence de traduction,
  pas un bug technique).
- **« Go the extra mile, be an ORGAN DONOR »** (mv p3) : titre stylisé traité
  hors reflow → rendu original (limite assumée du CONTEXTE).
- **Paragraphe trans-page** (mv p18→19) : un paragraphe coupé par le bas de page
  est traduit par page → le fragment pendant (« Your foreign ») devient « Votre
  permis étranger » en fin de page. Nécessiterait une couture inter-pages
  (nouvelle fonctionnalité).
- Trous verticaux résiduels quand une traduction est plus courte (pas de
  remontée de blocs — le flux vertical reste volontairement désactivé).

## 🧰 Outils de vérification (scratchpad de session)

- `repro_cesure.py` — repro isolé P2 (0 débordement attendu).
- `check_overflow.py` — instrumente `reflow._layout` et rejoue les 2 docs :
  compte les violations de bord droit (attendu : 0).
- `check_seg.py` — vérifie P6/P7 sur les extractions fraîches.
- `check_fonts.py` — intégrité (encre) + hauteur d'x des polices assorties.
- `repair_overshort.py` — retraduit normalement les paragraphes sur-abrégés
  d'un cache (< 0,75× la source).
- `run_translate20.py` — pipeline complet 20 pages (cache, vérif par item,
  retraduction compacte, réinjection + debug).

## 📎 Reproduction

```powershell
$env:PYTHONIOENCODING='utf-8'
backend\venv\Scripts\python.exe -m pdf_engine_v2.cli extract "backend\tests files\mv21.pdf"
backend\venv\Scripts\python.exe <scratchpad>\run_translate20.py "backend\tests files\mv21_objects.json" "backend\tests files\mv21_traduit_p1-20.pdf" 20
```
