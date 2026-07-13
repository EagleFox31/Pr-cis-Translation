# Problèmes identifiés — pdf_engine_v2 (campagne 20 pages du 2026-07-10, corrigés le 2026-07-10/11)

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

## ⏳ Résiduels (documentés, non bloquants)

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
