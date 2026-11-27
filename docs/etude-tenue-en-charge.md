# Étude : tenue en charge (beaucoup d'utilisateurs en même temps)

Date : 27/11/2026. Question de départ : « si beaucoup d'utilisateurs traduisent, prévisualisent ou téléchargent en même temps, est-ce que le serveur tient ? ».

Méthode :
- Chaque route HTTP et chaque tâche de fond ont été relues.
- Pour chacune, on a noté ce qu'elle fait de lourd, ce qui la limite, et si elle peut bloquer les autres utilisateurs.
- Les points critiques ont été vérifiés dans le code ligne par ligne.
- **Aucune mesure de charge n'a encore été faite.** Les chiffres « mémoire par appel » sont des estimations tirées du code et des mesures précédentes. Le plan prévoit de les mesurer (§7).

## 1. Besoin

- **Ne jamais tomber.** Le serveur doit refuser poliment ce qu'il ne peut pas faire, plutôt que de s'effondrer et de perdre le travail de tout le monde.
- **Rester réactif.** Un utilisateur qui consulte sa bibliothèque ne doit pas attendre parce qu'un autre traduit 300 pages.
- **Être équitable.** Une seule personne, ou un script, ne doit pas pouvoir monopoliser le serveur.
- **Être honnête avec l'utilisateur.** Quand il faut attendre, l'écran le dit (« en file, position 3 »). Il ne doit pas tourner sans fin.

## 2. Le serveur aujourd'hui

| Élément | Valeur | Où |
|---|---|---|
| Mémoire du conteneur backend | 1 Go | `deploy/vps/docker-compose.vps.yml` |
| Processus | 1 seul uvicorn, donc une seule « boucle » qui répond à toutes les requêtes | `backend/docker-entrypoint.sh` |
| Threads pour le travail bloquant | 40, partagés par toutes les routes | réglage par défaut de FastAPI/anyio |
| Places de traduction | **1 seule** : (1024 − 300 − 284 − 234) / 150 | `app/services/memoire.py:74`, `scheduler.py:44` |
| Conversions LibreOffice | 1 à la fois, sur tout le serveur | `engines/office.py:45` (`preview_lock`) |
| Détection OCR | 1 à la fois | `app/services/ocr_v2/ppocr.py:59` |
| Taille max d'un fichier | 100 Mo | nginx et backend |
| Limite de débit | Seulement sur la connexion, l'extension, le support et les journaux | `app/rate_limit.py` |

**Ce qui est déjà bon, et que l'on garde :**
- un seul LibreOffice et une seule détection OCR à la fois ;
- des places de traduction comptées, avec une file affichée dans l'ordre d'arrivée ;
- un cache du rendu par document ;
- un remboursement des jobs interrompus au redémarrage ;
- des réponses sensibles marquées `no-store` ;
- un refus quand le disque est presque plein.

## 3. Normes de référence

| Norme | Ce qu'elle demande |
|---|---|
| OWASP API Security Top 10, **API4:2023 « Consommation de ressources sans limite »** | Limiter le nombre d'appels, la taille des entrées, la mémoire, le temps de traitement et le nombre de travaux par client. |
| **RFC 6585 (code 429)** et **RFC 9110 (code 503 et en-tête `Retry-After`)** | Trop de demandes d'un même client : répondre 429. Serveur saturé : répondre 503. Dans les deux cas, dire dans combien de temps réessayer. |
| AWS Builders' Library, *Using load shedding to avoid overload* | Près de la saturation, refuser tout de suite ce qui dépasse, pour garder rapides les demandes acceptées. |
| AWS Builders' Library, *Timeouts, retries and backoff with jitter* | Les clients réessaient avec un délai croissant et un peu de hasard, pour ne pas revenir tous en même temps. |
| Patrons d'architecture Microsoft Azure : **Bulkhead**, **Queue-Based Load Leveling**, **Throttling** | Cloisonner les ressources par type de travail, faire passer les travaux lourds par une file de taille bornée, et freiner chaque client. |
| Documentation Python asyncio et FastAPI : *running blocking code* | Ne jamais faire de calcul ni d'attente bloquante dans une fonction `async`. Sinon tout le serveur s'arrête. |
| Docker HEALTHCHECK et sondes Kubernetes | La sonde de santé doit être légère, et jamais limitée en débit. Sinon le serveur est redémarré à tort. |

## 4. Les cas à risque, du plus grave au moins grave

Chaque cas est présenté avec un exemple concret, sa cause et la correction conforme.

### Critiques : le serveur tombe ou ne répond plus

**C1. Le suivi de traduction en direct gèle tout le serveur.**
- *Exemple.* Six personnes ont un onglet ouvert sur une traduction en cours. Le serveur passe l'essentiel de son temps à attendre pour elles. La bibliothèque des autres utilisateurs met plusieurs secondes à répondre. La sonde de santé finit par échouer, Docker redémarre le conteneur, et toutes les traductions en cours sont perdues.
- *Cause.* `q.get(timeout=0.2)` est une attente bloquante, appelée dans une fonction `async` ([translate.py:980](../backend/app/api/translate.py#L980)). Le commentaire dit « non-bloquante », mais c'est faux.
- *Correction (norme asyncio).* Attendre sans bloquer : relire la file sans délai, puis `await asyncio.sleep`. Ou passer l'attente dans un thread.

**C2. La file d'attente garde les fichiers en mémoire, sans limite.**
- *Exemple.* Dix utilisateurs lancent chacun un fichier de 100 Mo. Une seule traduction démarre. Les neuf autres attendent, chacune avec son fichier entier en mémoire. Cela fait 900 Mo avant le moindre travail, donc dépassement de mémoire, redémarrage et tout est perdu.
- *Cause.* La file n'a pas de taille maximale ([scheduler.py:129](../backend/app/services/scheduler.py#L129)), et chaque job en attente garde le contenu du fichier dans ses arguments ([translate.py:832-863](../backend/app/api/translate.py#L832-L863)).
- *Correction (Queue-Based Load Leveling, AWS load shedding).*
  - Le job en file ne garde que le **chemin** du fichier, déjà enregistré sur disque. Le fichier n'est relu qu'au démarrage du job.
  - La file a une taille maximale. Au-delà, le serveur répond **503 avec `Retry-After`** et un message clair : « Le service est très demandé. Réessayez dans 2 minutes. Aucun crédit n'a été débité. »

**C3. Le budget mémoire ne couvre que les traductions.**
- *Exemple.* Trois personnes téléchargent en même temps un PDF traduit de 300 pages qui n'est pas en cache. Chaque téléchargement reconstruit le document, soit environ 3 fois sa taille en mémoire. Une traduction tourne en parallèle. Le serveur tombe.
- *Cause.* Ces travaux tournent hors du budget mémoire, qui ne compte que les traductions et les scans :
  - téléchargement ([documents.py:446](../backend/app/api/documents.py#L446)) ;
  - aperçu ([documents.py:706](../backend/app/api/documents.py#L706)) et aperçu partiel ([translate.py:1069](../backend/app/api/translate.py#L1069)) ;
  - rendu de fond du cache ([render_cache.py:154](../backend/app/services/render_cache.py#L154)) ;
  - filigrane des pages d'essai.

  De plus, une traduction qui attend de la mémoire depuis plus de 600 s démarre quand même ([memoire.py:163](../backend/app/services/memoire.py#L163)).
- *Correction (Bulkhead).*
  - Deux « compartiments » bornés pour les travaux lourds hors traduction : les **rendus** (reconstruction de document, rendu de fond) et la **rastérisation** (images filigranées). Chacun a un nombre fixe de places, compté dans le budget mémoire.
  - Le délai de 600 s ne lance plus le travail sans marge. Le job reste en file et l'écran l'affiche.

**C4. Un téléchargement peut reconstruire le même document plusieurs fois en même temps.**
- *Exemple.* Un utilisateur impatient clique trois fois sur « Télécharger ». Le serveur lance trois rendus de 280 s du même document de 285 pages, en parallèle.
- *Cause.* La route de téléchargement ne prend pas le verrou de rendu par document ([documents.py:530-538](../backend/app/api/documents.py#L530-L538)). L'aperçu, lui, le prend.
- *Correction.* Prendre le même verrou par document (`build_lock`) : le deuxième clic attend le premier rendu et réutilise son résultat.

### Graves : tout le monde ralentit, ou une personne monopolise le serveur

**G1. Des calculs lourds tournent directement sur la boucle.**
- *Exemple.* Un utilisateur envoie un PDF de 100 Mo. Pendant que le serveur compte ses pages lisibles et calcule son empreinte, **toutes** les autres requêtes attendent plusieurs secondes.
- *Cause.* Ces calculs sont lancés directement dans une fonction `async` :
  - `pages_avec_texte` ([translate.py:499](../backend/app/api/translate.py#L499)) ;
  - l'empreinte SHA ([translate.py:582](../backend/app/api/translate.py#L582), [:791](../backend/app/api/translate.py#L791)) ;
  - `office_illisible` ([translate.py:150](../backend/app/api/translate.py#L150)).
- *Correction (norme asyncio).* Passer chaque calcul dans un thread (`run_in_threadpool`).

**G2. Aucune limite de débit sur les routes lourdes.**
- *Exemple.* Un script appelle « aperçu PDF » en boucle avec des fichiers différents. Chaque appel déclenche une conversion LibreOffice. La file LibreOffice s'allonge sans fin, et les vrais utilisateurs attendent des minutes pour voir leur document.
- *Cause.* L'upload, l'analyse, la traduction, l'aperçu, l'aperçu partiel, le téléchargement et l'original n'ont aucune limite de débit. nginx n'en a pas non plus.
- *Correction (OWASP API4, RFC 6585).*
  - Une limite **par utilisateur connecté**, et par adresse IP pour les visiteurs. Elle est adaptée à chaque route : par exemple 10 envois par minute, 60 aperçus par minute.
  - Une limite au niveau de nginx (`limit_req`), qui arrête un excès avant qu'il n'atteigne Python.
  - Réponse 429 avec `Retry-After`.
  - **Une conversion « pour voir » à la fois par utilisateur** : un nouvel envoi annule la conversion qu'il remplace dans la file.

**G3. Une conversion LibreOffice est lancée après chaque envoi, sans plafond.**
- *Exemple.* Vingt personnes déposent un fichier Word dans la même minute. Vingt conversions passent l'une après l'autre, à environ 10 s chacune. La vingtième attend plus de 3 minutes, et l'aperçu d'un utilisateur qui traduit attend derrière elles.
- *Cause.* Une tâche est créée par envoi ([translate.py:163-171](../backend/app/api/translate.py#L163-L171)). Toutes passent par l'unique LibreOffice, sans priorité ni limite.
- *Correction (Bulkhead + priorité).*
  - Une file LibreOffice bornée, avec **priorité aux travaux dont un écran a besoin tout de suite** : l'aperçu d'une traduction en cours passe avant la conversion préparée à l'avance.
  - Une conversion préparée à l'avance pour un fichier que l'utilisateur a déjà remplacé est annulée.

**G4. Les 40 threads peuvent être tous pris.**
- *Exemple.* Dix téléchargements lents et vingt conversions en attente occupent les 40 threads. Même la connexion d'un utilisateur reste bloquée, parce qu'elle a aussi besoin d'un thread.
- *Cause.* Un seul réservoir de threads sert tout le monde, y compris les travaux qui attendent LibreOffice pendant des minutes.
- *Correction (Bulkhead).* Les travaux longs (rendus, conversions) attendent leur place **avant** de prendre un thread, dans leur compartiment de C3. Les requêtes courtes gardent toujours des threads libres.

**G5. Le filigrane des pages d'essai est refait à chaque affichage.**
- *Exemple.* Un visiteur gratuit traduit un deck de 75 diapos. À chaque page terminée, l'écran redemande l'aperçu, et le serveur refiligrane toutes les pages. Cela fait environ 75 × 75 / 2 ≈ 2 800 images. Avec dix visiteurs, le processeur et la mémoire saturent.
- *Cause.* `rasterize_for_trial` n'a pas de cache ([translate.py:1069](../backend/app/api/translate.py#L1069), [documents.py:834](../backend/app/api/documents.py#L834)).
- *Correction (Cache-Aside).*
  - Chaque page filigranée est mise en cache sur disque, identifiée par son contenu.
  - Seules les nouvelles pages sont fabriquées, dans le compartiment « rastérisation » de C3.

**G6. Un envoi de 100 Mo occupe 200 à 300 Mo de mémoire.**
- *Exemple.* Trois envois de 100 Mo en même temps font environ 800 Mo. Le serveur tombe.
- *Cause.* Le fichier est reçu en morceaux, puis recollé en mémoire ([translate.py:139-148](../backend/app/api/translate.py#L139-L148)), puis relu entier ([translate.py:176](../backend/app/api/translate.py#L176)).
- *Correction (OWASP API4).* Écrire les morceaux directement dans un fichier temporaire, en calculant l'empreinte au passage. Ensuite, travailler à partir du chemin du fichier.

### Moyens : gêne ou fragilité

**M1. La sonde de santé est limitée à 10 appels par minute** ([system.py:24](../backend/app/api/system.py#L24)).
- *Exemple.* La sonde Docker, une sonde de surveillance externe et un administrateur qui vérifie la version partagent la même limite. La sonde reçoit un 429, et le conteneur peut être redémarré alors qu'il fonctionne.
- *Correction.* Retirer la limite de `/health` (norme des sondes). La garder légère : aucun accès à la base ni au disque.

**M2. Les aperçus et téléchargements sont envoyés d'un bloc, depuis la mémoire.**
- *Exemple.* Un client sur une connexion lente télécharge un PDF de 150 Mo. Les 150 Mo restent en mémoire du serveur pendant toute la durée du transfert.
- *Cause.* Ces routes renvoient le fichier entier ([documents.py:503](../backend/app/api/documents.py#L503), [:563](../backend/app/api/documents.py#L563), [:660](../backend/app/api/documents.py#L660), [:770](../backend/app/api/documents.py#L770), [:820](../backend/app/api/documents.py#L820)).
- *Correction.* Servir un fichier déjà sur disque **en flux** (`FileResponse`). Le serveur n'a alors en mémoire que le morceau en cours d'envoi.

**M3. Le cache d'aperçu s'efface à chaque mise à jour du moteur PDF, même pour les PPTX et DOCX.**
- *Exemple.* Le lendemain d'une mise à jour du moteur PDF, dix utilisateurs rouvrent leur PPTX. Dix reconversions complètes passent une par une derrière LibreOffice, et le dernier attend plus d'une heure.
- *Cause.* Le nom du cache contient la version du moteur PDF ([render_cache.py:57](../backend/app/services/render_cache.py#L57)), quel que soit le format du document.
- *Correction.* Le nom du cache contient la version **du moteur qui a produit ce rendu** (moteur PPTX pour un PPTX, moteur DOCX pour un DOCX). Le principe reste le même : la clé dit tout ce dont le résultat dépend.

**M4. Les rendus de fond n'ont pas de plafond global** ([render_cache.py:154](../backend/app/services/render_cache.py#L154)).
- *Exemple.* Un utilisateur parcourt ses 15 anciens documents. Cela lance 15 rendus complets en parallèle.
- *Correction.* Ces rendus passent dans le compartiment « rendus » de C3, une à deux places au plus, et le plus récent demandé passe en premier.

**M5. Le verrou en base est gardé longtemps pendant l'envoi d'une traduction** ([translate.py:565](../backend/app/api/translate.py#L565)).
- *Exemple.* Le verrou sur le compte de l'utilisateur reste posé pendant l'écriture du fichier sur disque. Les autres actions de ce compte attendent, et des connexions à la base restent occupées.
- *Correction.* Faire tout le travail sur les fichiers **avant** d'ouvrir la transaction. Ne garder sous verrou que le débit des crédits et la création du job : quelques millisecondes.

**M6. La limite de débit est gardée en mémoire et par adresse IP** ([rate_limit.py](../backend/app/rate_limit.py)).
- *Exemple.* Cinquante salariés d'une même entreprise sortent sur Internet par la même adresse IP. Ils partagent donc une seule limite, et se bloquent les uns les autres.
- *Correction.* Compter **par utilisateur connecté**, et par IP seulement pour les visiteurs. Garder la mémoire actuelle tant qu'il n'y a qu'un seul processus, et le noter comme condition pour passer à plusieurs processus.

**M7. Chaque onglet ouvert interroge le serveur toutes les 4 secondes** ([useDocumentLibrary.ts:234](../frontend/src/hooks/useDocumentLibrary.ts#L234)).
- *Exemple.* 200 utilisateurs ont la bibliothèque ouverte, cela fait 50 requêtes par seconde rien que pour elle, plus deux lignes de journal par requête.
- *Correction.*
  - Ne pas interroger quand l'onglet est caché (`document.visibilityState`).
  - Espacer les appels avec un délai croissant et un peu de hasard (AWS backoff + jitter), et respecter `Retry-After`.
  - Ne pas journaliser chaque appel de suivi.

**M8. Tout est perdu au redémarrage.**
- *Exemple.* Après un manque de mémoire, les traductions en cours sont arrêtées et remboursées, mais l'utilisateur doit tout relancer lui-même.
- *Correction.*
  - Les corrections C1 à C3 suppriment la cause principale.
  - Ensuite, une **reprise automatique** : le job reprend là où il en était, à partir des pages déjà traduites sur disque.
  - Cette reprise est à étudier à part, parce qu'elle touche la facturation (point à trancher, §8).

**M9. Un deuxième onglet sur la même traduction « vole » une partie des événements** ([jobs.py:162](../backend/app/services/jobs.py#L162)).
- *Exemple.* Le même utilisateur ouvre sa traduction sur deux onglets. Chaque onglet ne reçoit qu'une partie des pages terminées, et l'aperçu saute des pages.
- *Correction.* Chaque onglet suit l'état du job (les pages faites) au lieu de consommer une file commune.

### Faibles

**F1. Le démarrage est un peu long**, à cause du préchauffage de LibreOffice et de l'aperçu d'essai, et du balayage du disque. C'est borné et acceptable. La sonde de santé répond dès que le serveur est prêt.

**F2. Les routes d'administration convertissent sans limite**, mais seuls les administrateurs y ont accès. Elles passent quand même dans les compartiments de C3, pour qu'un administrateur ne fasse pas tomber le service par mégarde.

**Vérifiés et sans problème :**
- L'extension de navigateur : limite de 60 appels par minute, détection OCR une à la fois, cache des images.
- L'envoi d'e-mails : asynchrone, avec un délai maximal.
- Le téléchargement du résultat (`/result`) : déjà envoyé en flux.

## 5. Options

| Option | Pour | Contre |
|---|---|---|
| **A. Corriger dans l'application actuelle** (cloisons, file bornée, limites, flux, cache du filigrane) | Corrige les causes. Rien à payer. Tient sur le serveur de 1 Go. Conforme aux normes du §3. | Le nombre de traductions simultanées reste limité par la mémoire, mais la file est honnête et rien ne tombe. |
| B. Plus de mémoire ou plusieurs processus | Simple à faire. | Ne corrige rien : le blocage C1, les files sans limite et l'absence de limite de débit restent. Plusieurs processus multiplieraient même les LibreOffice. Coût mensuel en plus. |
| C. Sortir LibreOffice et les rendus dans un service séparé (file Redis, workers dédiés) | Isolement complet, montée en charge horizontale. | Gros chantier, nouveau composant à exploiter. Prématuré tant que A n'est pas fait et mesuré. |

**Recommandation : A.** Ensuite, mesurer (§7). B ou C ne se justifient que si la mesure montre que A ne suffit plus.

## 6. Plan (option A), par lots vérifiables

1. **Lot 1, le serveur ne tombe plus et ne gèle plus :**
   - C1 : attente non bloquante du suivi en direct.
   - G1 : calculs passés dans des threads.
   - M1 : `/health` sans limite de débit.
   - C2 : la file ne garde que le chemin des fichiers, avec une taille maximale et une réponse 503 + `Retry-After`.
   - G6 : envoi écrit sur disque au fil de l'eau.
2. **Lot 2, cloisons :**
   - C3 et G4 : compartiments « rendus » et « rastérisation » comptés dans le budget, fin du démarrage sans marge après 600 s.
   - C4 : verrou de rendu sur le téléchargement.
   - M4 : plafond des rendus de fond.
   - G3 : file LibreOffice bornée avec priorité.
3. **Lot 3, équité :**
   - G2 et M6 : limites de débit par utilisateur, `limit_req` nginx, réponse 429 + `Retry-After`.
   - M5 : verrou en base raccourci.
4. **Lot 4, économie :**
   - G5 : cache du filigrane.
   - M2 : envoi des fichiers en flux.
   - M3 : clé du cache selon le moteur réel.
5. **Lot 5, côté navigateur :**
   - M7 : pas d'interrogation quand l'onglet est caché, délai croissant, respect de `Retry-After`, messages « service très demandé ».
   - M9 : suivi multi-onglet.
6. **Hors de ces lots :** M8, reprise automatique après redémarrage, à étudier séparément.

Chaque lot fera l'objet d'une PR distincte, avec ses tests et une mesure avant/après.

## 7. Comment on prouve que ça tient

On utilise la reproduction existante : un conteneur Docker de 1 Go, identique à la production. Un script de charge (Locust ou k6, outils standard) joue des scénarios réalistes, chacun **avant puis après** chaque lot :

| Scénario | Critère de réussite |
|---|---|
| 20 utilisateurs ouvrent leur bibliothèque et y restent | Réponse en moins de 300 ms pour 95 % des requêtes |
| 10 traductions lancées en même temps, avec 10 onglets de suivi ouverts | Aucun redémarrage. La bibliothèque reste sous 300 ms. Les jobs en file affichent leur position. |
| 10 envois de 100 Mo en même temps | Pic mémoire sous 900 Mo. Au-delà de la capacité : 503 + `Retry-After`, aucun crédit débité. |
| 10 visiteurs gratuits suivent un deck de 75 diapos | Aucun redémarrage. Chaque page filigranée n'est fabriquée qu'une fois. |
| 5 téléchargements de gros PDF non en cache + 3 clics répétés | Un seul rendu par document. Pic mémoire sous 900 Mo. |
| Un script appelle l'aperçu en boucle | 429 après la limite. Les autres utilisateurs ne voient aucun ralentissement. |
| Le lendemain d'une mise à jour du moteur PDF | Les aperçus PPTX et DOCX s'ouvrent depuis le cache. |

## 8. Points à trancher

1. **Seuils de la file.** Combien de traductions en attente avant de répondre « service très demandé » ? Proposition : 20 au total et 3 par utilisateur.
2. **Limites de débit par route.** Les valeurs proposées sont données au G2. Elles seront ajustées d'après la mesure du lot 3.
3. **Reprise automatique après redémarrage (M8).** Faut-il l'étudier maintenant, ou après les lots 1 à 5 ? Recommandation : après, parce que les lots 1 à 3 suppriment l'essentiel des redémarrages.

## Sources

- [OWASP API4:2023 Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/fr/0xa4-unrestricted-resource-consumption/)
- [RFC 6585, code 429](https://datatracker.ietf.org/doc/html/rfc6585) ; [MDN, en-tête Retry-After (RFC 9110)](https://developer.mozilla.org/docs/Web/HTTP/Headers/Retry-After)
- [AWS Builders' Library, Using load shedding to avoid overload](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload)
- [AWS Builders' Library, Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter)
- [AWS Well-Architected, limiter les nouvelles tentatives](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel05-bp03.md)
- Microsoft Azure Architecture Center : patrons [Bulkhead](https://learn.microsoft.com/azure/architecture/patterns/bulkhead), [Queue-Based Load Leveling](https://learn.microsoft.com/azure/architecture/patterns/queue-based-load-leveling), [Throttling](https://learn.microsoft.com/azure/architecture/patterns/throttling), [Cache-Aside](https://learn.microsoft.com/azure/architecture/patterns/cache-aside)
- Documentation Python, [asyncio : exécuter du code bloquant](https://docs.python.org/3/library/asyncio-dev.html#running-blocking-code)
