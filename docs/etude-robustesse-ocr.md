# Étude : robustesse de la traduction d'images de documents

## Besoin et contraintes
Le moteur doit traiter correctement les images qu'on trouve **dans des documents** (scans,
schémas annotés, graphiques, tableaux, tickets, factures, infographies, diapositives), pas
seulement celles sur lesquelles ses règles ont été réglées. Démarche demandée :
tester sur des images publiques des cas d'usage courants → relever chaque problème →
**regrouper par cause** → corriger la cause (règle générale) → revérifier.

Critères de jugement (mémoire du projet, inchangés) :
1. texte non compris, douteux ou sans sens : **laissé tel quel** dans l'image ;
2. mise en forme fidèle (taille, police, nombre de lignes) ;
2bis. emplacements respectés (même zone, même ancrage, pas de chevauchement) ;
3. détails de traduction : noms propres, chiffres, unités intacts.

Contraintes : corrections par règles générales, jamais cas par cas ; pas de recul sur le
banc interne (18 cas) ; lots de 5 ; images de tiers hors dépôt, scripts lancés en `-I`.

## Existant
- Banc public (`docs/etude-banc-public.md`) : 50 images, 6 sources (AI2D 15, FUNSD 7,
  DocVQA 8, ChartQA 10, organigrammes 5, schémas de procédé 5), traductions figées.
- Lot 0 jugé **mauvais** le 10/11 ; trois causes déjà identifiées (PASSATION .13h) :
  **A** lignes empilées fusionnées alors que chacune a sa valeur en face (formulaires,
  `blocs()`) ; **B** texte clair sur bandeau foncé (bandeau perdu, taille fausse) ;
  **C** noms de société et chiffres altérés par la traduction (« 199o »).
- Outil : `banc_images.py --banc _banc_public --lot N [--live] [--reference]`, planches
  côte à côte et indicateurs (coupes, écarts, occupation, restes, manque).

## Ce qui manque pour couvrir les usages courants
| Cas d'usage courant | Couvert ? | Source publique ajoutée |
|---|---|---|
| Schéma annoté, graphique, organigramme, procédé | oui | — |
| Formulaire et page scannés | oui | — |
| Ticket de caisse | non | CORD v2 (`naver-clova-ix/cord-v2`, test) |
| Facture | non | `katanaml-org/invoices-donut-data-v1` (test) |
| Tableau extrait d'un article | non | PubTabNet (`apoidea/pubtabnet-html`, validation) |
| Infographie | non | InfographicVQA (`lmms-lab-encoder/DocVQA`, validation) |
| Dessin technique coté | non | Wikimedia `Category:Technical drawings` |
| Diapositive de présentation | non | Wikimedia `Category:Presentation slides` |

**5 images par nouvelle source → 80 cas.** Même graine, même règle d'admission (≥ 2 textes
avec une lettre), sources ajoutées **à la fin** de `SOURCES` : les 50 cas existants et leur
tirage ne bougent pas.

## Options de démarche
| Option | Pour | Contre |
|---|---|---|
| A. Corriger A/B/C puis tester le reste | rapide | on corrige avant de connaître toutes les causes : retouches répétées |
| **B. Diagnostic complet d'abord (retenue)** | toutes les causes connues avant de coder, corrections groupées par cause | un passage de plus sur les 80 images |
| C. Ne tester que les nouvelles sources | moins cher | ignore les 45 cas pas encore jugés |

## Démarche retenue
1. Tirage des 30 nouvelles images, traduction réelle une fois (`--live`).
2. Diagnostic lot par lot (16 lots de 5) : pour chaque cas, défauts constatés sur les
   critères 1–3, consignés dans le registre `docs/revues/robustesse-ocr.md`
   (cas, défaut, étape fautive : lecture OCR / regroupement / effacement / traduction / pose).
3. Regroupement par cause, classement par nombre de cas touchés.
4. Correction par cause (règle générale + test unitaire), plus forte d'abord.
5. Après chaque cause : rejeu des lots touchés + banc interne (non-régression) + pytest.
6. Rapport : avant/après par cause, causes laissées et pourquoi.

## Impacts
- Code : `backend/app/services/ocr_v2/*` seulement (moteur d'images) ; aucune donnée en base.
- Coût : ~30 images × ~15 textes ≈ 450 courtes traductions, une fois (mémoire figée).
- Sécurité : inchangée (images de tiers décodées par Pillow/OpenCV, taille plafonnée, `-I`).
- Travail parallèle : worktree `Precis-Translator-ocr`, branche `fix/ocr-robustesse-documents`
  (le dossier principal est occupé par la mission Nouveautés).

## Risques
- Défauts de **lecture** OCR (scans bruités, petits caractères) : classés à part ; on ne les
  maquille pas au rendu. La règle 1 s'applique : texte douteux laissé tel quel.
- Jeux Hugging Face indisponibles (API de lignes en panne le 10/11) : nouvel essai, sinon
  lecture directe du fichier parquet.
- Tickets CORD en indonésien : bon test de « nom propre / prix intact » et de langue source autre.

## Résultats
**Diagnostic des 16 lots (11/11/2026)**, tolérance zéro : 72 cas notés un à un (plus les
4 anciens cas du lot 0, jugés en bloc). **6 conformes**, tous sans rien à traduire (schémas à
lettres seules, organigramme déjà en français). Aucun cas avec du texte traduit n'est conforme.

Cas touchés par cause (un cas compte une fois par cause), regroupés par étape fautive :

| Famille (étape) | Cause | Cas | Exemple type |
|---|---|---|---|
| Pose : fidélité typographique | H police, graisse, italique, serif perdus | 47 | facture DejaVu → Roboto ; « 45% » gras perdu |
| | D texte plus petit que l'original | 41 | étiquettes d'un schéma réduites de moitié |
| | F couleur plus pâle ou grise | 29 | texte noir rendu gris clair |
| Regroupement des lignes | A lignes ou colonnes fusionnées | 43 | libellé + valeur d'un fax sur une ligne ; 2 articles d'un ticket en un bloc |
| | 2bis chevauchement, ancrage perdu | 38 | date posée sur le paragraphe voisin |
| Effacement | G traînées, fantômes, rectangles visibles, traits rognés | 39 | « 10017 » encore visible ; rectangles blancs sur une carte |
| Traduction | C noms propres, chiffres, symboles, formats altérés | 27 | « NORTHERN » → « DU NORD » ; « 450 °C » → « 450▯ » ; graduation avalée |
| | M traduction partielle | 13 | 2 textes traduits sur 20 |
| Fond | B bandeau foncé perdu, contour ajouté | 11 | texte blanc sur aplat |
| Seuils | J texte < 9 px jamais traduit | 9 | note de bas de page |
| Hors rendu | K texte vertical ou incliné | 7 | axe vertical d'un graphique |
| | L mauvaise lecture OCR, I alphabet non lu | 3 + 3 | « Pb1 » lu « En1 » ; cyrillique |
| | N texte effacé sans rien de posé | 1 | lot 7 |

Lecture : les défauts ne viennent pas d'une seule étape. **A** est la cause amont la plus
lourde : une fusion entraîne presque toujours 2bis (bloc trop grand qui déborde) et G (lignes
d'origine mal couvertes). **H/D/F** viennent de la pose : la taille, la graisse, la police et
la couleur posées ne sont pas mesurées sur l'original mais déduites ou plafonnées.

**Ordre de correction retenu** (impact × nombre de cas, cause amont d'abord) :
1. N (perte de texte : grave même si rare) ;
2. A + 2bis : découpe des blocs (colonnes, libellé/valeur, listes numérotées, titres) ;
3. D, F, H : mesurer taille, couleur et graisse sur les pixels de l'original ;
4. G : masque d'effacement ajusté au tracé réel ;
5. C + M : protection des noms propres, nombres, symboles (°, $, %) et des textes non traduits ;
6. B, J ; K, L, I restent hors rendu (règle 1 : laisser tel quel ce qui est douteux).
