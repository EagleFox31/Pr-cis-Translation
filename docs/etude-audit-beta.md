# Audit du programme bêta (22/10/2026)

Périmètre : #33, #37, #39, #41, #43 (fonctions, interface, sécurité). Tests auto : 3 suites OK, dont les 4 tests de course sur PostgreSQL jetable.
Verdict sécurité : conforme avec réserves. Aucun défaut critique.

## Écarts

| # | Gravité | Écart | Fichiers | Correctif proposé | Décision |
|---|---------|-------|----------|-------------------|----------|
| 1 | Élevé | L'IP client est falsifiable : uvicorn avec `--forwarded-allow-ips '*'` lit la première valeur de X-Forwarded-For, et nginx ajoute à la suite de l'en-tête client. Toutes les limites par IP sont contournables (bêta, login, register, Google), et l'attaquant peut créer de faux signaux « same_ip ». | `backend/docker-entrypoint.sh:54`, `frontend/nginx.conf:46`, `beta_abuse.py:76` | nginx : `X-Forwarded-For $remote_addr` (écrase l'en-tête) ; uvicorn : n'accepter que l'IP ou le sous-réseau de nginx ; corriger `beta-program.md:98,121` | corrigé (A, 22/10) |
| 2 | Moyen | Une page PDF ou une diapo vaut 1 unité quel que soit le texte. Un DOCX de 40 000 mots converti en PDF de 20 pages contourne le plafond Word. | `beta_meter.py:12`, `translate.py:276,400` | Plafond de mots par page et par diapo, ou budget de mots global | laissé tel quel (décision 22/10 : comptage à la page conservé) |
| 3 | Moyen | `precise=1` (modèle de raisonnement) n'est vérifié nulle part : tout compte l'obtient, au même coût de quota. | `translate.py:188,216` | Réserver aux admins, ou compter ×N | corrigé (A, 22/10 : `qualite_autorisee`, `tests/test_mode_precis.py`) |
| 4 | Moyen | À la suppression du compte, l'e-mail en clair et la motivation sont gardés indéfiniment. | `models/beta.py:31,72,77` | À la suppression : HMAC de l'e-mail et motivation effacée | corrigé (A, 22/10 : `anonymize_deleted_accounts` dans la purge quotidienne, test dans `test_beta_abuse.py`) |
| 5 | Moyen (à confirmer) | Un job en `error` rembourse tout le quota, alors que l'aperçu partiel a été servi en clair. | `jobs.py:281`, `translate.py:675` | Ne rembourser que les unités non livrées | laissé tel quel (B, 22/10 : remboursement total ; A seulement avec une reprise page par page, qui n'existe que pour le PPTX `translation_runner.py:681`, chantier à part) |
| 6 | Faible | La limite « 5 par navigateur » ne bloque rien : sans cookie, chaque requête reçoit un nouvel identifiant. | `beta_abuse.py:87` | La documenter comme un simple signal | corrigé (25/10 : machine `anti_abus` — cookie signé, copie locale, empreinte — pour la bêta et le gratuit, `test_anti_abus.py`) |
| 7 | Faible | Une IPv6 est hachée sur /128 : changer d'adresse dans un /64 suffit à la contourner. | `beta_abuse.py:79` | Hacher le préfixe /64 | corrigé (A, 25/10 : `beta_abuse.network_key`, IPv4 encapsulée ramenée à l'IPv4, test `test_ipv6_regroupee_par_prefixe_64`) |
| 8 | Faible | Seuls les alias Gmail sont rapprochés : `+tag` Outlook/iCloud/Proton, le `-` de Yahoo et les domaines jetables passent. | `beta_abuse.py:35` | Liste de fournisseurs, domaines jetables affichés comme signal | corrigé (25/10 : alias Outlook/iCloud/Proton/Fastmail/Yahoo, clés recalculées par `0014_anti_abus`, domaines jetables refusés) |
| 9 | Faible | Normalisation `casefold()` côté bêta, `lower()` côté compte : `strasse` peut activer l'invitation de `straße`. | `beta.py:55,126`, `auth.py:207` | Aligner sur `User.email` | corrigé (A) : `lower()` partout côté bêta et anti-abus, test `test_invitation_is_matched_like_account_emails` |
| 10 | Faible | Pas d'index unique en base sur `mailbox_key` des inscriptions activées. | `0012_beta_abuse_guards.py:39` | Index partiel `(campaign_id, mailbox_key) WHERE activated_at IS NOT NULL` | corrigé (A) : migration `0015_beta_mailbox_unique` (doublons historiques : clé remise à NULL sauf la plus ancienne), test `test_database_refuses_two_activated_trials_for_one_mailbox` |
| 11 | Faible | Aucune limite de débit HTTP sur apply, activate et program. | `api/beta.py:75,210` | `@rate_limit_decorator` | corrigé (A) : activate 5/min, applications 10/min (au-dessus de la rafale 5/10 min), program 30/min ; test `test_beta_routes_are_rate_limited_per_ip` |
| 12 | Faible | `use_beta="auto"` par défaut : un client API consomme la bêta sans l'avoir demandé, contre la doc. | `translate.py:173,249` | Défaut `"0"`, ou corriger la doc | accepté (B) : `auto` conservé (le gratuit passe avant le payant), doc `beta-program.md` corrigée |
| 13 | Faible | Les écritures sans espaces (thaï, khmer…) sont sous-comptées. | `beta_meter.py:26` | Découper ces plages, ou compter en équivalent caractères | corrigé (A) : 1 mot / 5 caractères (thaï, lao, birman, khmer) |
| 14 | Faible | nginx n'envoie aucun en-tête de sécurité : clickjacking possible sur « Activer » et sur `/admin/beta`. | `nginx.conf:96` | `frame-ancestors 'none'`, X-Frame-Options, Referrer-Policy | corrigé (A) : frontend/security-headers.conf inclus partout, vérifié nginx 1.27 |
| 15 | Faible | L'e-mail passe dans l'URL `/verify-email?email=`. | `BetaPage.tsx:97` | Passer par l'état du routeur | corrigé (A) : lien sans e-mail, la page reprend celui du compte connecté |
| 16 | Faible | La motivation accepte les caractères de contrôle et bidi (U+202E). | `api/beta.py:67` | Refuser Cc/Cf sauf `\n` | corrigé (A) : 422 sur contrôle/bidi (retours à la ligne et emoji permis), message i18n |
| 18 | Moyen | Les messages d'erreur bêta du serveur sont en français codé en dur et affichés tels quels : un utilisateur anglophone lit « Les candidatures à la bêta sont fermées. » (apply, activate, admin). | `services/beta.py:123-163`, `services/beta_applications.py:44-56`, `api/beta.py:119-187`, `BetaPage.tsx:28,65` | Codes d'erreur stables côté serveur, traduits par i18n côté front (repli sur `beta.error`) | corrigé (A) : `detail` = {code, message}, page traduite via `beta.errors.<code>` (repli `beta.error`) |
| 19 | Faible | Jauges : le texte visible « 0 / 20 pages » est le reste, sans le dire (seul l'`aria-label` dit « restant ») ; un quota épuisé se lit « 0 utilisé ». | `BetaAllowances.tsx:15` | « 0 pages restantes sur 20 » (clé i18n) | corrigé (A) : clés plurielles `beta.left.<unité>`, ligne Excel alignée |
| 20 | Faible | Nombres formatés avec la langue du navigateur (`toLocaleString()`) et non celle de l'interface : « 7 500 / 10 000 words » sous « 10,000 words ». | `BetaAllowances.tsx:15,20` | `toLocaleString(i18n.language)` | corrigé (avec #19) |
| 21 | Faible | Mobile : l'erreur d'activation s'affiche sous les quatre jauges, hors écran après le clic sur « Activer ». | `BetaPage.tsx:122` | Afficher le message juste sous le bouton | corrigé (A) |
| 22 | Faible (hors bêta) | Mobile 375 px : le menu « Administration » de l'en-tête est coupé à droite. | en-tête global | Réduire en icône sous 420 px | corrigé (A) : engrenage sous 420 px |
| 23 | Moyen | La case « Utiliser mon quota Bêta » est cochée par défaut dès qu'une inscription existe, quel que soit son état (invitée, expirée, révoquée) et quel que soit le format. Le front envoie alors `use_beta=1` : un fichier `.txt`, ou tout fichier d'un testeur expiré, est refusé (402 `beta_inactive`) tant que la case n'est pas décochée. | `TranslationSection.tsx:79,126,146`, `translate.py:249-256` | Front : n'afficher et n'envoyer la case que si l'état est `active` et le format bêta. Serveur : `use_beta=1` sur un format hors bêta se comporte comme « auto ». | corrigé (A) : case seulement si actif + format bêta ; serveur ignore `use_beta=1` hors format bêta (`test_non_beta_format_ignores_beta_choice`) |
| 17 | Hors périmètre | 127 commits historiques ont un trailer d'attribution. Aucun sur cette branche. | historique | Ne pas réécrire l'historique publié | aucune |

## Vérifiés sans écart (résumé)

- Routes admin protégées par `require_admin`.
- Pas d'IDOR.
- Lien d'activation sans secret.
- Activation liée à l'e-mail vérifié, à usage unique.
- Verrous de concurrence corrects.
- Quotas : cache et retraduction facturés, aucun débordement sur les pages payantes.
- Pas de XSS, pas de CSRF.
- Cookie HMAC HttpOnly.
- `no-store` sur les réponses sensibles.

## Parcours UI (22/10, Playwright, API simulée)

20 scénarios × fr/en × bureau 1280 px / mobile 375 px (80 captures) : visiteur (programme fermé réel, ouvert, erreur), e-mail non vérifié, formulaire (succès, erreur serveur, inscriptions fermées), candidature en attente / refusée, invitation (activation refusée, fenêtre fermée), accès actif / expiré / révoqué, erreur `/api/beta/me`, admin (vide, complet avec signaux, erreur), offre bêta sur la page tarifs (ouverte, fermée réelle).
Résultat : aucun débordement horizontal, aucune clé i18n brute, aucun mojibake, aucune erreur JS ; états vide/erreur/chargement présents avec bouton « Actualiser ». Écarts #18 à #22 ci-dessus.

## Interactions avec la branche (5e)

- Invitations e-mail (0013) : aucun lien avec la bêta (ni code partagé ni quota commun), pas de confusion possible entre les deux invitations.
- Paiement carte / Fapshi : un testeur peut acheter normalement ; `_document_pages` n'intervient pas en mode bêta.
- Quota gratuit #45 : en mode bêta, le document est marqué payé (`doc_is_paid`), donc ni `KIND_FREE_OFFER` ni future mention « Traduit avec Précis ». Le quota bêta épuisé renvoie un message clair qui invite à décocher la case.
- Écart : #23.

## Non vérifié

- Proxy en amont de nginx en production (concerne #1 et #14).
- Possibilité réelle de provoquer #5.
- Prise en compte de `quality` par le job PDF v2 (concerne #3).
