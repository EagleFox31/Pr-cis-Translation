# PASSATION — 22/10/2026

## 1. Objectif en cours
Audit point par point des apports de main (section 4b, prochain : point 4), puis finaliser la mise à jour unique regroupant trois chantiers sur la branche `feat/mise-a-jour-carte-invitations-visionneuse` (depuis `origin/main` 1.5.2) : paiement par carte Paddle, invitations par e-mail, visionneuse + documents admin.

## 2. Fait
- Fusion de `feat/visionneuse`, `feat/invitations`, `feat/paiement-paddle` (branches d'origine conservées, non supprimées).
- Conflits résolus en gardant les deux côtés : routeurs `backend/app/__init__.py` (beta + invitations), `README.md`, locales fr/en (`beta` + `invite`), imports `frontend/src/App.tsx` (pages beta + `CardPaymentPage` hors `AuthProvider`).
- Migration invitations renumérotée `0013_invitations` après `0012_beta_abuse_guards` (deux têtes `0010` sinon) ; une seule tête Alembic.
- Docs par chantier : `docs/paiement-carte-paddle.md`, `docs/etude-frais-carte.md`, `docs/etude-invitations.md`, `docs/etude-visionneuse.md`.

## 3. Décisions
- Un seul worktree à lancer : les trois occupaient les ports 3000/8000 (imposés par l'OAuth Google) et se coupaient mutuellement.
- Paiement carte : zone A en EUR (XAF / 655,957), crédit seulement après relecture API, minimum par moyen (`MIN_CARD_AMOUNT`).
- Invitations : réponses génériques (pas d'oracle de comptes), expéditeur = marque, `Reply-To` = inviteur, quotas anti-abus.

## 4. Plan
1. [x] Fusion des trois branches + conflits + chaîne de migrations.
2. [x] Vérif : suites backend (paddle, paiement_minimum, fapshi, verrous_plan, invitations, emails, admin_documents, retraduction_fidele), tsc + lint + build.
3. [x] Base locale : marquage corrigé (0009 → upgrade 0012 → stamp 0013, table invitations déjà présente) ; `alembic current` = `0013_invitations`.
4. [ ] ← Vérif locale par l'utilisateur sur http://localhost:3000 (visionneuse, invitations, carte sandbox).
5. [ ] Passage en live Paddle : checklist de `docs/paiement-carte-paddle.md` (MCP `paddle-live` sur demande explicite).
6. [ ] Push + une seule PR vers main (sur accord).

**Hors plan** : rattrapage serveur des paiements Fapshi `PENDING` ; secrets Paddle dans SSM ; informer les clients que l'admin accède à leurs fichiers ; `tests/test_invitations_api.py` (base requise) ; Playwright de la fenêtre d'invitation ; suppression des worktrees invitations / visionneuse une fois la PR fusionnée.

## 4b. Mission en cours : audit des apports de main (EagleFox31, 1.5.2 → 1.6.2)
Commits #45 (quota gratuit 5 pages équivalentes, comptage Office/TXT par 500 mots, droits par document `paid`/`can_download`), #47 (PlanToggle accessible), #49 (prix frais compris sur les cartes, mentions « Facturé annuellement » et « puis X/page » retirées). Fusion sans conflit (`git merge-tree`).
1. [x] Inventaire + analyse risque par point (présentée à l'utilisateur).
2. [x] Revue point par point avec l'utilisateur (décisions ci-dessous).
3. [x] Fusion de origin/main (commit b42cf32, sans conflit) ; 13 suites backend OK (aiosqlite installé dans le venv via `requirements-test.txt`), tsc + lint + build OK.
4. [x] Corrections de normalisation (étude `docs/etude-normalisation-main.md`) :
   a. [x] `_document_pages` : `ValueError` → 422 ; message neutre dans `beta_meter.office_cost`.
   b. [x] `MIN_CARD_AMOUNT` = minimum Paddle (427 F / 0,65 € / 0,70 $) + tests.
   c. [x] Retirer `monthly_total`/`annual_total` (API, type, cartes, tests) ; cartes au prix net.
   d. [x] Rétablir `billed_annually_total` (sans frais) + `equivalence` (fr/en).
   e. [x] Vérif : suites backend, tsc/lint/build, Playwright page tarifs. Fait 22/10 : 9 suites OK, tsc/lint/build OK, page tarifs vérifiée (annuel « 14 400 FCFA facturés par an », mensuel sans ligne, équivalence affichée).
5. [ ] ← Liste de modifications de l'utilisateur (à recevoir). Hors plan : page CGU inexistante (liens `#`), mention du comptage à y mettre quand elle sera rédigée.

Décisions de revue :
- Point 1 (gratuit en clair) : garder le principe de main. Dans cette branche : mention « Traduit avec Précis » en pied des documents gratuits (`KIND_FREE_OFFER`), garde-fous bêta généralisés au gratuit (e-mails jetables, limite IP/appareil), fenêtre « quota épuisé » avec petit pack Mobile Money + bonus premier achat. Branche à part : offre de lancement datée (20 pages le 1er mois, tarif Fondateur) et parrainage (+5 pages chacun, plafonné). Étude `docs/etude-<sujet>.md` avant chaque développement.
- Point 2 (comptage 500 mots Office/TXT) : garder. À la fusion : intercepter `ValueError` dans `_document_pages` (payments.py) → 422 clair ; message neutre au lieu de « …pour la bêta » ; mention du comptage sur la page tarifs/CGV (avec le point 4).
- Point 3 (prix frais compris de main, calculés au taux Mobile Money même pour la carte) : décision utilisateur = les frais n'apparaissent QUE dans la fenêtre de paiement. À la fusion : retirer `monthly_total`/`annual_total` des cartes d'offre (PricingCards) et toute autre mention de frais hors PaymentModal (chercher `fee_percent`, `fees_included`, « frais »). Minimum Paddle : le blocage avant ouverture existe déjà (message par défaut `payment.min_pages_card` « x pages minimum requises pour ce moyen de paiement ») → seulement trouver le vrai montant minimum accepté par Paddle et aligner `MIN_CARD_AMOUNT` dessus ; ne pas toucher au message ni à l'UI.
- Point 4 (#49, mentions sous les cartes retirées) : garder le retrait des frais. À la fusion : rétablir « {{total}} facturés par an » en mode Annuel (sans « frais inclus ») et la ligne d'équivalence (pages / diapositives / 1 page pour N mots), + mention dans les CGV.
- Point 5 (#47, PlanToggle en boutons accessibles) : garder tel quel ; vérifier le rendu après fusion.
- Point 6 (#45, droit par document `paid` / `can_download`) : garder tel quel, pas de déblocage rétroactif.

## 5. Pièges / contexte
- `backend/.env` en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi.
- Lancer : `npm run stop`, puis en arrière-plan `PYTHONUTF8=1 <venv backup>/python.exe scripts/dev.py` à la racine. Ne lancer aucun autre worktree en même temps.
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Tests : `cd backend && PYTHONUTF8=1 <venv>/python.exe tests/<suite>.py` (pas de pytest).
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`.
- Autre base marquée `0010_invitations` (révision disparue) : `stamp --purge 0009_abonnements`, `upgrade 0012_beta_abuse_guards`, `stamp 0013_invitations`.
- Certains fichiers front ont des chaînes en mojibake (`Ã©`) : éditer en UTF-8 sans réencoder.
- Produit Paddle sandbox `pro_01m5cza0wrhn34kss0tk9zxg4j`. Remote `origin` = EagleFox31.
