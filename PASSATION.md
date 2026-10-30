# PASSATION — 30/10/2026

## 1. Objectif en cours
Page publique `/beta` refondue et section « À propos » de l'accueil refaite (étude validée), sur `feat/page-beta-candidature` (empilée sur la PR #53). En attente de la vérification locale par l'utilisateur.

## 2. Fait
- Page Bêta : `docs/etude-page-beta.md` ; `pages/BetaPage.tsx` (deux colonnes, formulaire allégé), `BetaProgramDetails.tsx` (option `badges`), `AdminShell.tsx` (`.admin-head--sticky`), `beta.css`. Commits 59b2af1, 535c6a6, 3fa501a.
- À propos : `docs/etude-section-a-propos.md` (référencée dans `README.md`, §7 = décisions).
  - `components/about/AboutSection.tsx` : à gauche, titre, défi du métier, méthode Précis et 3 engagements prouvés ; à droite, fiche éditeur (siège, 2026, autres produits, e-mail, tél./WhatsApp si renseignés, LinkedIn · Facebook, bouton « Nous écrire »). Mascotte retirée.
  - `index.css` : classes `about-*` (après `.about-section`), sélecteur `.story-grid.about-grid` pour ne pas étirer la carte.
  - Locales fr/en : `about.*` réécrit (`pledge_*`, `card_*`, `contact_cta`) ; `mission` et `val_*` supprimés.
  - `frontend/.env.example` : `VITE_CONTACT_PHONE`, `VITE_CONTACT_WHATSAPP` (chiffres, format international).
- Rien n'est poussé.

## 3. Décisions
- Bêta : format gardé en léger, pas de champ langues, aucune modification serveur.
- À propos : contact `contact@trigenys.com` ; entreprise anonyme (aucun nom) ; pas d'angle FR/EN, mais la méthode des traducteurs de métier ; prestataire de traduction non mentionné (future page Confidentialité) ; AgenStudio et Insight sans lien (aucun site trouvé).
- Numéros en variables `VITE_*` (publiques dans le bundle, c'est voulu) pour ne pas les figer dans le code.

## 4. Plan
1. [x] Étude page Bêta + choix validés.
2. [x] Mise en page deux colonnes + en-tête collé.
3. [x] Formulaire allégé + compteur + mention unique.
4. [x] Équilibrage des cartes + zone d'action du bouton.
5. [x] Vérif Bêta : tsc, lint, build, Playwright 1266×900 et 390.
6. [x] Section À propos, première version (texte fr/en).
7. [x] Étude À propos + refonte option B ; tsc, lint, build ; Playwright 1266×900 (tout sur un écran, pied de page compris) et 390 (empilé, sans débordement).
8. [ ] ← Vérif locale par l'utilisateur (http://localhost:3000/beta et http://localhost:3000/#about) ; renseigner les numéros dans `frontend/.env`.
9. [ ] Push + PR (sur accord) ; rebaser après fusion de la PR #53.

**Hors plan** : pages Mentions légales, CGU, Confidentialité (liens encore en `#`) → branche dédiée, avec validation juridique ; `frontend/tsconfig.tsbuildinfo` non suivi (à ignorer).

## 5. Pièges / contexte
- `backend/.env` en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi.
- Lancer : `npm run stop`, puis en arrière-plan `PYTHONUTF8=1 <venv>/python.exe scripts/dev.py` à la racine. Un seul worktree à la fois (ports 3000/8000).
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Tests backend sur Postgres 5433, jamais la base dev 5432.
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`.
- Jetons gris disponibles : 50/100/200/300/500/700/900 (pas de `--gray-600`).
- `.story-grid` force `align-items: stretch` plus loin dans `index.css` : surcharger avec un sélecteur composé.
- Changer de variable `VITE_*` impose de relancer le serveur front.
- Éditer les locales en UTF-8 sans réencoder. Remote `origin` = EagleFox31.
