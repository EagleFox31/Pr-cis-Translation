# Étude : page Nouveautés, annonces à la connexion et abonnement par e-mail

*10/11/2026 — mission G (PASSATION.md). Étude seule, aucun code modifié.*

## 1. Besoin

1. Une **page** qui présente toutes les fonctionnalités de Précis en détail, et le journal de ce qui a été ajouté, amélioré ou corrigé.
2. À la **première connexion** : une fenêtre courte avec les fonctions phares, un bouton vers la page, un bouton « Recevoir les nouveautés par e-mail ».
3. Aux **connexions suivantes** : seulement ce que l'utilisateur n'a pas encore vu, rangé en trois rubriques au plus (Nouveautés, Améliorations, Correctifs), rubrique absente si vide. Rien s'il n'y a rien.
4. Un **abonnement par e-mail** aux nouveautés, avec un e-mail construit sur la carte existante : bref résumé ordonné, pas un déversement.

Contraintes : simple, concis, cohérent avec l'interface ; FR/EN ; aucune gêne pendant une traduction en cours.

## 2. Existant (mesuré le 10/11)

| Élément | Où | Utilité ici |
|---|---|---|
| Carte e-mail unique (`_carte`, niveaux info/avertissement/critique, logo en pièce jointe `cid:`) + briques `_titre`, `_para`, `_bouton`, `_atouts`, `_details` | `backend/app/core/email.py:60-240` | Gabarit de l'e-mail Nouveautés : niveau `info`, bandeau « Nouveautés », une liste par rubrique. Rien à inventer. |
| Textes séparés de l'envoi, FR/EN, langue = celle de l'interface (`Accept-Language`) | `backend/app/core/email_content.py` | Ajouter `textes_nouveautes(langue)`. **Mais** l'utilisateur n'a pas de langue enregistrée : un envoi groupé ne peut pas lire d'en-tête → colonne `langue` à ajouter. |
| Envoi SMTP Spacemail, `EmailIndisponible` | `email.py:368-482` | Réutilisé. **Spacemail est limité par jour** (Hors plan PASSATION) → envoi groupé étalé. |
| Modèle `User` (pas de langue, pas de préférences, pas de « vu ») | `backend/app/models/user.py` | Migration **0024** (la chaîne de la branche s'arrête à `0023_extension_auth`). |
| `GET /api/auth/me` → `_user_response` | `backend/app/api/auth.py:434` | Y exposer `nouveautes_vues_le`, `abonne_nouveautes`. |
| Contenu éditorial FR/EN en fichiers TS typés | `frontend/src/content/legal/{fr,en,types}.ts` | Même principe pour le catalogue, mais il doit aussi servir l'e-mail → source côté **backend** (voir §4). |
| Fenêtres : `InviteModal` (hôte unique + bus `inviteBus`), `PaymentModal` (portail), `contact-modal`, `Drawer` (`role="dialog"`, Échap) | `components/invite`, `components/payment`, `components/ui/Drawer.tsx` | Même structure (portail, `aria-modal`, Échap, focus rendu). Pas de composant `Modal` partagé : on suit `InviteModal`. |
| Panneau compte = `DocumentLibrary` (ouvert par l'avatar) | `components/library/DocumentLibrary.tsx` | Entrée « Nouveautés » + pastille du nombre non vu ; interrupteur d'abonnement. |
| Menu mobile `MobileMenu.tsx`, pied de page `.about-footer` | navbar, `AboutSection.tsx:156-160` | Lien vers la page. |
| Fonctionnalités vitrine | `components/features/FeaturesGrid.tsx` (clés `features.*`) | Textes réutilisables pour les « phares » de la première fenêtre. |
| `CHANGELOG.md` (release-please, messages de commit en anglais technique) | racine | **Pas** une source affichable : « canonical, structured data… » ne parle pas à un utilisateur. Sert seulement d'aide à la rédaction. |
| Routes paresseuses + préchargement | `lib/routes.ts`, `App.tsx` | Nouvelle route `/nouveautes`, chargée à la demande. |

## 3. Ce que verra l'utilisateur (exemples concrets)

**Première connexion (Awa crée son compte)** — fenêtre de 4 cartes au plus :
« Bienvenue sur Précis » · Documents traduits sans perdre la mise en page · Images et scans traduits · Extension navigateur · Visionneuse côte à côte. Deux boutons : **Découvrir toutes les fonctionnalités** (→ `/nouveautes`) et **Recevoir les nouveautés par e-mail** (bascule en « ✓ Abonné », sans quitter la fenêtre). Lien discret « Plus tard ».

**Connexion suivante, 3 semaines plus tard** — trois éléments ajoutés entre-temps :
> **Depuis votre dernière visite**
> Nouveauté · Connexion de l'extension par le site
> Amélioration · Site plus rapide sur mobile
> Correctif · Pages scannées illisibles mieux signalées

Bouton **Tout voir** · lien « J'ai compris ». Au-delà de 5 éléments : les 5 plus importants + « et 4 autres ». Une connexion sans nouveauté n'affiche **rien**.

**E-mail** (même carte que le code de connexion) : bandeau « Nouveautés », titre « Ce qui change dans Précis », puis par rubrique 3 lignes au plus (titre en gras + une phrase), bouton « Voir les détails », pied « Vous recevez cet e-mail car vous êtes abonné… Se désabonner » (lien en un clic).

## 4. Options comparées

### 4.1 Source du contenu

| Option | Pour | Contre |
|---|---|---|
| **A. Catalogue versionné côté backend** (`backend/app/content/nouveautes.py` : liste d'entrées FR/EN), servi par `GET /api/nouveautes` | Une seule source pour la page, la fenêtre et l'e-mail ; relu en PR ; testable | Publier = un déploiement |
| B. Généré depuis `CHANGELOG.md` | Automatique | Anglais technique, granularité de commit, rien pour le public |
| C. Table + écran admin d'édition | Publier sans déployer | Écran admin, migration, traductions saisies à la main ; trop pour le rythme actuel (une version par semaine ou deux) |

→ **A**. C reste possible plus tard sans changer le format.

Entrée type : `id` (slug stable), `date`, `type` (`nouveaute` | `amelioration` | `correctif`), `phare` (bool), `importance` (1-3, pour trier et couper), `titre`/`resume`/`detail` × FR/EN, `lien` facultatif (`/extension`…), `domaine` (documents, images, extension, visionneuse, compte, API).

Les **fonctionnalités** (catalogue stable, « ce que sait faire Précis ») et le **journal** (daté) sont deux listes du même fichier : la première est rédigée une fois, la seconde s'allonge.

### 4.2 Mémoire de « ce qui a été vu »

| Option | Pour | Contre |
|---|---|---|
| **A. Côté serveur : `users.nouveautes_vues_le`** (date de la dernière entrée vue) | Suit l'utilisateur d'un appareil à l'autre ; nul = jamais vu → première fenêtre | Migration |
| B. `localStorage` | Rien côté serveur | Réapparaît sur chaque appareil / navigation privée ; l'e-mail ne sait pas ce qui a été vu |

→ **A**. Une date suffit (pas de table par élément) : « non vu » = entrées plus récentes que cette date. Fermer la fenêtre, ou ouvrir la page, avance la date (`POST /api/nouveautes/vues`).

### 4.3 Envoi des e-mails

| Option | Pour | Contre |
|---|---|---|
| **A. Envoi déclenché à la main** (script `backend/scripts/envoyer_nouveautes.py`, puis éventuellement bouton admin) pour une sélection d'entrées ; étalé (lots, pause) ; journal des envois | Contrôle total du moment ; respecte la limite Spacemail ; idempotent | Une action à penser à chaque version |
| B. Automatique au déploiement | Rien à faire | Envoi accidentel d'un correctif mineur à tous ; difficile à rejouer |
| C. Résumé mensuel automatique | Régulier | Planificateur à ajouter ; peut partir vide ou trop chargé |

→ **A**, avec garde : une entrée n'est jamais envoyée deux fois (table `nouveautes_envois`), et un utilisateur ne reçoit que les entrées publiées après son abonnement.

### 4.4 Forme de l'abonnement

| Option | Pour | Contre |
|---|---|---|
| **A. Un seul interrupteur** « Recevoir les nouveautés par e-mail » ; l'e-mail range par rubrique, correctifs en une ligne chacun | Simple, conforme à la demande « rien qui embrouille » | Pas de tri fin |
| B. Trois cases (nouveautés / améliorations / correctifs) | Choix fin | Trois décisions à prendre pour un bénéfice faible |

→ **A** ; B s'ajoute plus tard sans migration lourde si on stocke dès maintenant une colonne `abonne_nouveautes` (booléen).

## 5. Choix recommandé — architecture

**Backend**
- `app/content/nouveautes.py` : `FONCTIONNALITES` et `JOURNAL` (dataclasses FR/EN) + validation au démarrage (ids uniques, deux langues remplies, types connus) couverte par un test.
- Migration `0024_nouveautes` : `users.nouveautes_vues_le` (timestamptz, nul), `users.abonne_nouveautes` (bool, défaut faux), `users.abonne_nouveautes_le` (timestamptz, preuve du consentement), `users.langue` (`fr`/`en`, défaut `fr`) ; table `nouveautes_envois` (`entree_id`, `user_id`, `envoye_le`, unique sur le couple).
- `app/api/nouveautes.py` :
  - `GET /api/nouveautes?lang=` (public) : fonctionnalités + journal.
  - `GET /api/nouveautes/a-voir` (connecté) : `{premiere: bool, entrees: [...]}` déjà trié et coupé à 5, rubriques groupées.
  - `POST /api/nouveautes/vues` : avance `nouveautes_vues_le`.
  - `PUT /api/nouveautes/abonnement {actif}` : enregistre aussi `langue` depuis `Accept-Language`.
  - `GET|POST /api/nouveautes/desabonnement?jeton=` : jeton signé HMAC (`JWT_SECRET`, objet dédié), sans connexion ; le POST répond à l'en-tête `List-Unsubscribe-Post` (désabonnement en un clic exigé par Gmail/Yahoo pour les envois groupés).
- `email.py` : `_html_nouveautes` + `send_nouveautes_email` sur `_carte` (niveau `info`), en-têtes `List-Unsubscribe`/`List-Unsubscribe-Post` ; `email_content.py` : `textes_nouveautes(langue)`.
- `scripts/envoyer_nouveautes.py --entrees id1,id2 [--essai moi@…] [--lot 50 --pause 60]` : essai sur une adresse d'abord, puis envoi étalé, reprise sans doublon.
- `_user_response` : expose `nouveautes_vues_le`, `abonne_nouveautes`.

**Frontend**
- `pages/NouveautesPage.tsx`, route publique `/nouveautes` (paresseuse, préchargée au survol, ajoutée au sitemap) : en-tête court ; **Fonctionnalités** groupées par domaine (cartes avec détail dépliable) ; **Journal** par mois avec pastille de rubrique ; encart d'abonnement (connecté : interrupteur ; invité : « Connectez-vous pour être averti »). Une ancre `#journal`.
- `components/nouveautes/NouveautesModal.tsx` (hôte unique, comme `InviteModal`) : deux modes, *accueil* et *depuis votre dernière visite*. Monté dans `App.tsx`.
- Règles d'apparition (sinon la fenêtre gêne) : seulement si connecté, sur `/home`, après l'écran de démarrage, **jamais pendant une traduction en cours ni si une autre fenêtre est ouverte** (paiement, invitation), jamais sur `/extension/autoriser|connecte` ; une fois par session au plus ; « Plus tard » / Échap / clic dehors = vu.
- Panneau compte (`DocumentLibrary`) : ligne « Nouveautés » + pastille du nombre non vu ; interrupteur d'abonnement. Menu mobile et pied de page : lien « Nouveautés ».
- i18n : clés `nouveautes.*` FR/EN (les textes d'entrées viennent de l'API dans la bonne langue).

## 6. Impacts

| Domaine | Effet |
|---|---|
| Données | Migration 0024 additive (colonnes nulles ou à défaut, une table). Utilisateurs existants : `nouveautes_vues_le` nul → ils verront **une fois** la fenêtre d'accueil (voulu : ils ne l'ont jamais vue). |
| Sécurité | Désabonnement sans connexion → jeton signé, sans expiration, propre à l'usage (pas un jeton d'accès) ; abonnement uniquement par l'utilisateur connecté ; textes du catalogue échappés dans l'e-mail. |
| Juridique (RGPD) | Consentement explicite, jamais coché d'avance, date gardée ; désabonnement en un clic dans chaque e-mail ; mention à ajouter dans `confidentialite` (finalité « informations produit »). |
| Délivrabilité | Limite journalière Spacemail → envoi étalé ; au-delà de quelques centaines d'abonnés, passer à Amazon SES (déjà noté Hors plan). |
| Performance | Page et fenêtre en morceaux paresseux ; `a-voir` = une requête après la connexion, rien pour un invité. |
| i18n | Toute entrée doit exister en FR et EN (contrôlé par test). |
| Déploiement | Migration au déploiement (`deploy-vps.yml`) ; aucune variable nouvelle. |
| Coût | Nul hors temps d'envoi. |

## 7. Risques

- **Lassitude** : trop d'annonces → bornes fixes (5 éléments, une fois par session, rien si vide, correctifs mineurs exclus de la fenêtre via `importance`).
- **Contenu non tenu** : un catalogue oublié vieillit → case « Nouveautés mises à jour ? » dans le modèle de PR / la checklist de version.
- **E-mail en spam** : désabonnement en un clic + envoi étalé + essai sur sa propre adresse avant chaque envoi.

## 8. Points à trancher par l'utilisateur

**Tranché le 10/11 : les cinq recommandations sont validées** (`/nouveautes`, envoi à la main par version, un seul interrupteur, fenêtre d'accueil une fois pour les comptes existants, catalogue rédigé par moi puis relu).

1. **Adresse de la page** : `/nouveautes` (recommandé, cohérent avec `/conditions`, `/confidentialite`) ou `/fonctionnalites`.
2. **Envoi** : à la main par version (recommandé) ou résumé mensuel automatique.
3. **Abonnement** : un seul interrupteur (recommandé) ou trois cases par rubrique.
4. **Utilisateurs existants** : leur montrer la fenêtre d'accueil une fois (recommandé) ou seulement le journal.
5. **Rédaction initiale** : je rédige le catalogue (≈ 12 fonctionnalités, journal depuis la 1.5) à partir du CHANGELOG et du code, tu relis (recommandé).

## 9. Plan

Branche `feat/nouveautes`, créée depuis `perf/fluidite-responsive` une fois F.5b/F.6 terminés et committés (évite de mêler les chantiers et reprend le menu mobile et le pied de page refaits).

1. Catalogue `app/content/nouveautes.py` + test de validation ; brouillon des textes FR/EN relu par l'utilisateur.
2. Migration 0024 + modèle + `_user_response` ; tests de migration sur Postgres 5433.
3. API `nouveautes.py` (liste, à voir, vues, abonnement, désabonnement signé) + tests.
4. E-mail : gabarit, textes, en-têtes de désabonnement, script d'envoi (essai / lots / reprise) + tests (`test_emails.py`) ; essai réel sur l'adresse de l'utilisateur.
5. Page `/nouveautes` (impeccable `shape` puis raffinement sur les jetons existants) ; route, sitemap, liens pied de page / menu mobile.
6. Fenêtre `NouveautesModal` (2 modes) + règles d'apparition ; entrée et pastille dans le panneau compte ; interrupteur.
7. Mention RGPD dans `content/legal/{fr,en}.ts` (confidentialité).
8. Vérifier : tsc/lint/build, pytest, Playwright (1re connexion, connexion suivante avec et sans nouveauté, 375/1280 px, clavier), impeccable `audit` ; `/code-review` (données + e-mail) ; captures montrées avant commit.
