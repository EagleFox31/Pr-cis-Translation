# Étude — connexion de l'extension par le site

*10/11/2026 — branche `feat/connexion-extension-site`*

## 1. Besoin

Une seule porte d'entrée : on se connecte **uniquement sur le site**. L'extension renvoie vers le site, qui demande l'accord de l'utilisateur, puis l'extension reçoit sa propre session. C'est le schéma de Claude Code, GitHub CLI ou Spotify sur une télévision.

Ce que l'on gagne :
- une seule interface de connexion à maintenir (mot de passe, code e-mail, Google, oubli du mot de passe, Turnstile) ;
- les comptes créés avec Google peuvent enfin utiliser l'extension (aujourd'hui, impossible : elle ne connaît que e-mail + mot de passe) ;
- l'extension ne manipule plus aucun mot de passe, ce qui est plus simple à défendre devant les boutiques ;
- chaque utilisateur de l'extension passe par le site, ce qui le fait connaître.

## 2. Existant

| Élément | État |
|---|---|
| `extension/src/background.ts` `connexion()` | `POST /api/auth/login-password` avec e-mail et mot de passe saisis dans la fenêtre de l'extension |
| Stockage extension | jeton d'accès dans `chrome.storage.session`, jeton de renouvellement dans `chrome.storage.local` |
| Déconnexion extension | `POST /api/auth/logout`, qui **révoque toutes les sessions** du compte, site compris |
| Site (`AuthContext.tsx`) | jetons dans le `localStorage` du site ; connexion mot de passe, code e-mail, Google |
| `refresh_tokens` | un jeton haché par session, rotation à chaque renouvellement, aucune notion de « client » |
| Retour après connexion | `lib/authReturn.ts` : seul `?next=/beta` est accepté (liste blanche) |
| Lien site ↔ extension | `externally_connectable` sur le site, message `precis-ping` (détection d'installation) |
| nginx | les routes de l'application sont listées une à une ; `/extension/...` tomberait aujourd'hui en 404 |
| Stockage temporaire serveur | pas de Redis : Postgres seulement |

## 3. Options

| Option | Pour | Contre |
|---|---|---|
| **A. Lire la session du site** (script de l'extension qui copie les jetons du `localStorage` du site) | rapide | une seule session partagée : la rotation fait que l'un déconnecte l'autre au hasard ; lecture de jetons d'une page par une extension, mal vue à l'examen |
| **B. `chrome.identity.launchWebAuthFlow`** | API prévue pour ça | fenêtre séparée dont le partage de session avec le navigateur varie selon les navigateurs ; adresse de retour `chromiumapp.org` propre à chaque identifiant d'extension (Chrome ≠ Edge ≠ version locale) |
| **C. Onglet du site + code à usage unique + PKCE** | même navigateur, donc session du site déjà présente ; aucune permission nouvelle (l'extension a déjà accès au domaine du site) ; marche à l'identique sur Chrome, Edge et en local | un peu plus de code (2 pages, 3 routes) |

**Choix : C.**

## 4. Fonctionnement retenu

1. L'extension tire un secret aléatoire (`verifier`, 32 octets) et un `state` aléatoire, les garde dans `chrome.storage.session`, puis ouvre un onglet :
   `/extension/autoriser?challenge=<SHA-256(verifier)>&state=<state>`.
2. Pas connecté → le site envoie vers `/login?next=...`, puis ramène sur la page d'autorisation après connexion (y compris par Google).
3. La page affiche le compte et « Autoriser l'extension Précis Translator à utiliser ce compte ? » avec **Autoriser** et **Annuler**.
4. Autoriser → `POST /api/extension/auth/code` (session du site) : le serveur crée un code aléatoire, valable 60 s, lié au compte et au `challenge`, et n'en garde que l'empreinte. Le site part alors sur `/extension/connecte#code=...&state=...`. Le code est dans le **fragment** (`#`), donc il n'est ni envoyé au serveur, ni écrit dans les journaux nginx.
5. L'extension surveille l'onglet qu'elle a ouvert. Quand il arrive sur `/extension/connecte`, elle vérifie le `state`, appelle `POST /api/extension/auth/token` avec le code et le `verifier`, enregistre la session et ferme l'onglet.
6. Le serveur supprime le code dès sa première présentation, valide ou non, et vérifie `SHA-256(verifier) == challenge` : un code volé seul ne sert à rien.

Déconnexion :
- extension → `POST /api/extension/auth/deconnexion` avec son jeton de renouvellement : seule **sa** session est révoquée ;
- site → `/api/auth/logout` ne révoque plus que les sessions du site ;
- réinitialisation du mot de passe → toutes les sessions sont révoquées, extension comprise (inchangé : c'est voulu).

## 5. Impacts

- **Données** : migration `0023_extension_auth` qui crée la table `extension_auth_codes` (empreinte du code, compte, challenge, échéance) et ajoute `refresh_tokens.client` (`site` par défaut, `extension`). Aucune donnée existante modifiée.
- **Sécurité** : PKCE S256 obligatoire ; code de 60 s à usage unique ; `state` contre les connexions forcées ; accord explicite par un clic ; limitation de débit sur les 3 routes ; e-mail vérifié exigé ; la page d'autorisation n'accepte qu'un `challenge` et un `state` au format attendu.
- **Site** : 2 pages (`/extension/autoriser`, `/extension/connecte`), `authReturnTo` accepte aussi le retour vers la page d'autorisation (chemin fixe, paramètres validés), textes FR/EN, règle nginx (`noindex`).
- **Extension** : le formulaire est remplacé par un bouton ; aucune permission nouvelle ; nouvelle archive à envoyer à Edge.
- **Boutiques** : fiche « Comment ça marche » étape 2 et notes de certification à mettre à jour ; l'examinateur se connecte sur le site avec le compte de test.
- **Compatibilité** : les extensions déjà connectées gardent leur session (jeton de renouvellement inchangé, `client = site` par défaut).

## 6. Risques

- Onglet fermé avant la fin ou service worker endormi → l'état est dans `chrome.storage.session` et l'écouteur est déclaré au démarrage du service worker ; au pire l'utilisateur reclique.
- Tests de bout en bout impossibles sans navigateur : logique PKCE et lecture du fragment testées en unitaire côté extension, routes testées côté serveur, parcours vérifié à la main en local.

## 7. Points tranchés

- Option C, sans permission nouvelle.
- Faite **avant** le premier envoi Edge, pour éviter un deuxième examen.
