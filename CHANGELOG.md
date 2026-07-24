# Changelog

Toutes les évolutions notables de **Précis Translator**. Format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnage
[SemVer](https://semver.org/lang/fr/). Le numéro ci-dessous est la **version
projet** (le tag git) ; les composants — backend, moteurs, interface — portent
leurs propres numéros internes.

Rubriques : `Ajouté`, `Modifié`, `Corrigé`, `Retiré`, `Sécurité`.

## [Unreleased]

### Ajouté
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
- Backend : 13 suites de tests hors ligne (aucun appel réseau ni DeepSeek),
  chacune en `exit=0`.
