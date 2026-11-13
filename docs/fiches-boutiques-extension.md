# Fiches boutiques de l'extension Précis

Date : 06/11/2026. Textes prêts à recopier pour le Chrome Web Store et Edge
Add-ons. Contexte et décisions : `docs/etude-distribution-extension.md`.
Archive à envoyer : `npm run package` dans `extension/` (`precis-translator-<version>.zip`, version 0.1.0).

## 1. Identité

| Champ | Valeur |
|---|---|
| Nom | Précis Translator |
| Catégorie Chrome | Productivité (Productivity) |
| Catégorie Edge | Productivité |
| Langue principale | Français (traduction anglaise fournie ci-dessous) |
| Site web | `https://precis-translator.trigenys.com` |
| Page d'aide / assistance | `https://precis-translator.trigenys.com/extension` |
| E-mail d'assistance | `contact@trigenys.com` |
| URL de confidentialité | `https://precis-translator.trigenys.com/confidentialite` |
| Éditeur | Structure qui exploite le service (compte à créer par le propriétaire du produit) |

## 2. Résumé (132 caractères au plus)

FR (105 caractères) :

```
Traduisez le texte et les images d'une page web en un clic, mise en page conservée. Compte Précis requis.
```

EN (95 caractères) :

```
Translate a web page's text and images in one click, layout preserved. Précis account required.
```

## 3. Description longue

### Français

```
Précis traduit une page web entière en un clic : le texte comme les images, avec la mise en page conservée.

Comment ça marche
1. Installez l'extension et épinglez son icône dans la barre d'outils.
2. Cliquez sur « Se connecter avec Précis » : le site Précis s'ouvre, connectez-vous (ou créez un compte) puis autorisez l'extension.
3. Sur une page en langue étrangère, cliquez sur l'icône puis sur « Traduire ».

Ce que vous obtenez
- Le texte de la page remplacé par sa traduction, au même endroit.
- Le texte contenu dans les images traduit lui aussi, sur accord.
- Une mémoire locale : une page déjà traduite n'est pas repayée.
- Aucune installation de logiciel supplémentaire.

Tarif
L'extension utilise les crédits de votre compte Précis (precis-translator.trigenys.com). Aucun abonnement supplémentaire pour l'installer.

Vos données
- La page n'est lue que lorsque vous cliquez sur l'icône.
- Le texte et les images de la page sont envoyés aux serveurs Précis uniquement pour être traduits.
- Aucune donnée de navigation n'est collectée, rien n'est vendu, aucune publicité.
- L'accès à un site n'est demandé que pour le site affiché, au premier clic sur « Traduire ».

Politique de confidentialité : https://precis-translator.trigenys.com/confidentialite
```

### English

```
Précis translates a whole web page in one click: text and images, with the layout preserved.

How it works
1. Install the extension and pin its icon to the toolbar.
2. Click "Se connecter avec Précis": the Précis website opens, sign in (or create an account) and authorize the extension.
3. On a page in a foreign language, click the icon, then "Translate".

What you get
- The page text replaced by its translation, in the same place.
- Text inside images translated too, with your consent.
- A local memory: a page you already translated is not charged again.
- No extra software to install.

Pricing
The extension uses the credits of your Précis account (precis-translator.trigenys.com). No extra subscription to install it.

Your data
- The page is read only when you click the icon.
- The page's text and images are sent to Précis servers only to be translated.
- No browsing data is collected, nothing is sold, no ads.
- Access to a site is requested for the site you are on only, the first time you click "Translate".

Privacy policy: https://precis-translator.trigenys.com/confidentialite
```

## 4. Objectif unique (single purpose)

FR : « Traduire le texte et les images de la page web consultée, à la demande de
l'utilisateur, grâce à son compte Précis. »

EN : "Translate the text and images of the web page being viewed, on the user's
request, using their Précis account."

## 5. Justification des permissions

À coller dans les champs « Justification » (Chrome) ou « Notes pour la
certification » (Edge). Texte anglais pour Chrome, qui l'exige en pratique.

| Permission | Justification (EN) | Version FR |
|---|---|---|
| `storage` | Keeps the user's sign-in session, preferences and the local translation memory in the extension's own storage. Nothing else is stored. | Conserve la session, les préférences et la mémoire locale de traductions dans le stockage propre de l'extension. |
| `activeTab` | Gives temporary access to the tab the user is viewing, only after they click the extension icon, to read the page text and images to translate. | Accès temporaire à l'onglet consulté, seulement après un clic sur l'icône, pour lire le texte et les images à traduire. |
| `scripting` | Injects the content script into the active tab so the translated text and images replace the original ones in place. Used only after the user's click. | Injecte le script dans l'onglet actif pour remplacer le texte et les images par leur traduction. Seulement après un clic. |
| Hôte `https://precis-translator.trigenys.com/*` | Lets the extension call the Précis API (sign-in, credit balance, translation) and lets the Précis website detect that the extension is installed (`externally_connectable`). | Appels à l'API Précis (connexion, solde, traduction) et détection de l'extension par le site. |
| Hôte facultatif `<all_urls>` | Optional, never requested as a whole. When the user first clicks "Translate" on a site, `chrome.permissions.request` asks for that site's origin only, so images served by the page can be read and translated. The user can revoke each site at any time. | Facultatif, jamais demandé en entier : au premier clic sur « Traduire », seule l'origine du site affiché est demandée. Révocable site par site. |

Points d'attention à l'examen :

- `<all_urls>` en facultatif peut allonger l'examen : préciser que seule
  l'origine du site affiché est demandée, au clic de l'utilisateur.
- Le code est entièrement inclus dans l'archive : aucun code distant exécuté.
- Fournir un compte de test (voir §9) : sans connexion, l'extension ne traduit rien.

## 6. Déclarations d'usage des données (Chrome, onglet « Confidentialité »)

Types de données à cocher :

| Type | Case | Motif |
|---|---|---|
| Informations d'identification personnelle | Non | L'e-mail est saisi sur le site, pas par l'extension |
| Données de santé | Non | |
| Informations financières et de paiement | Non | |
| Informations d'authentification | **Oui** | Jetons de connexion au compte Précis, stockés dans le navigateur |
| Communications personnelles | Non | |
| Données de localisation | Non | |
| Historique web | Non | Aucun historique ni liste de sites visités |
| Activité de l'utilisateur | Non | Pas de suivi des clics ni des frappes |
| Contenu du site web | **Oui** | Texte et images de la page, envoyés pour être traduits à la demande |

Certifications (les trois cases à cocher) :

- [x] Je ne vends pas les données des utilisateurs à des tiers hors cas d'utilisation approuvés.
- [x] Je n'utilise ni ne transfère les données à des fins sans rapport avec l'objectif unique de l'élément.
- [x] Je n'utilise ni ne transfère les données pour déterminer la solvabilité ou à des fins de prêt.

Autres réponses : code distant utilisé : **Non**. Publicité : **Non**.

Côté Edge : renseigner la même politique de confidentialité et indiquer que
l'extension traite du contenu de page à la demande, sans collecte de navigation.

## 7. Visibilité et distribution

| Boutique | Réglage au lancement | Passage au public |
|---|---|---|
| Chrome Web Store | Visibilité « Non répertorié » (Unlisted) : accessible par lien seulement | Passer en « Public » après le groupe d'essai |
| Edge Add-ons | Visibilité « Masqué » (Hidden) : accessible par lien seulement | Passer en « Public » |

Régions : toutes. Gratuit. Une fois la fiche créée, copier l'identifiant et
l'adresse de la fiche dans `VITE_EXTENSION_ID_*` et `VITE_EXTENSION_URL_*`.

## 8. Visuels à fournir

| Visuel | Taille | Remarques |
|---|---|---|
| Captures d'écran (1 à 5, viser 4) | 1280×800, PNG ou JPEG 24 bits sans transparence | 1. Page étrangère avant traduction. 2. Même page traduite, mise en page conservée. 3. Fenêtre de l'extension, connexion. 4. Une image dont le texte est traduit. 5. (option) Épinglage de l'icône |
| Vignette promotionnelle | 440×280 | Obligatoire sur Chrome ; logo et accroche courte |
| Grande vignette promotionnelle | 1400×560 | Facultative |
| Icône | 128×128 | Déjà dans l'archive (`icones/icone-128.png`) |

Conseils : interface en français et en anglais selon la langue de la fiche,
pas de données personnelles visibles, pas de logo tiers en gros plan.

## 9. Notes pour les examinateurs

```
The extension translates the current web page using a Précis account.
Test account: <e-mail de test> / <mot de passe de test> (credits loaded).
Steps: open any page in a foreign language, click the extension icon,
click "Se connecter avec Précis" (sign in with Précis): a tab opens on
https://precis-translator.trigenys.com, sign in there with the test account and
click "Autoriser" (Authorize); the tab closes by itself. Then click "Traduire" (Translate).
The extension never sees the password: it receives its own session through a
one-time code (60 s, PKCE S256). Signing out of the extension does not sign out the website.
The page text is sent to https://precis-translator.trigenys.com only on that click.
Optional all-sites access is only requested from the settings of the popup.
```

## 10. Checklist d'envoi

- [ ] Compte éditeur créé au nom de la structure (Chrome : 5 $ uniques ; Edge : gratuit).
- [ ] Archive produite par `npm run package` : manifeste de production (aucun `localhost`, nom « Précis », icônes 16/32/48/128).
- [ ] Version du manifeste incrémentée si une version a déjà été envoyée.
- [ ] Textes §2 à §4 collés, FR et EN.
- [ ] Permissions justifiées (§5) et déclarations de données cochées (§6).
- [ ] URL de confidentialité vérifiée en ligne, section « Extension navigateur » présente (FR et EN).
- [ ] Captures 1280×800 et vignette 440×280 chargées.
- [ ] Visibilité : Non répertorié (Chrome) / Masqué (Edge).
- [ ] Compte de test fourni aux examinateurs, crédits suffisants.
- [ ] Après validation : identifiant et adresse de fiche reportés dans les quatre variables `VITE_EXTENSION_*`, site reconstruit.
- [ ] Vérifier sur `/extension` : bouton vers la bonne boutique, statut « installée » après installation.
- [ ] Après le groupe d'essai : passage en visibilité publique.
