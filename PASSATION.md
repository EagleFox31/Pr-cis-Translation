# PASSATION — 21/10/2026

## 1. Objectif en cours
Une seule mise à jour regroupant trois chantiers sur la branche `feat/mise-a-jour-carte-invitations-visionneuse` (depuis `origin/main` 1.5.2) : paiement par carte Paddle, invitations par e-mail, visionneuse + documents admin.

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

## 5. Pièges / contexte
- `backend/.env` en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi.
- Lancer : `npm run stop`, puis en arrière-plan `PYTHONUTF8=1 <venv backup>/python.exe scripts/dev.py` à la racine. Ne lancer aucun autre worktree en même temps.
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Tests : `cd backend && PYTHONUTF8=1 <venv>/python.exe tests/<suite>.py` (pas de pytest).
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`.
- Autre base marquée `0010_invitations` (révision disparue) : `stamp --purge 0009_abonnements`, `upgrade 0012_beta_abuse_guards`, `stamp 0013_invitations`.
- Certains fichiers front ont des chaînes en mojibake (`Ã©`) : éditer en UTF-8 sans réencoder.
- Produit Paddle sandbox `pro_01m5cza0wrhn34kss0tk9zxg4j`. Remote `origin` = EagleFox31.
