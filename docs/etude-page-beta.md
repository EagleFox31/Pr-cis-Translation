# Étude — page publique Bêta (`/beta`) simplifiée

## 1. Besoin
La page `/beta` (candidature au Programme Bêta) doit être simple, tenir sur un écran
d'ordinateur portable (1266 × 900) sans défilement, ressembler aux autres pages du site
et ne demander que ce qui sert à la décision.

Critères d'acceptation :
- Sur 1266 × 900, programme et formulaire visibles ensemble, sans défilement.
- Sur mobile (390 px), les deux blocs s'empilent ; « Retour » et le titre restent visibles en haut au défilement.
- Le formulaire envoie toujours `primary_format` + `motivation` ; aucun changement serveur.
- Tous les états restent couverts : non connecté, e-mail non vérifié, candidatures fermées, candidature en attente / approuvée / refusée, accès actif.

## 2. Existant
| Élément | Rôle aujourd'hui |
|---|---|
| `frontend/src/pages/BetaPage.tsx` | Deux cartes l'une sous l'autre : la fiche programme, puis la carte « Participer » (formulaire ou état). C'est l'empilement qui fait défiler la page. |
| `ApplicationForm` (même fichier) | Liste déroulante « Format principal à tester », zone de texte 4 lignes, deux paragraphes de mentions (`commitment`, `privacy_hint`). |
| `components/pricing/BetaProgramDetails.tsx` | Fiche programme partagée avec `BetaOffer.tsx` (page Tarifs). Ne l'afficher différemment que via une option, pour ne pas toucher la page Tarifs. |
| `components/admin/AdminShell.tsx` | Gabarit commun : barre du site, en-tête `.admin-head` (Retour + titre). L'en-tête défile avec la page. |
| `beta.css` | Styles `beta-*` ; `.beta-public` place déjà les quotas en colonne de droite sur grand écran. |
| i18n `beta.public.*` | `availability.open`, `conditions`, `selection` existent mais ne sont pas affichés sur `/beta`. |
| `AdminBetaPage.tsx` | Le format choisi ne sert qu'au tri et à l'affichage côté admin ; il est recopié sur l'invitation et n'agit pas sur les quotas. |

## 3. Options comparées
| Option | Pour | Contre |
|---|---|---|
| A. Garder l'empilement, réduire les marges | Très peu de code | Ne tient toujours pas sur un écran |
| B. **Deux colonnes : programme à gauche, formulaire / état à droite** | Tout visible d'un coup ; même grille que les autres pages ; pile naturelle sur mobile | Fiche programme à resserrer (quotas en liste compacte) |
| C. Assistant en plusieurs étapes | Formulaire très court par écran | Plus de clics pour 2 champs ; incohérent avec le reste du site |

## 4. Choix (validé par l'utilisateur)
Option B :
- **Gauche** : étiquette, titre, description, pastilles « Candidatures ouvertes » / durée / « Sur validation », puis les 4 formats et leurs quotas.
- **Droite** : formulaire, ou état de la candidature / de l'accès (contenu actuel conservé).
- **Format** : gardé, en léger. Une ligne de choix cliquables « Je testerai surtout : PDF · PowerPoint · Word · Excel », avec la mention « vous aurez accès aux 4 formats » (évite de croire que le choix limite l'accès).
- **Texte libre** : libellé « Que souhaitez-vous traduire ? », 3 lignes, compteur 0/1000 (le serveur exige 10 à 1000 caractères). Pas de champ « langues » : l'exemple invite à les préciser.
- `commitment` et `privacy_hint` fusionnés en une seule ligne sous le bouton.
- En-tête « Retour » + titre collé en haut au défilement (`position: sticky`) sur les pages sans onglets du gabarit, soit `/beta` ; les pages admin ne bougent pas.

## 5. Impacts
- Données / serveur : aucun.
- Sécurité : aucune (même requête, mêmes contrôles serveur).
- i18n : nouvelles clés fr/en (`beta.application.format_hint`, `all_formats`, `notice`, libellé du texte libre) ; anciennes clés inutilisées retirées.
- Page Tarifs : inchangée (les pastilles et la mise en page compacte passent par une option de `BetaProgramDetails`).
- Accessibilité : choix de format en `fieldset` + boutons radio (clavier, lecteur d'écran) ; compteur annoncé via `aria-describedby`.

## 6. Risques
- Hauteur sur 900 px si la description est longue : vérifié par Playwright ; le texte se coupe à la ligne, pas de troncature.
- Bandeau collé au défilement qui masque du contenu : fond opaque, faible hauteur, vérifié sur mobile.

## 7. Points tranchés
Tous les points ont été validés avant l'implémentation (mise en page, champ format gardé en léger, pas de champ langues, aucune modification serveur).
