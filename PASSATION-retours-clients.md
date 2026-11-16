# Passation — retours clients (Francko, 16/11/2026) + positionnement face aux IA

PASSATION.md est réservé par une autre session (extension Edge, e-mails) : ne pas l'écraser.

## Objectif en cours
Corriger les retours clients et l'aperçu admin, sous la direction de l'utilisateur ; en parallèle, clarifier le positionnement de Précis face à Claude/IA.

## Fait
- Étude : `docs/etude-retours-clients-2026-11.md` (5 points vérifiés sur origin/main 2b6e380 + aperçu admin).
- Coordination : sessions precis-translator-02 (extension Edge, e-mails : `backend/app/core/email*.py`, `backend/app/api/invitations.py`) et precis-translator-23 (libre). Fichiers que cette mission réserve : `frontend/src/pages/Home.tsx`, `frontend/src/components/hero/HeroSection.tsx`, `frontend/src/components/pricing/*`, `backend/app/api/admin_documents.py`, `frontend/src/pages/AdminDocumentsPage.tsx`.

- Recherche web « IA généraliste vs Précis » (non écrite dans un fichier) : ChatGPT/Gemini rendent du texte, pas un fichier remis en page ; Copilot traduit par sélection, le traducteur Word ne gère ni PDF ni scans ; OCR préalable requis partout. Forum OpenAI (témoignages) : export tronqué après la 1re page (fil 1270759), faux .docx « traduit » resté en anglais sur 30 pages (fil 1154468), refus sur PDF/livres et qualité instable (fil 927677), API = texte uniquement (fil 716117). Aucun fil Reddit exploitable trouvé.
- Lia Go (Acolad/RWS) écarté : ce n'était pas le concurrent visé (l'utilisateur parlait de « l'IA »).
- Incohérences landing relevées : « 50+ langues » (`fr/translation.json:57`) vs « 23 langues, 36 variantes » (l. 31) ; `row_ocr_other` « Non disponible » faux pour DeepL.

## Constats clés (code)
- Annuel présélectionné : `Home.tsx:36` `useState(true)`.
- Bouton hero « Voir comment ça marche » → `#features` (`HeroSection.tsx:272`) ; menu → `#story` (`AppBar.tsx:74`).
- Tarifs en bas de page (`Home.tsx:909`).
- Bêta consommée par défaut : `translate.py:267` `use_beta="auto"`, case cochée `TranslationSection.tsx:87`.
- Admin : téléchargement seul (`admin_documents.py:110,126`) ; aucune édition de texte traduit n'existe, seulement images et pages illisibles (`documents.py:760,878`).
- Paiement mobile money (MTN/Orange via Campay) : `backend/app/api/payments.py:33,152`.

## Décisions prises
- Aucun code modifié tant que l'utilisateur n'a pas donné ses consignes point par point.
- Positionnement : ne pas se battre sur la qualité de traduction (même famille de moteurs IA).

## Plan
1. [x] Analyse et vérification des retours clients
2. [x] Avis puis contre-revue sur « Précis vs Claude »
3. [ ] Consignes de l'utilisateur, point par point (tarifs, hero, aperçu admin A/B) ←
   - [x] 1 mensuel par défaut : `Home.tsx:36` `useState(false)` (non commité, tsc OK)
   - [x] 1b bascule Mensuel/Annuel + « Économisez X par mois » dans `PaymentModal.tsx` (prop `onPlanAnnualChange`, branchée dans `PricingCards.tsx`), `.pay-cycle`/`.pay-save` dans `index.css`, clés `payment.annual_save(d)` ; vérifié Playwright (Edge, API simulée) bureau + mobile ; textes courts « Économisez X/mois en annuel », une ligne garantie jusqu'à 320 px (nowrap + min(…, 3.4vw) sur `.pay-save` et `.pay-breakdown`). Script de test : scratchpad `pay.py` (mocks /api, lancer `npx vite --port 5199`).
   - [x] 2 (+3 fusionné) bouton hero secondaire → `#pricing`, libellé « Voir les tarifs » / « See pricing » (clé `hero.btn_how`), badge « Bêta ouverte » (point ambré pulsé, `.btn-ghost__badge`) affiché seulement si `useBetaProgram().program.applications_open` ; vérifié Playwright 1280/390/320 px, bêta ouverte/fermée, une ligne. Script : scratchpad `hero.py`. Point 4 reformulé par l'utilisateur
   - [x] 4 Bêta dans le panneau de compte, une ligne par forfait + choix du solde utilisé en premier (radio, partagée avec la case de la zone de traduction via `useBetaPreference`) : étude `docs/etude-forfaits-panneau.md` validée, implémentée, vérifiée Playwright (gratuit / payant+pages / bêta+payant+pages / bêta expirée × 1280/390/320)
   - [x] Crédibilité de l'accueil + comparatif par catégories : étude `docs/etude-credibilite-accueil.md` (décisions validées), textes FR/EN corrigés (langues, sécurité, mise en forme, SLA, carte « IA + méthode du traducteur professionnel »), `ComparisonTable.tsx` en 3 colonnes / 5 lignes, `FeaturesGrid.tsx` (clé `method`) ; tsc 0, i18n OK, Playwright 1280/390/320 sans débordement (script scratchpad `comp.py`) ; ensuite, à la demande : note sous le comparatif retirée (clé `comparison.note`, `.comp-note`), descriptions des cartes réécrites en phrases simples (3 lignes max, pas de style télégraphique : l’utilisateur l’a refusé)
   - [x] Aperçu admin (16/11, non commité) : le bouton « Aperçu » de `AdminDocumentsPage.tsx` ouvre l'aperçu EXISTANT de l'accueil (`navigate('/home', {state:{apercuAdmin}})`, consommé dans `Home.tsx`), lecture seule via `GET /api/admin/documents/{id}/source-pdf` et `/apercu`, sans retraduction ni débit ; « Créer ma copie » dans `ViewerToolbar.tsx` → `POST …/copie` (409 non terminé, 400 si déjà à l'admin ou si c'est une copie, idempotent, un seul commit après la photo `copie_du_document`) ; Retour ramène à la console (sauf déconnexion). Modale `AdminPreviewModal` supprimée. Barre d'aperçu mobile (≤680 px) : libellés masqués, passage sur deux lignes (corrige aussi un débordement côté client). Colonne `copie_de` (migration 0025). Preuves : `python tests/test_admin_documents.py` 39/39, tsc 0, Playwright 1280/390/320 (script scratchpad `admin.py`). Revue : limite acceptée = deux clics simultanés peuvent créer deux copies ; `backend/.zip` contient le `.env` (fichier de l'utilisateur, à ne pas commiter) ; corrigés ensuite (validés) : préférence bêta par compte (`useBetaPreference`, clé `precis_beta_first:<id>`) et panneau replié qui montre un format Bêta encore approvisionné. Sous-menu (`navbar/appbar.css`, `.nav-sub-in`) : pages en pastilles + séparateur après le titre, pour ne plus ressembler au menu principal.
   - [x] Vérification d'ensemble (16/11) : tests admin 39/39, tsc 0, build OK, JSON i18n OK ; Playwright 1280/390/320 rejoué : paiement, hero, comparatif, panneau (gratuit, payant, bêta, bêta expirée, format épuisé, préférence par compte), aperçu admin, sous-menu.
4. [ ] Test comparatif réel (Précis, Google Traduction, DeepL, Word, Claude) sur un PDF long et chargé
   - Kit proposé (accord attendu) : `docs/banc-concurrence/`, 5 docs (`scan_mv21.pdf` + vérité, pages du Code de la Route, `original.pptx` de la sauvegarde, Excel + Word réels à fournir par l'utilisateur ou fabriqués), même consigne pour chaque outil, grille (fichier rendu, pages manquantes, mise en page, tableaux/schémas, sens). L'utilisateur passe ChatGPT/Gemini/Copilot (pas d'accès ici), Précis lancé localement, comparaison HTML côte à côte.
5. [ ] Recherche marché + plan marketing

## Hors plan
- Rien.

## Pièges
- Aperçu admin : `copie_du_document` (`backend/app/services/documents.py:312`) fait la photo de la traduction ; `_racine_orpheline` (`documents.py:174`) garde les fichiers tant qu'une fiche les vise ; aperçu client = `/documents/{id}/preview` et `/original?as=pdf` (`documents.py:455,526`), rendu = `_render_or_404` (l. 213).
- Docs sources : sauvegarde `../Precis_Translator_backup_2026-06-10_13-10/backend/tests files/` (PDF + `scans/`), `.../backend/translations/d3a01a4d40bd/original.pptx`.
- Branche courante feat/nouveautes, fichiers non commités appartenant à l'utilisateur : PASSATION.md, docs/fiches-boutiques-extension.md, extension/assets/boutique/, backend/.zip.
