# Passation — retours clients (Francko, 16/11/2026) + positionnement face aux IA

PASSATION.md est réservé par une autre session (extension Edge, e-mails) : ne pas l'écraser.

## Objectif en cours
**18/11 — Retours du 18/11 : 10 problèmes classés dans `docs/etude-retours-18-11.md`, traités un par un, dans l'ordre (méthode par problème, confirmer chaque étape).**
- [x] 1. Filigrane bêta (18/11, fait, non commité : branche bêta retirée de `_apercu_filigrane`/`pages_filigranees`, CGU FR/EN l.82-83/273/297 réécrites, test bêta adapté free+pro, assertions ajoutées dans `test_traduction_libre`, 4 suites + tsc OK ; reste vérif locale utilisateur) ← option A : retirer la branche `reglages_de(doc).get("beta")` dans `api/documents.py:292` `_apercu_filigrane` et `:301` `pages_filigranees`. Aligner l'aperçu affiché juste après la traduction (`api/translate.py:959-967`) et l'aperçu ouvert depuis la liste. Mettre à jour les CGU `frontend/src/content/legal/fr.ts:82,83,275,299` et leur version EN. Tests à faire sur 4 cas (libre, offert, bêta, payant) × (aperçu juste après la traduction, aperçu depuis la liste, fichier téléchargé). Erreur à ne pas refaire : la règle (a) « tout ce qui est traduit avec un crédit appartient au client » était déjà décidée (`docs/etude-traduction-libre.md` l.7) ; ce filigrane est un oubli de 5.1, pas une règle en vigueur.
- [ ] 2. ← Mails admin : option A + gravité **implémentée le 18/11** (`services/alertes_admin.py`, migration 0028, 3 refus de paiement passés en `critical`), test_error_logs 21/21 et suites voisines OK sur 5433 ; **en attente de la vérification locale**, non commitée. (Origine : demandé le 18/11, compléter la section 2 de `docs/etude-retours-18-11.md` : quels événements, fréquence, regroupement des erreurs pour éviter l'avalanche, puis attendre l'ok) : seuls les tickets de support en envoient (`api/support.py:48` `_notify_admins`). À ajouter pour les candidatures bêta, les nouveaux comptes et les erreurs. Réutiliser `_notify_admins`.
- [ ] 3. ← Compte des images au dépôt : section 3 de l'étude rédigée (19/11), options A/B/C, **C recommandée, en attente de l'ok** (détails dans PASSATION.md l.3).
- [ ] 4 à 10 : voir le tableau de l'étude.

Traduction libre (`docs/etude-traduction-libre.md`) : 5.3c faite le 17/11 (écarts 14 à 18 corrigés, 47 tests + tsc/lint/build OK, achat sous l’aperçu vérifié au navigateur PC et mobile). 5.4 faite le 17/11 (« Acheter » règle d'abord avec le solde, test document tout libre, navigateur 1280/390/320) ; 5.5 faite le 17/11 (purge des aperçus sans page payée à 30 j, rappel e-mail 5 j avant, `services/purge_libres.py`, 6 tests + 57 voisins OK) ; 5.6 faite le 17/11 (402 de téléchargement réécrit, pluriels page/pages FR/EN, 2 tests anti-abus adaptés au mode libre automatique, 251 tests + tsc/lint/build + navigateur OK). Reste : vérification locale par l'utilisateur, puis commit sans push.

## Fait
- 5.3b : `POST /api/documents/{id}/regler-libres`, téléchargement `?sans_libres=1` (fichier `_PARTIEL`), fenêtre Acheter/Continuer (`frontend/src/components/library/TelechargementLibres.tsx`), bouton « Acheter » du bandeau (`StorySection.tsx` prop `onBuyLibres`, `Home.tsx`). Revue passe 1 (n° 1–12 corrigés, 13 rejeté) + contre-revue passe 2 : registre `docs/revues/traduction-libre-5.3b.md`.
- Preuves : 18 tests `test_traduction_libre` + 34 tests des suites voisines OK ; tsc/lint/build OK ; Playwright bureau, mobile, 320 px OK. Bouton « Acheter » sous l'aperçu non essayé au navigateur.
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
- Traduction libre : A1 (Continuer = fichier des seules pages payées) et B1 (le solde paie d'office ce qu'il peut au téléchargement).
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
   - [ ] 5 Forfait gratuit / téléchargement (oublié, relevé le 16/11 après la PR #83) : les pages offertes ne sont PAS téléchargeables (`translate.py:618` `doc_is_paid = not gratuit or achetees > 0`, 402 `documents.py:393`, aperçu filigrané `documents.py:285`), alors que la carte Gratuit affiche « Téléchargement des traductions inclus » (`PricingCards.tsx:74`, clé `pricing.feat_download`) et le panneau « Téléchargement inclus » (clé `free_plan_hint`). Décision attendue : corriger les textes, ou ouvrir le téléchargement des pages offertes.
     - **Règle décidée par l'utilisateur (16/11)** :
       - (a) Toute page traduite avec un forfait (y compris les 5 pages offertes du Gratuit, la Bêta et les pages achetées) est en clair, sans limite : aperçu net et téléchargement.
       - (b) Sans forfait ni solde, on peut quand même traduire librement. Le résultat n'est visible qu'en aperçu, avec le filigrane et toutes les protections actuelles (rastérisation `rasterize_for_trial`, pas de téléchargement). Aujourd'hui cette traduction est refusée (402 `insufficient_credits`).
       - (c) Document mixte (des pages avec forfait, d'autres sans) : il n'est pas téléchargeable tant que les pages libres ne sont pas payées. Le client paie pour les débloquer ; rien d'autre.
     - Prochaine étape : étude `docs/etude-traduction-libre.md`, mesurée à l'existant. Points à couvrir :
       - comptage des pages par document : forfait ou libre ;
       - `doc.paid` à remplacer par un nombre de pages à débloquer ;
       - points d'entrée : `translate.py:446-618` (calcul de `doc_is_paid`), `documents.py:270-291` (`_may_read_clear`, `_apercu_filigrane`), `documents.py:864` (402 à la relecture), `extension.py:100-118`, `payments.py:515` (déblocage) ;
       - parcours de paiement « débloquer N pages » ;
       - textes FR/EN (carte Gratuit, `free_plan_hint`) ;
       - abus possibles d'une traduction libre illimitée (coût moteur) : plafond quotidien ? ;
       - extension navigateur.
     - Garde-fous validés (16/11) : plafond 20 p/24 h compte+appareil, 3e choix dans la fenêtre 402, déblocage via paiement par document limité aux pages libres, purge 30 j + rappel.
     - Étude écrite : `docs/etude-traduction-libre.md`. Branche `feat/traduction-libre` (empilée sur feat/retours-clients).
     - Sous-étapes :
       - [x] 5.1 Règle (a) : pages offertes en clair + déblocage rétroactif (migration 0026, non appliquée sur la base locale partagée) + tests (16 fichiers OK) + navigation réelle : compte Gratuit, PDF 1 p, bouton « Télécharger la traduction » actif, fichier traduit reçu (script scratchpad `nav51.py`)
       - [x] 5.2 Mode libre serveur : migration `0027_traduction_libre` (idempotente ; colonne + table posées sur la base locale, version laissée à 0025), `LibreGrant`, `anti_abus.libre_used/record_libre` + purge 2 j, `translate.py` param `libre` (402 `libre_limit`, images coupées, sélection entière), droit au clair exige `pages_libres == 0` ; 24 fichiers de tests OK dont `test_traduction_libre.py` ; essai API réel (PDF 7 p, Gratuit) : 200, `pages_libres` 2, `can_download` False, téléchargement 402 (script scratchpad `api52.py`)
       - Révision 17/11 (étude §1 « Révision ») : plus de 3e choix ; mode libre d'office ; téléchargement des seules pages payées (débit auto, fenêtre Acheter/Continuer).
       - [x] 5.3 Mode libre d'office (plus de `libre=1`), ligne « N pages en aperçu » sous l'aperçu, aperçu net par page + tests + Playwright
       - [x] 5.3b Téléchargement : débit auto, fichier limité aux pages payées, fenêtre « Acheter / Continuer » + tests + Playwright
       - [x] 5.3c Écarts de la contre-revue 5.3b (docs/revues/traduction-libre-5.3b.md, n° 14 à 18)
       - [x] 5.4 Déblocage des pages libres (devis, paiement) + tests + Playwright
       - [x] 5.5 Purge 30 j + rappel e-mail + tests (document en partie payé gardé)
       - [x] 5.6 Textes FR/EN (dont le 402 de téléchargement « Passez à Starter », périmé) + vérif d'ensemble
4. [ ] Test comparatif réel (Précis, Google Traduction, DeepL, Word, Claude) sur un PDF long et chargé
   - Kit proposé (accord attendu) : `docs/banc-concurrence/`, 5 docs (`scan_mv21.pdf` + vérité, pages du Code de la Route, `original.pptx` de la sauvegarde, Excel + Word réels à fournir par l'utilisateur ou fabriqués), même consigne pour chaque outil, grille (fichier rendu, pages manquantes, mise en page, tableaux/schémas, sens). L'utilisateur passe ChatGPT/Gemini/Copilot (pas d'accès ici), Précis lancé localement, comparaison HTML côte à côte.
5. [ ] Recherche marché + plan marketing

## Hors plan
- 5.2 à revoir plus tard : `cap_pages_for_plan` ne recalcule pas `pages_libres` (sans effet, limites None) ; PDF scanné en mode libre sans budget, non testé.
- `.txt` accepté à l'envoi (`translate.py`) mais refusé par le moteur (`translation_runner.py:206` « Type de fichier .txt non supporté ») : la traduction échoue après débit puis remboursement. Défaut préexistant, à traiter à part.
- Le serveur local (port 8000) ne rechargeait plus le code : redémarré le 17/11.
- Retours du 18/11 (n° 3 à 10 : bouton « Voir les tarifs », soldes « 5/5 », images bêta, formulaire de dépôt, nouveautés, « Script error. », badges admin, filigrane trop fort) : détaillés dans `docs/etude-retours-18-11.md`, traités dans l'ordre du tableau.

## Pièges
- Le backend 8000 (tâche bpgydeloe) ne recharge pas toujours : après une modification, refaire un essai API et le relancer si besoin.
- Aperçu admin : `copie_du_document` (`backend/app/services/documents.py:312`) fait la photo de la traduction ; `_racine_orpheline` (`documents.py:174`) garde les fichiers tant qu'une fiche les vise ; aperçu client = `/documents/{id}/preview` et `/original?as=pdf` (`documents.py:455,526`), rendu = `_render_or_404` (l. 213).
- Docs sources : sauvegarde `../Precis_Translator_backup_2026-06-10_13-10/backend/tests files/` (PDF + `scans/`), `.../backend/translations/d3a01a4d40bd/original.pptx`.
- Tests backend : `cd backend && python -X utf8 tests/test_beta_program.py` (Python 3.14 système, `aiosqlite` installé le 18/11 ; suites voisines : test_traduction_libre, test_anti_abus, test_incorpores_facturation, test_admin_documents). Heredoc Python avec accents : passer par un script en fichier (encodage stdin). Playwright : `python libre_dl.py <dossier>` (scratchpad).
- Branche courante feat/traduction-libre, fichiers non commités appartenant à l'utilisateur : PASSATION.md, docs/fiches-boutiques-extension.md, extension/assets/boutique/, backend/.zip.
