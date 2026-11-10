# Journal de mise en production — novembre 2026

Consolidation des PR (#57), SEO (#58, #59), release 1.7.0 et bascule de la production sur le VPS OVH (#68). Repris de l’ancienne PASSATION de `main`.

## 2026-11-07 03:42 — Consolidation des 7 PR ouvertes

- **Doublons** : PR empilées. #32 et #35 ⊂ #53 ⊂ #54 ⊂ #55 et #56. Seules #55 (extension), #56 (3 commits OCR) et #52 (inbox orchestrateur, indépendante) portent du travail propre.
- **Branche** : `integration/pr-consolidation`, fusions dans l'ordre #55, #56, #52 ; PR #57 vers `main`.
- **Corrigé** : migration de #52 renommée `0020_orchestrator_events` (down_revision `0019_extension_avance`) ; sinon deux têtes Alembic et `upgrade head` en échec au déploiement. Conflits d'import (`api/extension.py`) et de routeurs (`app/__init__.py`) résolus en gardant les deux côtés.
- **Vérifié en local** : une seule tête Alembic, compilation Python, JSON valides, `npm run lint` et `npm run build` OK. Suites backend complètes : CI de la PR #57.
- **Reste** : fusionner #57 une fois la CI verte, fermer #32/#35/#53/#54/#55/#56/#52 comme intégrées, fusionner la PR Release Please, puis lancer manuellement le workflow de déploiement AWS.

## 2026-11-07 04:00 — Relecture de la PR #57 en attente, audit SEO/GEO

- **État** : PR #57 (`integration/pr-consolidation`) ouverte, CI 7 vertes / 2 en cours / 0 échec au dernier relevé. Rien fusionné sur `main`, aucune PR fermée.
- **Verrou** : le commanditaire relit #57 avant toute fusion. Ne pas fusionner sans son accord explicite.
- **Audit SEO/GEO du site en ligne** : bases correctes (title, description, canonical, OG, JSON-LD, robots, sitemap). Manques : sitemap d'une seule URL, toutes les routes servent le même `<head>` avec canonical `/home`, pas de hreflang ni d'URL anglaise, pas de `llms.txt`, pas de compression gzip/brotli, ~800 Ko de JS. Les nouvelles pages des PR (`/extension`, pages légales) ne sont pas dans `frontend/public/sitemap.xml`.
- **Prochaine étape** : après accord, fusionner #57, fermer les 7 PR intégrées, fusionner la PR Release Please, déclencher le déploiement AWS manuel, puis traiter le SEO/GEO dans une PR séparée.

## 2026-11-07 04:10 — Correctifs SEO / GEO (branche feat/seo-geo)

- Branche `feat/seo-geo`, partie de `integration/pr-consolidation` (PR #57, toujours en attente de relecture : ne pas fusionner sans accord).
- Source unique des pages publiques : `frontend/seo/site.json`. `frontend/scripts/prerender.mjs` (lancé par `npm run build`) écrit `dist/<route>.html`, `sitemap.xml` et `llms.txt` ; `frontend/public/sitemap.xml` supprimé.
- `frontend/nginx.conf` : `gzip_proxied any` (Caddy ajoute `Via`), `try_files $uri $uri.html`, redirection `/index`.
- `scripts/ci/verify_public_seo.py` étendu ; job CI `seo` lance le prérendu avant nginx.
- Vérifié localement : build + lint OK, contrôle SEO PASS sur nginx 1.27 (sources et vrai `dist`), JS 802 Ko → 294 Ko en gzip.
- Non traité : hreflang / URL anglaises (routage i18n à concevoir), FAQ structurée sur `/home` (aucune FAQ visible sur la page React).
- `public-https-verification` échouera contre la production tant que cette branche n'est pas déployée.

## 2026-11-07 04:29 — Pages d'intention SEO/GEO (branche feat/seo-intent-pages)

- Branche `feat/seo-intent-pages`, partie de `feat/seo-geo` (PR #58). Plan venant de la session « expert-seo-geo », vérifié contre le code avant exécution.
- P0 : nœud `SoftwareApplication` complété (`offers` gratuit, `featureList`, `inLanguage`) ; `url` de l'Organization → `https://www.trigenys.com` (trigenys.com n'expose pas de JSON-LD, l'`@id` local est gardé).
- P1 : 9 pages statiques sans JavaScript, décrites dans `frontend/seo/pages/*.json` et déclarées dans `site.json` (`source: "content"`) : `/traduire-pdf`, `/traduire-word`, `/traduire-powerpoint`, `/traduire-excel`, `/traduire-anglais-francais`, `/traduire-francais-anglais`, `/tarifs`, `/confidentialite-documents`, `/comparatif`. Blocs réutilisables (étapes, limites, avant/après, confidentialité) dans `site.json`. FAQPage par page, date `verified`, sources citées pour le comparatif.
- `verify_public_seo.py` : contrat prix/limites contre le backend, pages de contenu sans script, FAQ visible, lien vers `/home`, `offers`/`featureList`.
- Vérifié : build + lint OK, prérendu idempotent (octets identiques), contrôle SEO PASS sur nginx 1.27, test de mutation du contrat, rendu mobile sans défilement horizontal de page.
- À décider : landing `comparison.row_data_precis` (« Supprimées sous 24h ») et `row_ocr_other` contredisent la politique / les faits concurrents. P2 (annuaires, Product Hunt, AlternativeTo, fiche store, article) à créer en issues après accord.
- Ordre de fusion après accord : #57 → #58 → cette PR. Aucune fusion faite.

## 2026-11-07 10:29 — Issues P2 SEO hors site et synchronisation du board

- Issues activées sur le dépôt (`gh repo edit --enable-issues`, réversible) avec l'accord de l'utilisateur.
- Créées avec métadonnées `appfactory-project` intégrées (P2, phase Release) : #60 annuaires, #61 Product Hunt, #62 AlternativeTo (S), #63 fiches Chrome/Edge, #64 article de lancement (Documentation). Script idempotent (saute un titre existant).
- Board : #61 à #63 manquaient (runs annulés par la concurrence du workflow réutilisable) ; resynchronisées via `workflow_dispatch`, les 5 sont en Backlog avec les bons champs. Leçon ajoutée dans `docs/engineering/lessons-learned.md`.
- PR ouvertes, rien fusionné : #57 (consolidation), #58 (feat/seo-geo), #59 (feat/seo-intent-pages, base #58).
- Après accord : fusionner #57 → #58 → #59, fermer #32/#35/#52/#53/#54/#55/#56, fusionner la PR Release Please, déployer sur AWS, vérifier la production (`public-https-verification.yml`).
- Toujours à décider : textes de la landing `comparison.row_data_precis` et `row_ocr_other`.

## 2026-11-07 21:49 — Ré-épinglage appfactory v1.4.0 (PR #65)

- PR #65 (`chore/repin-appfactory-v1.4.0`, base main) : `project-automation.yml` passe de `14d51168` à v1.4.0 `0523510` (concurrence par issue/PR, corrige la perte de syncs en rafale). Testée par `workflow_dispatch` depuis la branche sur #62 : succès, aucun doublon. Non fusionnée.
- Côté appfactory : PR EagleFox31/appfactory-project-automation#148 (épinglage documenté, test anti-SHA défectueux, LESSON-2026-017), non fusionnée.

## 2026-11-09 08:15 — Audit SEO à froid de la production

- Prod mesurée : sitemap 1 URL, `/extension`, `/tarifs`, `/llms.txt` en 404, pas de gzip. Aucun des travaux #57/#58/#59 n'est en ligne.
- Estimation : prod ~20/100 ; après déploiement ~45/100 (technique fort, autorité quasi nulle, contenu FR seulement).
- Prochaine étape inchangée : accord de fusion #57 → #58 → #59 (+ #65, appfactory#148), puis déploiement et Search Console.

## 2026-11-09 09:49 — Fusion, release 1.7.0, déploiement bloqué
- **Fait** : #59 → #58 → #57 (squash 3bfbdc2) et #65 fusionnées dans main, CI verte ; #32, #35, #52–#56 fermées (renvoi vers #57). Tests de #57 stabilisés (490a598 : `with TestClient`, unicité PPTX par id d'élément).
- **Release** : v1.7.0 publiée via #66 (PR ouverte à la main : Actions n'a pas le droit de créer des PR ; titre « chore: » de #57 corrigé par `BEGIN_COMMIT_OVERRIDE`).
- **Verrou** : le job `deploy-production` (reusable-aws-ssm-compose-deploy @9496878) exige ≥ 75 USD de crédits AWS Free Plan ; seuil non atteint, prod toujours sur l'ancienne version. L'utilisatrice vérifie AWS (Billing → Free Tier).
- **Prochaine étape** : une fois AWS débloqué, `gh workflow run aws-production-deploy.yml --ref main`, vérifier prod (sitemap 15 URL, /extension, /tarifs, /llms.txt, gzip, public-https-verification), puis renvoyer `https://precis-translator.trigenys.com/sitemap.xml` dans Search Console (propriété domaine `sc-domain:trigenys.com`, déjà vérifiée).
- **Ouvert** : appfactory#148 (non fusionnée, sans accord) ; texte landing « Supprimées sous 24h ».

## 2026-11-09 10:23 — Piste migration vers le VPS OVH
- Déploiement AWS toujours bloqué (crédits Free Plan < 75 USD). Option étudiée : migrer Précis sur le VPS OVH `ubuntu@15.235.90.215` (infos consignées dans le CLAUDE.md global, section « Infrastructure partagée »).
- Inventaire en lecture seule : 2 vCPU, 3,7 Go RAM (~2 Go disponibles), swap 2 Go, 16 Go disque libres ; Docker + Compose, Caddy systemd ; 9 conteneurs déjà présents (WAHA ~430 Mo).
- Prochaine étape : accord explicite avant toute modification du VPS ; puis compose Précis avec limites mémoire, site Caddy, dump/restore Postgres depuis EC2, bascule DNS, EC2 gardé en secours.

## 2026-11-09 11:02 — Migration vers le VPS OVH (stack prête, bascule DNS en attente)
- Export EC2 : workflow jetable (OIDC + SSM), archive chiffrée RSA/AES, branche et artefact supprimés. Base 43 Ko, 13 tables.
- VPS : `~/precis-translation/{releases,app-<sha>,current,shared/backend.env (600),migration-ec2}`, projet compose `precis-translation`, overlay `deploy/vps/` (PR #68). Relais `edge` sur 127.0.0.1:8090.
- Restauration : comptes identiques ; migrations 0014→0020 appliquées. Mémoire : backend ~390 Mo / 1 Go.
- Reste : installer `deploy/vps/precis-translator.caddy` dans `/etc/caddy/sites/` + reload **après** la bascule DNS (A `precis-translator` 13.36.127.47 → 15.235.90.215, Spaceship, TTL 1800) ; vérifier prod ; resoumettre le sitemap GSC ; EC2 en repli quelques jours.
- Déploiement CI vers le VPS : nécessite une clé SSH dédiée en secret GitHub (création refusée par le garde-fou, décision utilisateur).

## 2026-11-09 11:20 — Précis en production sur le VPS
- DNS basculé (A `precis-translator` → 15.235.90.215), site `/etc/caddy/sites/precis-translator.caddy` installé, certificat obtenu (tls-alpn-01).
- Vérifié via le VPS : 8 routes clés OK, sitemap 15 URLs, gzip, IP client réelle transmise jusqu'au backend, `X-Forwarded-For` falsifié ignoré.
- GSC : sitemap resoumis, lu le 9 nov. 2026, 15 pages découvertes.
- EC2 (i-0ce97ff971dd343b2) intact, en repli quelques jours puis à arrêter (coûts).
- Reste : fusion PR #68 ; déploiement CI vers le VPS (clé SSH dédiée en secret GitHub, accord utilisateur requis) ; texte landing « Supprimées sous 24h » ; appfactory#148 (confirmation).
- Redéploiement manuel : `git archive` → `~/precis-translation/releases/`, extraire dans `app-<sha>`, lien `current` + `backend/.env` → `shared/backend.env`, puis `docker compose -p precis-translation --env-file backend/.env -f docker-compose.yml -f docker-compose.https.yml -f deploy/vps/docker-compose.vps.yml up -d --build`.

## 2026-11-09 11:57 — Déploiement CI vers le VPS
- Clé `precis-deploy-ci` dans `~/.ssh/authorized_keys` du VPS avec `restrict,command="/home/ubuntu/precis-translation/bin/deploy.sh"` (copie de `deploy/vps/remote-deploy.sh`) ; sauvegarde `authorized_keys.bak-precis-deploy`. Privée seulement dans le secret GitHub `PRECIS_VPS_SSH_KEY` ; variables `PRECIS_VPS_TARGET`, `PRECIS_VPS_KNOWN_HOSTS`.
- `deploy-vps.yml` (dispatch + appel depuis `release.yml`) ; job EC2 seulement si `vars.PRECIS_DEPLOY_TARGET=aws`.
- Testé avec la clé CI : shell refusé, `déployé : 7630ad91a314`, rejeu no-op. PR #68 CI 8/8 verte, **non fusionnée**.
- Prochaine étape : fusionner #68 (et #67), lancer `deploy-vps.yml` sur main pour valider le chemin GitHub → VPS. Si le script change : réinstaller `bin/deploy.sh` à la main (volontairement hors du flux de déploiement).

## 2026-11-09 12:08 — Chemin GitHub → VPS validé
- #68 fusionnée (`be46d55`), #67 fusionnée. Pas de release déclenchée (commits `ci`/`docs`).
- `deploy-vps.yml` lancé sur main (run 42605991292) : succès, `déployé : 865e40a045f0`, contrôles publics OK.
- Vérifié : /health 200, /tarifs 200, sitemap 15 URLs ; `current -> app-865e40a045f0`, 3 versions gardées ; conteneur db non recréé (données conservées).
- Restant : arrêter l'EC2 i-0ce97ff971dd343b2 après quelques jours de stabilité ; supprimer ensuite `~/precis-translation/migration-ec2` et `~/.ssh/authorized_keys.bak-precis-deploy` sur le VPS.
