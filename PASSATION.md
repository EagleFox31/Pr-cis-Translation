# Passation — Precis Translator

> But de ce document : permettre de reprendre le travail dans une **nouvelle
> conversation** sans re-explorer le code (économie de crédits). À lire en
> premier, puis ouvrir directement les fichiers/fonctions cités.

Date de rédaction : 2026-06-12 · Branche de travail : `feat/refonte-ui`

---

## 1. Où en est-on

### Commits récents (du plus récent au plus ancien)
- `d342f15` **Grille d'évaluation : texte vertical fusionné + anti-débordement tableau** ← dernier
- `16fd549` Refonte allégée : backend stable rétabli, sélecteur de langues enrichi
- `12d5269` Garde-fou de légitimité sur l'étirement de colonne (MIN_ALIGNED = 3)
- `b3bf18f` Étirement de colonne appliqué aussi aux blocs individuels
- `1d92006` Étirement des paragraphes à la largeur réelle de leur colonne

### État validé (ne PAS retoucher sans raison)
- **Livre « Data Science Interview »** (multi-colonnes, sommaire) : pages 1-5 correctes.
- **Grille d'évaluation formateurs** (tableau + texte vertical en têtes de
  lignes/colonnes) : **corrigée et validée visuellement** — texte vertical
  fusionné proprement, plus de débordement dans la colonne NOTES, plus de
  répétitions de type « questions? questions? ».

### ⚠️ Incident à connaître
Pendant la session, le working tree de `backend/` est revenu tout seul à un
commit antérieur (probablement déclenché par un changement de modèle / l'IDE),
**effaçant des correctifs déjà testés**. Ils ont été ré-appliqués puis commités
(`d342f15`). **Leçon : committer immédiatement après validation**, ne pas
laisser du travail validé non commité.

---

## 2. Architecture (l'essentiel pour intervenir)

Pipeline : **extraction** (PyMuPDF → `extraction.json`) → **traduction**
(DeepSeek, `translator_ai.py` → `translated.json`) → **réinjection**
(`pdf_translator_engine.py` → PDF traduit).

### Fichiers clés
| Fichier | Rôle |
|---|---|
| `backend/pdf_translator_engine.py` (~3000 l.) | Extraction + réinjection. Cœur du rendu. |
| `backend/translator_ai.py` | Appel DeepSeek, batching **par page**, clés de paragraphe, anti-répétition. |
| `backend/app.py` | API FastAPI. |

### Principes intangibles (exigences utilisateur — NE PAS violer)
1. **Aucune règle spécifique à un document** : tout doit reposer sur des
   propriétés géométriques/typographiques universelles. (Mémoire :
   `no-document-specific-rules.md`.)
2. Traduction **par page**, on n'envoie que `{id, text}` par élément.
3. **Pas de regroupement de blocs à l'extraction** (`_group_paragraphs` et
   `_group_rotated_paragraphs` sont volontairement triviaux : 1 span = 1 bloc).
   Le regroupement se fait UNIQUEMENT à l'injection, via les clés IA.
4. Traductions **jamais abrégées**, jamais de substitution de symbole
   (« & » pour « et », etc.). Longueur : même taille (idéal) > plus court
   (acceptable) > plus long (pire cas).
5. Limite temporaire : **5 pages** (`if page_num >= 5: break` dans `extract_text`).

### Réinjection — les passes (méthode `inject_translation`, ~ligne 252)
Pour chaque page :
1. `insert_pdf` (copie fond/images) → `redact` (efface texte original) → rendu.
2. **Fusion par clés de paragraphe** (`paragraph_key` posée par l'IA) :
   - Les fragments d'une même clé sont rendus dans **un conteneur unique** =
     rectangle englobant de leurs bbox d'ORIGINE. Chaque fragment garde sa mise
     en forme ; seul le flux (retours à la ligne) est recalculé.
   - **Horizontaux** : validés par `_split_group_runs` (taille homogène ±15 %,
     baselines consécutives ≤ 2.5×taille), rendus par `_render_paragraph_group`.
   - **Pivotés (90/270°)** : validés par `_split_rotated_group_runs`, rendus par
     `_render_rotated_group` (flux le long de l'axe X). ← AJOUT `d342f15`
3. **Étirement de colonne** (passes 2a/2c) : un bloc/paragraphe aligné à gauche
   (même x0, ±3 pt) avec ≥ `MIN_ALIGNED`(=3) autres peut s'étendre jusqu'au bord
   droit max de sa colonne, **borné par** : premiers obstacles à droite dans sa
   bande verticale = autres blocs, blocs **pivotés** (`rot_geoms`) et **filets
   verticaux vectoriels** (`_vertical_rules`). ← bornes ajoutées `d342f15`
4. Réduction de police = **dernier recours** (`_fit_fontsize`), après étirement.
   Plancher adaptatif : `min(min_font_size, 0.75*orig_size)` — un bloc qui EST
   déjà le plus petit texte garde une marge plutôt qu'un débordement.

### Fonctions ajoutées en `d342f15` (texte vertical / tableau)
- `_split_rotated_group_runs(grp, rot)` — découpe géométrique des runs pivotés.
- `_render_rotated_group(page, grp, rot, min_size)` — conteneur unique + flux
  axe de lecture + `_insert_rotated_paragraph`.
- `_strip_fragment_overlap(prev, frag)` — retire la redondance quand l'IA
  traduit un fragment comme une phrase complète (anti « questions? questions? »).
  Appelée côté horizontal (boucle `words` de `_render_paragraph_group`) ET
  vertical.
- `_vertical_rules(page)` — segments verticaux vectoriels (bordures de cellules),
  utilisés comme obstacles d'étirement.
- Bloc mono-ligne pivoté : ajuste la taille sur la **hauteur de bbox** (axe de
  lecture), pas la largeur.
- `translator_ai.py` : règle prompt « JAMAIS DE RÉPÉTITION entre fragments ».

---

## 3. À FAIRE — autre PDF en échec

**Un autre PDF rencontre des problèmes** (non encore diagnostiqué dans cette
session — l'utilisateur le fournira). Démarche recommandée :

1. Demander/identifier **quel PDF** et **quels symptômes** (débordement ?
   superposition ? police ? texte manquant ?).
2. Le PDF traduit est en cache sous
   `backend/translations/<NomDoc>_<hash>/<lang>/translated.json` + `..._TRADUIT.pdf`.
   **Attention** : les dossiers de langue utilisent désormais des **variantes
   régionales** (`fr-FR`, `en-US`, `pt-BR`…), PAS `fr`/`en` — vérifier le nom réel
   avec un `Get-ChildItem`.
3. Réinjecter depuis le cache (rapide, gratuit — pas de réappel DeepSeek) avec un
   petit script appelant `PDFTranslatorEngine().inject_translation(...)`.

### 💸 Diagnostic ÉCONOME (le poste de coût = les images)
La lecture d'images PNG rendues est **très chère** en crédits. Pour limiter :
- Diagnostiquer d'abord par la **géométrie** (lire `translated.json` : bbox,
  rotation, size, paragraph_key, textes) — pas par capture.
- Si une image est nécessaire : **une seule**, page entière, **DPI ≤ 110**.
  Éviter les rendus multi-zones à 180 dpi.
- Faire une **passe de smoke-test sans image** (`inject_translation` renvoie
  `True`/`False`) avant tout rendu visuel.
- Committer dès qu'un correctif est validé.

---

## 4. Environnement / commandes utiles

- venv : `backend\venv\Scripts\python.exe` (Python du projet ; l'IDE utilise
  un Python système 3.14 → les diagnostics « fontTools introuvable » sont de
  **faux positifs**, ignorer).
- Encodage console : `$env:PYTHONIOENCODING = "utf-8"` avant tout script.
- Chemins avec accents (`Grille_d_évaluation…`) : la saisie manuelle du `é` peut
  ne pas matcher la normalisation Unicode du nom sur disque → préférer un
  `Get-ChildItem` pour récupérer le chemin réel, ou cibler par hash.
- Lancer l'app : `npm run dev` (front + back). `dev:backend` =
  `backend\venv\Scripts\uvicorn --app-dir backend app:app --reload --port 8000`.

### Stratégie de cache
- Changement de règle d'**extraction ou de traduction** → purger tout le cache
  du doc (re-traduction payante).
- Changement d'**injection seulement** → supprimer uniquement le
  `*_TRADUIT*.pdf` (préserve les `translated.json` déjà payés) et réinjecter.

---

## 5. Points ouverts (non bloquants)
- Cas limite étirement (jamais reproduit) : colonne 2 vide à la hauteur d'un
  paragraphe de colonne 1 partageant le x0 de blocs pleine largeur → étirement
  potentiel au-delà de la vraie colonne, faute d'obstacle local. `_vertical_rules`
  couvre désormais le cas s'il y a une bordure dessinée. À surveiller seulement.
- Décision en attente : merge de `feat/refonte-ui` (ou des correctifs backend)
  vers `main`.
