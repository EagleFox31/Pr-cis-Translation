# Étude — section « Comment ça marche ? » (page d'envoi du fichier)

24/11/2026. Audit UX (usage), UI (aspect) et CX (expérience client) de la section `#story` de l'accueil, avant de la retoucher pour l'envoi unique (lot 1 du test gros fichier).
Captures : bureau 1440 px, tablette 900 px, mobile 390 px, visiteur et compte payé.

## Existant

- Colonne gauche : étiquette, titre, phrase d'accroche, 4 étapes numérotées 01 à 04 (`frontend/src/components/story/StorySection.tsx:305-331`, styles `frontend/src/index.css:1153-1262`).
- Colonne droite : la carte du formulaire (`TranslationSection.tsx`), avec ses propres étapes 1 « Votre document » et 2 « Traduire vers ».
- Deux icônes décoratives animées en continu (globe, loupe) et un léger glissement de la carte au défilement.
- Le bandeau « Découvrir l'extension » (`ExtensionBanner.tsx`) s'affiche en tête de la carte pour un compte connecté.
- Règles applicables : `DESIGN.md` (une seule couleur d'action, carte posée = filet sans ombre, cibles de 44 px, Body UI 13 px) et `PRODUCT.md` (dire vrai, une information à la fois).

## Problèmes relevés (par gravité)

### Structure (ce qui trompe ou gêne l'utilisateur)

| # | Problème | Exemple concret |
|---|---|---|
| S1 | Deux numérotations qui ne correspondent pas. | À gauche « 01 Dépôt, 02 Analyse & Traduction » ; dans la carte « 1 Votre document, 2 Traduire vers ». L'utilisateur lit « étape 2 = analyse » à gauche et « étape 2 = langue » à droite. |
| S2 | Les étapes ne décrivent pas ce que l'utilisateur fait. | Rien ne dit « choisissez la langue », alors que c'est la seule décision à prendre. L'étape « Analyse » décrit un travail interne. |
| S3 | Textes inexacts au regard du produit. | « puis le traduit en entier » : faux si l'on choisit des pages ou si le solde ne couvre pas tout ; les images sont proposées après le texte. « en temps réel » : les pages arrivent une par une. |
| S4 | Sur mobile, le formulaire arrive après les 4 étapes. | Sur un téléphone il faut faire défiler environ un écran et demi avant de pouvoir choisir un fichier. |
| S5 | Le bandeau publicitaire de l'extension passe avant la tâche. | Compte payé : la première chose dans la carte est « Traduisez aussi les pages web… », avant « Votre document ». Contraire à « une information à la fois ». |

### Aspect

| # | Problème | Exemple concret |
|---|---|---|
| A1 | Le fil qui relie les numéros est cassé. | Entre 01 et 02 on voit un trait de 4 px puis un vide : le trait s'arrête à la fin du texte, pas au numéro suivant. |
| A2 | Les icônes décoratives chevauchent le texte. | La loupe passe sur « Récupérez votre document… » (étape 04, bureau) ; le globe flotte au milieu des étapes (tablette). Elles bougent sans arrêt, même si l'utilisateur a demandé à son système de réduire les animations. |
| A3 | Textes trop petits. | Formats « PDF DOCX… » en 10 px, aides « La langue du document est détectée… » et « Choisissez un document… » en 11,5 px ; le minimum du projet est 12–13 px. |
| A4 | Trou au-dessus du bouton Traduire en tablette. | À 900 px, un vide d'environ 70 px sépare l'aide de langue du bouton : la hauteur minimale de la carte (580 px) n'a de sens que sur deux colonnes. |
| A5 | La carte a une grande ombre. | `DESIGN.md` : une carte posée sur la page n'a qu'un filet gris, l'ombre est réservée à ce qui flotte. |
| A6 | Accroche en gris très fin (graisse 300). | « Quatre étapes, et vous voyez le résultat… » est moins lisible que le reste. |

### Finition

| # | Problème | Exemple concret |
|---|---|---|
| F1 | Pluriel trompeur. | « Glissez-déposez vos documents ici » alors qu'on n'en prend qu'un. |
| F2 | Titre à l'anglaise. | « Analyse & Traduction » (esperluette, majuscules) au lieu de « Analyse et traduction ». |
| F3 | Faux effet cliquable. | Le numéro devient bleu au survol alors qu'il ne fait rien. |
| F4 | Liste non structurée pour les lecteurs d'écran. | Les étapes sont des blocs simples, pas une liste numérotée. |
| F5 | Bouton « retour en haut » sur la zone de dépôt (mobile). | Le rond bleu recouvre le coin de la zone de dépôt à 390 px. |

## Options pour S1–S4 (le cœur du sujet)

| Option | Ce que l'utilisateur voit | Pour | Contre |
|---|---|---|---|
| **A. Étapes = gestes de l'utilisateur (recommandée)** | 01 Choisissez votre document · 02 Choisissez la langue · 03 Suivez la traduction page par page · 04 Téléchargez. Les étapes 01 et 02 portent les mêmes mots que les étapes 1 et 2 de la carte. Sur mobile, les étapes se resserrent en une ligne chacune (titre seul), la carte remonte. | Une seule numérotation cohérente ; plus de texte inexact ; formulaire visible plus tôt sur mobile. | On perd la mention de la fiche du document (domaine, vocabulaire) : elle passe dans le texte de l'étape 03. |
| B. Garder les 4 étapes actuelles, corriger les textes | Mêmes titres, phrases rendues exactes ; numéros de la carte retirés. | Changement minimal. | Les étapes restent abstraites (« Analyse ») ; le mobile reste long. |
| C. Formulaire d'abord sur mobile | Sur téléphone, la carte passe au-dessus des étapes. | Action immédiate. | Le lien de menu « Comment ça marche » ouvre alors un formulaire sans explication. |

## Corrections proposées (avec l'option A)

1. Étapes réécrites (fr et en), exactes : « Suivez la traduction page par page : Précis repère d'abord le domaine et le vocabulaire du document, et chaque page s'affiche dès qu'elle est prête. » ; « Téléchargez le fichier traduit, dans son format d'origine. »
2. Étapes en liste numérotée (`<ol>`), fil continu d'un numéro à l'autre, plus d'effet de survol.
3. Mobile : description des étapes masquée (titre seul), espacements réduits ; le bouton « retour en haut » ne recouvre plus la carte.
4. Icônes décoratives retirées (elles gênent la lecture et n'apportent rien) ; glissement de la carte coupé si l'utilisateur réduit les animations.
5. Tailles minimales : formats 11 px en capitales → 12 px, aides 12,5 px ; accroche en graisse normale.
6. Hauteur minimale de la carte seulement sur deux colonnes (au-delà de 1024 px).
7. Carte : filet gris, petite ombre au plus (règle du projet).
8. Bandeau extension déplacé sous le bouton Traduire, en version discrète (une ligne avec lien) ; toujours refermable.
9. « Glissez-déposez votre document ici » ; « Analyse et traduction » disparaît avec l'option A.

## Impacts et risques

- Front seulement : `StorySection.tsx`, `TranslationSection.tsx`, `FileUploader.tsx`, `ExtensionBanner.tsx`, `index.css`, `locales/fr|en/translation.json`. Aucun changement serveur, aucune donnée.
- La carte est retouchée aussi par l'envoi unique (P1/P3) : on fait cette section **juste avant** P1, sur une branche à part, pour ne pas mêler les deux.
- Risque : la visite guidée (`useVisite`) pointe peut-être des éléments de la section ; à vérifier au moment du code.
- Vérification : tsc, lint, build ; captures bureau / tablette / mobile avant-après, visiteur et compte payé.

## À trancher

1. Option A, B ou C (recommandation : A).
2. Bandeau extension : sous le bouton Traduire (recommandé) ou retiré de la carte.
