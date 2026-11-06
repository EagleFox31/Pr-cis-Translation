# Étude — reprise après coupure, pause et annulation d'une traduction

## Besoin (capture 22)
Ordinateur éteint à plus de 50 % d'une traduction PPTX. Au retour, le document
est en « Échec de la traduction » et « Réessayer » repart de la page 1.
Demandes : vérifier si le client est débité deux fois et si les pages déjà
faites repartent à l'API de traduction ; ajouter **pause** et **annulation**.

## Existant (mesuré)
### Facturation
- Au redémarrage, `services/startup.py:13-59` passe chaque document « en cours »
  en erreur et le **rembourse entièrement** (`usage.py:114-131`, bêta : `beta.py:255`).
- « Réessayer » (`Home.tsx:257-281`) renvoie l'original à `POST /api/translate` :
  nouveau job, **nouveau débit complet** (`translate.py:438-491`), ancien document supprimé.
- Bilan : le client paie **une seule fois** le document. Pas de double débit,
  pas de gratuité.
- Défauts :
  1. Le retry **perd la sélection d'origine** (plage de pages, mode précis, pages
     couvertes) : il peut coûter plus de pages, ou répondre 402.
  2. Si l'ancien job vivait encore (deux processus), son « terminé » refacturerait
     (`usage.py:134-156`) : double débit possible, cas rare.

### Recalcul (appels à l'API de traduction)
| Format | Sauvegarde page par page | Au « Réessayer » |
|---|---|---|
| PDF | oui, `pages*.json` écrit après chaque page (`engines/pdf/stream.py:97-107`) | pages faites **non retraduites**, seulement redessinées |
| PPTX | oui, `reprise_*.json` après chaque diapositive (`translation_runner.py:901-906`) | diapositives faites sautées (`:827-831`) |
| DOCX / XLSX | non, tout en mémoire jusqu'à la fin (`translation_ai.py:892`) | **tout est retraduit** |

Deux limites :
- **Le cache est perdu si la sélection change.** Il n'est réutilisé qu'avec
  exactement la même sélection (`translate.py:230-232, 498-515`). Or le retry
  la perd (défaut 1) : le cache peut alors être raté.
- **Les pages reprises du cache s'affichent comme si elles repartaient de zéro.**
  Leurs statuts sont réémis depuis la page 1.
  - **Comment les deux limites expliquent la capture 22.** Toute la question est
    de savoir si le cache a été retrouvé ou non :
    - **s'il a été retrouvé**, la traduction reprend vraiment, mais l'écran la
      montre repartir de 0 ;
    - **s'il a été raté**, la traduction repart vraiment de 0.
  - **À vérifier :** mesurer lequel des deux cas s'est produit, à l'étape 1.

### Pause / annulation
- **Rien n'existe côté serveur.**
  - Le bouton d'arrêt de l'interface (`useStreamingTranslation.ts:99-105`) ferme
    seulement le flux de progression. Le serveur continue de traduire, et le
    client paie.
  - `jobs.forget` retire le job de la table sans stopper son exécution.
  - L'ordonnanceur ne sait pas interrompre un travail (`scheduler.py:20-24`).
- **Un motif d'arrêt réutilisable existe déjà.** `translation_ai.py:867-869`
  vérifie un drapeau avant chaque lot.

## Options
| | Pause = arrêt propre + reprise sur le cache (recommandé) | Pause = travail figé en mémoire |
|---|---|---|
| Ressources | rien n'est bloqué pendant la pause | un poste de traduction immobilisé, les autres clients attendent |
| Coupure serveur | la pause y survit (cache sur disque) | perdue |
| Effort | moyen, mêmes points d'arrêt que l'annulation | faible mais fragile |

## Choix proposé
1. **Retry fidèle.** Garder sur le document la sélection d'origine. « Réessayer »
   devient « Reprendre » et relance avec les mêmes réglages, donc sur le cache.
2. **Reprise visible.** Les pages déjà faites passent directement « traduites »,
   au lieu de rejouer leurs étapes.
3. **Arrêt.** Un drapeau d'arrêt par job, vérifié à quatre endroits :
   - avant chaque page PDF ;
   - avant chaque diapositive ;
   - avant chaque lot DOCX/XLSX ;
   - avant le démarrage d'un job en file.
   Une route `POST /api/translate/{job}/cancel` contrôle le propriétaire.
4. **Pause** = arrêt avec cache conservé, document « En pause », bouton
   « Reprendre ». **Annuler** = on laisse finir la page en cours, puis arrêt ;
   les pages faites sont débitées, le reste est rendu (ex. : 20 pages réservées,
   annulation pendant la page 8 → 8 pages débitées, 12 rendues). Document
   « Annulé », les pages traduites restent téléchargeables.
5. **DOCX/XLSX.** Sauvegarder après chaque lot pour qu'eux aussi reprennent.
6. **Coupure serveur.** Le document passe « Interrompue — en pause » au lieu de
   « Échec ». **Facturation page par page** : les pages déjà traduites restent
   débitées, seules les pages non terminées sont rendues (ex. : 20 pages
   réservées, coupure pendant la page 8 → 7 débitées, 13 rendues). À la
   reprise, seules ces 13 pages sont débitées : les pages déjà traduites
   réapparaissent tout de suite, et le travail repart de la page non terminée
   (celle en cours est refaite entièrement, par sécurité).
   - Le décompte des pages faites se lit dans la sauvegarde sur disque
     (`pages*.json` PDF, `reprise_*.json` PPTX), seule trace qui survit à l'arrêt.
   - La remise « pages déjà payées » ne vaut que pour la reprise du propre
     document interrompu du client (contrôle serveur du propriétaire) : le cache
     est partagé par fichier, un autre compte qui dépose le même fichier paie
     normalement.
6b. **Coupure côté client** (onglet fermé, réseau perdu). Le serveur continue ;
   à la reconnexion, le client retrouve la traduction finie ou en cours dans
   sa bibliothèque. Pas de pause automatique : un client parti sur mobile
   reviendrait sinon sur un travail arrêté ; s'il veut arrêter, il a les
   boutons Pause / Annuler.
7. **Double débit.** Garde-fou : ne refacturer à la fin que si ce job est
   toujours celui du document.

## Impacts / risques
- **Base de données.** Ajout de la sélection d'origine sur le Document : petite
  migration, avec de nouveaux statuts `paused` / `cancelled`.
- **i18n.** Ajout de libellés : Pause, Reprendre, Annuler, En pause, Annulé,
  Interrompu.
- **Délai d'arrêt.** L'arrêt n'est pas instantané : il attend la fin de la page
  ou du lot en cours, quelques secondes.

## Décisions (utilisateur, 2026-10-30)
- **A. Annulation** : pas de remboursement du travail fait. On attend la page en
  cours et on débite tout ce qui a été fait ; le reste réservé est rendu.
  Bêta : unités et mots débités au prorata des pages faites.
- **B. Reprise** : le document est facturé une fois au total.
- **C. Coupure client** : le serveur continue, résultat présenté à la
  reconnexion (point 6b).
- **D. Arrêt serveur** (précisée) : on débite page par page. Les pages faites
  restent débitées, le reste est rendu, le document est mis en pause ; la
  reprise ne débite que les pages restantes (point 6).
- **E. Document annulé** : le fichier partiel est livré (pages traduites, reste
  en langue d'origine), téléchargeable comme un document terminé ; il reste
  reprenable pour traduire la suite sans repayer les pages faites.

## Plan
1. Mesure : rejouer la coupure sur un PPTX et dire si le cache est réutilisé (journal).
2. Sélection d'origine gardée + « Reprendre » (points 1, 6, 7) + tests.
3. Reprise visible (point 2).
4. Drapeau d'arrêt + route annuler/pause + statuts (points 3, 4) + tests.
5. Boutons Pause / Reprendre / Annuler (aperçu et bibliothèque) + i18n.
6. Sauvegarde par lot DOCX/XLSX (point 5).
7. Vérification navigateur par l'utilisateur.

## Retours du 30/10

| # | Constat | Cause mesurée dans le code | Correction |
|---|---|---|---|
| 1 | Après déconnexion, l'aperçu du document reste affiché | `Home.tsx` ne réagit pas au passage de `user` à `null` : ni l'aperçu, ni le flux, ni le document courant ne sont vidés | Effet sur `user` : connecté → déconnecté ⇒ `handleBack()` (coupe le flux SSE) et remise à zéro du document |
| 2 | Aperçu rouvert depuis la bibliothèque : la traduction s'affiche avant l'original | L'original est demandé converti en PDF (`?as=pdf`, conversion serveur), la traduction sort souvent du cache : elle gagne la course | La traduction est retenue tant que l'original n'est pas arrivé (ou en échec) |
| 3 | Après un arrêt, « 24/38 pages » et les vignettes continuent de tourner | a) aperçu bibliothèque : le serveur peut répondre 404 (document arrêté sans page traduite) ; après 3 échecs le suivi s'arrête mais `suiviBiblio` n'est jamais vidé ; b) flux SSE : l'événement `stopped` laisse les pages en vol à `translating`/`extracting`/`rendering` | Suivi bibliothèque vidé à l'arrêt (et dès le clic sur Arrêter) ; pages non finies remises « en attente » à `stopped` |
| 4 | L'arrêt attend la fin des pages en cours | PDF : l'arrêt n'était vérifié qu'entre deux pages ; PPTX : `f.result()` dans l'ordre puis sortie du `with` qui attend tout le pool | Arrêt immédiat : la page en vol tourne dans un fil abandonné (PDF) ; PPTX attend `FIRST_COMPLETED` par pas de 0,3 s et ferme le pool sans attendre. Une page abandonnée n'est ni livrée, ni facturée, ni mise en cache. DOCX/XLSX : le lot en cours se termine (inchangé) |
| 5 | Annuler puis quitter l'écran | À vérifier de bout en bout : statut « annulé », facturation = pages finies, bibliothèque et aperçu à jour au retour | Vérification Playwright |
