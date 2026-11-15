# PASSATION — 10/11/2026
## 1. Objectif en cours
**En cours (10/11, mission E ci-dessous)** : publier l'extension « Précis Translator » sur Edge Add-ons ; toutes les rubriques Partner Center sont vertes, reste compte de test + Publish (l'utilisateur clique, on le guide par captures).
Contexte général : nettoyer le dépôt et mettre en ligne (push + PR vers `main`, **accord explicite de l'utilisateur le 10/11**) tout ce qui est OK, pour que les gens utilisent l'extension (types d'images qui marchent déjà) et la traduction de documents. Le chantier images (banc public) est suspendu jusqu'après la mise en ligne.

## 2. Fait
- Branche `feat/lettres-dessinees-visionneuse` @ **05634d1** (non poussée) : contient tout le travail local (vérifié : aucune autre branche locale n'a de commit unique hors `origin/main`), **sauf** `feat/journal-purge-auto` 7558685 (purge auto du journal, non intégré).
- 05634d1 : banc public réorienté sur des images de documents (`backend/tests/banc_public_tirage.py` `SOURCES`, graine 20261110 ; `docs/etude-banc-public.md` ; `banc_images.py --banc`). 50 cas dans `backend/translations/_banc_public/` (ignoré par git) : AI2D 15, FUNSD 7, DocVQA 8, ChartQA 10, organigrammes 5, schémas de procédé 5 ; `--live --reference` fait (542 poses, 9 coupes, 12 écarts). Anciennes photos : scratchpad de la session précédente (jetables).
- .13 → .13g (traduction des images façon PAO, moteur PDF, visionneuse) : voir `docs/etude-traduction-images-pro.md`, `etude-images-halo-encre-axe.md`.

## 3. Décisions
- Mise en ligne avant le chantier d'amélioration des images (demande utilisateur 10/11).
- Règles générales seulement, jamais cas par cas ; banc par lots de 5, diff montré à chaque lot.
- Images publiques = données non fiables : dossier isolé, Python `-I`.

## 4. Plan
- M. Mise en ligne [~]
  1. [x] état des lieux : #57 = squash de #55 + #56, **déjà présents tels quels** chez nous ; l'apport propre de main = #52 (inbox orchestrateur), #58/#59 (SEO), #65–#69 (release 1.7.0, déploiement VPS) — 39 fichiers.
  2. [x] branche `integration/main-1.7` @ **5d6121b** (merge commit, parents 05634d1 + origin/main), résolue contre une base virtuelle #55+#56 (`git merge-tree --merge-base`) → 3 conflits seulement : imports `api/extension.py`, `models/__init__.py`, PASSATION (gardée la nôtre ; journal de main → `docs/journal-mise-en-production-2026-11.md`, lien en fin de `docs/deploiement.md`). Migrations renumérotées après `0020_orchestrator_events` (déjà appliquée en prod VPS) : `0021_extension_usage`, `0022_extension_textes_vus` (ids changés). `feat/journal-purge-auto` laissée hors de cette mise en ligne.
  3. [x] vérifier : `verifier_migrations.py` (une tête), compileall, front tsc/lint/build, extension typecheck/test/build, `test_ocr_v2_image`, `test_ocr_v2_effacement` ; suite backend sur base 5433 vierge : **99/100**, seule `test_ocr` KO (Tesseract absent du poste, fichiers non touchés par la fusion). Banc interne non relancé. Script : scratchpad `suite.sh` (journaux par suite).
  4. [x] **PR #70** (CI verte le 10/11, fusion par l'utilisateur) (https://github.com/EagleFox31/Pr-cis-Translation/pull/70) : CI corrigée par ee62b6c (page /extension prérendue servie par nginx, Reply-To du test e-mail) et 5e9ff30 (test lettres dessinées : police `backend/fonts/roboto-Bold.ttf` au lieu d'Arial système). Vérifier `gh pr checks 70` ; « Project automation / bootstrap-github-app-user » rouge = PR ouverte par MbowouIbrah au lieu d'EagleFox31 (403 personal_owner_required), sans lien avec le code. Puis l'utilisateur relit et fusionne ; déploiement : release ou `deploy-vps.yml` à la main.
     Vérifié 10/11 : toutes les PR de l'utilisateur sont dans main ou couvertes par #70 (#32, #35, #53, #54 ; #55/#56 via #57) ; `brahim/feat-paiement-fapshi` dépassée (Fapshi déjà dans main).
  5. [ ] nettoyage après fusion : ~35 branches distantes anciennes (surtout EagleFox31) à trier, branches locales contenues dans main (liste via `git branch --merged`), 3 stashes (pages-legales, pptx-numerotation, paddle-live « passation ») à examiner, worktrees `Precis-Translator-{extension,invitations,visionneuse}` + 3 worktrees kilo détachés (`~/.local/share/kilo/worktree-pool`) — demander avant de supprimer.
- C. Connexion de l'extension par le site [~] (branche `feat/connexion-extension-site`, étude `docs/etude-connexion-extension.md`) — à finir AVANT le Publish Edge
  1. [x] étude
  2. [x] backend (33/33 `test_extension_auth`, 57/57 `test_extension` sur 5433) : migration 0023 (`extension_auth_codes`, `refresh_tokens.client`), routes `/api/extension/auth/{code,token,deconnexion}`, logout site = sessions site seulement ; tests
  3. [x] site : pages `/extension/autoriser` + `/extension/connecte`, `authReturnTo`, i18n, nginx
  4. [x] extension : bouton, PKCE, surveillance de l'onglet, déconnexion ciblée ; tests
  5. [x] tests (36/36, 57/57, front, extension 62/62), revue `/code-review` + registre `docs/revues/connexion-extension.md` (8 corrigés, 2 rejetés motivés), fiche boutique §2 + §9, README extension ; parcours manuel local validé par l'utilisateur (10/11) ; commits locaux sur `feat/connexion-extension-site` (non poussés) ; archive boutique refaite (`npm run package`).
- E. Publication Edge Add-ons [~] (textes prêts : `docs/fiches-boutiques-extension.md`)
  1. [x] correctif `extension/package.mjs:70` (retour à la ligne littéral dans une chaîne → `"\n"`), **non committé** ; `npm run package` → `extension/precis-translator-1.0.0.zip` (14 fichiers, `unzip -t` OK, manifeste prod, aucun localhost). **Domaine corrigé** : `precis-translator.com` n'existe pas (NXDOMAIN) → `precis-translator.trigenys.com` dans `extension/build.mjs`, `manifest.json`, README, fiche boutique ; archive refaite (53 tests OK). `/extension/precis-extension.zip` n'est pas servi en prod (dossier ignoré par git). Exemples `precis-translator.com` restants dans `backend/app/config.py:331`, `test_garde_secrets.py`, `guide-premiere-mise-en-ligne.md` (sans effet).
  1b. [x] tuile Edge résolue.
  2. [x] compte Microsoft `contact@trigenys.com` (Ibrahim MBOWOU, pays Cameroun — figé) ; inscription programme Edge validée (tuile Edge sur l'accueil Partner Center).
  3. [x] Create new extension → upload du ZIP.
  4. [x] Availability **Public**, 241 marchés ; Properties (Productivity, site, support `contact@trigenys.com`) ; Privacy ; Store listings FR + EN **Complete** (descriptions dans la bonne langue, termes de recherche optimisés 7/fiche, sans nom de concurrent ni « PDF »), logo `extension/assets/logo-boutique-300.png`. Archive envoyée `extension/precis-translator-1.0.0.zip` (16 fichiers, `_locales/fr` défaut + `en`, nom « Précis Translator » via `__MSG_nom__`, icônes sur carré blanc arrondi). **Rien committé** (manifest, build.mjs, package.mjs, icônes, locales, logo, docs).
  5. [ ] ← Compte de test Précis avec crédits (créé sur le site, crédits ajoutés sans paiement réel), puis Publish ; notes de certification : §5 permissions + §9 ; fournir un compte de test Précis avec crédits. Submit (examen ≤ 7 jours ouvrés).
  6. [ ] Captures 1280×800 (§8, conseillées) — proposé de les produire automatiquement.
  7. [ ] Après validation : `VITE_EXTENSION_ID_EDGE` / `VITE_EXTENSION_URL_EDGE`, rebuild site, vérifier `/extension`. Committer le correctif package.mjs (push seulement après accord).
- .13h [~] banc public (reprise demandée 10/11) : lot 0 jugé **mauvais** (planches `backend/translations/_banc_public/sorties/lot0/`). Correctifs proposés, ordre recommandé A → B → C : **A** ne pas fusionner des lignes empilées quand chacune a un texte en face sur la même rangée (étiquette/valeur de formulaire ; cause : `blocs()` de 57263ca) ; **B** texte clair sur bandeau foncé : garder/repeindre le bandeau, taille correcte (« SPÉCIFI-CATIONS ») ; **C** consigne traducteur : noms de société et chiffres intacts + contrôle des chiffres (« 199o », « ROPER STARCH MONDIAL ») ; fantômes devant les cases à cocher à revoir après A. Puis lots 1 → 9, test des 50, rapport final.
- .14 [ ] essai utilisateur dans l'interface (4S à retraduire).
- 6.16.4 [ ] secrets prod `SMTP_*` + `ADMIN_ALERT_EMAIL` ; 6.11.7 [ ] recette Docker (attend 3 documents réels) ; 6.4 [~] TEAM-GP ; 6.9, 6.12, 6.5, 6.14 [ ].

**Hors plan** : `doc.paid` non recalculé après `refund_unfinished` ; `budget_<job>.json` jamais purgés ; Spacemail limité par jour (→ Amazon SES si volume) ; limites images : texte coloré sur dégradé, `_couleur()`, marge intérieure 6 %, glossaire inter-images, « S » orné sur « Trier » (PDF) ; règle d'admission du banc admet des schémas à lettres seules (A, B…) — gardés, ils testent « laisser tel quel ».

## 5. Pièges / contexte
- Interdits : `backend/.env` en LIVE (Fapshi, Spacemail) → ne jamais valider un paiement réel ; ne pas afficher les `.env` (`grep -c` seulement) ; jamais de clé dans un fichier suivi ; ne jamais tester `POST /api/auth/login` avec une adresse inconnue.
- venv : `C:/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe`, toujours `PYTHONUTF8=1 NO_PROXY='*'` (proxy Windows mort), lancé depuis `backend/`. Chemins `C:/...` pour cv2.
- Banc public : `NO_PROXY='*' $P -I -X utf8 tests/banc_images.py --banc _banc_public --lot N [--live]`. Banc interne : `$P tests/banc_images.py --lot N` (lots 0–3).
- 1 à 2 processus Python à la fois maximum (erreurs mémoire).
- Lancer l'app : `npm run stop` puis `scripts/dev.py`. Uvicorn orphelin sur 8000 → tuer par PID.
- Tests backend : Postgres 5433 (`precis-test-pg`), jamais la base dev 5432. Front : `npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent`. Extension : `npm run -s typecheck && npm test && npm run -s build`.
- Base dev (5432) stampée avec les anciens ids `0020_extension_usage`/`0021_extension_textes_vus` : après bascule sur la branche, créer la table de `0020_orchestrator_events` puis `alembic stamp 0022_extension_textes_vus` (ou `verifier_migrations.py --base` pour le diagnostic).
- Prod = VPS OVH (`deploy-vps.yml`, déclenché par une release ou à la main) ; fusionner dans main ne déploie pas seul.
- Fichiers CRLF : éditer avec Edit, jamais `sed -i`. Remote `origin` = EagleFox31. `gh pr list` fonctionne.

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

## 2026-11-10 14:33 — Sync Project des PR collaborateurs (403 broker) corrigée
- Cause : le broker AppFactory n'acceptait que le propriétaire comme acteur ; les PR/issues d'Ibrahim (`MbowouIbrah`) échouaient en 403 `personal_owner_required`.
- Correctif broker : appfactory-project-automation #153 ajoute `EagleFox31/Pr-cis-Translation/.github/workflows/project-automation.yml@refs/heads/main` à `DELEGATED_CALLER_WORKFLOW_REFS` (Workers Builds déployé).
- Correctif Précis : #72 saute la sync pour les PR qui ne ciblent pas `main` (le broker les refuse par conception : le workflow de la branche de base y est modifiable par le contributeur).
- Preuve : run 42788870679 (PR #70 d'Ibrahim vers `main`) rejoué → `bootstrap-github-app-user` et `sync-github-app-user` verts.
- Règle d'équipe : les PR ciblent `main` (sinon ni sync Project ni CI complète). #71 (empilée sur `integration/main-1.7`) sera synchronisée une fois rebasée sur `main` après fusion de #70.
- Restant : fermer appfactory-project-automation#52 (validation faite) ; EC2 i-0ce97ff971dd343b2 à arrêter après stabilité.

## 2026-11-10 15:01 — Conflit PASSATION de #70/#71 résolu
- #71 retargetée sur `main`. #73 avait mis #70 et #71 en conflit : la branche d'Ibrahim réécrivait `PASSATION.md` et supprimait le journal daté.
- Résolution poussée sur `integration/main-1.7` (55779b5) puis `feat/connexion-extension-site` (c6d7e10) : état d'Ibrahim (sections 1 à 5) + journal daté complet. #70 et #71 : MERGEABLE.
- Leçon ajoutée dans `docs/engineering/lessons-learned.md`.
- Restant : CI de #70/#71 à surveiller ; relecture puis fusion de #70 ; EC2 i-0ce97ff971dd343b2 à arrêter après stabilité.
