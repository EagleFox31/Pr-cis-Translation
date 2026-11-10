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
