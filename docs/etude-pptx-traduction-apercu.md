# Étude — PPTX non traduit et aperçu qui clignote (test du 29/10/2026)

## Ce qui a été observé

Deux traductions lancées en test : un PDF (13 pages, correct) et un PPTX de
38 diapositives (« Compte rendu formation Préparation des éléments plan de
carrosserie… »).

- Le PPTX est marqué **terminé, 38/38**, en 2 min 30.
- Aucune diapositive n'est traduite, ni pendant le traitement, ni en rouvrant
  l'aperçu depuis la bibliothèque.
- À chaque page qui se termine, **tout l'aperçu se redessine**, y compris les
  pages déjà affichées et le panneau de l'original.

## Problème 1 — Le PPTX n'est pas traduit du tout (bloquant)

**Preuve.** Le fichier de traduction enregistré
(`translations/954d0c8dab1f/en-US/translated.json`) contient seulement
`{"slides": []}`. Rejouée à la main, l'extraction répond pour chaque
diapositive : « Slide 1 introuvable », « Slide 2 introuvable »…

**Cause.** Le moteur suppose que la diapositive n°1 est le fichier
`slide1.xml`, la n°2 `slide2.xml`, etc. Ce document nomme ses diapositives
`slide1000.xml`, `slide1001.xml`… (cas courant après un export Google Slides
ou des copier-coller entre présentations). Le moteur compte bien 38 fichiers,
puis cherche `slide1.xml` à `slide38.xml`, n'en trouve aucun, et range chaque
diapositive dans « rien à traduire » au lieu de signaler une erreur.

Même avec des noms « normaux », l'hypothèse est fausse dès qu'on a réordonné
des diapositives dans PowerPoint : `slide3.xml` peut être affichée en
première position. L'ordre réel est celui de `ppt/presentation.xml`.

**Endroits touchés** (`backend/engines/pptx/engine.py`) :
`_slide_path`, `_rels_path`, `extract_slide`, `inject_slide`,
`build_partial_pptx` (sélection `only_slides` et `up_to_slide`),
`regenerate_ole_previews` (`only_slides`). Côté
`translation_runner.run_pptx_progressive_job`, la boucle 1..N et la greffe de
l'aperçu (page N du socle) reposent sur la même hypothèse.

## Problème 2 — Le job se déclare « terminé » alors que rien n'a été fait

« Diapositive introuvable » est traité comme « diapositive sans texte ». Le
travail passe donc en succès, 38/38, sans un seul mot traduit. L'utilisateur
n'a aucun message ; les pages sont potentiellement décomptées de son forfait
(à vérifier dans le décompte bêta / crédits).

Conséquence annexe : le PPTX final est construit avec
`build_partial_pptx(output, 38)`, qui ne garde que les fichiers numérotés
≤ 38 — ici aucun. Le fichier téléchargeable risque d'être vide de
diapositives.

## Problème 3 — La réouverture de l'aperçu montre l'original

À la réouverture, l'aperçu est recalculé depuis `translated.json` (vide), donc
c'est l'original qui est rendu, puis **mis en cache**
(`translated.json.render.v1.0.12.pdf`). Une fois le problème 1 corrigé, ce
document devra être retraduit et ce rendu en cache supprimé, sinon il
continuera d'afficher l'original.

## Problème 4 — Tout l'aperçu se redessine à chaque page (PPTX et PDF)

**Cause** (`frontend/src/components/preview/PdfViewer.tsx`, effet de la
ligne 115). Un seul effet charge **les deux documents** (original ET
traduction) et redessine **les deux panneaux**. Il se relance dès que le
fichier partiel change, c'est-à-dire à chaque page terminée. Chaque fois :
le PDF original est relu et réanalysé, les deux canevas sont vidés puis
repeints — d'où le flash, même sur une page déjà affichée.

S'y ajoute le poids : chaque page terminée retélécharge le **PDF partiel
entier** (11 Mo pour ce PPTX). Sur 38 pages, environ 400 Mo transférés et
réanalysés pour afficher un seul document.

## Plan de correction, par priorité

| # | Correction | Effet visible | Taille |
|---|---|---|---|
| P0 | **Correspondance position → fichier** dans le moteur PPTX, lue dans `presentation.xml` (liste ordonnée des diapositives + relations). Toutes les méthodes « par diapositive » reçoivent la *position* et résolvent le fichier. | Le PPTX de test est traduit, dans le bon ordre, aperçu compris. | Moyenne (moteur + runner) |
| P0 | **Garde-fou** : « diapositive introuvable » devient une erreur ; un deck qui a des diapositives mais zéro texte extrait n'est pas déclaré traduit. Rien n'est décompté dans ce cas. | Plus jamais « terminé » sur un document intact. | Petite |
| P1 | **Tests de non-régression** : un PPTX de test dont les fichiers sont renommés `slide1000.xml…` et dont l'ordre est permuté ; vérifier extraction, injection, PPTX final (même nombre de diapositives que l'original) et pages de l'aperçu. | — | Petite |
| P1 | **Purger** le rendu en cache du document de test et le retraduire. | La bibliothèque montre la traduction. | Triviale |
| P2 | **Aperçu sans clignotement** : séparer le chargement de l'original (une fois par document) de celui de la traduction ; ne repeindre que le panneau traduit, et seulement si la page affichée a changé d'état ; peindre hors écran puis échanger, pour supprimer le flash. | Les pages déjà affichées ne bougent plus ; l'original ne se redessine jamais pendant la traduction. | Moyenne (frontend) |
| P3 | **Alléger les transferts** : ne pas relire le partiel si la page affichée n'est pas concernée, ou exposer la page traduite seule. | Aperçu plus fluide sur gros documents / connexion lente. | Moyenne, optionnelle |

Ordre proposé : P0 (les deux) → P1 → vérification sur le fichier réel du test
→ P2 → P3 si le gain reste nécessaire après P2.

## Décisions prises à l'implémentation (P0 + P1)

- **Tout le moteur parle en positions.** La n°1 est la première diapositive
  affichée, lue dans `presentation.xml` (`sldIdLst` → relations → fichier).
  Les identifiants de texte (`slide{n}_p_…`) portent donc la position : le
  traitement progressif et le rendu à la demande les calculent de la même
  façon, sinon la traduction ne retrouverait pas ses paragraphes.
- **Diapositive introuvable = erreur** (plus « rien à traduire »). Une
  présentation dont aucune diapositive ne livre de texte termine en erreur
  avec un message clair. Un travail en erreur est déjà remboursé (décompte
  neutralisé) : rien de plus à faire côté crédits.
- **Version du moteur PPTX : 1.0.1.** Le rendu en cache est indexé sur la
  version du moteur PDF, pas PPTX : la purge du document de test a donc été
  faite à la main.
- **Limite connue.** Une ancienne traduction d'un deck *réordonné* (noms
  `slide1.xml…` mais ordre différent) portait des identifiants par nom de
  fichier ; son rendu à la demande peut ne plus retrouver certains
  paragraphes. Cas rare ; la retraduction le règle.
- **Test** : `backend/tests/test_pptx_ordre_diapositives.py` construit un deck
  aux fichiers renommés `slide1001.xml…` et à l'ordre inversé ; 12/12 avec le
  correctif, 5/12 avec l'ancien code (dont « terminé » sans traduction).

## Correctifs de l'aperçu (P2 / P3) — capture « diapositive 20 »

### Ce qui a été vu
- Diapositive 20 marquée « Page traduite » alors que les deux volets
  montraient le français.
- Aucun indicateur pendant que la traduction tournait encore.
- Les pages déjà traduites clignotaient à chaque nouvel envoi de l'aperçu.

### Causes trouvées
| Symptôme | Cause |
|---|---|
| Page « traduite » encore en français | Le navigateur **devinait** quelles pages étaient prêtes (à partir du nombre de pages du fichier reçu), et une réponse « rien de prêt » (code 202) était lue comme un PDF. Par ailleurs des identifiants de paragraphes abrégés par le modèle n'étaient pas rattachés. |
| Plus d'indicateur | Une coupure de la connexion de suivi (SSE) était traitée comme la fin ; l'indicateur se cachait dès qu'un nombre de pages était connu. |
| Clignotement | À chaque envoi, les deux documents étaient rouverts et les deux volets **vidés puis redessinés**. |

### Options étudiées
| Option | Pour | Contre |
|---|---|---|
| Continuer à deviner côté navigateur | Rien à changer côté serveur | C'est la source de l'erreur : impossible à fiabiliser |
| **Le serveur annonce la liste exacte des pages greffées** (en-tête `X-Pages-Pretes`) | Une page n'est dite traduite que si elle l'est vraiment | Un en-tête de plus à exposer (CORS) |
| Redessiner directement sur l'écran | Simple | Volet blanc le temps du rendu = clignotement |
| **Dessiner hors écran puis copier d'un coup**, document ouvert une seule fois par fichier reçu | L'image précédente reste jusqu'à ce que la suivante soit complète ; l'original n'est plus jamais redessiné | Un peu plus de code |

### Choix retenus
- Liste des pages prêtes fournie par le serveur ; une réponse 202 n'est plus
  jamais affichée.
- Connexion de suivi : jusqu'à 5 reconnexions (jeton rafraîchi à chaque fois) ;
  le serveur renvoie l'événement final si le travail est déjà terminé.
- Tant qu'une page n'est pas prête : **un chargement avec l'étape en cours**
  (« Préparation de l'aperçu » / « Traduction en cours »), jamais l'original
  en repli.
- Volets original et traduit indépendants ; rendu hors écran ; pas de
  redimensionnement inutile du canevas (qui l'effacerait).
- Tests : `test_ids_abreges.py` (4/4), `test_apercu_progressif.py` (23/23,
  dont la liste exacte des pages).
