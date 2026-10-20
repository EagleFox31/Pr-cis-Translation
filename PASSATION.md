# PASSATION — 20/10/2026

## 1. Objectif en cours
Branche `feat/visionneuse` (worktree `Precis-Translator-visionneuse`) : visionneuse (sortie libre, molette = page suivante, vignettes lisibles, re-télécharger l'original), plancher de fidélité de la retraduction compacte, documents originaux côté admin. Étude : `docs/etude-visionneuse.md`. **En attente de la vérification locale par l'utilisateur.**

## 2. Fait
- `frontend/src/lib/sectionBus.ts` (`goToSection`) + écoute dans `Home.tsx` (après `handleNavClick`) : tout lien `#section` et bouton « voir les forfaits » ferme l'aperçu puis défile (`StorySection.tsx`, `ViewerToolbar.tsx`).
- Molette en bord de page, vignettes bordure verte + coche, bouton « Original » (`ViewerToolbar.tsx`, `Home.tsx` `handleDownloadOriginal`).
- `backend/engines/pdf/translate.py` `retranslate_overflows` : version compacte < 60 % de la source rejetée.
- `backend/app/api/admin_documents.py` + page `/admin/documents`.
- Vérif : tsc, lint, build OK ; test_retraduction_fidele 3/3, redécoupage 12/12, test_admin_documents 14/14 (test corrigé : l'espace de « attachment; » faisait échouer le contrôle), test_admin_users 10/10.

## 3. Décisions
- Analyse « Les 4S en bref » : faite sur la capture d'écran + lecture du code, SANS le fichier original → hypothèse, testée en simulation ; à confirmer en retraduisant 4S_EN.pdf.
- Ports 3000/8000 imposés (origines autorisées dans la console Google OAuth) : ne pas lancer sur un autre port.

## 4. Plan
1. [x] Nav depuis l'aperçu : `handleNavClick` ferme l'aperçu puis défile (`Home.tsx`).
1b. [x] Tout lien / bouton vers une section (pas seulement la barre) — commit local 9dea336.
2. [x] Molette en bord de page → page suivante / précédente (`Home.tsx`).
3. [x] Vignettes : bordure verte + coche, anneau bleu = page affichée (`StorySection.tsx`, `index.css`).
3b. [x] Aperçu : bouton « Original » (re-télécharger son fichier source, chaque utilisateur) dans `ViewerToolbar`.
4. [x] Plancher de fidélité 60 % dans `retranslate_overflows` + test.
5. [x] Admin : `/api/admin/documents` (liste, original, traduit, journalisé) + page `/admin/documents` + tests.
6. [ ] ← Vérif locale PAR L'UTILISATEUR sur http://localhost:3000 (app lancée depuis ce worktree). Tests auto : tous verts.
7. [ ] Commits a8211d9, f572655, 587f976 déjà poussés (PR #35, par erreur). Commits locaux NON poussés : 9dea336, 688cb08 + PASSATION. Proposer de passer la PR #35 en brouillon ; push seulement après son accord.

**Hors plan** : informer les clients (politique de confidentialité) que l'admin accède à leurs fichiers — à trancher par l'utilisateur.

## 5. Pièges / contexte
- **Aucun push / PR sans accord explicite de l'utilisateur après sa vérification locale.**
- Ne pas toucher le dépôt principal (feat/paiement-paddle) ni le worktree invitations.
- Ne jamais lire ou grep les `.env` (seulement `grep -c` / existence). `backend/.env` est présent dans ce worktree (copié par l'utilisateur).
- Lancer l'app : à la racine du worktree, en arrière-plan `PYTHONUTF8=1 /c/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe scripts/dev.py` ; arrêt `npm run stop`. Un seul worktree à la fois sur 3000/8000.
- Tests : `cd backend && PYTHONUTF8=1 <venv backup>/python.exe tests/<suite>.py` (pas de pytest).
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 5` (`node_modules` = jonction vers le dépôt principal).
- Certains fichiers front (ex. `StorySection.tsx`) ont des chaînes en mojibake (`Ã©`) : éditer en UTF-8 sans réencoder.
