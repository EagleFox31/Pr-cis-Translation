# PASSATION — 12/11/2026
**Chantier actif = G Nouveautés** (OCR en pause : `C:/Users/IBRAH/Documents/Projets/Precis-Translator-ocr/PASSATION-OCR.md`, branche `fix/ocr-robustesse-documents`, prochaine étape cause A+2bis découpe `blocs()`).
## 1. Objectif en cours
**Mission G, branche `feat/nouveautes`** (non poussée, dernier commit 30850b2) : G.10 → G.12c faits, commités et validés par l'utilisateur (« tout est ok on peut continuer », 12/11) ; reste push + PR. Push + PR seulement sur accord (GitHub : erreur de certificat `SEC_E_UNTRUSTED_ROOT`).
Mission F terminée (PR #75). En attente de fusion par l'utilisateur : #70, puis #71, puis #75, puis E.4b.
## 2. Fait
- Branche `feat/lettres-dessinees-visionneuse` @ **05634d1** (non poussée) : tout le travail local sauf `feat/journal-purge-auto` 7558685. Banc public : 50 images de documents dans `backend/translations/_banc_public/` (`docs/etude-banc-public.md`).
## 3. Décisions
- Visite : même contenu pour tous ; seul le bouton final change (invité → /register, gratuit → /home#pricing, payant → « Terminé », ferme simplement) ; pendant la visite la barre du haut reste au-dessus du voile, seul FR/EN y est actif (`modal.css` classe `vst-ouverte`) ; écran de fin « Restez informé » (Non merci / Oui, m'avertir) après « Passer » ou le bouton final, connectés non abonnés seulement ; la croix et Échap ferment sans le montrer. `plan==='free'` = gratuit, tout autre plan (admin compris) = payant.
- Ouverture auto : après le splash, 1 essai/session ET par identité (`sessionStorage precis.nouveautes_session:<userId|invite>`) ; invité : `localStorage precis.visite_vue` ; compte : `user.nouveautes_vues_le`. Exigence 12/11 : JAMAIS vue deux fois, connecté ou non ; navigateur et compte se renseignent dans les deux sens (G.10).
- Tarifs : les 2 bandeaux (bêta à gauche, à la page à droite, pastilles pleine largeur) seulement si la bêta est ouverte ; sinon l'ancien bandeau `.pricing-payg` (titre + phrase avec prix + bouton) — demande utilisateur 12/11.
- Fondu : `BrowserRouter` ignore l'option `viewTransition` de React Router (réservée aux routeurs « data ») → appel direct à `document.startViewTransition` + `flushSync` ; immédiat sans support ou avec « réduire les animations ».
- Navigation : le menu principal qui change selon la page est un vrai défaut (on perd Tarifs/À propos hors accueil) ; bonne pratique = menu global stable + sous-menu local.
- Archivés : clic → bulle flottante au-dessus de `.p-foot` (`DocumentLibrary.tsx` `.archive-float`), hors liste pour que rien ne bouge, retirée après 9 s sauf survol/focus. Sélection : menu « … » → Sélectionner, cases 18 px, suppression séquentielle avec confirmation en 2 clics.
- Textes des documents d'exemple dans les scènes : identiques en FR/EN ; seule l'interface passe par i18n.
- Règles générales seulement, jamais cas par cas ; banc par lots de 5, diff montré à chaque lot.
- Images publiques = données non fiables : dossier isolé, Python `-I`.
## 4. Plan
- M. Mise en ligne [~]
  1–3. [x] branche `integration/main-1.7` @ 5d6121b (merge 05634d1 + origin/main), vérifications migrations/front/extension OK.
  4. [x] **PR #70** (CI verte le 10/11, fusion par l'utilisateur) (https://github.com/EagleFox31/Pr-cis-Translation/pull/70) : CI corrigée par ee62b6c (page /extension prérendue servie par nginx, Reply-To du test e-mail) et 5e9ff30 (test lettres dessinées : police `backend/fonts/roboto-Bold.ttf` au lieu d'Arial système). Vérifier `gh pr checks 70` ; « Project automation / bootstrap-github-app-user » rouge = PR ouverte par MbowouIbrah au lieu d'EagleFox31 (403 personal_owner_required), sans lien avec le code. Puis l'utilisateur relit et fusionne ; déploiement : release ou `deploy-vps.yml` à la main.
     Vérifié 10/11 : toutes les PR de l'utilisateur sont dans main ou couvertes par #70 (#32, #35, #53, #54 ; #55/#56 via #57) ; `brahim/feat-paiement-fapshi` dépassée (Fapshi déjà dans main).
  5. [ ] nettoyage après fusion : ~35 branches distantes anciennes (surtout EagleFox31) à trier, branches locales contenues dans main (liste via `git branch --merged`), 3 stashes (pages-legales, pptx-numerotation, paddle-live « passation ») à examiner, worktrees `Precis-Translator-{extension,invitations,visionneuse}` + 3 worktrees kilo détachés (`~/.local/share/kilo/worktree-pool`) — demander avant de supprimer.
- C. Connexion de l'extension par le site [~] (branche `feat/connexion-extension-site`, étude `docs/etude-connexion-extension.md`) — à finir AVANT le Publish Edge
  1–5. [x] étude, backend (migration 0023, tests 33/33 + 57/57), pages site, extension (PKCE), revue `docs/revues/connexion-*`.
  6. [ ] CI de #71 verte (vérifié 10/11) ; l'utilisateur fusionne #70 puis #71 (re-cibler #71 sur `main` si GitHub ne le fait pas) ; `deploy-vps.yml` (migration 0023 au déploiement) ; refaire le parcours de connexion sur `precis-translator.trigenys.com`.
- N. [x] 3 commits locaux sur `feat/connexion-extension-site` non poussés (5e20aa2, c47084d, 595c2f4) ← accord pour les pousser dans #71.
- F. Fluidité/responsive [x] (étude `docs/etude-fluidite-responsive.md`, revue `docs/revues/fluidite-responsive.md`, PR #75).
- G. Nouveautés [~] (étude `docs/etude-nouveautes.md` fait foi, fiche `docs/integration-nouveautes.md` ; confirmer chaque étape avec l'utilisateur)
  0–9. [x] maquettes, catalogue, migration 0024, API, e-mail, pages `/fonctionnalites` + `/desabonnement`, visite (`components/nouveautes/`), ligne du panneau compte (`NouveautesLigne.tsx`), refonte panneau + archivés (registre `docs/revues/panneau-compte.md`), RGPD, vérifs 11/11, retours du 12/11 (commits 6e7ca0c → 2afa9c7).
  10. [x] visite jamais vue deux fois, dans les 2 sens (Playwright : invité, navigateur→compte, compte→navigateur neuf) : `pages/Home.tsx:602-660` ; compte non vu + `localStorage precis.visite_vue` présent → `marquerVu()` sans rouvrir ; visite vue avec un compte ou compte déjà vu → poser `localStorage precis.visite_vue` (`NouveautesModal.tsx:11,59`). Seule limite : invité sur un navigateur neuf la voit une fois.
  10–11 commités : ca95db1 (visite), 7e1bf06 + 4929199 (tarifs).
  11. [x] piste E (`PricingCards.tsx` `.pricing-duo`, `BetaOffer.tsx`, CSS `.pricing-strip*` dans `index.css`, `pricing-grid--with-beta` retiré de `beta.css`) ; sans bêta = ancien bandeau. Playwright 1280/375 bêta ouverte (simulée via `page.route('**/api/beta/program')` `applications_open: True`) et fermée : pas de débordement ni d'erreur JS.
  12. [x] navigation piste B (étude `docs/etude-navigation-tarifs.md`) : `AppBar` unique partout (`Navbar.tsx` supprimé), 2ᵉ rangée intégrations/légal/admin, repli mesuré `navbar/useRepli.ts`, `--nav-total`. Contrôle Playwright `scratchpad/nav/chevauchement.py [--balayage]` : 342 + 2 432 situations, 0 défaut ; lint OK.
  12b. [x] 0a148c8 : Nouveautés retiré du menu (reste via panneau compte + bloc Qui sommes-nous) ; liens vers d'autres pages après un trait, fléchés ↗ (barre `.nav-sep`/`.nav-ailleurs`, menu ☰ `.mm-sep`) ; fondu 0,25 s au changement de page (`avecFondu` dans `AppBar.tsx`, aussi sur la 2ᵉ rangée et le logo). Contrôle 342 + 2 432 situations, 0 défaut ; lint + build OK.
  12c. [x] e1fa21e + 30850b2 : bouton flottant rond bleu en bas à droite, aligné sur le cadre de la barre (`right: max(--frame-pad, calc((100% - --frame-max)/2 + --frame-pad))`, `index.css` `.retour-haut`) : accueil = « Revenir en haut » hors section hero et aperçu fermé (`Home.tsx`) ; autres pages = « Accueil » (icône maison, `AppBar.tsx` quand pas de `section`). /extension sur téléphone : onglet Installation retiré (il était vide), ouverture sur Tarif, 3 onglets icône au-dessus du libellé (`ExtensionPage.tsx` `onglets`/`vue`, `extension-page.css` ≤480 px). Vérifs 12/11 : front tsc/lint/build OK, extension typecheck + 62/62 + build OK, backend compileall OK + catalogue 8/8 ; tests backend avec base NON lancés (Docker arrêté → `precis-test-pg` 5433 indisponible).
  13. [x] 12/11 : tests backend Nouveautés 23/23 + 24/24 + 8/8, poussé, **PR #76** (base `perf/fluidite-responsive`, empilée sur #75). Ordre de fusion : #70 → #71 → #75 → #76.
- E. Publication Edge Add-ons [~] (textes prêts : `docs/fiches-boutiques-extension.md`)
  1–4. [x] ZIP corrigé (`extension/package.mjs:70`, domaine `precis-translator.trigenys.com`), compte Partner Center `contact@trigenys.com`, extension créée, Public 241 marchés, Properties remplies.
  4b. [ ] Après C.6 : Partner Center → renvoyer `extension/precis-translator-1.0.0.zip` (connexion par le site) + mettre à jour l'étape 2 des descriptions FR/EN et les notes de certification (`docs/fiches-boutiques-extension.md` §2, §9).
  5. [ ] Compte de test Précis avec crédits (créé sur le site, crédits ajoutés sans paiement réel), puis Publish ; notes de certification : §5 permissions + §9 ; fournir un compte de test Précis avec crédits. Submit (examen ≤ 7 jours ouvrés).
  6. [ ] Captures 1280×800 (§8, conseillées) — proposé de les produire automatiquement.
  7. [ ] Après validation : `VITE_EXTENSION_ID_EDGE` / `VITE_EXTENSION_URL_EDGE`, rebuild site, vérifier `/extension`. Committer le correctif package.mjs (push seulement après accord).
- .13h [~] banc public (reprise demandée 10/11) : lot 0 jugé **mauvais** (planches `backend/translations/_banc_public/sorties/lot0/`). Correctifs proposés, ordre recommandé A → B → C : **A** ne pas fusionner des lignes empilées quand chacune a un texte en face sur la même rangée (étiquette/valeur de formulaire ; cause : `blocs()` de 57263ca) ; **B** texte clair sur bandeau foncé : garder/repeindre le bandeau, taille correcte (« SPÉCIFI-CATIONS ») ; **C** consigne traducteur : noms de société et chiffres intacts + contrôle des chiffres (« 199o », « ROPER STARCH MONDIAL ») ; fantômes devant les cases à cocher à revoir après A. Puis lots 1 → 9, test des 50, rapport final.
- .14 [ ] essai utilisateur dans l'interface (4S à retraduire).
- 6.16.4 [ ] secrets prod `SMTP_*` + `ADMIN_ALERT_EMAIL` ; 6.11.7 [ ] recette Docker (attend 3 documents réels) ; 6.4 [~] TEAM-GP ; 6.9, 6.12, 6.5, 6.14 [ ].
**Fait hors plan** : carte compacte `/extension` commitée (6ea558a). Signalé non traité : bordures latérales épaisses `.ext-notes` (l.62) et `.api-chantier` (l.182).
**Hors plan** : page `/extension` étape 2 : rendre `edge://extensions` copiable au clic + adresse selon le navigateur (un lien direct est impossible, bloqué par les navigateurs) — proposé, non validé ; `doc.paid` non recalculé après `refund_unfinished` ; `budget_<job>.json` jamais purgés ; Spacemail limité par jour (→ Amazon SES si volume) ; limites images : texte coloré sur dégradé, `_couleur()`, marge intérieure 6 %, glossaire inter-images, « S » orné sur « Trier » (PDF) ; règle d'admission du banc admet des schémas à lettres seules (A, B…) — gardés, ils testent « laisser tel quel ».
## 5. Pièges / contexte
- Interdits : `backend/.env` en LIVE (Fapshi, Spacemail) → ne jamais valider un paiement réel ; ne pas afficher les `.env` (`grep -c` seulement) ; jamais de clé dans un fichier suivi ; ne jamais tester `POST /api/auth/login` avec une adresse inconnue.
- venv : `C:/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe`, toujours `PYTHONUTF8=1 NO_PROXY='*'` (proxy Windows mort), lancé depuis `backend/`. Chemins `C:/...` pour cv2. Le `backend/venv` local est vide (mis de côté en `venv_vide_1549`).
- Compte démo local : `demo-gratuit@example.com` / `Demo-Precis-2026` via `POST /api/auth/login-password` (6 docs : 2 archivés, 1 échec, 1 pause) ; ses Nouveautés sont déjà vues. Vérif navigateur : `scratchpad/verif.py` (panneau), `verif5.py` (défilement /extension). API sur 127.0.0.1 (pas localhost : IPv6).
- Banc public : `NO_PROXY='*' $P -I -X utf8 tests/banc_images.py --banc _banc_public --lot N [--live]`. Banc interne : `$P tests/banc_images.py --lot N` (lots 0–3).
- 1 à 2 processus Python à la fois maximum (erreurs mémoire).
- Lancer l'app : `npm run stop` puis `scripts/dev.py`. Uvicorn orphelin sur 8000 → tuer par PID, y compris les workers `multiprocessing` du `--reload`. Les copies ocr/extension servent aussi 8000/3000 (sans Nouveautés → 404 `/api/nouveautes/abonnement`) : vérifier quel dossier sert les ports. Actuellement 8000 et 3000 servis par CE dossier (base migrée 0024) ; les arrêter avant de reprendre l'OCR.
- Tests Nouveautés : scripts `PYTHONUTF8=1 $P tests/test_*.py` depuis `backend/` ; `test_nouveautes_catalogue.py` est pytest → `PYTHONPATH=. python -m pytest -q` (pytest absent du venv, présent dans le Python système). Captures panneau : `py -X utf8 scratchpad/captures.py <out> <axe.min.js>` (Playwright = Python 3.14 utilisateur, donc sans `-I`).
- Tests backend : Postgres 5433 (`precis-test-pg`), jamais la base dev 5432. Front : `npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent`. Extension : `npm run -s typecheck && npm test && npm run -s build`.
- Base dev (5432) stampée avec les anciens ids `0020_extension_usage`/`0021_extension_textes_vus` : après bascule sur la branche, créer la table de `0020_orchestrator_events` puis `alembic stamp 0022_extension_textes_vus` (ou `verifier_migrations.py --base` pour le diagnostic).
- Prod = VPS OVH (`deploy-vps.yml`, déclenché par une release ou à la main) ; fusionner dans main ne déploie pas seul.
- Fichiers CRLF : éditer avec Edit, jamais `sed -i`. Remote `origin` = EagleFox31. `gh pr list` fonctionne.
- Playwright connecté sans vraie connexion : `localStorage precis_tokens` factice + `page.route("**/api/**")` simulé (sauf `/api/pricing` et `/api/beta/program` en `continue_`, `/api/beta/me` → 404) ; bouton du tiroir = `nav button[title]` (« Mon compte »).

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
