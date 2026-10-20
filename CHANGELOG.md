# Changelog

Toutes les évolutions notables de **Précis Translator**. Format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnage
[SemVer](https://semver.org/lang/fr/). Le numéro ci-dessous est la **version
projet** (le tag git) ; les composants — backend, moteurs, interface — portent
leurs propres numéros internes.

Rubriques : `Ajouté`, `Modifié`, `Corrigé`, `Retiré`, `Sécurité`.

## [1.5.2](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.5.1...v1.5.2) (2026-10-20)


### Bug Fixes

* **beta:** prevent repeated trials and flag suspicious applications ([#43](https://github.com/EagleFox31/Pr-cis-Translation/issues/43)) ([79d3586](https://github.com/EagleFox31/Pr-cis-Translation/commit/79d35862578327261f524cba0acb4f49f82907a9))

## [1.5.1](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.5.0...v1.5.1) (2026-10-20)


### Bug Fixes

* **ui:** simplify the public beta offer card ([#41](https://github.com/EagleFox31/Pr-cis-Translation/issues/41)) ([292112e](https://github.com/EagleFox31/Pr-cis-Translation/commit/292112e74f5c1f48fc6b3bda03761f85b49248d2))

## [1.5.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.4.1...v1.5.0) (2026-10-20)


### Features

* **beta:** publish the program and review tester applications ([#39](https://github.com/EagleFox31/Pr-cis-Translation/issues/39)) ([1084b61](https://github.com/EagleFox31/Pr-cis-Translation/commit/1084b617a948c822a9a90b8e85ebec9320c0a926))

## [1.4.1](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.4.0...v1.4.1) (2026-10-20)


### Bug Fixes

* **beta:** serve direct activation links through nginx ([#37](https://github.com/EagleFox31/Pr-cis-Translation/issues/37)) ([f25dfc7](https://github.com/EagleFox31/Pr-cis-Translation/commit/f25dfc73460101583f28f75a58ebcc79bdeb1ce8))
* **ui:** acknowledge delivered documents without free-plan restriction ([#36](https://github.com/EagleFox31/Pr-cis-Translation/issues/36)) ([0b568ed](https://github.com/EagleFox31/Pr-cis-Translation/commit/0b568edd9f08146e582fd53b6a846444a910a005))

## [1.4.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.3.0...v1.4.0) (2026-10-20)


### Features

* **beta:** manage invited testers with per-format quotas ([#33](https://github.com/EagleFox31/Pr-cis-Translation/issues/33)) ([4c7f80e](https://github.com/EagleFox31/Pr-cis-Translation/commit/4c7f80eb4b6aeb7a3ddaaf4ef0d5c0513bc0871e))


### Bug Fixes

* **config:** preserve Fapshi settings in production env imports ([#31](https://github.com/EagleFox31/Pr-cis-Translation/issues/31)) ([a4db1f6](https://github.com/EagleFox31/Pr-cis-Translation/commit/a4db1f6efefe9b7d1cc96560e5b273949a68ccc8))

## [1.3.0](https://github.com/EagleFox31/Pr-cis-Translation/compare/v1.2.0...v1.3.0) (2026-10-20)


### Features

* **paiement:** Fapshi, achat des pages manquantes et frais client (backend 1.2.0) ([44c9b8f](https://github.com/EagleFox31/Pr-cis-Translation/commit/44c9b8fd0cd5fb2eba4b6863f0a54dc88344462d))

## 1.2.0 (2026-10-20)


### Features

* **pdf:** polices non embarquées et correctifs de rendu (moteur 1.0.12) ([b5eb58c](https://github.com/EagleFox31/Pr-cis-Translation/commit/b5eb58c3955bba6c2a62afb2317f7cd34e9fd27c))
* **pdf:** résoudre les polices non embarquées (identique, clone, la plus proche) ([5e62360](https://github.com/EagleFox31/Pr-cis-Translation/commit/5e62360f396857696c16bc3c18d94eadce5c63f5))


### Bug Fixes

* **ci:** propagate production and connect AppFactory release automation ([#27](https://github.com/EagleFox31/Pr-cis-Translation/issues/27)) ([e169d2f](https://github.com/EagleFox31/Pr-cis-Translation/commit/e169d2f46ac88d3576c09646c08146c7cdc8de53))
* **pdf:** lire et reproduire l'italique synthétique (police droite penchée par la matrice de texte) ([47eb4bd](https://github.com/EagleFox31/Pr-cis-Translation/commit/47eb4bd9ab7769b0d69a7ecd36e213c460d4a185))
* **pdf:** lire et reproduire le gras synthétique (police Regular peinte en mode 2) ([8d55814](https://github.com/EagleFox31/Pr-cis-Translation/commit/8d55814ce4aae9e4c94a55400a58f31d74e50d7c))
* **pdf:** ne pas souder une ligne en capitales et la ligne en casse mixte qui suit ([a143361](https://github.com/EagleFox31/Pr-cis-Translation/commit/a1433619c9dbb906d5b30b1ab5ac001b3dca16ce))
* **pdf:** polices — catégorie serif/sans respectée, noms composés, licences, absences bornées ([982b102](https://github.com/EagleFox31/Pr-cis-Translation/commit/982b1026613ed9ef760ef9565e91f5f7174581da))
* **pdf:** polices — liste blanche Google Fonts, rendu dégradé non mis en cache, polices système désactivées par défaut ([7782f45](https://github.com/EagleFox31/Pr-cis-Translation/commit/7782f45d1458cd25c3c1316192602a9aaf7bb8eb))
* **pdf:** rattacher chaque pose d'image à son objet et reporter son opacité ([185e577](https://github.com/EagleFox31/Pr-cis-Translation/commit/185e57730f07067e886f0f6cfd096993cb66b674))
* **release:** bound first AppFactory release to deployed lineage ([#28](https://github.com/EagleFox31/Pr-cis-Translation/issues/28)) ([1e93b19](https://github.com/EagleFox31/Pr-cis-Translation/commit/1e93b19766b9ab53fbd981b3208fcdd63264bac4))
* **traduction:** même libellé, même traduction d'une page à l'autre ([d51b589](https://github.com/EagleFox31/Pr-cis-Translation/commit/d51b589cce3952e7768561da1401ffdc64dcffed))
* **traduction:** redemander un fragment rendu entièrement inchangé ([88b8a82](https://github.com/EagleFox31/Pr-cis-Translation/commit/88b8a82faa2054eeaa489147bd6dfd3f1c15c2a4))

## [Non publié]

### Ajouté
- Excel : gestion de l'expansion. Une traduction plus longue que sa source
  élargit sa colonne (selon l'alignement et les voisines vides) au lieu d'être
  coupée, une cellule à retour à la ligne gagne la hauteur de ses lignes en
  plus, un nombre dont le format porte un littéral traduit ne s'affiche plus
  en `#####`.
- **Paiement Fapshi** (Mobile Money MTN et Orange, Cameroun). Par défaut,
  paiement direct : le client saisit son numéro et valide l'invite reçue sur
  son téléphone ; le crédit arrive par le suivi du statut ou par le webhook
  (`FAPSHI_WEBHOOK_SECRET`). La page de paiement hébergée, affichée DANS la
  fenêtre de paiement sans défilement, est conservée en repli désactivé
  (`FAPSHI_FLOW=checkout`, voir `docs/deploiement.md`).
- **Crédits insuffisants à l'import** : au lieu d'un refus sec, la traduction
  propose d'acheter les pages manquantes ou de ne traduire que les pages
  couvertes (PDF, PPTX). Rien n'est lancé ni débité avant ce choix ; après
  l'achat, le document entier est traduit.
- **Achat à la page** : un seul champ (1 à 500 pages, 2 par défaut), montant
  recalculé à la volée ; bandeau dédié sous la grille des tarifs.
- PDF : polices non embarquées résolues (police identique locale ou Google
  Fonts sur liste blanche, sinon clone métrique, sinon la plus proche par
  largeurs mesurées) ; catalogue pré-chargé au build.

### Modifié
- Moteur XLSX `0.2.0` → `1.0.0`.
- Moteur PDF `1.0.5` → `1.0.12`.
- **Frais de transaction (3 %) à la charge du client**, affichés avant de
  payer : sous-total, frais, total. Le montant enregistré est le total payé ;
  les pages créditées ne changent pas.
- Forfait Gratuit : les pages achetées passent avant l'offre du mois et valent
  pour tous les formats (l'essai offert reste limité au PDF et au PPTX).
- Backend `1.1.0` → `1.2.0` : `/api/payments/quote` et `/plan/quote` renvoient
  `subtotal`, `fee`, `amount` ; `/api/pricing` expose `fee_percent` ; la
  traduction répond 402 `need_credits` (structuré) et accepte `covered_only`.

### Corrigé
- Un compte Gratuit qui a acheté des pages voit désormais la reconnaissance
  (OCR) d'un scan porter sur tout le document, et non sur la seule page d'essai.
- L'essai sur un scan propose de nouveau l'achat des pages manquantes : la
  limite d'OCR à une page ne réduit plus le document compté.
- Double dépense possible de crédits sur deux imports simultanés : le solde est
  relu sous verrou.
- PDF : gras et italique synthétiques lus et reproduits ; opacité des images
  reportée sur chaque pose ; une ligne en capitales n'est plus soudée à la
  ligne en casse mixte qui suit.
- Traduction : un même libellé reçoit la même traduction d'une page à
  l'autre ; un fragment rendu inchangé est redemandé au modèle.

## [1.1.0] - 2026-10-09 — Comptes, paiement et mise en ligne

### Ajouté
- **Traduction Excel complète, avec aperçu progressif** (moteur XLSX `0.2.0`).
  Les **dix** endroits où Excel range du texte sont désormais traités : chaînes
  partagées et en ligne, noms d'onglets, graphiques, zones de texte, les **deux**
  formats de commentaires (ancien et fils modernes), en-têtes de tableaux
  structurés, croisés dynamiques, formats de nombre personnalisés et propriétés
  du document. L'aperçu suit le même flux progressif que le PDF et le PPTX —
  socle en langue source affichable tout de suite, puis chaque feuille traduite
  greffée à sa place.
  Deux règles gouvernent le moteur : **on ne traduit jamais un nombre ni une
  formule** (une cellule cassée propage `#VALUE!` dans toute la feuille), et
  **on traduit la source, on aligne ses copies** — les caches de graphiques,
  d'en-têtes de tableaux et de croisés reflètent des cellules déjà traduites ;
  les retraduire donnerait deux formulations pour la même donnée.
  Ce qui n'est **pas** couvert : l'**expansion**. Une traduction plus longue que
  sa source déborde de sa colonne ou s'affiche en `#####`. C'est la raison du
  `0.2.0` plutôt qu'un `1.0.0`.
- **Journal central des erreurs** : toutes les erreurs (interface, backend, API)
  sont captées et regroupées par empreinte. Capture front (erreurs JS, promesses
  rejetées, rendu React via `ErrorBoundary`, échecs réseau/5xx) → `POST
  /api/logs/client` ; capture backend (handler d'exception global + tout
  `logger.error` via un handler DB). Vue d'administration **`/admin/logs`**
  (réservée aux comptes admin) : liste groupée, filtres, détail (pile + contexte),
  et cycle **exporter → marquer traité → supprimer** (suppression refusée tant
  qu'un log n'est pas traité). Alerte e-mail à l'admin au-delà d'un seuil de logs
  non traités (throttlée). Migration `0006_error_logs`.
- **Console d'administration des comptes** (`/admin/users`, réservée admin) :
  liste filtrable des comptes et changement de plan. Sert à promouvoir un testeur
  (Starter/Pro) sans desserrer le forfait Gratuit. Garde-fous : plan restreint à
  une liste blanche, et un admin ne peut pas changer son propre plan
  (anti-verrouillage).
- **Vitesse de traitement affichée sur les cartes de tarifs** : le gratuit passe
  en file standard, chaque palier payant remonte dans la file (priorité 0→3).
  C'est le nouveau levier de vente. ⚠ L'attribut est *déclaré et vendu* ; son
  application réelle (l'ordonnancement de la file) reste à faire — chantier
  « file de priorité ».

- **Assistance / support** : les utilisateurs connectés peuvent **signaler un
  problème** ou demander de l'**aide sur leur abonnement** depuis une fenêtre
  (catégorie + sujet + message ; la page d'origine et le plan partent avec la
  demande sans être saisis). Accessible depuis le tiroir de compte. Vue
  d'administration **`/admin/support`** (menu Administration) : liste filtrable,
  détail, cycle **traiter (note interne) → supprimer** (suppression refusée tant
  qu'un ticket est ouvert). Alerte e-mail à l'admin à chaque ticket. Migration
  `0007_support_tickets`. **Référencement automatique du document** : signaler
  un problème depuis l'aperçu (barre d'outils) ou une carte de bibliothèque
  attache l'identité du document (id + nom) au ticket — l'utilisateur ne saisit
  rien, l'admin voit tout de suite de quel document il s'agit.
- **File de priorité de traduction** : les traductions ne démarrent plus toutes
  en parallèle sans limite. Un ordonnanceur borné (`TRANSLATION_WORKERS`, défaut
  2) mène N traductions de front ; au-delà, les demandes attendent dans une file
  ordonnée par le **niveau de plan** (admin > pro > starter > gratuit), FIFO à
  priorité égale. C'est ce qui rend enfin RÉELLE la vitesse vendue sur la carte.
  Le client voit un état « en file d'attente » (événement SSE `queued`). Pas de
  préemption : un job prioritaire passe devant ceux qui attendent, sans couper un
  job en cours.

- **Paiement à la page depuis l'écran de traduction** : quand le forfait Gratuit
  n'a plus de crédit, le message d'erreur porte désormais un bouton **« Payer N
  page(s) »** qui ouvre directement le paiement mobile money du nombre exact de
  pages du document, puis **relance la traduction** une fois payé. Le 402 « crédits
  insuffisants » renvoie une réponse structurée (`pages_needed`) pour que le client
  sache quoi facturer sans que l'utilisateur ait à deviner.

### Modifié
- **Aperçu d'essai — projecteur à un seul canevas** : la fenêtre nette qui suit
  le curseur ne s'appuie plus sur un second canevas « net » qu'il fallait aligner
  au pixel (il se décalait au zoom, laissant une zone blanche). Un seul canevas
  désormais, assombri par un voile percé d'un trou — aucune couche à aligner,
  plus de décalage.
- **Filigrane d'essai = mini-publicité, cuite dans les pixels** : « PRÉCIS ·
  Professional Translation · <site> » (contenu configurable via `BRAND_NAME`,
  `BRAND_TAGLINE`, `PUBLIC_SITE`). Il n'est plus une couche de texte détachable
  mais fait partie de l'image (double rastérisation) — le retirer demande de
  retoucher l'image, pas de supprimer un objet texte.
- **Tarifs zone A (Cameroun, FCFA) baissés** pour l'adoption bêta : Starter
  2 500 → **1 500** F/mois (annuel 1 900 → 1 200), Pro 6 900 → **4 500** F/mois
  (annuel 5 200 → 3 500), page à l'unité 100 → **75** F. Zones B/C inchangées.

### Sécurité
- **Un secret qui s'annonce provisoire est désormais refusé en production.**
  `dev-secret-key-change-in-production-…` traversait les trois contrôles : absent
  de la liste noire, sans marqueur connu (la liste cherchait `change-me`, le
  secret disait `change-in-production`) et assez long pour passer le plancher. Il
  aurait signé les jetons en ligne, et quiconque ayant lu ce fichier aurait pu
  forger un jeton d'administrateur.
- **`FRONTEND_URL` resté sur `localhost` bloque le démarrage en production.**
  Ce n'est pas un secret, l'application démarrait très bien sans lui : les liens
  de vérification de compte et le retour de connexion Google partaient vers la
  machine de l'utilisateur — **aucune inscription ne pouvait aboutir**, sans une
  ligne de journal.

### Corrigé
- **Quatre lectures de fichier figeaient l'application entière.** Un
  `open().read()` dans un `async def` bloque la boucle d'événements : avec un
  seul worker uvicorn et des fichiers jusqu'à 100 Mo, un téléchargement
  suspendait les aperçus de tous les autres utilisateurs, flux SSE de la
  traduction progressive compris. Lectures déportées hors de la boucle
  (`run_in_threadpool` / `asyncio.to_thread`).
- **Les 23 dépendances du backend sont épinglées** (`==` au lieu de `>=`) aux
  versions sur lesquelles les 21 suites passent : une construction d'image ne
  ramène plus une version majeure non testée.
- Les sorties des bancs d'essai (`.ocr_out/`, plusieurs dizaines de Mo,
  régénérables) ne sont plus candidates au suivi de version.
- Décomptes de tests périmés corrigés dans six documents (13 suites / 313
  contrôles → **21 suites / 418 contrôles**).

### Ajouté (mise en ligne)
- [`docs/deploiement.md`](docs/deploiement.md) : la marche à suivre pour mettre
  le service en ligne sur une machine AWS derrière Cloudflare — choix de
  l'hébergement argumenté, configuration obligatoire, HTTPS, parcours de
  vérification, limites connues et retour arrière.

Limites connues (assumées, non bloquantes) : PDF scannés non traduits (aucun OCR,
étude dans [`docs/etude-ocr.md`](docs/etude-ocr.md)) ; une colonne PDF justifiée de
≤ 5 lignes peut rester mal recollée ; moteur XLSX à l'état de squelette (couverture
partielle) ; l'interface n'a aucun test de rendu automatisé (vérification manuelle).

## [1.0.0] - 2026-07-24 — MVP

Première version stable. L'application traduit un document **sans lui faire perdre
sa mise en forme** : le texte est relevé avec sa géométrie et ses styles, traduit,
puis réinjecté dans le document d'origine — jamais reconstruit.

### Ajouté
- **Moteurs de traduction fidèle** : PDF (moteur v2 *from scratch* — glyphes →
  spans → lignes → paragraphes, reflow borné, rendu depuis le seul JSON), PPTX,
  DOCX, et XLSX (squelette). Chaque moteur est indépendant de l'application
  (`api → services → engines → rien`).
- **Aperçu progressif page par page** : flux SSE ; le document d'origine s'affiche
  d'abord, puis chaque page traduite s'y substitue dès qu'elle est prête (un thread
  mène le cycle complet extraction → traduction → rendu par page).
- **Reprise et cache honnête** : un job interrompu reprend sans repayer ; la clé de
  cache de rendu inclut la version du moteur (plus de rendu périmé servi en silence).
- **Comptes & facturation** : authentification **sans mot de passe** (code e-mail)
  + Google OAuth ; forfaits `free` (1 page/mois) · `starter` · `pro` · `enterprise`
  · `admin` ; paiement **à la page** via Campay (droit acquis au document, pas au plan).
- **Interface** React 19 + Vite : dépôt de document, bibliothèque, aperçu côte à
  côte (original ↔ traduction), mise en page **responsive** à cadre commun,
  **scroll-snap** par section, **mode agrandi** de l'aperçu, raccourcis clavier et
  souris, décor multilingue animé du hero.
- **Documentation** : `ARCHITECTURE.md`, README backend/frontend, contexte par
  moteur (`backend/engines/*/CONTEXTE.md`), doc API autonome (`npm run docs:api`),
  ce `CHANGELOG.md` et un `CONTRIBUTING.md`.

### Sécurité
- CORS restreint aux origines déclarées (plus de `*` avec `allow_credentials`).
- Plafonds de débit sur les routes d'authentification ; `503` parlant en cas de
  panne SMTP.

### Vérifié
- Interface : `npm run build` + parité i18n (`scripts/check-i18n.mjs`).
- Backend : 21 suites de tests hors ligne (aucun appel réseau ni DeepSeek),
  chacune en `exit=0`.
