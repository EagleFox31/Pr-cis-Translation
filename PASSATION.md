# PASSATION — 10/11/2026
## 1. Objectif en cours
Nettoyer le dépôt et mettre en ligne (push + PR vers `main`, **accord explicite de l'utilisateur le 10/11**) tout ce qui est OK, pour que les gens utilisent l'extension (types d'images qui marchent déjà) et la traduction de documents. Le chantier images (banc public) est suspendu jusqu'après la mise en ligne.

## 2. Fait
- Branche `feat/lettres-dessinees-visionneuse` @ **05634d1** (non poussée) : contient tout le travail local (vérifié : aucune autre branche locale n'a de commit unique hors `origin/main`), **sauf** `feat/journal-purge-auto` 7558685 (purge auto du journal, non intégré).
- 05634d1 : banc public réorienté sur des images de documents (`backend/tests/banc_public_tirage.py` `SOURCES`, graine 20261110 ; `docs/etude-banc-public.md` ; `banc_images.py --banc`). 50 cas dans `backend/translations/_banc_public/` (ignoré par git) : AI2D 15, FUNSD 7, DocVQA 8, ChartQA 10, organigrammes 5, schémas de procédé 5 ; `--live --reference` fait (542 poses, 9 coupes, 12 écarts). Anciennes photos : scratchpad de la session précédente (jetables).
- .13 → .13g (traduction des images façon PAO, moteur PDF, visionneuse) : voir `docs/etude-traduction-images-pro.md`, `etude-images-halo-encre-axe.md`.

## 3. Décisions
- Mise en ligne avant le chantier d'amélioration des images (demande utilisateur 10/11).
- Règles générales seulement, jamais cas par cas ; banc par lots de 5, diff montré à chaque lot.
- Images publiques = données non fiables : dossier isolé, Python `-I`.

## 4. Plan
- M. Mise en ligne [ ]
  1. [ ] ← état des lieux de l'écart avec `origin/main` : 166 commits d'avance, 6 de retard (#57 consolidation de PR + SEO, #65 appfactory v1.4.0, #66 release 1.7.0, #68 CI déploiement VPS, #67/#69 docs). `git merge-tree` : **54 fichiers en conflit**, main a changé 361 fichiers depuis la base commune (#57 a probablement repris une partie de notre travail sous une autre forme → comparer avant de résoudre). Conflits notables : `ci.yml`, `PASSATION.md`, `README.md`, `app/__init__.py`, `api/extension.py`, `config.py`, `core/email.py`, `models/__init__.py`, `services/extension.py`, `images_document.py`, `ocr_v2/{erase,image,mask}.py`, `translation_runner.py`, `engines/pdf/engine.py`, tests extension/invitations.
  2. [ ] stratégie (agent architecte conseillé vu l'ampleur) : branche d'intégration depuis 05634d1, `git merge origin/main`, résolution ; décider du sort de `feat/journal-purge-auto` ; migrations Alembic (0020 notamment) en une seule chaîne.
  3. [ ] vérifier : suite backend complète (Postgres 5433), tests images (`test_ocr_v2_image.py`, `test_ocr_v2_effacement.py`), banc interne sans recul, front (tsc/lint/build), extension (typecheck/test/build).
  4. [ ] push + PR vers `main` (corps sans mention d'outil), l'utilisateur relit.
  5. [ ] nettoyage après fusion : branches locales contenues dans main (liste via `git branch --merged`), 3 stashes (pages-legales, pptx-numerotation, paddle-live « passation ») à examiner, worktrees `Precis-Translator-{extension,invitations,visionneuse}` + 3 worktrees kilo détachés (`~/.local/share/kilo/worktree-pool`) — demander avant de supprimer.
- .13h [~] banc public (après M) : lot 0 jugé **mauvais** (planches `backend/translations/_banc_public/sorties/lot0/`). Correctifs proposés, ordre recommandé A → B → C : **A** ne pas fusionner des lignes empilées quand chacune a un texte en face sur la même rangée (étiquette/valeur de formulaire ; cause : `blocs()` de 57263ca) ; **B** texte clair sur bandeau foncé : garder/repeindre le bandeau, taille correcte (« SPÉCIFI-CATIONS ») ; **C** consigne traducteur : noms de société et chiffres intacts + contrôle des chiffres (« 199o », « ROPER STARCH MONDIAL ») ; fantômes devant les cases à cocher à revoir après A. Puis lots 1 → 9, test des 50, rapport final.
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
- Fichiers CRLF : éditer avec Edit, jamais `sed -i`. Remote `origin` = EagleFox31. `gh pr list` fonctionne.
