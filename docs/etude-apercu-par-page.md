# Étude : aperçu et stockage page par page

Date : 26/11/2026. Point de départ : le PPTX « TSA Program Deployment Guide », 75 diapositives et 19,8 Mo. Sa traduction s'arrête vers la diapositive 34 avec le message « Connexion au serveur perdue ».

## 1. Besoin

- **Fiabilité.** Un document de 75 pages ou plus doit aller au bout sur le serveur de production, qui a 1 Go de mémoire.
- **Rapidité.** La première page traduite doit être visible le plus tôt possible.
- **Économie.** Rien de ce qui est déjà fait ne doit être refait, ni recalculé, ni retéléchargé.
- **Sécurité.** Une page qui n'a pas été payée ne doit jamais arriver « en clair » chez le client, même si quelqu'un fouille dans les outils de développement de son navigateur.
- **Idée de départ (demande de l'utilisateur).** Garder chaque page à part sur le serveur, et n'assembler le document qu'au moment du téléchargement. Les pages gardent les réglages du document parent : thème, polices, styles.

## 2. Mesures (machine de développement, LibreOffice réel)

| Opération | Durée | Pic mémoire LibreOffice |
|---|---|---|
| Original converti EN ENTIER (le « socle » actuel) | 107 s | **1 494 Mo** |
| Lot de 20 diapositives | 31 s par lot | 842 Mo |
| Lot de 10 diapositives | 20 s par lot | 645 Mo |
| Lot de 5 diapositives | 12 s par lot | 642 Mo |
| 1 diapositive | 10,5 s | **307 Mo** au plus (234 Mo en moyenne) |
| Une diapositive traduite affichée (greffe), sur 40 diapositives | environ 11 s chacune | 200 à 309 Mo, stable |

**Lecture.**
- Le serveur tombe à cause du socle. Avant toute traduction, l'application convertit l'original entier pour l'afficher en fond, et cette conversion à elle seule dépasse 1 Go.
- Si elle échoue, le code la relance à chaque diapositive ([translation_runner.py:983-985](../backend/app/services/translation_runner.py#L983-L985)). Cela fait jusqu'à deux minutes de plus et 1,5 Go de pic à chaque fois.
- Découper l'original en lots ne suffit pas. Une seule diapositive lourde fait monter le lot entier, si bien que dès 5 diapositives par lot le pic est à 642 Mo.
- Seule l'unité « une page » tient sous le budget prévu, qui est de 234 Mo dans [memoire.py](../backend/app/services/memoire.py).

**Défauts secondaires mesurés.**
- Le navigateur retélécharge l'aperçu ENTIER à chaque page traduite. Il passe de 9 à 17 Mo, soit environ 500 Mo transférés pour 40 pages ([useStreamingTranslation.ts:175](../frontend/src/hooks/useStreamingTranslation.ts#L175)).
- Le serveur reconstruit aussi le PDF complet à chaque page, côté PPTX (`ProgressivePreview.assembler`) comme côté PDF (`stream._save_partial`). Le travail grossit donc au carré du nombre de pages.
- Les pages filigranées sont repassées en image à chaque requête (`trial_preview.rasterize_for_trial`).

## 3. Normes de référence

| Pratique reconnue | Source | Ce que fait Precis aujourd'hui |
|---|---|---|
| Le serveur envoie les pages **affichées**, une par une, plutôt que le fichier complet | Nutrient/PSPDFKit, mode « server-backed » ; Dropbox, aperçus découpés en parties | Le fichier complet est envoyé à chaque fois |
| Tout ce qui est envoyé au navigateur peut être enregistré. La protection consiste à **ne jamais envoyer** ce qui n'est pas dû, pas à le masquer | Nutrient, « Open without downloading » | Bon pour les pages non payées : elles sont filigranées et envoyées en image, sans texte. Le voile CSS n'est qu'un complément |
| Les réponses sensibles portent `Cache-Control: no-store` (ni cache du navigateur, ni historique) | OWASP, Web Cache Security Cheat Sheet ; WSTG « Browser Cache Weaknesses » | Déjà en place sur `/partial` |
| Chaque requête de page vérifie l'accès (propriétaire, droit de lecture) ; pas d'adresse devinable sans contrôle | OWASP ; contre-exemple documenté de DocumentSpark | Déjà en place (`_job_of`, `_may_read_clear`), à conserver pour chaque page |
| Les gros documents bureautiques se convertissent par petites unités ; LibreOffice charge tout le fichier même pour une plage de pages | Forums et rapports de bug LibreOffice | `build_partial_pptx` extrait déjà une diapositive avec son thème. Seul le socle ne s'en sert pas |
| Le document final est **reconstruit depuis l'original et les données traduites**, plutôt que recollé à partir de fichiers bureautiques découpés | Pratique des moteurs de traduction de documents ; format OOXML (thèmes, masques et numérotation partagés) | Déjà le cas (`render_translation_bytes`) |

## 4. L'idée « une page = un fichier, assemblage au téléchargement »

L'idée est bonne. La norme lui donne la forme suivante.

| Ce qu'on garde par page | Verdict | Raison |
|---|---|---|
| **Le rendu d'aperçu de la page** (PDF d'une page, et sa version filigranée) | **Oui** | Il est calculé une seule fois, servi tel quel, et jamais recalculé ni retéléchargé. C'est le gain principal |
| **La traduction de la page** (données) | **Déjà le cas** | `pages*.json` et `translated*.json` sont repris page par page |
| **Un fichier Word, PowerPoint ou Excel par page**, recollés au téléchargement | **Non** | On perdrait des choses. Dans un Word, les pages n'existent pas avant la mise en page : un paragraphe, une note de bas de page ou une table des matières passe d'une page à l'autre. Dans un PowerPoint, le thème, les masques et la numérotation sont partagés. Dans un Excel, les textes sont communs à toutes les feuilles. Recoller ces morceaux dupliquerait les masques et casserait les renvois. Reconstruire depuis l'original et la traduction donne un fichier identique à l'original, et c'est déjà ce que fait Precis |

**Exemple concret.** Un PowerPoint de 75 diapositives utilise un seul masque. Découpé en 75 fichiers puis recollé, il en contiendrait 75 copies, et la diapositive 12, qui renvoie vers la 40, pointerait dans le vide. Reconstruit depuis l'original, il garde son unique masque et son renvoi intact.

## 5. Options

| | Description | Pour | Contre |
|---|---|---|---|
| **A** | Socle par lots de 10 | Peu de changements | 645 Mo mesurés : le risque reste. Durée inchangée. Le fichier complet est toujours retéléchargé |
| **B** | Plus de socle. Une page = un rendu gardé sur disque. Les pages sont servies une par une. L'original d'une page n'est converti qu'à la demande, quand on l'affiche | Pic d'environ 300 Mo au lieu de 1 494 Mo. Première page visible en environ 11 s au lieu de 107 s ou plus. Environ 17 Mo transférés au lieu d'environ 500. Plus de travail au carré. Moins d'exposition côté client | Le lecteur d'aperçu doit charger page par page (front et API à adapter) |
| **C** | Option B, plus un fichier bureautique par page recollé au téléchargement | — | Perte de fidélité (§ 4). Écarté |

## 5 bis. Le parcours d'affichage retenu (recherche du 26/11)

Ce parcours suit les visualiseurs de référence : Syncfusion, Telerik « load on demand », Nutrient/pdf.js.

1. **Une fiche du document d'abord.** Le navigateur reçoit le nombre de pages, la taille de chaque page et l'état de chaque page : en attente, traduite ou filigranée. Il dessine tout de suite des cadres à la bonne taille, sans que la page saute ensuite.
2. **Seules les pages visibles, plus une avant et une après, sont demandées.** Le navigateur repère les pages à l'écran (`IntersectionObserver`). Si on fait défiler vite, les demandes devenues inutiles sont annulées.
3. **Une page n'est téléchargée qu'une seule fois.** Quand le serveur annonce « page 12 prête », le navigateur ne la charge que si elle est à l'écran, sinon plus tard. Elle est gardée en mémoire le temps de la session, jamais sur le disque (`no-store`).
4. **Ce qui est envoyé dépend du droit.** Une page payée part en PDF d'une page : net, avec un texte sélectionnable. Une page non payée part en image filigranée, sans texte.

**Variante étudiée puis écartée : un seul PDF « optimisé pour le web », lu par morceaux.** Il s'agit d'un PDF linéarisé que pdf.js lit par plages d'octets.
- Le navigateur peut demander n'importe quelle plage du fichier, donc tout le document reste récupérable.
- Le serveur doit construire le PDF complet, et c'est justement ce qui le fait tomber.
- Le réglage de pdf.js est fragile : la documentation officielle et Nutrient se contredisent sur `disableAutoFetch`.

## 6. Choix recommandé : B, en trois lots livrables

1. **Lot 1. Plus de chute serveur (PPTX).**
   - Suppression du socle complet. Chaque diapositive traduite est gardée sur disque comme une page :
     - `pages/{n}.pdf`, avec sa version `pages/{n}.wm.png` filigranée ;
     - le dossier est nommé avec la version du moteur, la qualité et la sélection, comme les fichiers de traduction actuels.
   - Une diapositive pas encore traduite est montrée comme « en attente ». Son original n'est converti qu'à la demande : une diapositive à la fois, environ 300 Mo, sous le budget mémoire, et gardée en cache par contenu.
   - Plus de relance du socle à chaque page.
   - Critère de réussite : le TSA complet passe dans le conteneur de 1 Go, et le pic mesuré reste sous 1 Go.
2. **Lot 2. Le navigateur charge page par page.**
   - L'API sert une page avec `GET …/pages/{n}` : contrôle d'accès, `no-store`, version filigranée si la page n'est pas due.
   - Le lecteur ne demande que les pages nouvelles ou visibles.
   - Critère de réussite : environ 17 Mo transférés pour le TSA, chaque page téléchargée une seule fois.
3. **Lot 3. Même principe pour le PDF.**
   - `_save_partial`, qui réécrit tout le document à chaque page, est remplacé par l'écriture de la page seule.
   - Pour Excel et Word, l'aperçu reste par feuille ou converti en fin de traduction : la mise en page de ces formats n'est connue qu'à la fin. Le stockage par page ne s'applique qu'une fois cette mise en page connue.

Le téléchargement ne change pas. Il assemble à partir de l'original et de la traduction, garde les contrôles de paiement en place (402, `sans_libres`, `_garder_pages`), et produit donc le même fichier qu'aujourd'hui.

## 7. Impacts

- **Sécurité.**
  - En mieux : le client ne reçoit plus que les pages affichées.
  - Ce qui reste : une page non payée n'arrive qu'en image filigranée, sans texte.
  - À ajouter : le contrôle `_job_of` et `_may_read_clear` sur chaque page servie.
  - Limite honnête : une page affichée peut toujours être photographiée ou capturée. C'est vrai pour tous les visualiseurs, et c'est le filigrane qui y répond.
- **Disque.**
  - Environ 0,2 Mo par page, plus l'image filigranée.
  - Le nettoyage existant (`stockage.py`) couvre le dossier de la traduction. À vérifier au lot 1.
- **Performance.** Ordres de grandeur pour le TSA (75 diapositives) :
  - pic : 1 494 Mo → environ 300 Mo ;
  - première page : 107 s ou plus → environ 11 s ;
  - données transférées : environ 500 Mo → environ 17 Mo ;
  - temps LibreOffice : environ 107 s de moins (le socle disparaît).
- **Rien ne change** pour le paiement, la traduction ou le fichier final.
- **Déploiement.** Aucune migration de base de données. Il faut incrémenter la version du moteur d'aperçu.

## 8. Risques

- **L'appariement des diapositives.** Une page rendue doit toujours correspondre à la bonne diapositive. Les gardes de `ProgressivePreview.greffer` sont conservées et testées.
- **`preview_lock` est commun à tout le serveur.** Les conversions à la demande de l'original passent après celles des pages traduites, pour ne pas les ralentir.
- **Un ancien partiel en cours au moment du déploiement.** Il est servi par l'ancien chemin jusqu'à la fin de sa traduction.

## 9. Points à trancher

1. **Valider l'option B** et le découpage en trois lots, dans l'ordre 1, 2, 3.
2. **Pendant la traduction d'un PPTX, une diapositive pas encore traduite affiche :**
   - (a) son original, converti à la demande (recommandé, rien n'est perdu par rapport à aujourd'hui) ;
   - (b) une simple vignette « en attente », plus rapide mais moins parlante.
