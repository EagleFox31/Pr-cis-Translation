# Lessons learned

Mémoire des incidents et quasi-incidents. Consulter avant de toucher une zone citée.

## 2026-11-07 — Aucune compression HTTP en production

- **Contexte** : audit SEO du site public. HTML, CSS et JS (~800 Ko) servis sans compression, même avec `Accept-Encoding: gzip`.
- **Cause racine** : nginx tourne derrière Caddy, qui ajoute `Via: 1.1 Caddy`. Sans `gzip_proxied`, nginx ne compresse pas une réponse à une requête relayée. Le test CI interrogeait nginx directement, sans `Via`, donc ne pouvait pas le voir.
- **Classification** : configuration, écart entre l'environnement de test et la production.
- **Résolution** : `gzip_proxied any; gzip_vary on;` et types étendus dans `frontend/nginx.conf`.
- **Prévention vérifiable** : `scripts/ci/verify_public_seo.py` envoie `Via: 1.1 Caddy` et exige `Content-Encoding: gzip` (CI locale et vérification de production).
- **Leçon** : un contrôle d'infrastructure doit reproduire les en-têtes ajoutés par chaque relais présent en production.

## 2026-11-07 — Pages publiques invisibles des moteurs

- **Contexte** : `/extension` et les pages légales renvoyaient 404 au chargement direct, et toutes les routes partageaient le même `<head>` (canonical vers `/home`). Sitemap limité à `/home`.
- **Cause racine** : application monopage sans prérendu ; nginx ne connaissait qu'une liste figée de routes ; sitemap écrit à la main.
- **Résolution** : `frontend/seo/site.json` est la source unique des pages publiques. `scripts/prerender.mjs` génère au build une page HTML par route, `sitemap.xml` et `llms.txt`. nginx sert `$uri.html`.
- **Prévention vérifiable** : le contrôle SEO lit `site.json` et vérifie pour chaque page 200, canonical propre, un seul `h1`, JSON-LD `WebPage`, maillage interne, présence au sitemap et dans `llms.txt`.
- **Leçon** : toute nouvelle page publique s'ajoute dans `site.json`, jamais directement dans nginx ou le sitemap.

## 2026-11-07 — Affirmations publiques sans source vérifiée

- **Contexte** : rédaction des pages `/tarifs`, `/comparatif` et `/confidentialite-documents`. Deux quasi-incidents : un premier jet annonçait le Mobile Money dans toutes les zones (il n'existe qu'en zone A), et le comparatif de la landing (`comparison.row_data_precis` : « Supprimées sous 24h ») contredit la politique de confidentialité (documents gardés jusqu'à suppression, fichiers temporaires 7 jours).
- **Cause racine** : textes marketing écrits de mémoire, sans lien avec les constantes du backend ni avec la politique publiée.
- **Classification** : contenu, divergence silencieuse entre promesse publique et comportement réel.
- **Résolution** : prix, quotas, stockage, taille maximale, formats et mots par page des pages de contenu sont vérifiés contre `backend/app/core/pricing.py`, `models/plans.py`, `config.py` et `services/documents.py`. Le texte de la landing reste à corriger (décision produit/juridique).
- **Prévention vérifiable** : `scripts/ci/verify_public_seo.py` échoue si `frontend/seo/pages/tarifs.json` ou une limite citée diverge du backend (test de mutation : une page à 0,18 € fait échouer le contrôle). Chaque page de contenu porte une date `verified`, et le comparatif cite ses sources.
- **Leçon** : toute valeur chiffrée affichée publiquement doit avoir une source de vérité dans le code ou une source externe datée, et un contrôle qui casse quand elle change.

## 2026-11-07 — Issues créées en rafale absentes du board

- **Contexte** : création de 5 issues P2 (#60 à #64) en quelques secondes. Seules #60 et #64 sont arrivées sur le board « Précis Translator Development ».
- **Cause racine** : le workflow réutilisable `appfactory-project-automation` (SHA 14d51168) utilise un groupe de concurrence par dépôt (`project-automation-<repo>`, `cancel-in-progress: false`). GitHub ne garde qu'un seul run en attente par groupe : chaque nouvel événement annule le run en attente précédent, donc les événements intermédiaires d'une rafale sont perdus.
- **Classification** : automatisation, perte silencieuse d'événements (runs « cancelled », aucun échec visible).
- **Résolution** : resynchronisation une par une via `workflow_dispatch` (`issue_number`), en attendant la fin de chaque run. Vérifié par GraphQL : les 5 issues sont sur le board avec Priority, Work type, Phase et Size.
- **Prévention vérifiable** : après une création en lot, vérifier `projectItems` de chaque issue (pas seulement le statut des runs) ; correctif durable à porter dans le dépôt partagé (groupe de concurrence par issue/PR, ou bootstrap qui réconcilie toutes les issues ouvertes).
- **Leçon** : un run « cancelled » par concurrence n'est pas un no-op ; une synchronisation pilotée par événements doit avoir une réconciliation périodique ou par lot.

## 2026-11-09 — Release Please muette après une consolidation squash
- **Contexte** : #57 (7 PR, plusieurs `feat`) fusionnée en squash sous un titre `chore:` ; Release Please : « No user facing commits found », aucune release.
- **Cause racine** : le type Conventional Commits du titre de squash décide seul de la release ; un `chore:` masque les `feat` agrégés. Second écueil : le réglage du dépôt interdit à GitHub Actions de créer des PR.
- **Classification** : processus de release, near miss (version et changelog absents, aucun échec visible).
- **Résolution** : bloc `BEGIN_COMMIT_OVERRIDE` dans la description de #57, relance de `release.yml`, PR de release ouverte manuellement depuis la branche Release Please avec le label `autorelease: pending` (#66 → v1.7.0).
- **Prévention vérifiable** : pour toute PR de consolidation, titre de squash au type le plus fort agrégé (`feat` si au moins un `feat`) ou bloc `BEGIN_COMMIT_OVERRIDE` avant fusion ; après fusion, vérifier le log Release Please (« skipping » = alerte).
- **Leçon** : une consolidation hérite du type de changement le plus fort de ses composants, pas du type « ménage » de l'opération.


## 2026-11-09 — `gh -R` sur l'ancien nom du dépôt vise un autre dépôt

- **Contexte** : migration vers le VPS ; vérifications `gh run list` / `gh api .../environments` lancées avec `-R EagleFox31/precis-translation`.
- **Cause racine** : le dépôt s'appelle `EagleFox31/Pr-cis-Translation` ; `precis-translation` est un **autre** dépôt existant. Pas de redirection : les commandes répondaient sans erreur, mais sur le mauvais dépôt (0 environnement, runs étrangers).
- **Classification** : near miss — contexte erroné, sans écriture.
- **Résolution** : repérage via des runs incohérents ; nom pris depuis `git remote get-url origin`.
- **Prévention vérifiable** : dans ce dépôt, ne jamais taper `-R` à la main : `R=$(gh repo view --json nameWithOwner -q .nameWithOwner)` depuis la copie locale.
- **Leçon** : un identifiant de ressource se découvre (remote, API), il ne se reconstitue pas de mémoire ; une réponse vide n'est pas une preuve.

## 2026-11-10 — PR collaborateur : sync Project en 403, puis conflit PASSATION

- **Contexte** : PR #70/#71 d'Ibrahim (`MbowouIbrah`) ; job `bootstrap-github-app-user` en 403 `personal_owner_required`. Après correctif, l'ajout d'une entrée PASSATION sur `main` (#73) a mis #70 et #71 en conflit.
- **Cause racine** : (1) le broker AppFactory n'autorisait que le propriétaire, et refuse par conception tout workflow hors de la branche par défaut (modifiable par le contributeur) ; #71 était empilée sur `integration/main-1.7`. (2) La branche d'intégration réécrivait `PASSATION.md` (sections d'état) et supprimait le journal daté ; tout ajout sur `main` entrait alors en conflit, et une fusion telle quelle aurait effacé le journal.
- **Classification** : intégration CI (échec visible) + near miss de perte de journal.
- **Résolution** : broker appfactory #153 (délégation du workflow de `main`), #72 (sync sautée hors `main`), rejeu du run 42788870679 vert ; conflit résolu en gardant l'état d'Ibrahim (sections 1 à 5) puis le journal daté complet de `main`, sur `integration/main-1.7` et `feat/connexion-extension-site`.
- **Prévention vérifiable** : les PR ciblent `main` (sinon ni sync Project ni CI complète) ; une PR qui retire des entrées datées de `PASSATION.md` est refusée en relecture (`git diff main -- PASSATION.md` ne doit montrer que des ajouts sous les sections d'état).
- **Leçon** : un fichier « en ajout seulement » partagé entre branches ne se réécrit pas en entier ; on met à jour l'état en tête, on n'efface jamais le journal.

## 2026-11-15 — Release 1.8.0 : version codée en dur, puis disque VPS plein
- **Contexte** : la PR de release 1.8.0 échouait sur `test_version_alignee` ; une fois corrigée, le premier déploiement VPS échouait en `npm ci` / extraction de couche.
- **Cause racine** : (1) `VERSION` et l'instantané SEO recopiaient la version de `package.json` sans être déclarés à Release Please ; (2) disque partagé à 99 %, cache de build Docker jamais purgé (~4 Go).
- **Classification** : configuration de release incomplète ; capacité d'hôte non surveillée.
- **Résolution** : `extra-files` dans `release-please-config.json` (#78) ; purge du cache de build et des images orphelines, relance du job.
- **Prévention vérifiable** : `test_version_suivie_par_release_please` ; avant un déploiement VPS, vérifier `df -h /` (≥ 5 Go libres) — à automatiser dans `remote-deploy.sh` (refus explicite plutôt qu'échec en plein build).
- **Leçon** : toute copie d'une donnée versionnée doit être soit dérivée au build, soit déclarée à l'outil de release ; un hôte partagé a besoin d'un garde-fou de capacité avant chaque build.

## 2026-11-15 — Faux « retour arrière en échec » après un build VPS raté
- **Contexte** : lors du déploiement 1.8.0 (disque plein), `remote-deploy.sh` a affiché « retour arrière en échec : intervention requise » alors que la prod tournait toujours sur 865e40a.
- **Cause racine** : le lien `current` était basculé avant le build ; sur tout échec, le script restaurait le lien puis lançait `compose up -d --build`, qui reconstruisait l'ancienne version sur le même disque plein et échouait à nouveau. Les conteneurs, eux, n'avaient jamais été recréés (l'échec précédait `up`).
- **Classification** : near miss — diagnostic trompeur pouvant pousser à une intervention inutile sur une prod saine.
- **Résolution** : garde-fou de capacité avant toute écriture (`PRECIS_MIN_FREE_GB`, défaut 5 Go, refus code 73 avec `docker builder prune` proposé, non lancé) ; échec de build traité à part (lien restauré, santé vérifiée, ni `up` ni rebuild) ; le retour arrière avec rebuild est réservé aux échecs après `up`. No-op d'une version déjà saine : plus aucune écriture.
- **Prévention vérifiable** : `scripts/ci/test-vps-remote-deploy.sh` (job CI `production-deploy`) couvre disque bas, seuil configurable, no-op, build en échec avec prod saine ou KO, échec après `up`, succès.
- **Leçon** : un message de retour arrière doit refléter l'état réellement touché ; distinguer les phases sans effet sur la prod (build) de celles qui la modifient (`up`).

## 2026-11-18 — PR empilée fusionnée dans sa branche de base au lieu de `main`
- **Contexte** : release 1.9.0. #85 (traduction libre) ciblait `feat/retours-clients`, la branche de #83. #83 a été fusionnée la première dans `main` par squash, puis #85 a été fusionnée. GitHub l'a marquée « MERGED », mais `main` n'a pas bougé : le contenu était arrivé dans `feat/retours-clients`.
- **Cause racine** : la base d'une PR empilée n'est pas reciblée sur `main` quand la PR parente est fusionnée par squash sans suppression de branche. Le contrôle avant fusion ne regardait que la mergeabilité et la CI, pas `baseRefName`. Sur cette branche, la CI de #85 n'avait d'ailleurs pas tourné (seul « Project automation », ignoré).
- **Classification** : near miss. La release aurait été publiée sans la fonctionnalité annoncée.
- **Résolution** : branche d'intégration `feat/retours-clients` + `main` (un conflit dans `Home.tsx`, résolu côté #85), puis #86 vers `main`. Diff vérifié identique à #85 (37 fichiers, +1742/−107), CI complète verte avant la fusion.
- **Prévention vérifiable** : avant de fusionner un lot, `gh pr list --json number,baseRefName` ; toute PR dont la base n'est pas `main` est reciblée (`gh pr edit N --base main`) avant la fusion. Après chaque fusion, vérifier que `git ls-remote origin refs/heads/main` a bien changé.
- **Leçon** : « MERGED » ne veut pas dire « sur `main` ». Pour une PR empilée, la base fait partie du contrôle avant fusion, au même titre que la CI.

## 2026-11-18 — Nouveautés 1.8.0 et 1.9.0 absentes du catalogue (date du 9 novembre)
- **Contexte** : après la release 1.9.0, le panneau « Nouveautés » de l'app affichait la date du 9 novembre et aucune des fonctionnalités de 1.8.0 (texte des images, connexion de l'extension par le site…) ni de 1.9.0 (traduction libre, solde par forfait…).
- **Cause racine** : le catalogue `backend/app/content/nouveautes.py` est tenu à la main ; seule une case du modèle de PR rappelait de l'alimenter. Release Please monte `VERSION`, pas `DATE_VERSION` ni les entrées, et `test_version_alignee` ne compare la date qu'au contenu du catalogue lui-même : un catalogue oublié reste cohérent.
- **Classification** : oubli répété (deux releases de suite) — un rappel en prose ne suffit pas, il faut un contrôle bloquant.
- **Résolution** : 9 entrées FR/EN ajoutées (dont 1 réservée aux admins), `DATE_VERSION` = 2026-11-18, instantané SEO régénéré.
- **Prévention vérifiable** : `test_version_avec_fonctionnalites_publiee_au_catalogue` lit `CHANGELOG.md` ; si la section de la version courante contient « ### Features », au moins un élément public doit être daté après la version précédente. Il échoue donc sur la PR de release elle-même. Vérifié : avec l'ancien catalogue, le test échoue sur 1.9.0 avec un message qui indique quoi faire.
- **Near miss associé** : `test_nouveautes_api.py` codait en dur 19 éléments et comptait l'entrée admin parmi les nouveautés d'un client ; seul `test_nouveautes_catalogue.py` avait été lancé en local, la CI « Suites backend » l'a vu. Attentes désormais dérivées du catalogue ; avant de pousser une modification du catalogue, `grep -rn nouveautes backend/tests` pour lister toutes les suites concernées.
- **Leçon** : une étape manuelle répétée à chaque release doit être reliée à un artefact que la release produit (ici le CHANGELOG) et vérifiée par un test, pas par une case à cocher.
