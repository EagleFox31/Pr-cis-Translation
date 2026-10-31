# PASSATION — 31/10/2026

## 1. Objectif en cours
Pages légales livrées (commit 60ffdfa sur `feat/pages-legales`, non poussée). En attente : retour de l'utilisateur sur les choix par défaut (§5 de `docs/etude-pages-legales.md`), puis push + PR sur accord. Relecture par un juriste avant l'ouverture publique.

## 2. Fait
- Page Bêta : `docs/etude-page-beta.md` ; `pages/BetaPage.tsx` (deux colonnes, formulaire allégé), `BetaProgramDetails.tsx` (option `badges`), `AdminShell.tsx` (`.admin-head--sticky`), `beta.css`. Commits 59b2af1, 535c6a6, 3fa501a.
- À propos : `docs/etude-section-a-propos.md` (référencée dans `README.md`, §7 = décisions).
  - `components/about/AboutSection.tsx` : à gauche, titre, méthode en une phrase (justifiée) et 3 engagements prouvés ; à droite, mascotte derrière la fiche éditeur (siège, autres produits, e-mail · LinkedIn · Facebook sur une ligne, bouton « Nous écrire »).
  - « Nous écrire » : connecté → `openSupport({category:'other'})` ; visiteur → `ContactModal` (même fichier, portail dans `body`, Échap, panneau bas ≤ 640 px ; tél./WhatsApp si renseignés). `POST /api/support` exige un compte.
  - `index.css` : classes `about-*` et `contact-*` (après `.about-section`), sélecteur `.story-grid.about-grid` pour ne pas étirer la carte.
  - Locales fr/en : `about.*` réécrit (`pledge_*`, `card_*`, `contact_cta`) ; `mission` et `val_*` supprimés.
  - `frontend/.env.example` : `VITE_CONTACT_PHONE`, `VITE_CONTACT_WHATSAPP` (chiffres, format international).
- Texte À propos remplacé (règles des traducteurs expérimentés, commit 1dd2736).
- Contact : ligne MTN (appel + WhatsApp) dans `frontend/.env` ; lien Trigenys Insight dans la fiche (commit 3a1c408).
- Pages légales (60ffdfa) : `pages/LegalPage.tsx`, `content/legal/{types,fr,en}.ts` (textes), `legal.css`, 4 routes dans `App.tsx`, 4 liens `Link` dans `FooterSection`, ligne d'acceptation `auth.accept_terms` dans `RegisterPage.tsx`, clés `footer.*` et `legal.*`. tsc, lint, build, Playwright 1266/390 verts.
- Rien n'est poussé.

## 3. Décisions
- Bêta : format gardé en léger, pas de champ langues, aucune modification serveur.
- À propos : contact `contact@trigenys.com` ; entreprise anonyme (aucun nom) ; pas d'angle FR/EN, mais la méthode des traducteurs de métier ; prestataire de traduction non mentionné (future page Confidentialité) ; Insight lié (insight.trigenys.com/fr), AgenStudio sans lien (pas de site). Numéro Orange non utilisé (dernier chiffre illisible sur la photo ; un seul champ téléphone).
- Ni année de création ni délai de réponse affichés (jouent contre la confiance).
- Numéros en variables `VITE_*` (publiques dans le bundle, c'est voulu) pour ne pas les figer dans le code.

## 4. Plan
1. [x] Étude page Bêta + choix validés.
2. [x] Mise en page deux colonnes + en-tête collé.
3. [x] Formulaire allégé + compteur + mention unique.
4. [x] Équilibrage des cartes + zone d'action du bouton.
5. [x] Vérif Bêta : tsc, lint, build, Playwright 1266×900 et 390.
6. [x] Section À propos, première version (texte fr/en).
7. [x] Étude À propos + refonte option B ; tsc, lint, build ; Playwright 1266×900 (tout sur un écran, pied de page compris) et 390 (empilé, sans débordement).
8. [x] Finition À propos (texte court justifié, liens sur une ligne, mascotte, fenêtre de contact) ; tsc, lint, build, Playwright bureau/mobile + ouverture/fermeture de la fenêtre.
9. [x] Vérif locale par l'utilisateur ; numéros MTN dans `frontend/.env`, lien Insight ; tsc, lint, build, Playwright (3 canaux, lien Insight).
10. [ ] Push + PR de `feat/page-beta-candidature` (sur accord, pas encore donné) ; rebaser après fusion de la PR #53.
11. [x] Pages légales : étude, pages, routes, pied de page, inscription ; tsc, lint, build, Playwright.
11b. [x] Mise en page des pages légales (6f8f26f) : barre de navigation comme l'administration (4 documents au centre, hamburger en mobile), page à hauteur d'écran, Retour et titre fixes, seul le texte défile (`.legal-scroll`). Vérifié avec Playwright à 1266 et 390 px.
12. [ ] ← Retour utilisateur sur les choix §5 de l'étude, corrections éventuelles dans `content/legal/*.ts` ; push + PR sur accord.
13. [x] Source des crédits : étude, pages gratuites en aperçu seul, bêta téléchargeable avec aperçu filigrané ; tests ciblés OK (37).

**Hors plan** : `frontend/tsconfig.tsbuildinfo` non suivi (à ignorer).

## 5. Pièges / contexte
- `backend/.env` en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi.
- Lancer : `npm run stop`, puis en arrière-plan `PYTHONUTF8=1 <venv>/python.exe scripts/dev.py` à la racine. Un seul worktree à la fois (ports 3000/8000).
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Tests backend sur Postgres 5433, jamais la base dev 5432.
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`.
- Jetons gris disponibles : 50/100/200/300/500/700/900 (pas de `--gray-600`).
- `.story-grid` force `align-items: stretch` plus loin dans `index.css` : surcharger avec un sélecteur composé.
- Changer de variable `VITE_*` impose de relancer le serveur front.
- Éditer les locales en UTF-8 sans réencoder. Remote `origin` = EagleFox31.
