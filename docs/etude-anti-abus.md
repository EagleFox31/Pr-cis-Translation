# Étude — anti-abus du gratuit et de la bêta

Date : 22/10/2026. Origine : écart #6 de `docs/etude-audit-beta.md` (+ #8 alias e-mail, décision Point 1 « garde-fous bêta généralisés au gratuit »).

## 1. Besoin et contraintes

- Bloquer réellement « 5 pages offertes par navigateur », pas seulement par IP ; identifier la machine par tout moyen fiable.
- Borner le cumul : changer de navigateur, d'appareil ou d'adresse ne doit pas multiplier les 5 pages.
- Détecter et refuser les e-mails jetables / temporaires.
- **Ne pas bloquer un compte légitime** sur une machine déjà servie (deux comptes réels possibles) : le quota reste **par compte**, la machine borne seulement le cumul.
- S'appuyer sur des systèmes éprouvés, pas du « maison » fragile.
- Contexte réseau : public surtout camerounais, IP mobiles partagées (CGNAT), cybercafés, appareils partagés en famille → une IP seule ne doit **jamais** bloquer.

## 2. Existant

| Élément | État | Fichier |
|---|---|---|
| Quota gratuit | 5 pages équivalentes / mois **par compte** (`KIND_FREE_OFFER`), réservé atomiquement, remboursement exclu | `services/usage.py:61-84`, `api/translate.py:418-451` |
| Inscription | e-mail + code, mot de passe, Google ; connexion impossible sans e-mail vérifié | `api/auth.py:201,277,318,530` |
| Identifiant navigateur | cookie signé `precis_beta_device` (HMAC), limité à `/api/beta` ; **sans cookie, nouvel identifiant à chaque requête → rien n'est bloqué** (#6) | `services/beta_abuse.py:83-110` |
| Limites bêta | 5 candidatures / navigateur et 20 / IP par 10 min, signaux admin 30 j, purge quotidienne | `beta_abuse.py:113-208` |
| Rapprochement d'adresses | Gmail seul (points, `+tag`) | `beta_abuse.py:27` |
| E-mails jetables | aucun contrôle | — |
| IP client | fiable depuis le correctif #1 (nginx écrase XFF) | `nginx.conf`, `docker-entrypoint.sh` |

Réutilisable : `_digest` (HMAC, aucune donnée brute stockée), `ClientSignals`, la purge quotidienne `cleanup_loop`, `canonical_mailbox`.

## 3. Pratiques reconnues (recherche 22/10)

- **Approche en couches, score plutôt que oui/non** : empreinte d'appareil + réputation du domaine e-mail + vélocité IP ; laisser passer le risque faible, bloquer l'abus net, demander une vérification en plus pour la zone grise (Stripe, Stytch).
- **Domaines jetables** : liste communautaire `disposable-email-domains` (GitHub, ~4 000+ domaines, paquet PyPI officiel publié par l'organisation, mis à jour en continu ; comparaison sur le domaine enregistré, sous-domaines inclus).
- **Empreinte navigateur** : FingerprintJS open source **v5, licence MIT** depuis le 22/10/2025 (v4 était BSL, interdite en production). Moins précise que la version payante (pas d'identification côté serveur) ; collisions possibles entre appareils identiques (même modèle de téléphone, même navigateur). Fingerprint Pro (~99,5 %) est payant (≈ 200 $/mois annoncés).
- **Anti-robots à l'inscription** : Cloudflare Turnstile, gratuit, vérification serveur `siteverify` obligatoire (jeton 300 s, usage unique).
- **Juridique** : la CNIL range le calcul d'empreinte du terminal dans l'article 82 (comme les cookies) ; l'exemption « lutte contre la fraude » n'est pas clairement acquise. Au Cameroun (loi 2024-017), information + finalité limitée + durée courte. → minimiser : empreinte calculée seulement au moment d'une traduction gratuite, stockée hachée (HMAC), purgée, mentionnée dans la politique de confidentialité.

Sources : [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains), [PyPI](https://pypi.org/p/disposable-email-domains), [FingerprintJS v5 MIT](https://fingerprint.com/blog/fingerprintjs-version-5-0-mit-license/), [OSS vs Pro](https://fingerprint.com/blog/open-source-vs-fingerprint-pro-accuracy/), [Stripe — trial abuse](https://stripe.com/en-li/resources/more/how-to-prevent-free-trial-abuse-in-saas-and-ai-products), [Stytch](https://stytch.com/docs/fraud/guides/prevent-free-trial-abuse), [Turnstile siteverify](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/), [CNIL FAQ traceurs](https://cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies/FAQ).

## 4. Options

### 4.1 Identifier la machine

| Option | Pour | Contre |
|---|---|---|
| A. Cookie signé seul (existant, élargi à `/api`) | simple, aucun tiers | navigation privée / effacement = nouvelle machine |
| **B. Cookie signé + copie `localStorage` + empreinte FingerprintJS v5 (MIT)** | survit à l'effacement d'un seul stockage ; l'empreinte survit souvent à la navigation privée ; gratuit, éprouvé | collisions (appareils identiques) → ne peut servir qu'à **borner**, jamais à bloquer un compte seul ; sensible juridiquement |
| C. Fingerprint Pro | le plus fiable | ~200 $/mois, données chez un tiers |

**Choix : B.** Le serveur regroupe sous une même « machine » tout identifiant déjà vu ensemble (cookie, copie locale, empreinte) : effacer un stockage ne suffit plus, il faut tout changer à la fois.

### 4.2 Borner le cumul

| Option | Pour | Contre |
|---|---|---|
| A. 5 pages / mois / machine strict | « 5 par navigateur » au sens littéral | bloque le 2ᵉ compte légitime d'un foyer (contraire aux contraintes) |
| **B. Plafond machine = 2 comptes (10 pages / mois), plafond IP souple, aucun blocage par IP seule** | 2ᵉ compte réel servi ; le 3ᵉ compte sur la même machine ne reçoit plus de pages offertes (il peut payer) | un abuseur a 2 × 5 pages par machine |
| C. Score de risque (machine + IP + domaine + âge du compte) | le plus fin | plus de code, plus dur à expliquer au support |

**Choix : B**, avec un signal IP en complément : au-delà de 30 pages offertes / 24 h depuis une même IP, le compte doit avoir **au moins un appareil déjà connu** (sinon refus poli et proposition d'achat). Le compte n'est jamais bloqué : seule la page offerte est refusée, l'achat reste possible.

Cumul inter-appareils : le quota par compte est déjà indépendant de l'appareil ; un compte qui change de machine consomme le même quota. Le multi-comptes multi-machines est freiné par : e-mails jetables refusés, alias rapprochés, plafond machine et IP, Turnstile à l'inscription.

### 4.3 E-mails jetables

| Option | Pour | Contre |
|---|---|---|
| **A. Paquet `disposable-email-domains` épinglé + liste locale d'ajouts / exceptions** | liste maintenue, hors ligne, aucune latence | mise à jour = montée de version du paquet |
| B. API payante (Kickbox, ZeroBounce…) | détection plus fraîche | coût, latence, tiers |
| C. Vérification MX | attrape les domaines morts | ne détecte pas les jetables actifs |

**Choix : A**, appliqué à `register`, `register-password`, candidature bêta et invitations reçues ; Google exclu (adresses Gmail réelles). Message neutre : « Les adresses e-mail temporaires ne sont pas acceptées. » Les comptes existants à domaine jetable ne reçoivent plus de pages offertes (pas de suppression).

### 4.4 Alias d'adresses (#8)

Étendre `canonical_mailbox` : `+tag` pour Outlook/Hotmail/Live, iCloud, Proton, Fastmail ; `-` pour Yahoo. Clé de rapprochement seulement, l'adresse de connexion ne change pas. Utilisée pour : un seul quota gratuit par boîte réelle.

### 4.5 Robots à l'inscription

Turnstile en mode invisible sur l'inscription (option, voir § 7). Sans clé configurée, le contrôle est désactivé (dev, tests).

Mise en œuvre (`app/services/turnstile.py`, `components/auth/Turnstile.tsx`) :
- contrôlé **seulement à la création de compte** : `register`, `register-password` et la branche de `login` qui crée le compte implicitement ; un compte existant se connecte sans jeton ;
- jeton absent, trop long (> 2048) ou refusé → 400 ; **panne réseau vers Cloudflare → laisse passer avec un journal** (bloquer toutes les inscriptions coûte plus que quelques robots, freinés par ailleurs) ;
- widget `appearance: interaction-only`, script chargé à la demande sur /login et /register ; le bouton reste désactivé jusqu'au jeton, réinitialisé après chaque envoi (jeton à usage unique) ;
- clés : `TURNSTILE_SECRET_KEY` (backend), `TURNSTILE_SITE_KEY` → `VITE_TURNSTILE_SITE_KEY` au build du front. Clé de test Cloudflare toujours valide : `1x00000000000000000000AA`.

## 5. Conception retenue

- **Service** `services/anti_abus.py` (généralise `beta_abuse`) : `client_signals` lit cookie `precis_device` (path `/api`, 1 an, httponly), en-tête `X-Device-Copy` (copie localStorage), en-tête `X-Device-Print` (visitorId FingerprintJS) ; tout est haché en HMAC avant usage.
- **Table** `device_links` (hash, kind ∈ cookie/copy/print, machine_id, last_seen) et `free_grants` (user_id, machine_id, ip_hash, pages, created_at) — migration `0014_anti_abus`. Purge : liens > 60 j, attributions > 35 j.
- **Contrôle** dans `translate.py` sur la branche gratuite, sous le verrou déjà pris : plafond machine (comptes distincts servis ce mois ≤ 2), plafond IP souple, domaine jetable. Refus → 402 `reason: "free_limit_device"` (réutilise la fenêtre « quota épuisé » + pack Mobile Money).
- **Bêta** : `check_submission_rate` passe sur les mêmes signaux (fin de #6).
- **Front** : FingerprintJS v5 chargé à la demande (page de traduction et candidature bêta seulement), en-têtes ajoutés par le client API ; échec du chargement = cookie seul (jamais bloquant).
  Mise en œuvre (`frontend/src/lib/device.ts`) : `@fingerprintjs/fingerprintjs` 5.3.0 épinglé, importé dynamiquement (chunk séparé, ~16 ko gzip, `monitoring: false`), attente bornée à 1,5 s par appel, calcul mis en cache pour la page ; copie `localStorage` = identifiant aléatoire (`precis_device_copy`). En-têtes posés sur `POST /api/translate` (`useStreamingTranslation`) et `POST /api/beta/applications` (`BetaPage`, via le 3ᵉ paramètre de `api.post`). Le 402 `free_limit_device` réutilise le panneau d'achat du manque de crédits (`creditsNeeded`) et y affiche le motif (`creditsReason`, clé `story.free_limit_device` fr/en). Vérifié sous Playwright : empreinte stable après effacement du `localStorage`, stockage interdit sans erreur, panneau et en-têtes sur une réponse 402 simulée.
- **Revue de sécurité (g.6, 25/10)** — ajustements retenus :
  - *Fusion* : seuls cookie et copie locale fusionnent des machines (la plus ancienne l'emporte, jamais de séparation ; la purge à 60 j borne les fusions erronées). L'empreinte ne rattache un navigateur que s'il n'apporte aucun identifiant fort connu : deux appareils identiques gardent chacun leur machine (`test_empreinte_ne_fusionne_jamais_deux_machines`).
  - *Vélocité IP* : compte les pages offertes réellement attribuées, `min(besoin, reste du forfait)`, et non la taille du document.
  - *En-têtes d'appareil* : envoyés seulement par un compte Gratuit (aucune empreinte calculée pour un abonné).
  - *Turnstile* : script bloqué ou widget en erreur → le bouton se réactive et le serveur répond un 400 clair, plutôt qu'un blocage muet.
  - *IP de confiance* : nginx ne croit X-Forwarded-For que de Caddy, à l'adresse fixe `172.30.250.10` (`docker-compose.https.yml`, sous-réseau `172.30.250.0/24` ; recréer le réseau au déploiement : `down` puis `up`).
  - *Attribution conservée après remboursement* : signal seulement, accepté.
  - *Ancien cookie bêta* `precis_beta_device` non relu : accepté, documenté dans `beta-program.md`.
- **i18n** fr/en des nouveaux messages ; **politique de confidentialité** : mention du contrôle anti-abus (texte fourni dans la PR, page CGU encore à rédiger).

## 6. Impacts et risques

| Domaine | Impact |
|---|---|
| Données | 2 tables, uniquement des HMAC ; purge automatique ; migration 0014 |
| Sécurité | en-têtes client falsifiables → ne servent qu'à **relier** des identifiants (jamais à délier) ; le cookie reste signé |
| Performance | 2–3 requêtes indexées par traduction gratuite ; script ~40 Ko chargé à la demande |
| Dépendances | `disposable-email-domains` (PyPI, MIT/CC0), `@fingerprintjs/fingerprintjs@5` (MIT), Turnstile si retenu |
| Risques | faux positifs (même modèle de téléphone dans un cybercafé) → plafond à 2 comptes et refus limité aux pages offertes ; liste jetable jamais complète |

## 7. Points tranchés (22/10/2026)

Décision de l'utilisateur : **s'aligner sur la pratique du marché** pour tous les points.

Pratique observée : Claude (Anthropic) quote par compte, vérifie souvent un numéro de téléphone à l'inscription et interdit par ses conditions le partage de compte et le multi-comptes pour contourner les limites. ChatGPT, DeepL et Canva quotent aussi par compte, freinent le multi-comptes par un score (appareil, IP, domaine) et demandent une vérification en plus dans la zone grise. Aucun ne bloque durement par machine. Le prêt de compte est interdit par les conditions, pas bloqué techniquement.

Conception révisée (remplace § 4.2 B) :
- **Quota par compte** inchangé (5 pages / mois).
- **Score de risque** sur la traduction gratuite : machine déjà servie à ≥ 2 autres comptes ce mois, vélocité IP (> 30 pages offertes / 24 h), compte créé il y a moins de 24 h sans appareil connu.
- **Zone grise → vérification du téléphone (SMS)** : un numéro vérifié = un seul quota gratuit, comme Claude. Tant qu'aucun fournisseur SMS n'est configuré, la zone grise retombe sur le refus des pages offertes (l'achat reste possible).
- **Abus net** (domaine jetable, numéro déjà lié à un autre quota) → pages offertes refusées.
- **Prêt / partage de compte** : clause des CGU (page à rédiger) ; pas de blocage technique.
- FingerprintJS v5 + mention dans la politique de confidentialité ; Turnstile à l'inscription ; comptes jetables existants : pages offertes coupées.

Reste ouvert : **fournisseur SMS** (Twilio Verify, Vonage, ou agrégateur local au Cameroun). Coût par SMS au Cameroun à chiffrer avant de choisir. N'empêche pas de livrer le reste.

Questions posées :

1. **Plafond par machine** : 2 comptes servis / mois (10 pages) — recommandé — ou 5 pages strictes par machine ?
2. **Empreinte navigateur** (FingerprintJS) : l'accepter avec mention dans la politique de confidentialité — recommandé — ou cookie + copie locale seulement (plus faible, sans question juridique) ?
3. **Turnstile** à l'inscription : oui (gratuit, compte Cloudflare + 2 clés à créer) ou plus tard ?
4. **Comptes existants à domaine jetable** : couper seulement les pages offertes (recommandé) ou aussi les signaler à l'admin ?
