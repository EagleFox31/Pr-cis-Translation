# Problèmes identifiés — Moteur de traduction PDF (`pdf_translator_engine.py`)

> Fichier de suivi des bugs, limitations et axes d'amélioration.
> À remplir au fur et à mesure de l'analyse et des tests.
>
> _Dernière mise à jour : 2026-06-09_

## 📋 Légende des priorités

| Priorité | Signification |
|----------|---------------|
| 🔴 **Critique** | Bloque la fonctionnalité, produit un PDF corrompu ou une perte de données |
| 🟠 **Élevée** | Résultat incorrect visuellement ou fonctionnellement |
| 🟡 **Moyenne** | Comportement non-optimal, cas limite non géré |
| 🔵 **Faible** | Amélioration cosmétique ou refactor souhaitable |
| ⚪ **Info** | Comportement volontaire mais à documenter |

---

## 🔴 Critiques

| # | Problème | Fichier / Ligne | Statut |
|---|----------|-----------------|--------|
| C1 | **Crash `inject_translation()` sur `format_options`** — `app.py` appelle les trois moteurs avec `format_options=…`, mais les moteurs `*_translator_engine.py` n'acceptaient pas ce paramètre → `TypeError: inject_translation() got an unexpected keyword argument 'format_options'`. Bloquait **toute** génération (PDF, DOCX, PPTX). **Corrigé :** ajout du paramètre `format_options=None` aux signatures des trois moteurs (accepté pour compatibilité ; non encore exploité — voir note N1) | `pdf_translator_engine.py` · `docx_translator_engine.py` · `pptx_translator_engine.py` | ✅ Corrigé |

## 🟠 Élevées

| # | Problème | Fichier / Ligne | Statut |
|---|----------|-----------------|--------|
| 1 | **Puces / listes perdues** — (a) filtre `re.search(r'[a-zA-Z0-9]', text)` ignorait les lignes commençant par une puce → remplacé par `strip()` + `_detect_bullet()` + `_extract_bullet()`. (b) **Puce diamant `❖` (U+2756) rendue en point `·`** : le glyphe réel du document (police *SegoeUISymbol*) n'était pas dans `BULLET_CHARS` (seul `◆` U+25C6 y figurait), et les 14 polices PDF de base ne contiennent aucun symbole → substitution en `·`. **Corrigé :** embarquement d'une police Unicode (`_embed_font_for` / `_insert_text_smart`, ex. `seguisym.ttf`) pour rendre fidèlement tout glyphe hors base-14 ; ajout des losanges à `BULLET_CHARS` ; correction du saut des blocs « puce seule » (texte propre vide) qui faisait disparaître le marqueur | `pdf_translator_engine.py` | ✅ Corrigé |
| 2 | **Texte souligné (underline) ignoré** — Dans les PDF générés par Word, le soulignement n'est ni un attribut de texte (`char_flags` ne le contient pas) ni un trait vectoriel, mais un **fin rectangle plein** (`type='f'`, item `'re'`, hauteur ≈ 1 pt). La détection ne regardait que les traits `type='s'`/`'l'` → underline jamais détecté. **Corrigé :** collecte des segments horizontaux fins issus des traits **et** des rectangles pleins via `get_cdrawings()`, rattachés aux spans par proximité verticale (juste sous la baseline) + recouvrement ≥ 30 %. **Garde-fou anti-faux-positifs :** règle d'alignement horizontal pour rejeter les lignes de grille de tableau (qui débordent jusqu'au bord de colonne). Réinjection via `_draw_underline()` (≈ 1.5 pt sous baseline, couleur/épaisseur proportionnelles, support rotation) | `pdf_translator_engine.py` (détection à l'extraction) | ✅ Corrigé |
| 3 | **Phrases multi-lignes traduites ligne par ligne** — Une phrase sur plusieurs lignes produisait N spans indépendants, traduits séparément → disposition cassée. **Corrigé :** regroupement des spans en paragraphes à l'extraction (`_group_paragraphs`, bbox unifiée, texte complet traduit d'un coup), réinjection via `insert_textbox`. **Sous-cas couverts :** (a) détection d'alignement gauche/centre/droite (`_detect_alignment`) ; (b) **paragraphes pivotés** (titres verticaux de tableau) regroupés dans leur repère + rendus via `insert_textbox(rotate=90/270)` ; (c) **libellé en ligne** (« Base de données : MySQL… ») → retrait de 1re ligne (`_insert_indented_paragraph`, conteneur en « L ») pour ne pas écraser le libellé ; (d) **puces en police symbole** (ZapfDingbats « O » = ❖) reconnues (`_is_marker_span`), rattachées au texte de leur ligne (fusion wrap correcte) et rendues via `zadb`, sans décalage du texte (puce séparée ≠ puce collée) | `pdf_translator_engine.py` (extraction + réinjection) | ✅ Corrigé |
| 4 | **Plus de redimensionnement de police — reproduction fidèle** — Décision finale : on NE réduit ni n'agrandit **jamais** la police. `_fit_fontsize()` renvoie toujours la taille d'origine ; les trois chemins de rendu (`_insert_paragraph`, `_insert_rotated_paragraph`, `_insert_indented_paragraph`) dessinent à taille fixe et **agrandissent la boîte** (vers le bas / dans le sens du wrap) si le texte traduit est plus long. Validé : tailles rendues = tailles d'origine à l'identique (no-op rendu strictement identique à l'original), y compris texte doublé. La gestion de l'espace est déléguée à la passe de mise en page (#5/#6) | `pdf_translator_engine.py:_fit_fontsize` + `_insert_*paragraph` | ✅ Corrigé |
| 5 | **Passe de mise en page (reflow vertical conservateur)** — recalcul des positions après traduction : un paragraphe plus court rétrécit et les blocs suivants de la **même colonne** remontent (écarts d'origine préservés) ; plus long, ils descendent dans l'espace libre. **Implémenté :** `_reflow_page` / `_reflow_column` — modèle d'occupation (tableaux via grille H+V, fonds pleins hors fond de page, marges), classification (texte libre uniquement), détection de colonnes (union-find par recouvrement x), hauteur mise à l'échelle par **ratio de lignes** (no-op = 0 dérive), garde-fous anti-collision (rejet seulement si NOUVELLE) avec repli « vers le haut » puis position d'origine. **Hors périmètre (v1) :** tableaux, fonds colorés, images, multi-colonnes croisées → restent en boîte fixe ; pas de repagination | `pdf_translator_engine.py:_reflow_page` | ✅ Corrigé (v1) |
| 6 | **Élargissement horizontal (règle 1)** — Quand la traduction d'un paragraphe multi-lignes est **plus longue** (ex. blocs fusionnés), on agrandit d'abord sa boîte vers la **droite** dans l'espace libre — *juste assez* pour qu'elle retrouve son nombre de lignes d'origine (donc sa hauteur), avant tout déplacement vertical. **Implémenté :** `_expand_widths` + `_min_width_x1` (dichotomie sur la largeur), exécuté en amont du reflow vertical dans `_reflow_page`. Marge droite symétrique à la marge gauche, écart min. 6 pt préservé avec tout voisin, obstacles = autres blocs + tableaux + fonds (jamais d'empiètement ni d'effacement de voisin). `_old_bbox` posé pour effacer l'aire d'origine uniquement. **Périmètre :** paragraphes **gauches, horizontaux, multi-lignes** ; centrés/droite et cellules de tableau exclus. **Ordre de priorité prévu :** 1️⃣ horizontal (fait) → 2️⃣ vertical (#5, fait) → 3️⃣ réduction proportionnelle de police (à venir, dernier recours) | `pdf_translator_engine.py:_expand_widths` | ✅ Corrigé (règle 1) |
| 7 | **Reflow inline — refermeture des trous (texte plus court)** — Quand un bloc **mono-ligne** rétrécit (traduction plus courte), son voisin **directement adjacent sur la même ligne** (chaîne inline, écart ≈ 0 : « Société – Poste », « label : valeur ») se décale à **gauche** de `x = réduction` pour refermer le trou « espace blanc sans texte » ; symétriquement à droite s'il s'allonge (borné anti-collision, tout-ou-rien). **Implémenté :** `_reflow_inline` + `_apply_inline_chain` dans `_reflow_page` (après fusion multi-ligne). Détection : horizontal, hors tableau, même ligne de base (tol. 0,4×taille), écart ≤ 0,6×taille (les voisins à grand écart = **colonnes** ne sont jamais déplacés). **Cas valeur multi-ligne (« Base de données : MySQL… » → « Databases »)** : un maillon **terminal multi-ligne à 1ʳᵉ ligne indentée** est accepté — on le repère via `first_x` (et non `bbox[0]`, qui est la marge de retour) et on décale **uniquement `first_x`** (la 1ʳᵉ ligne suit le libellé ; les lignes de retour restent à la marge ; bbox inchangée). Largeurs estimées en **proportionnel** (largeur réelle d'origine × ratio longueur traduite/source) → biais des métriques gras/embarquées annulé, no-op = 0 dérive. Ancre fixe, écarts d'origine préservés, `_old_bbox` posé. **Validé :** voisins inline + valeur multi-ligne recollés sans trou, maquette 2 colonnes intacte, no-op identique (0 bloc déplacé) | `pdf_translator_engine.py:_reflow_inline` | ✅ Corrigé |

| 8 | **Police d'origine non conservée (écrasée en Helvetica)** — `_map_font()` réduisait **toute** police à une des 14 polices PDF de base (helv/times/cour), et `_embed_font_for()` n'embarquait un vrai fichier **que** pour les glyphes hors Latin-1 (symboles). Résultat : un document en **Calibri / Segoe UI / Verdana / Cambria…** ressortait en **Helvetica** (la « base des bases » non respectée). **Corrigé :** nouveau résolveur `_resolve_family_font(font_raw)` qui mappe la famille d'origine + variante (gras/italique, détectée dans le nom de police) vers le **fichier système** correspondant (`_FONT_FAMILY_FILES` : Calibri, Carlito, Cambria, Segoe UI, Georgia, Verdana, Tahoma, Consolas, Trebuchet, Comic Sans, Courier New, Candara, Constantia, Corbel, Garamond…). `_embed_font_for()` embarque désormais cette police pour **tout** texte (latin inclus), pas seulement les symboles. Les familles déjà fidèles en base-14 (**Helvetica / Times / Courier / Arial**) restent en base-14 (pas d'embarquement inutile → zéro régression). Un seul point de changement propagé à tous les chemins de rendu (`_insert_*`, `_text_length`, `_wrap_line_count`). **Validé :** PDF Calibri → sortie embarque Calibri Regular/Bold (rendu Calibri visible) ; CV Helvetica → sortie inchangée (base-14, non embarqué). **Limite :** dépend des polices système (voir N2) ; gras/italique détecté via le nom de police (fiable pour exports Word/LibreOffice).<br>**Extension (polices web absentes du système, ex. Merriweather + Open Sans embarquées mais sous-ensemblées) :** les polices embarquées dans le PDF source sont des **sous-ensembles incomplets** (il manque les glyphes absents du texte d'origine : `j z J K W X Z`, chiffres… → ☒ dans la traduction) → **inutilisables telles quelles**. Résolution en 3 niveaux : (1) `backend/fonts/` — vraie police complète déposée par l'utilisateur (fidélité exacte) ; (2) police système de même nom ; (3) **substitut de même classe serif/sans/mono** (`_FONT_SIMILAR` : Merriweather→Georgia, Open Sans/Roboto/Lato/Montserrat…→Segoe UI, mono→Consolas). **Validé sur document réel :** nom+corps serif (Merriweather→Georgia), contacts sans (Open Sans→Segoe UI), titres serif italique — la **combinaison multi-polices est restaurée** (avant : tout en Helvetica) | `pdf_translator_engine.py:_resolve_family_font` + `_embed_font_for` | ✅ Corrigé |

| 9 | **Inventaire des polices à l'extraction** — Ajout d'un diagnostic `extraction["fonts"]` calculé pendant l'extraction (PDF ouvert), **sans rien installer** : pour chaque police → `embedded` (embarquée ?), `subset` (sous-ensemble ?), `embedded_covers_ascii` (le sous-ensemble couvre-t-il A-Z/a-z/0-9 ? sinon glyphes manquants à la traduction), `match` (bundled / base14 / system / similar / symbol / fallback), `render_as` (substitut effectif) et `exact` (fidélité). Un avertissement `progress_callback` liste les polices qui seront **substituées** (à déposer dans `backend/fonts/` pour l'exact). **Implémenté :** `_font_inventory()` + `_font_resolution_info()`, appelés dans `extract_text`. **Validé :** sur le CV réel, signale Merriweather/Open Sans comme `embedded+subset, ascii=False, similar→Georgia/Segoe UI, exact=False` et ArialMT comme `base14, exact=True` | `pdf_translator_engine.py:_font_inventory` | ✅ Ajouté |

| 10 | **Téléchargement automatique des polices manquantes (Google Fonts)** — Pour les polices web absentes du système (Merriweather, Open Sans, Roboto…), récupération automatique de la **vraie** police pour une fidélité exacte (au lieu du substitut serif/sans). **Implémenté :** `_ensure_font()` + `_download_google_font()` — télécharge la police **variable** depuis le dépôt `google/fonts` (raw GitHub), en extrait des **instances statiques** Regular/Bold/Italic/BoldItalic via **fonttools** (`instantiateVariableFont`, pinné à wght 400/700), corrige la **table de noms + bits de style** de chaque instance (sinon noms internes identiques → déduplication = gras rendu en regular), et les enregistre dans `backend/fonts/` (réutilisées en priorité par `_resolve_family_font`). **Non bloquant :** le téléchargement part dans un **thread démon** (dédupe inter-thread via verrou) — la traduction courante sort immédiatement avec le substitut, les suivantes utilisent la police exacte. Déclenché à l'extraction (inventaire) et à l'injection. Échecs persistés (`backend/fonts/.dl_failed.json`) pour ne pas réessayer en boucle. Dépendance ajoutée : `fonttools`. **Validé :** document Merriweather/Open Sans → 8 TTF générés, inject 1,5 s, sortie embarque Merriweather Regular/Bold/Italic + Open Sans Regular/Bold (rendu identique à l'original). **Limites :** nécessite réseau au 1ᵉʳ usage d'une police + fonttools ; polices commerciales/non-Google non couvertes (→ substitut) | `pdf_translator_engine.py:_download_google_font` | ✅ Ajouté |

## 🟡 Moyennes

| # | Problème | Fichier / Ligne | Statut |
|---|----------|-----------------|--------|
| M1 | **Extraction limitée à 3 pages** — `if page_num >= 3: break` dans `extract_text()` (commentaire « Limitation à 3 pages pour test »). Les documents de plus de 3 pages sont tronqués silencieusement | `pdf_translator_engine.py:extract_text` | ❌ Ouvert |

## 🔵 Faibles / Cosmétiques

| # | Problème | Fichier / Ligne | Statut |
|---|----------|-----------------|--------|
|   |          |                 | ❌ Ouvert |

## ⚪ Notes & Observations

| # | Note | Fichier / Ligne |
|---|------|-----------------|
| N1 | `format_options` est **accepté mais pas exploité** par les moteurs (no-op, identique à `doc_translators.py`). Les options de mise en forme choisies dans l'UI n'ont donc aucun effet sur le document généré — à câbler si la fonctionnalité est souhaitée | `*_translator_engine.py` |
| N2 | Le rendu fidèle des symboles dépend de la présence des polices système (Windows : `seguisym.ttf`, `arial.ttf`…). Sur un serveur **non-Windows**, prévoir d'embarquer des polices Unicode équivalentes, sinon repli sur substitution | `pdf_translator_engine.py:_embed_font_for` |
| N3 | Les corrections agissant à l'**extraction** (puces, underline), un `extraction.json` mis en cache d'une traduction antérieure ne bénéficie pas du correctif → retraduire / purger le cache `backend/translations/<doc>/` | `pdf_translator_engine.py` |

---

## 📝 Détails des corrections de cette session

### [#C1] Crash `inject_translation()` sur `format_options`

- **Fichier :** `pdf_translator_engine.py` · `docx_translator_engine.py` · `pptx_translator_engine.py`
- **Priorité :** 🔴 Critique
- **Statut :** ✅ Corrigé

#### Description
`app.py` transmet `format_options=format_opts` aux trois moteurs, qui n'acceptaient pas ce mot-clé.

#### Comportement observé
`TypeError: inject_translation() got an unexpected keyword argument 'format_options'` → aucune traduction ne se générait.

#### Correction
Ajout de `format_options=None` aux trois signatures `inject_translation(...)`. Paramètre accepté pour compatibilité (non encore exploité — voir N1).

---

### [#1] Puce diamant `❖` rendue en point `·`

- **Fichier :** `pdf_translator_engine.py` (`BULLET_CHARS`, `_embed_font_for`, `_insert_text_smart`, `_text_length`, boucle de réinjection)
- **Priorité :** 🟠 Élevée
- **Statut :** ✅ Corrigé

#### Reproduction
1. Traduire un PDF dont les listes utilisent la puce `❖` (U+2756, police SegoeUISymbol).
2. Dans le PDF traduit, la puce devient `·` (U+00B7, Helvetica).

#### Cause
- `❖` (U+2756) absent de `BULLET_CHARS` (seul `◆` U+25C6 y était).
- Les 14 polices PDF de base (helv/times/cour) ne contiennent aucun glyphe symbole → PyMuPDF substitue par `·`.
- Bonus : les blocs « puce seule » au texte propre vide étaient sautés à la réinjection.

#### Correction
- Embarquement d'une police TrueType qui contient réellement le glyphe (priorité à la police d'origine, ex. `seguisym.ttf` ; repli Arial/Segoe UI).
- Ajout des losanges (`❖ ◇ ♦ ⧫ …`) à `BULLET_CHARS`.
- Un bloc « puce seule » dessine désormais sa puce même sans texte traduit.

#### Validation
Aller-retour extraction → réinjection sur PDF de test : `U+2756` conservé en `SegoeUISymbol` dans la sortie. ✅

---

### [#2] Soulignement (rectangles pleins) non détecté

- **Fichier :** `pdf_translator_engine.py` (détection underline dans `extract_text`)
- **Priorité :** 🟠 Élevée
- **Statut :** ✅ Corrigé

#### Reproduction
1. Traduire un PDF Word dont l'en-tête contient du texte souligné.
2. Dans le PDF traduit, plus aucun soulignement.

#### Cause
Le soulignement est un fin **rectangle plein** (`type='f'`, item `'re'`, hauteur ≈ 1 pt), pas un trait. La détection ne traitait que les traits `type='s'`/`'l'` → rien détecté.

#### Correction
- Collecte des segments horizontaux fins depuis **traits ET rectangles pleins**.
- Rattachement aux spans : proximité verticale sous la baseline + recouvrement ≥ 30 %.
- **Garde-fou** : rejet des lignes de grille de tableau via règle d'alignement (`dRight`/`dLeft ≤ max(12, 0.3·largeur)`).

#### Validation
Sur le document réel : 5 vrais soulignements d'en-tête détectés et redessinés (y ≈ 72.7 / 92.2 ×2 / 111.8 ×2), 10 bordures de tableau correctement ignorées. ✅

---

## 📝 Template pour décrire un problème

```markdown
### [#X] Titre court du problème

- **Fichier :** `pdf_translator_engine.py:L123`
- **Priorité :** 🔴 / 🟠 / 🟡 / 🔵
- **Statut :** ❌ Ouvert / ✅ Corrigé / ⏸️ Reporté

#### Description
...

#### Reproduction
1. ...
2. ...

#### Comportement attendu
...

#### Comportement observé
...

#### Impact
...
```
