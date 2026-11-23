# Étude : file d'attente OCR et pages illisibles

État au 05/11/2026, à partir de `integration/version-complete` (b0f96a3). Fait suite au bilan `docs/bilan-ocr-deploiement.md`.

## 1. Besoin

- **Limite de pages :** trouver la cause. Si c'est le stockage, compresser ou limiter la taille selon le compte. Si c'est le traitement, ne pas lire plusieurs pages à la fois et classer les comptes dans une file d'attente.
- **Page illisible :** ne plus refuser l'envoi. La traduction démarre et ce qui est lisible est livré. Pour une page illisible ou en échec, un message concis propose : traduire quand même (page facturée si le client accepte), afficher l'original, ou laisser vide. Interface responsive, conforme au thème.
- **Japonais d'arrivée :** reporté, rien à faire.

**Critères d'acceptation :**
1. Un scan de 59 pages est accepté et ses pages apparaissent une à une, sans attendre la fin du document.
2. Jamais deux lectures OCR en même temps sur le serveur, images de l'extension comprises.
3. Un compte prioritaire passe après la page en cours, sans attendre la fin du long scan d'un autre compte. Un compte moins prioritaire finit quand même par passer.
4. Une page illisible n'annule rien. Elle n'est pas facturée tant que le client ne demande pas sa traduction.
5. Le panneau de choix fonctionne à 360 px et en thème clair comme en thème sombre.

## 2. Diagnostic : le traitement, pas le stockage

Mesures du 05/11 (2 CPU, 3 Go), détail au §3 du bilan.

| Hypothèse | Constat | Verdict |
|---|---|---|
| Stockage | Environ 2 Mo par page reconnue. Livret de 13,5 Mo : 15,1 Mo avec 1 page, 20 Mo avec 3 pages. Le PDF produit est déjà compressé (`garbage=3, deflate=True`). Aucun envoi refusé pour sa taille | **Écarté.** Compresser ou limiter la taille par compte ne ferait pas passer une page de plus |
| Temps | Délai de 90 s pour tout l'envoi. Une page dense prend environ 90 s seule, une légère 15 à 25 s. 5 pages denses : refus à 94,1 s | **Cause principale** |
| Mémoire | Scan : 1,1 Go au pic. 3 images en même temps : 2,2 Go | Justifie une seule lecture à la fois |

**Exemple :** un scan dense de 10 pages demande environ 15 minutes de lecture. Avec 90 s pour tout l'envoi, il ne peut pas passer, quelle que soit sa taille en Mo.

Les pages d'un envoi sont déjà lues l'une après l'autre. Il reste quatre vrais défauts :
- la lecture se fait pendant l'envoi du fichier, dans la requête HTTP ;
- le délai de 90 s est commun à toutes les pages ;
- un second client reçoit un refus (503) au lieu d'attendre ;
- une erreur sur une page annule tout.

## 3. Existant

| Élément | Fichier | Usage dans cette mission |
|---|---|---|
| OCR des scans | `services/ocr.py` : `prepare_scanned_pdf`, `_recognize`, verrou `_slot` | Découpé page par page |
| Images des documents | `services/images_document.py:461,477` : `with _slot:` | Passe par le guichet |
| Images de l'extension | `api/extension.py` : verrou par utilisateur seulement | Passe par le guichet (risque haut du bilan) |
| Ordonnanceur | `services/scheduler.py` : file par priorité, 2 travaux à la fois | Réutilisé tel quel, avec un second exemplaire pour les scans |
| Priorité | `models/plans.py:101` `get_plan_priority` | Inchangée |
| Moteur PDF | `engines/pdf/stream.py:117` : boucle de pages, cache par page, passe de cohérence | Point d'accroche de l'OCR |
| Réouverture | `translation_runner.py:1323` `render_translation_bytes` : lit `.source.pdf` | Source reconstruite à partir des pages |
| Remboursement | `usage.refund_unfinished`, clôture dans `jobs.py:375-425` | Déjà la bonne formule : payer les pages faites |
| Débit après coup | `services/extension.py:101` `debiter` (avec `document_id`) | Pour « traduire quand même » |
| Choix par élément | `api/documents.py:711,722`, `_copie_du_document`, `DocumentImagesPanel.tsx` | Modèle du panneau et de ses routes |

## 4. Options

### Quand lire les pages

| Option | Pour | Contre |
|---|---|---|
| A. Garder la lecture dans la requête et allonger le délai | Très peu de code | La requête reste ouverte plusieurs minutes, un seul scan à la fois, le refus 503 reste |
| B. Tout lire en tâche de fond, puis traduire | Assez simple | Scan dense de 59 pages : environ 90 minutes avant de voir la première page |
| **C. Lire puis traduire chaque page dans la boucle du moteur** | Pages visibles au fur et à mesure, reprise à la page près, une page en échec n'arrête rien | Le moteur et la reprise sont à adapter |

**Choix : C.** Le client voit vite un résultat et une erreur reste limitée à sa page.

### Comment partager l'OCR

| Option | Pour | Contre |
|---|---|---|
| Garder le verrou, qui refuse | Rien à faire | Le second client est refusé |
| Un verrou qui attend, sans ordre | Simple | Aucune priorité entre comptes |
| Un travail réservé à l'OCR par document | Facile à suivre | Un compte prioritaire attendrait la fin d'un scan de 90 minutes |
| **Un guichet par page, avec priorité** | Une seule lecture à la fois, le prioritaire passe à la page suivante, couvre aussi les images | Une petite pièce nouvelle à tester |

**Choix : guichet par page.** Priorité du forfait, puis ordre d'arrivée. **Anti-famine :** une demande qui attend depuis plus de 5 minutes passe en premier, sinon le très long scan d'un compte prioritaire bloquerait indéfiniment les autres.

**Ne pas bloquer les documents normaux :** les scans passent par un second ordonnanceur, de 3 travaux par défaut (`OCR_SCAN_WORKERS`). Sinon deux longs scans occuperaient les 2 places de traduction pendant des heures. Le guichet garantit qu'une seule page est lue à la fois, même avec 3 scans ouverts. Un quatrième scan attend sa place et voit sa position dans la file.

### Quand facturer « traduire quand même »

| Option | Pour | Contre |
|---|---|---|
| Débiter avant la lecture, rembourser en cas d'échec | Solde sûr | Un redémarrage du serveur au mauvais moment laisse un débit à rembourser |
| **Vérifier le solde, puis débiter seulement après réussite** | Rien à rattraper après un redémarrage, même méthode que les images | Si le solde a changé entre-temps, la page n'est pas livrée |

**Choix : débit après réussite**, lié au document. Solde insuffisant au moment de demander : refus 402 avec le parcours d'achat habituel. Solde devenu insuffisant à la fin : la page reste « illisible », avec un message.

## 5. Conception

### Guichet (`services/ocr_file.py`, nouveau)
`tour(priorite, delai=None, arret=None)` s'utilise avec `with`. L'attente vérifie régulièrement `arret` : une pause ou une annulation agit même dans la file. Passé `delai`, il lève `OCROccupe`. L'ordonnanceur indique la priorité du travail au fil d'exécution, ce qui évite de la faire passer par tous les moteurs. Remplace `_slot`.

| Appelant | Attente maximale | Au-delà |
|---|---|---|
| Page de scan | Sans limite, interruptible | |
| Image de document | Sans limite | |
| Image de l'extension | 120 s (une page dense dure environ 90 s) | 503 « Réessayez » |

### Lecture d'une page (`services/ocr.py`)
- `lire_page(doc, numero, repertoire)` a son propre délai de 90 s (`OCR_DELAI_PAGE_S`).
- Trois résultats : `ok`, `blanche`, `illisible` (avec le motif).
- **Page blanche :** aucun mot et image presque unie. Conservée telle quelle, non facturée, sans question : un verso blanc n'est pas un problème à signaler.
- Page sans mot mais avec du contenu (photo, écriture manuscrite) : `illisible`, le client décide.
- `forcee=True` lève les seuils de confiance et garde les lignes douteuses ; s'il reste zéro mot, seconde tentative avec PP-OCR. Sans aucun mot lu, la page reste illisible et n'est pas débitée.
- `OCR_VERSION` passe à `ocrv3`. Les anciens documents gardent leur `.source.pdf` et rouvrent normalement.

### Résultats sur disque
Dossier `<trad>.ocr/` : `p0012.json` (statut, motif), `p0012.pdf` si la page est lue, `choix.json`. Un fichier par page : deux écritures ne s'écrasent pas et une reprise ne relit rien. `.source.pdf` est reconstruit à la demande si le dossier est plus récent. `stockage.py` nettoie le dossier comme `.images/`.

### Moteur (`engines/pdf/stream.py`)
Nouveau paramètre `lecteur_ocr`, absent par défaut : les PDF normaux ne changent pas. Pour chaque page visée sans texte :
1. page déjà lue : elle remplace la page dans `src` ;
2. sinon, attente au guichet (`ocr_attente`), lecture (`ocr`), enregistrement ;
3. `illisible` ou `blanche` : l'original est copié, statut `illisible` ou `blanche`, et la boucle continue.

À l'ouverture, `pages_traduites` ne contient pas ces pages : elles s'affichent donc en original. C'est le comportement par défaut, sans action du client. Le choix « vide » pose une page blanche de même format.

### Envoi (`api/translate.py`)
- L'OCR quitte la requête. Le plafond de 10 pages disparaît. Restent les limites du forfait et la taille d'envoi (100 Mo).
- Plus de 422 `scanned_document` pour les PDF. Le `503 ocr_unavailable` reste, vérifié dès l'envoi si Tesseract manque.
- Les scans partent dans le second ordonnanceur.
- Les images restent exclues des scans, comme aujourd'hui.

### Facturation

| Moment | Effet |
|---|---|
| Lancement | Toutes les pages visées sont réservées, comme aujourd'hui. Solde insuffisant : 402 inchangé |
| Fin du travail | Ajout dans la clôture `done` : si des pages sont illisibles ou blanches, `refund_unfinished(doc, faites - déjà)`. C'est le calcul déjà employé à l'arrêt. Le solde bêta est couvert par le même chemin |
| Pause ou reprise | Inchangé : ces pages ne sont pas dans le cache, donc jamais comptées comme faites |
| Tout est illisible | Document terminé, aucun débit, les choix sont proposés |
| Traduire quand même | 1 page débitée après réussite |

**À surveiller :** `rebill_for_document` ne rétablit pas une ligne réduite. L'ordre dans la clôture et un remboursement rejoué seront testés.

### Routes (`api/documents.py`)
- `GET /{id}/pages-illisibles` : liste des pages, motif, choix, `en_cours`.
- `PATCH /{id}/pages-illisibles` : `{pages: [...], choix: "original" | "vide" | "traduire"}`. Copie `…_d<id>` si la traduction est partagée, cache d'aperçu invalidé.
- `traduire` lance un travail dans l'ordonnanceur des scans, hors de `jobs`. La clôture de `jobs` rembourse tout le document en cas d'erreur, ce qui serait faux sur un document déjà terminé.

### Interface
Panneau `ScanPagesPanel`, placé au même endroit que le panneau des images, avec les mêmes classes et jetons. Si deux pages ou plus sont concernées, une barre « Pour toutes les pages » s'ajoute. Texte :

> **Page 12 : lecture impossible**
> Cette page contient peut-être du contenu que nos méthodes n'identifient pas. Si vous la traduisez quand même, elle vous sera facturée.
> [Traduire quand même] [Afficher l'original] [Laisser vide]

Avancement : « Lecture du scan, page 12 » et « En attente de lecture ». Toutes les langues du projet sont traduites. Sous 480 px, les boutons passent en colonne.

## 6. Impacts

| Domaine | Effet |
|---|---|
| Base de données | Aucune migration : tout est dans les fichiers de traduction |
| Sécurité | Routes réservées au propriétaire, comme celles des images. Débit sous verrou |
| Performance | Une lecture à la fois : mémoire OCR plafonnée à environ 1,1 Go. Attente plus longue en charge (voir §7) |
| Coûts | Une page illisible ne coûte plus rien au client et ne déclenche aucun appel de traduction |
| Déploiement | Rien de neuf. Variables facultatives `OCR_SCAN_WORKERS`, `OCR_DELAI_PAGE_S` |
| Documentation | Bilan §1, §3, §7, §8 ; `README.md:38,57,90` ; `deploiement.md:231` ; `ocr-production.md` |

## 7. Risques

| Risque | Conséquence | Parade |
|---|---|---|
| Image de l'extension derrière un scan dense | Jusqu'à 90 s d'attente au lieu de 14 s | Attente bornée, message « Réessayez ». Mesure à refaire à 5–10 clients sur le serveur. Si c'est trop lent : réduire le temps d'effacement quand d'autres attendent |
| Scan très long | 59 pages denses : environ 90 minutes | Pages visibles au fil de l'eau, pause et reprise conservées |
| Redémarrage du serveur en pleine lecture | Travail interrompu | Reprise existante ; pages lues conservées sur disque |
| Disque | Environ 2 Mo par page lue, sans plafond dédié | Surveillance déjà prévue au bilan, cas d'un scan de 500 pages à mesurer |
| Passe de cohérence sur un document lu à moitié | Termes moins harmonisés | Sans gravité : les pages illisibles n'y entrent pas |

## 8. Décisions prises sans attendre

Réglables ensuite, aucune ne bloque :
- sans réponse du client, l'original reste affiché, sans limite de temps ;
- page blanche : ni question, ni facturation ;
- page qui a manqué de temps : même message qu'une page illisible, car le client a le même choix ;
- « traduire quand même » ne relance que la page choisie, jamais tout le document ;
- après un choix, le client peut changer d'avis entre « original » et « vide ». Une page traduite quand même reste traduite ;
- limite du forfait inchangée pour les scans.

Décidé par l'utilisateur à l'essai (06/11, P2 de 6.13.11) : une page illisible sans choix reste en langue d'origine dans le **fichier téléchargé**, avec une mention discrète en haut de page « Page non traduite : laissée en langue d'origine. » dans la langue cible (anglais si la langue n'a pas de texte prévu). Pas de mention si le client a choisi « garder l'original », ni sur une page blanche (`engines/pdf/stream.py` `signaler_illisibles`, `ocr_pages.pages_originales`).

Décidé par l'utilisateur (06/11, P3 de 6.13.11) : une page **hors sélection** se traite comme une page illisible, par un choix **page par page** avec « appliquer à toutes » :
- **Traduire** : la page est incluse après coup (une page, ou toutes les pages exclues d'un coup), facturée comme une page traduite ;
- **Garder l'original** : la page reste en langue d'origine, sans mention ;
- **Retirer** : la page disparaît du fichier téléchargé (ex. « retirer toutes les pages exclues » pour ne garder que les pages traduites). L'aperçu la garde à sa place avec le badge « Retirée du fichier · Modifier », pour que le client voie ce qu'il a retiré et puisse revenir sur son choix (décision de l'utilisateur, 06/11, option A).
Sans choix : original avec la mention « Page non incluse dans la traduction » (même règle qu'en P2). Le choix reste modifiable ensuite.

Conception P3 (PDF natif et scan ; PPTX hors plan) :
- **Quelles pages** : pages 1..N de l'original, moins la sélection (`reglages["pages"]`), moins celles déjà dans `pages.json` (incluses après coup), moins celles qui ont un état OCR (elles suivent le chemin des pages illisibles). Calculées seulement à la fin de la traduction ; sans sélection, aucune.
- **Routes** : les mêmes `GET`/`PATCH /pages-illisibles`, avec `motif: "hors_selection"`. Nouvelle valeur `retirer` dans `choix.json`. Un choix doit convenir à la sorte de page : `vide` pour une page illisible seulement, `retirer` pour une page hors sélection seulement (sinon 409).
- **Rendu** : la branche « copiée » du moteur pose la mention « Page non incluse dans la traduction » (7 langues) sauf si la page est en `original`. Téléchargement : les pages `retirer` sont ôtées du fichier (`_garder_pages`).
- **Aperçu** : la page retirée garde sa place avec une carte « Page retirée du fichier » et « Modifier » — sinon le choix ne pourrait plus être changé et la numérotation des pages glisserait. Écart avec « disparaît de l'aperçu », signalé à l'utilisateur.
- **Traduire** : tâche calquée sur « traduire quand même ». PDF natif : traduction d'une copie avec `pages={page}`, puis `_reporter_page` (sans PDF OCR). Scan : lecture normale ; si la page s'avère illisible ou blanche, elle rejoint le chemin des pages illisibles. Débit d'une page seulement si elle est traduite ; débit refusé → retour arrière.
- **Interface** : la carte de `ScanPageOverlay` adapte ses textes et boutons (Traduire / Garder l'original / Retirer) ; « appliquer à toutes » ne vise que les pages de même sorte ; le message global et le badge de bibliothèque ne comptent pas ces pages.

## 9. Points à trancher par l'utilisateur

Aucun point bloquant. Le japonais reste reporté.

## 10. Consignes d'implémentation

Points qui ne se déduisent pas du reste de l'étude :

- **Guichet :** `tour(priorite=None, delai=None, arret=None)` en `with`, réveil environ chaque seconde, ticket retiré du tas sur toute sortie anticipée. `definir_priorite` pose la priorité sur le fil, depuis `_worker` du scheduler. Aucun import d'`app` hormis la configuration, pour éviter les imports circulaires.
- **Extension :** le `with` reste dans la fonction exécutée en thread, pour ne pas bloquer la boucle async. `OCROccupe` aboutit au 503 existant, sans débit.
- **Lecture :** le délai de 90 s démarre après l'obtention du tour. Une `OCRError` de page devient `illisible`. Tesseract absent reste `OCRUnavailable`, car c'est une panne et non une page illisible.
- **Moteur :** `lecteur_ocr` est appelé avant la relecture du cache, même pour une page déjà traduite, afin que la source reste cohérente pour la passe de cohérence. Avec `lecteur_ocr=None`, le comportement doit rester strictement identique.
- **Envoi déjà en cache :** relire `api/translate.py` entre les lignes 653 et 790. Un second envoi du même fichier ne doit ni relire l'OCR, ni facturer les pages illisibles ou blanches, et doit exposer les pages illisibles.
- **Traduire quand même, travail de fond :** le worker exige un `job_id` valide pour `jobs.demarrer`. Créer un job non rattaché au document (`_document_id` renvoie None) pour que la clôture de `jobs` n'y touche jamais.
- **Traduire quand même, solde :** la page est d'abord reportée dans le cache JSON sous le verrou d'écriture, avec son statut `ok`, puis débitée sous ce même verrou. Si `debiter` renvoie Faux ou lève une erreur, l'ancien contenu du cache et l'ancien statut de la page sont remis. Sur un refus seulement, la page prend ensuite le motif `solde` ; sur une erreur, elle garde son motif d'avant et l'erreur remonte. Aucune livraison gratuite, aucun débit sans page livrée.
- **Lectures en cours :** la liste des pages en cours de lecture (`_pages_en_cours`) n'existe qu'en mémoire, dans un seul processus. Un redémarrage pendant une lecture la perd : la page reste `illisible` avec son choix, et l'utilisateur peut relancer. Dans ce processus unique (`deploiement.md`), deux demandes simultanées sur la même page sont sérialisées par le verrou de traduction, et la seconde à aboutir trouve la page déjà `ok` au moment du report : elle n'est ni reposée ni débitée. Ce verrou et `_verrou_copie` sont propres au processus : à revoir avant d'en ajouter un second.
- **Verrou obligatoire :** le moteur lit le cache JSON au début et réécrit tout à la fin. Deux travaux simultanés sur la même traduction perdraient une page : tenir un verrou par `translation_path` pendant tout l'appel du moteur et la mise à jour.
- **Traduction partagée :** la copie `…_d<id>` copie aussi le dossier `.ocr` et `.source.pdf`.

**Tests à écrire :**
- `test_ocr_file.py` : exclusion mutuelle, priorité, ordre d'arrivée, anti-famine, délai, arrêt pendant l'attente.
- `test_ocr_pages.py` : statuts, source reconstruite seulement si périmée, ancien `ocrv2` intact, page blanche contre photo.
- Moteur : PDF de 3 pages (texte, scan lu, illisible), reprise sans relecture, `pages_vides`, `lecteur_ocr=None`.
- `test_ocr_facturation_pages.py` : ordre avec `rebill_for_document`, clôture rejouée sans double remboursement, document entièrement illisible sans débit, traduire quand même (réussite, aucun mot, solde épuisé, 402), deux travaux concurrents, accès par un autre utilisateur.
- À adapter sans retirer de vérification de sécurité ou de facturation : `test_documents_scannes.py`, `test_ocr.py`, `test_ocr_credits_achetes.py`, `test_ocr_endpoint.py`, `test_ocr_v2_*`, `scripts/verify_ocr_runtime.py`.

## 11. P5 — Solde partiel sur un scan : budget à la page

### Besoin
Aujourd'hui, si le solde ne couvre qu'une partie du scan (« traduire les pages couvertes »), `api/translate.py` garde les K premières pages de la sélection. Une page illisible ou blanche parmi elles est remboursée à la clôture, mais elle a pris la place d'une page lisible : le crédit rendu aurait pu traduire la page suivante. Exemple : 10 pages, solde 5 crédits, et la page 2 est blanche. Le job traduit 1, 3, 4 et 5, puis rend 1 crédit. La page 6 reste non traduite alors que l'utilisateur pouvait la payer.

Décision de l'utilisateur : on traite les pages une par une, dans l'ordre. Une page illisible ou blanche est sautée sans être comptée. On s'arrête quand le solde est épuisé ou qu'il ne reste plus de pages, et on rend ce qui n'a pas servi.

### Existant mesuré
- **Débit au lancement** (`translate.py`) : une ligne pour le quota du forfait, une pour les crédits achetés. Pour un remboursement partiel, `refund_unfinished(gardees)` rend d'abord les pages achetées. Il est sans effet s'il est rejoué.
- **Lecteur de page** (`_lecteur_ocr`) : il est appelé une fois par page sélectionnée, dans l'ordre. Il renvoie `None` pour une page à texte, sinon un objet avec le statut `ok`, `illisible` ou `blanche`. Une page mémorisée dans `.ocr/` est relue sans OCR, donc le résultat est le même à chaque exécution.
- **Cache partagé** : le JSON de traduction est nommé d'après la sélection et peut servir à d'autres documents. Le rendu affiche toutes les pages traduites présentes dans le JSON. `_copie_du_document` crée déjà la copie propre à un document (utilisée par P3).
- **Pages hors sélection** (P3) : le fichier `selection.json` de la copie détermine la carte « Traduire » et la mention « page non incluse ».

### Options
| Option | Pour | Contre |
|---|---|---|
| A. Garder la coupe aux K premières pages | Rien à changer | Crédit inutilisé dès qu'une page est illisible ou blanche |
| B. Estimer avant le lancement (lire toutes les pages d'abord) | Sélection exacte dès le départ | Il faut tout lire par OCR avant de traduire, donc une attente longue et du coût pour des pages qui ne seront peut-être pas payées |
| **C. Budget à la page pendant le job (retenu)** | Fidèle à la décision ; pas d'OCR inutile au-delà du budget ; réutilise P3 pour la suite | Il faut isoler le document à la clôture (cache partagé) |

### Conception (option C)
1. **Lancement** : le mode budget s'applique quand on traduit seulement les pages couvertes, que le fichier est un PDF avec des pages scannées, que la couverture est partielle et que rien n'a déjà été payé. La sélection reste entière, le débit vaut `couvert`, et on enregistre `"budget": couvert` dans les réglages. Le PPTX et le PDF sans scan gardent la coupe actuelle : sans page à sauter, le résultat est le même.
2. **Job** (`translation_runner`) : une enveloppe compte les pages consommées. Une page `ok` ou une page à texte consomme 1, une page `illisible` ou `blanche` ne consomme rien. Une fois le budget atteint, elle renvoie `hors_budget` sans lire la page. Pour un job suivant, elle enregistre `.ocr/budget_<job>.json` avec la liste des pages traitées et celle des pages consommées.
3. **Moteur** : une page `hors_budget` est recopiée avec la mention « page non incluse », comme une page hors sélection.
4. **Clôture** (`jobs.py`, statut `done`) : le document reçoit sa copie propre. Elle ne garde que les pages consommées et reçoit `selection.json` = pages traitées. Les pages restantes passent donc par la carte P3 « Traduire », qui facture page par page. On garde `consommees − pages lues sans traduction` et on rend le reste. Cette étape n'a lieu qu'à la création de la copie : une clôture rejouée ne retire pas une page ajoutée ensuite par P3.

### Impacts et risques
- **Argent** : le débit n'est jamais supérieur au solde (même plafond qu'avant) ; le remboursement est sans effet s'il est rejoué. → revue **auditeur**.
- **Pause puis reprise** d'un job en mode budget : les pages faites sont gardées. Une reprise avec un solde encore partiel est refusée (règle existante `deja_payees == 0`).
- **Cache partagé** : la copie ne garde que les pages payées. Une page déjà traduite par un autre compte ne s'affiche donc pas gratuitement.
- **Une page lue sans texte traduit** consomme une place du budget, puis elle est remboursée. Ce cas est rare et on l'accepte.
- Rien à faire côté i18n ou interface : on réutilise la mention et la carte P3.
