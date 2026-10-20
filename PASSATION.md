# PASSATION — 20/10/2026

## 1. Objectif en cours
Branche `feat/visionneuse` (worktree `Precis-Translator-visionneuse`) : visionneuse (sortie par la barre de nav, molette = page suivante, vignettes lisibles), plancher de fidélité de la retraduction compacte, téléchargement des originaux côté admin. Étude : `docs/etude-visionneuse.md`.

## 4. Plan
1. [x] Nav depuis l'aperçu : `handleNavClick` ferme l'aperçu puis défile (`Home.tsx`).
2. [x] Molette en bord de page → page suivante / précédente (`Home.tsx`).
3. [x] Vignettes : bordure verte + coche, anneau bleu = page affichée (`StorySection.tsx`, `index.css`).
3b. [x] Aperçu : bouton « Original » (re-télécharger son fichier source, chaque utilisateur) dans `ViewerToolbar`.
4. [x] Plancher de fidélité 60 % dans `retranslate_overflows` + test.
5. [x] Admin : `/api/admin/documents` (liste, original, traduit, journalisé) + page `/admin/documents` + tests.
6. [ ] Vérif : tests backend, tsc, lint, build ; Playwright sur la visionneuse.
7. [ ] Commit, push, PR.

## 5. Pièges / contexte
- Ne pas toucher le dépôt principal (feat/paiement-paddle) ni le worktree invitations.
- Ne jamais lire ou grep les `.env` (seulement `grep -c`).
- Tests : `cd backend && PYTHONUTF8=1 /c/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe tests/<suite>.py`.
- Certains fichiers front (ex. `StorySection.tsx`) ont des chaînes en mojibake (`Ã©`) : éditer en UTF-8 sans réencoder.
