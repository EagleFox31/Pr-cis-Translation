# Étude : qualité des images traduites (causes racines)

## Besoin

Améliorer la qualité **globale** de la traduction d'images de l'extension.
L'objectif n'est pas de corriger les images une par une. Il s'agit de trouver les causes qui, une fois corrigées, améliorent toutes les images.

## Corpus analysé

- 14 images du cache (`translations/_images_extension`), toutes en 1910×1326 JPEG.
- Elles sortent d'un même support de formation automobile en japonais, construit sur 5 gabarits de diapositive.
- Pour chaque image, une planche avant | après a été produite, avec les boîtes OCR : rouge = remplacée, bleu = gardée. Chaque bloc a aussi été relevé : texte, traduction, boîte.

## Anomalies et causes racines (par impact décroissant)

| # | Anomalie observée | Exemples | Cause racine (code) |
|---|---|---|---|
| 1 | Texte minuscule collé en haut d'une grande forme ; retours à la ligne inégaux entre cases identiques | img 09 « Facteurs environnementaux », « Signalement client » ; img 00 point 1 sur 3 lignes, points 2 et 4 sur 1 | La zone de mise en page est la boîte du **texte source**, pas celle de son **contenant** (forme, cellule). `colonnes()` limite la largeur à 1,35 × la largeur lue, et `placer()` réduit le corps pour tenir dans `h + 0,1·hl`. Or le japonais est compact et le français 2 à 3 fois plus long : la place libre de la forme reste inutilisée. `image.py:256-300` |
| 2 | Tailles incohérentes entre éléments frères | « Reproduit » grand / « Non reproduit » petit ; liste de l'img 02 ; « possible. » orphelin en gros | Le corps est calculé **bloc par bloc** à partir de la hauteur lue. `_freres()` n'harmonise que les blocs qui ont le même bord gauche, la même hauteur, la même police et la même couleur. Les cases d'une même rangée (même `y`, même hauteur) ne sont jamais groupées. `image.py:383-406` |
| 3 | Mots coupés en plein milieu | « Début/ant », « Ba/se » | `_couper()` coupe par caractère dès que le texte n'a pas d'espace (une traduction d'un seul mot). Il ne réduit jamais le corps pour que le mot le plus long tienne entier. `image.py:193-205` |
| 4 | Restes de glyphes source (fantômes, « ◆ » sous le texte, « / » isolé) | img 09 fantômes ; « ◆e contrôle », « ◆ésultat » ; img 01 « / » | (a) L'effacement ne déborde que de **±2 px en vertical** (`_elargie`, `image.py:333-334`). Les boîtes OCR, plus basses que les glyphes CJK, laissent donc leurs hauts et leurs bas. (b) Les symboles non lus (◆, /) ne sont ni effacés ni traités comme un obstacle à la pose. |
| 5 | Fragmentation : une fin de phrase traduite à part | img 13 : bloc [8] « …がで » et bloc [10] « きる。 » | Dans `blocs()`, une ligne de continuation courte n'est pas rattachée : la fusion exige un recouvrement horizontal et une hauteur égale. Le traducteur reçoit alors deux moitiés de phrase. `image.py:157-190` |
| 6 | Terminologie instable d'une image à l'autre | 推定箇所の点検 → « point estimé » / « zone estimée » / « points estimés » ; « ステージ » et « Step » → « étape » | Chaque image est traduite seule : `traduire_textes(t, langue)` est appelé **sans titre ni contexte**, et il n'existe aucun glossaire partagé entre les images d'une même page ou d'un même site. `api/extension.py:166-167`, `services/extension.py:45-75` |
| 7 | Caractère « ・ » rendu en carré vide | « ・ » gardé tel quel entre deux termes traduits | La traduction garde la ponctuation CJK (・、。「」). Or la police de pose (Noto Sans ou Roboto, `image.py:119-126`) n'a pas ces glyphes, et aucune normalisation n'est faite après la traduction. |
| 8 | Variantes chinoises lues (特徵, 回复) ; chiffres des chevrons manqués | img 03, 05 | Limite du modèle OCR. Le traducteur s'en accommode : impact faible, rien à faire pour l'instant. |

## Corrections systémiques proposées

| Lot | Correction | Corrige | Effort | Risque |
|---|---|---|---|---|
| **A** | **Mise en page dans le contenant** : mesurer la forme ou la cellule autour du bloc (fond uniforme jusqu'au bord coloré, avec la logique de `cadre()` étendue au vertical). Mettre le texte en page dans ce contenant, centré verticalement s'il y était centré. | 1, une partie de 2 | M | Moyen : à valider sur des photos et des captures, pas seulement sur des diapositives. |
| **B** | **Coupure sans casser les mots** : réduire le corps jusqu'à ce que le mot le plus long tienne. On ne coupe par caractère que pour le CJK et en dernier recours (corps plancher atteint). | 3 | S | Faible |
| **C** | **Harmonisation par rangée et par colonne** : grouper les blocs alignés (même `y` ou même `x`, hauteur proche, même couleur) et leur donner le corps minimal du groupe. | 2 | S | Faible |
| **D** | **Effacement par l'encre réelle** : prolonger la boîte en vertical tant que l'encre continue (comme on le fait déjà sur les côtés), jusqu'à une demi-ligne. Ajouter au masque l'encre non lue située dans la boîte élargie. | 4 | S–M | Moyen : sur des fonds texturés, il ne faut pas effacer un élément graphique. |
| **E** | **Rattachement des lignes de continuation** : une ligne courte, juste sous un bloc, alignée à gauche et sans ponctuation finale au-dessus, rejoint ce bloc. | 5 | S | Faible |
| **F** | **Contexte et glossaire** : envoyer comme contexte les textes de toutes les images de la page, en analysant le lot avant la traduction. Garder un glossaire par page (et par domaine du site) des termes déjà traduits, réinjecté dans les appels suivants. | 6 | M | Faible ; un léger surcoût en jetons. |
| **G** | **Normalisation de la ponctuation** après la traduction vers une langue latine : ・→ •, 、→ , , 。→ . , 「」→ « ». Si une police n'a pas un glyphe, on passe à une police de secours. | 7 | XS | Nul |

**Ordre recommandé : G → B → C → E → D → A → F.**
On commence par les corrections rapides et sûres, qui règlent déjà une bonne part des défauts visibles. Viennent ensuite les deux chantiers qui demandent un banc d'essai : A (le contenant) et F (le contexte).

**Point commun à toutes les corrections :** chaque changement de rendu oblige à monter `cache_images.VERSION`. Sans cela, les anciennes images défectueuses continueraient d'être servies pendant 30 jours.

## Vérification

Avant de toucher au code, monter un **banc de non-régression** :

- Rejouer les 14 images du cache, plus quelques photos et captures d'un autre type, avec des lectures OCR figées.
- Produire les planches avant | après et quelques indicateurs mesurables :
  - mots coupés ;
  - écart de corps entre frères ;
  - taux d'occupation du contenant ;
  - pixels d'encre source restants.

Ce banc sert de « mémoire d'apprentissage » : chaque nouveau défaut signalé y entre comme cas de test.

## Décisions (08/11/2026)

1. Tous les lots, dans l'ordre G → B → C → E → D → A → F, après le banc de non-régression.
2. Lot F : on reprend le mécanisme des documents, **la page web jouant le rôle du document**. Rien n'est conservé au-delà de la page.

### Lot F : ce qui existe et ce qu'on réutilise

- **Fiche de document** (`engines/translation_ai.py:703`, `fiche_document`) : un appel unique, sans réflexion, lit un échantillon réparti de tout le document. Il produit une description courte : nature, domaine, public, et pour chaque terme propre le mot unique à employer en langue cible. Chaque lot la reçoit dans `cadre["fiche"]` (`translation_ai.py:463`). C'est elle qui tient le vocabulaire d'une page PDF à l'autre.
- **Passe de cohérence** (`translation_runner.py:682`, PPTX seulement) : elle reprend après coup un fragment qui a laissé en langue source un terme que le document traduit ailleurs. Elle ne s'applique pas aux images : chaque image est rendue et servie à son tour, sans retour en arrière possible.
- **Extension, aujourd'hui** : le texte des pages reçoit déjà `titre` + `contexte` (`api/extension.py:47-48`), mais pas de fiche. Les images ne reçoivent ni l'un ni l'autre.

**Choix** : l'extension envoie avec chaque image le titre de la page et un échantillon de son texte. Le serveur écrit **une fiche par page** avec `fiche_document`, la garde en mémoire quelques minutes (clé = empreinte du titre et de l'échantillon, rien sur disque), et la passe en `cadre` à la traduction des blocs de chaque image de cette page. Le texte de la page peut s'en servir aussi.
Limite assumée : le cache d'images partagé (empreinte + langue) garde la première traduction produite. Une même image vue sur deux sites différents garde donc le vocabulaire du premier site.
