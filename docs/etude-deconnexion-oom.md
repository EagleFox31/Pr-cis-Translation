# Étude : serveur tué par manque de mémoire et déconnexion pendant le redémarrage

## Besoin

Un PowerPoint de 3 Mo (« TSA Program Deployment Guide ») fait tomber le serveur de production.
Le conteneur est limité à 1 Go (`mem_limit: 1g`) ; le système le tue, puis il redémarre.
Pendant ce redémarrage, l'écran déconnecte l'utilisateur, qui doit se reconnecter.

Deux corrections sont attendues :

- le serveur traduit ce document sans dépasser la mémoire ;
- un redémarrage du serveur ne déconnecte plus personne.

## Cause, mesurée

Le traitement du texte du PowerPoint reste sous 260 Mo. Ce qui fait exploser la mémoire,
c'est la recherche du texte dans les images (`ppocr._detecter`,
`backend/app/services/ocr_v2/ppocr.py`).

Cette recherche agrandit ou réduit l'image jusqu'à 4000 px de côté (`COTE_MAX`), puis la
passe d'un bloc au modèle de détection. La mémoire du modèle croît avec la surface analysée.
Mesures sous Docker sur la photo `image1.jpeg` du document (4000 × 2964 px) :

| Côté analysé | Pic mémoire | Zones de texte trouvées |
|---|---|---|
| 960 px | 395 Mo | 0 |
| 1600 px | 656 Mo | 32 |
| 2400 px | 1154 Mo | 8 |
| 4000 px | processus tué | — |

Le serveur traite aussi plusieurs pages à la fois (4 fils par travail, plusieurs travaux).
Deux grandes images analysées en même temps suffisent donc à dépasser 1 Go, même après
correction de la taille.

Côté écran, deux endroits déconnectent sur n'importe quelle erreur, y compris une erreur
passagère du serveur (502 pendant le redémarrage, coupure réseau) :

- `frontend/src/contexts/AuthContext.tsx` : au chargement, si `/api/auth/me` échoue, les
  jetons sont effacés ;
- `frontend/src/services/api.ts` (`doRefreshAccessToken`) : si le renouvellement du jeton
  échoue, l'utilisateur est déconnecté.

Le serveur ne répond pourtant « jeton invalide » qu'avec un code 401
(`backend/app/api/auth.py`, `refresh` et `require_auth`).

## Options pour la mémoire

| Option | Pour | Contre |
|---|---|---|
| 1. Abaisser `COTE_MAX` (ex. 1600) | Une ligne de code | Perd du texte : les petits caractères des grandes images ne sont plus trouvés. Le nombre de zones trouvées ne suit pas la taille (32 à 1600 px, 8 à 2400 px) : aucun plafond n'est sûr |
| 2. Analyser l'image par tuiles, à la même résolution qu'aujourd'hui | Même finesse de lecture qu'avant ; mémoire bornée par la taille d'une tuile, quelle que soit l'image | Un peu plus de calcul aux bords des tuiles (recouvrement) |
| 3. Augmenter la mémoire du serveur | Aucun code | Coût mensuel ; ne protège pas d'une image plus grande ou de deux images en même temps |

## Choix retenu : option 2, plus un passage un par un

**Tuiles.** L'image est mise à l'échelle comme aujourd'hui. Si elle dépasse une tuile,
le modèle l'analyse par morceaux qui se recouvrent. Chaque morceau produit sa carte de
probabilité de texte. On ne garde que le centre de chaque carte, puis on recolle ces
centres en une seule carte de la taille de l'image. La suite (contours, zones, ordre de
lecture) ne change pas.

Recoller les cartes plutôt que les zones a un avantage : une ligne de texte à cheval sur
deux tuiles reste une seule zone, sans fusion de doublons à écrire. Une image qui tient
dans une tuile est analysée exactement comme avant : rien ne change pour les images
courantes.

**Un seul passage à la fois.** Un verrou commun à tout le serveur entoure l'appel au
modèle de détection. Deux grandes images ne sont plus analysées en même temps. Le reste
du travail (lecture du texte, traduction) continue en parallèle.

## Choix retenu pour l'écran

- Seul un code 401 (ou 403) déconnecte : il signifie que le jeton est refusé.
- Sur une erreur serveur (5xx), une limite de débit (429) ou une coupure réseau, l'écran
  réessaie plusieurs fois en espaçant les essais (environ une minute au total, la durée
  d'un redémarrage). Les jetons sont conservés.
- Si le serveur ne revient pas, les jetons restent : un rechargement de la page reconnecte
  l'utilisateur sans lui redemander son code.

## Impacts

- Données, migrations, déploiement, i18n : aucun.
- Sécurité : inchangée. Un jeton refusé déconnecte toujours.
- Performance : une grande image prend un peu plus de temps (recouvrement des tuiles, et
  attente si une autre détection tourne). Les images courantes ne changent pas.
- Coût : aucun.

## Risques et vérification

- Zones différentes aux bords des tuiles : vérifié par un test qui compare la détection
  par tuiles à la détection d'un bloc sur des images qui tiennent encore en mémoire, et
  par le banc d'images.
- Mémoire : preuve sous Docker limité à 1 Go, puis 768 Mo, avec le PowerPoint TSA traduit
  sans redémarrage.

## Analyse approfondie : tenir avec plusieurs utilisateurs

Mesures sous Docker limité à 1 Go (comme la prod VPS, 2 cœurs, ONNX Runtime sur CPU),
photo `image1.jpeg` du TSA. « Après » = mémoire gardée par le serveur une fois l'image finie.

| Réglage | 1600 px : pic / après | 2400 px : pic / après | Durée 2400 px |
|---|---|---|---|
| Actuel | 623 / 623 Mo | 1065 / **967 Mo** | 5,5 s |
| Réserve ONNX coupée (`enable_cpu_mem_arena=False`) | 726 / 362 Mo | 1088 / 363 Mo | 10,2 s |
| Réserve rendue après chaque passage (`memory.enable_memory_arena_shrinkage`) | 574 / 285 Mo | 1060 / 429 Mo | 6,3 s |
| Tuiles 1536 + réserve rendue | — | 785 / 343 Mo | 13 s |
| Tuiles 1024 + réserve rendue | — | 486 / 335 Mo | 16 s |
| Tuiles 1024 + réserve rendue, image à 4000 px | — | 538 / 332 Mo | 32 s |

### Deuxième cause, plus grave : la mémoire n'est jamais rendue

ONNX Runtime garde une réserve de mémoire (« arena ») à la taille du plus gros passage vu,
et ne la rend jamais. Après une seule grande image, le serveur reste à 967 Mo pour toujours.
L'utilisateur suivant n'a plus que 30 Mo de marge : c'est ce qui fera revenir la panne avec
plusieurs utilisateurs, même avec les tuiles. Le problème est connu (ONNX Runtime, tickets
11627 et 23339).

Demander à ONNX Runtime de rendre la réserve après chaque passage règle ce point sans
ralentir (6,3 s au lieu de 5,5 s). Couper complètement la réserve le règle aussi, mais
double la durée.

### L'idée de compresser les fichiers

Compresser le fichier (JPEG plus compressé, PNG optimisé) ne change rien à la mémoire.
Exemple : la photo pèse 490 Ko dans le PowerPoint, mais une fois ouverte elle fait
4000 × 2964 points, soit 35 Mo. Le modèle a besoin d'environ 190 octets par point analysé,
donc plus de 2 Go à 4000 px. Seul le nombre de points compte, pas le poids du fichier.

La forme de compression qui aide est celle de PowerPoint (« Compresser les images ») :
ramener l'image à sa taille affichée sur la diapositive. La photo du TSA est affichée en
plein écran (13,3 pouces) avec 300 points par pouce. À 150 points par pouce, elle ferait
2000 px. Un texte de 8 points (le plus petit lisible sur une diapositive) y mesurerait encore
17 px de haut, assez pour être détecté. Ce plafond est donc fondé sur ce qu'un lecteur voit,
pas sur un chiffre arbitraire. Il ne suffit pas seul (une image plein écran reste grande),
mais il réduit le temps de calcul des tuiles.

### Filets de sécurité pour « fonctionner en toute circonstance »

- **Garde mémoire** : avant chaque détection, le serveur lit la mémoire restante du conteneur
  (`/sys/fs/cgroup/memory.current` et `memory.max`). S'il manque de marge, la page attend son
  tour au lieu de faire tomber le serveur et tous les travaux en cours.
- **Allocateur** : `MALLOC_ARENA_MAX=2` dans l'image Docker. Le serveur a une dizaine de fils ;
  sans cette variable, la bibliothèque C garde une réserve par fil. Réglage standard des
  serveurs Python à plusieurs fils, sans code.

- **File d'attente des travaux** : une traduction ne démarre que s'il reste 250 Mo
  (`MEMOIRE_TRAVAIL_MO`). Sinon, l'écran l'affiche « en file d'attente » et elle part dès que
  la mémoire revient, au plus tard après 10 minutes.

Trois réglages sont venus du premier essai à trois utilisateurs. Le serveur n'a pas été tué,
mais aucune traduction ne finissait :

- **Mesure** : seule la mémoire réellement occupée compte, c'est-à-dire celle des processus et
  du noyau (`anon + kernel + shmem` dans `memory.stat`). Le cache de fichiers est repris par
  le système dès qu'il en a besoin. L'ancienne mesure comptait 165 Mo de cache comme pris.
- **Mémoire rendue** : après chaque travail, `malloc_trim(0)` rend au système ce que Python a
  libéré. Sans cela, le conteneur restait à 660 Mo au repos.
- **Attente courte pour une image** : une détection attend au plus 20 s
  (`ATTENTE_DETECTION_S`), et non 10 minutes. Elle tient le verrou de détection : une longue
  attente bloquait toutes les autres.

Tout reste dans la pile actuelle : ONNX Runtime CPU, numpy, Docker. Aucune dépendance ajoutée.

## Point tranché en cours d'étude

`images_actives` est forcé pour un PowerPoint même quand le client envoie `images=false`
(`backend/app/api/translate.py`). C'est voulu : les images sont traduites avec leur page,
et le champ n'est gardé que pour les anciens clients.

## Autre facteur examiné : le disque (25/11)

- Ce n'est pas lui qui cause le bug du PPTX. L'aperçu de l'original s'écrit sur le disque, et il s'affiche quand on rouvre le document : le disque avait donc encore de la place.
- Le risque existe quand même. La base de données est sur le même disque : s'il se remplit, la base s'arrête, et tout le site avec elle (connexions comprises).
- Solution temporaire, en attendant d'augmenter la capacité : `DISQUE_LIBRE_MIN_MO` (2048 par défaut ; « none » ou 0 désactive la garde). Sous ce seuil, les nouveaux envois sont refusés (code 507), avec un message clair : « le service est momentanément saturé, vos documents restent accessibles ». Une alerte critique part aux admins. Les envois concernés sont le dépôt d'un document, l'envoi direct avec la traduction ou l'aperçu, et les images de l'extension. Les documents déjà enregistrés restent lisibles.

## Bilan : prêt pour le lancement ? (26/11)

Oui, pour un premier lancement sur le serveur actuel (1 Go, 2 cœurs). Le serveur ne tombe plus, même quand dix personnes envoient un gros document en même temps. En contrepartie, ces personnes attendent leur tour.

**Ce qui a été vérifié sur une copie du serveur limitée à 1 Go :**

- Le PowerPoint TSA, envoyé trois fois en même temps pendant quatre minutes : aucun redémarrage, mémoire au plus haut à 702 Mo. Le premier document est fini en un peu plus de deux minutes, les deux autres attendent leur tour.
- Le même essai avec seulement 768 Mo : aucun redémarrage, mémoire au plus haut à 610 Mo.
- L'aperçu progressif du PowerPoint ne plante plus (il plantait sur les boutons qui renvoient vers une autre diapositive).
- La personne qui attend voit sa place et une durée estimée, mises à jour à chaque document terminé.
- Si le serveur répond mal pendant quelques secondes, la personne reste connectée. Elle n'est déconnectée que si sa session est réellement refusée.
- Si le disque est presque plein, l'envoi est refusé avec un message clair et l'incident est noté dans le journal des erreurs.

**Capacité, avec un exemple concret :** un seul gros document est traité à la fois. Le PowerPoint TSA prend environ deux à trois minutes. Si dix personnes l'envoient à la même seconde, la première l'a en trois minutes et la dixième attend environ une demi-heure. Les petits documents passent beaucoup plus vite.

**Ce qu'il faudra faire si l'attente devient gênante :** passer le serveur à 2 Go, sans toucher au code : le nombre de places se calcule d'après la mémoire du serveur. Le calcul donne alors huit documents en même temps. Ce chiffre n'a pas été essayé : il faudra refaire l'essai des trois PowerPoint à 2 Go avant de s'y fier.

**Limites connues :**

- Le message « l'attente est plus longue que prévu » n'a pas été provoqué en conditions réelles. La logique est simple, mais elle n'a pas été vue à l'écran.
- `test_pptx_debordement.py` échoue sur 13 cas. Ces échecs existaient avant ces travaux : le test ne prépare pas l'ordre des diapositives.
