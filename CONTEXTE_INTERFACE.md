# CONTEXTE — Interface (frontend React)

_Dernière mise à jour : 2026-07-13._

Ce document ne couvre **que l'interface**. Le moteur de traduction PDF est décrit
dans [`CONTEXTE.md`](CONTEXTE.md) ; les problèmes du moteur et leurs corrections
dans [`PROBLEMES_PDF_ENGINE_V2.md`](PROBLEMES_PDF_ENGINE_V2.md).

---

## Principe directeur

**Ne jamais afficher un contrôle qui ne fait rien.** Un réglage sans effet est
pire qu'un réglage absent : l'utilisateur croit agir, et le produit ment. Toute
option de l'interface doit correspondre à un paramètre réellement consommé par le
backend — vérifié dans le code, pas supposé.

Ce principe a motivé l'essentiel du nettoyage ci-dessous : le formulaire affichait
cinq réglages dont **quatre étaient sans effet**.

---

## Pile

| Élément | Choix |
|---|---|
| Build | Vite 6 + React 19 + TypeScript |
| Animation | `motion/react` (ex-Framer Motion) |
| Icônes | **`lucide-react`** — aucun emoji ni SVG en ligne dans le JSX |
| i18n | `react-i18next` — `fr` / `en`, **parité stricte des clés** |
| Rendu PDF | **pdf.js** chargé en global (`window.pdfjsLib`, script CDN dans `index.html`) |
| Persistance | IndexedDB (`utils/idbStore.ts`) pour la bibliothèque de documents |

---

## Fichiers

| Fichier | Rôle |
|---|---|
| [`pages/Home.tsx`](frontend/src/pages/Home.tsx) | Orchestration : sélection du fichier, démarrage, aperçu, bibliothèque |
| [`hooks/useStreamingTranslation.ts`](frontend/src/hooks/useStreamingTranslation.ts) | **Traduction progressive** : POST, flux SSE, PDF partiel, statut par page |
| [`lib/languages.ts`](frontend/src/lib/languages.ts) | **Catalogue des langues** : code envoyé à l'API, écriture, disponibilité par format |
| [`components/upload/TranslationSection.tsx`](frontend/src/components/upload/TranslationSection.tsx) | Formulaire (`<form>`, étapes numérotées, options avancées) |
| [`components/upload/FileUploader.tsx`](frontend/src/components/upload/FileUploader.tsx) | Zone de dépôt accessible au clavier, erreurs en ligne |
| [`components/upload/LanguagePicker.tsx`](frontend/src/components/upload/LanguagePicker.tsx) | Combobox recherchable, navigation aux flèches, langues indisponibles motivées |
| [`components/hero/HeroSection.tsx`](frontend/src/components/hero/HeroSection.tsx) | Accroche + **titre justifié** (`useJustifiedLines`) |
| [`components/hero/DocumentDemo.tsx`](frontend/src/components/hero/DocumentDemo.tsx) | **Démonstration animée** du pipeline (pdf.js + squelette + révélation) |
| [`components/preview/PdfViewer.tsx`](frontend/src/components/preview/PdfViewer.tsx) | Aperçu avant/après, placeholder par page |
| [`components/preview/ViewerToolbar.tsx`](frontend/src/components/preview/ViewerToolbar.tsx) | Zoom, pagination, barre de progression, téléchargement |
| [`components/story/StorySection.tsx`](frontend/src/components/story/StorySection.tsx) | Étapes + carte du formulaire + vignettes à pastille d'état |

**Actifs de démonstration** (`frontend/public/`) : `demo_journal_avant.pdf`
(*Global Tribune*, anglais) et `demo_journal_apres.pdf` (*Tribune Mondiale*,
français). Noms **sans accent** : une URL accentuée devrait être encodée, ce que
pdf.js ne fait pas.

---

## Traduction progressive (le flux)

Le moteur rend **une page à la fois** ; l'interface le montre au fil de l'eau.

1. `POST /api/translate` → `job_id`.
2. `EventSource` sur `/api/translate/events/{job}` :
   - `start{total}` → toutes les pages passent en `waiting` ;
   - `page{page, status, done, total}` avec `status` ∈ `extracting` · `translating` ·
     `rendering` · `done` · `copied`.
3. À chaque `done`/`copied` → `GET /api/translate/partial/{job}` (PDF des pages
   déjà prêtes). Les requêtes sont **coalescées** : une page peut se terminer
   pendant qu'on télécharge encore le partiel de la précédente.
4. `done` final → `GET /api/translate/result/{job}`, puis sauvegarde en
   bibliothèque (IndexedDB).

**L'aperçu s'ouvre au démarrage**, pas à la fin : le panneau gauche affiche
l'original tout de suite, le droit se remplit page par page. Les vignettes portent
une pastille d'état (gris = en attente, bleu pulsant = en cours, vert = prête).

---

## Options du formulaire — ce qui a été retiré, et pourquoi

Audit confronté au backend, pas aux apparences :

| Option affichée | Réalité constatée | Décision |
|---|---|---|
| Langue **source** + bouton d'inversion | **Jamais envoyée** : seul `target_lang` partait dans la requête | Retirée. La détection est faite par le modèle, et annoncée comme telle |
| 20 **variantes régionales** | `Home.tsx` les réduisait à leur base (`'en-US'.split('-')[0]`) → deux variantes produisaient une requête **identique** | **Rétablies pour de vrai** (voir plus bas) |
| Mode **Rapide / Précis** | `translate_pdf_progressive()` ne reçoit **ni modèle ni budget de tokens** ; l'option ne changeait que le suffixe du cache — donnant l'illusion d'un traitement différent (elle relançait tout, donc paraissait « plus lente ») | Retirée |
| `format_options` | Codé en dur sur `preserve`, **non lu** par le moteur v2 (qui préserve toujours la mise en page) | Retiré (type et champ) |
| Plage de pages | Réelle (PDF) | Conservée, en options avancées |
| Mode structure | Réel (diagnostic : contours de blocs, sans traduire) | Conservé, en options avancées |

Corrigé au passage : `error_too_large` annonçait « 5 Mo » pour une limite réelle de
**100 Mo**.

> **Si l'on veut récupérer le mode Précis ou la langue source**, ce sont de vraies
> fonctionnalités à câbler — faire descendre `model`/`max_tokens` jusqu'à
> `stream.py`, ajouter `source_lang` au prompt — et non des cases à recocher.

---

## Langues

### Variantes régionales — rendues effectives

Elles sont légitimes (colour/color, dates, *voseo*) mais **n'existaient que dans
l'interface** : le client réduisait `en-GB` à `en` avant l'envoi, et le backend ne
savait nommer que les codes de base. Les deux bouts sont désormais alignés :

- le **code complet** part à l'API (`en-GB`, `pt-BR`…) ;
- `TranslatorAI.lang_name()` (backend) **nomme chaque variante** dans le prompt :
  `en-GB` → « British English (UK spelling and conventions) », `es-AR` → « Argentine
  Spanish (rioplatense, voseo) ». C'est ce nommage qui rend le choix effectif :
  « en-GB » n'est pas une consigne qu'un modèle peut suivre, « British English » si ;
- un code hors table retombe sur sa **langue de base** au lieu de partir brut ;
- les répertoires de cache portant le code cible, `en-GB` et `en-US` **ne partagent
  aucun résultat**.

36 entrées, groupées par langue dans le sélecteur.

### Langues indisponibles en PDF — et pourquoi

Le rendu PDF réutilise les polices du **document source**, avec repli sur
`backend/fonts` (Roboto, Open Sans, PT Serif…) puis une base-14. **Aucune de ces
polices ne porte de glyphe CJK, arabe ou grec** — vérifié glyphe par glyphe. Une
cible dans ces écritures produirait un PDF vide ou illisible ; l'arabe demanderait
en outre un reflow droite-à-gauche, absent.

Ces langues **restent proposées pour DOCX et TXT** (où la police vient du lecteur)
et sont **désactivées avec un motif affiché** dès qu'un PDF est chargé. Écritures
rendables en PDF : **latin et cyrillique**.

---

## Le hero — démonstration animée

Le visuel d'accroche était **vide** : les deux `<canvas>` du mockup n'étaient
remplis par aucun code.

`DocumentDemo` rejoue désormais le pipeline réel, sans un mot, sur une **page de
journal** (colonnes, manchette, chapeau, encadrés, filets, texte justifié — un CV
ne montrait aucun des cas où la mise en page se casse) :

1. la page source apparaît (vraie page PDF, rendue par pdf.js) ;
2. un balayage l'analyse, les blocs détectés s'allument ;
3. la page de droite se remplit d'un **squelette dont la géométrie est extraite du
   document source** (`getTextContent()`) — le squelette a donc la forme exacte des
   blocs d'origine, ce qui montre que la mise en page est conservée **avant même
   que le texte n'arrive** ;
4. la traduction se révèle de haut en bas, chaque barre s'effaçant quand le front
   la dépasse — comme le streaming page par page du moteur.

Toutes les coordonnées sont en **pourcentage de la page PDF** : aucune mesure du
DOM, donc aucun recalage au redimensionnement.

**Piège du squelette (corrigé) :** regrouper les fragments par bande verticale
seulement fusionne deux colonnes côte à côte en **une barre traversant la
gouttière**. Mesuré sur la page de démonstration : 25 barres sur 57. Le
regroupement coupe donc aussi sur l'**écart horizontal** (> ~1,2 × la hauteur du
texte = gouttière, pas espace entre mots).

`prefers-reduced-motion` coupe boucle et flottements et affiche l'état final :
l'animation n'est **jamais** porteuse d'information.

---

## Le titre du hero — justification

Les trois lignes tombent à la **même largeur**. Deux points non triviaux :

- **`text-align: justify` est inopérant ici.** Chaque ligne est un bloc, donc
  chaque ligne est une *dernière* ligne — et une dernière ligne n'est jamais
  justifiée.
- **Les blancs sont un levier presque nul.** Mesuré, pour des lignes de 23 / 16 /
  12 signes ramenées à la même largeur :

  | Blanc visé | Corps des 3 lignes | Écart de corps |
  |---|---|---|
  | 0,25em (naturel) | 50 / 81 / 98 px | ×1,95 |
  | 0,50em | 48 / 75 / 89 px | ×1,86 |
  | 1,00em (×4, déjà voyant) | 44 / 65 / 76 px | ×1,74 |
  | 2,72em (mots éparpillés) | 34 / 45 / 50 px | ×1,49 |

  Quadrupler les blancs ne réduit l'écart de corps que de 1,95 à 1,74. Tout leur
  confier éparpille les mots **sans même** égaliser les corps.

`useJustifiedLines` se place donc au point d'équilibre : blanc de **0,5em** (deux
fois le naturel, invisible) et c'est le **corps** de chaque ligne qui comble le
reste. Aucune lettre n'est écartée, aucun mot disloqué. La largeur étant *linéaire*
en corps (le blanc ajouté est lui aussi en em), une règle de trois suffit ; les
passes suivantes ne rattrapent que les arrondis. Effet de sens : la ligne la plus
courte devient la plus grande — « mise en page », la promesse, est aussi ce que
l'œil voit en premier.

**Repères de coupe** autour de « mise en page » : ils sont calés sur l'**encre**
du mot (`actualBoundingBoxAscent/Descent`, mesurée à l'exécution), pas sur sa boîte.
Une boîte réserve toute la hauteur d'ascendante, or « mise en page » n'a ni capitale
ni hampe : un cadre posé sur la boîte paraît haut et décentré. La mesure suit aussi
la langue (« their layout » a des hampes, son cadre monte d'autant).

---

## Pièges rencontrés (à ne pas refaire)

1. **Collision de classes CSS nues.** `.tl` existait déjà (ligne de vignette,
   `height: 2.5px`) ; `.hd-float.tl` n'ayant pas de hauteur propre, celle de `.tl`
   s'appliquait — la spécificité se résout **propriété par propriété**, pas règle
   par règle. L'étiquette était écrasée. L'ancien code masquait le même bug par un
   `height: auto !important`. → **Modificateurs préfixés** (`--tl`, `--br`).
2. **Drapeaux emoji.** Windows ne les rend pas : `🇺🇸` s'affichait littéralement
   « US ». Et un drapeau associe à tort une langue à un pays. → **Puces de code**.
3. **CV de démo qui écrasait le document choisi.** Le basculement vers la démo se
   déclenchait dès que la *traduction* était absente — soit l'état normal au
   **démarrage** du streaming. → Le document choisi prime toujours ; la démo ne sert
   que si aucun document n'est chargé.
4. **Instabilité de la carte du formulaire.** La grille appliquait
   `align-items: center` : la carte n'était pas étirée, sa hauteur suivait son
   contenu **et elle était recentrée** à chaque changement — le moindre écart
   déplaçait tout le bloc. → `stretch` (bord supérieur figé) + la zone de dépôt garde
   la **même hauteur** dans ses deux états.
5. **`white-space: nowrap` sur le titre.** La colonne est en `minmax(0, …)` et
   `.hero` en `overflow: hidden` : un texte insécable trop large aurait été **rogné
   sans bruit**. → Corps calibré à la place, dégradation visible plutôt que
   silencieuse.

---

## Vérifications avant de livrer

```bash
cd frontend
npx tsc --noEmit          # types
npx vite build            # build de production
```

Et **la parité des clés i18n** — un oubli ne casse pas le build, il casse la page
dans une seule langue :

```bash
python -c "
import json
fr=json.load(open('src/locales/fr/translation.json',encoding='utf-8'))
en=json.load(open('src/locales/en/translation.json',encoding='utf-8'))
def flat(d,p=''):
    o=set()
    for k,v in d.items():
        key=f'{p}.{k}' if p else k
        o |= flat(v,key) if isinstance(v,dict) else {key}
    return o
f,e=flat(fr),flat(en)
print('divergences :', sorted(f^e) or 'aucune')
"
```

---

## Points ouverts

- **Affirmations non tenues ailleurs sur la page** : la grille de fonctionnalités
  promet toujours « 50+ Langues » (le catalogue en compte 23) et le comparatif
  « supprimées sous 24 h » (le backend met les traductions en cache sur disque).
  Décision produit, non technique — non modifié.
- `frontend/public/` contient encore un **CV personnel** (`CV_Mbowou_*.pdf`), plus
  référencé par aucun composant mais toujours embarqué dans le build.
- **DOCX / TXT** ne bénéficient pas du streaming page par page (le runner v2 est
  branché sur les PDF uniquement) : leur progression reste globale.
