# Étude : refonte des interfaces d'administration

*25/10/2026 — branche `feat/mise-a-jour-carte-invitations-visionneuse`*

## 1. Besoin

> « Les interfaces d'administration sont faites sans aucune norme […] ça doit rester simple, équilibré et bien réparti sur l'espace disponible comme les autres pages, y compris la campagne (un peu serrée à gauche). »

Critères d'acceptation :
- Les cinq pages admin (`/admin/users`, `/admin/documents`, `/admin/logs`, `/admin/support`, `/admin/beta`) suivent **un même gabarit** : en-tête, barre d'outils, liste, état vide, chargement.
- À 1440 px, le contenu occupe la largeur du cadre du site (1240 px), sans colonne à moitié vide.
- À 375 px : pas de défilement horizontal de la page, pas de badge renvoyé seul sous un texte, champs alignés.
- La page publique `/beta` n'a plus son contenu tassé à gauche.
- Aucun changement de comportement : les mêmes actions, les mêmes appels API, les mêmes textes (sauf les libellés harmonisés, en fr et en en).

## 2. Existant (relevé sur captures 1440 px et 375 px)

| Élément | Où | Constat |
|---|---|---|
| Coquille | `components/admin/AdminShell.tsx` | Bonne base : même barre que le site, cadre `--frame-max` (1240 px). Titre, compteur et actions sont en styles écrits directement dans le code. |
| Bouton d'actualisation | toutes les pages | « Actualiser » sans icône sur la page bêta, « Rafraîchir » avec icône ailleurs. |
| Champs de filtre | Users, Docs, Logs, Support | Chaque page a ses propres styles en ligne (`selectStyle`, `<input style=…>`). Ils sont presque identiques mais pas tout à fait. |
| Listes | Users (lignes), Docs (`<table>` min 860 px), Logs et Support (lignes dépliables) | Quatre façons de dessiner une liste. Users affiche le plan deux fois : un badge, puis une liste déroulante. |
| États vides | toutes | Une phrase grise qui flotte au milieu d'une page vide (« Aucun document. »). |
| Chiffres clés | aucune page sauf Bêta | Il faut lire la liste pour savoir combien de demandes sont ouvertes ou combien d'erreurs sont à traiter. |
| Journal | `AdminLogsPage` | Tout est en police à chasse fixe, y compris les messages. Les lignes longues sont tronquées. |
| Campagne bêta | `AdminBetaPage` + `beta.css` | Les quatre sections sont empilées à pleine largeur. Le formulaire compte 4 colonnes et les limites en comptent 5, donc les champs ne tombent pas les uns sous les autres. Le filtre « Participants » s'étire sur toute la largeur. Les titres sont plus légers que ceux des autres pages. |
| Page publique `/beta` | `beta.css` | `.beta-public .beta-program-quotas { max-width: 440px }` et `.beta-application-form { max-width: 700px }` placés dans une carte de 1240 px : le contenu tient sur environ 590 px à gauche et le reste est vide. **C'est le « serré à gauche ».** |
| Mobile 375 px | Bêta | Le badge de statut passe seul sous la description. Les champs vont sur 2 colonnes avec des libellés de hauteurs inégales, donc les cases sont décalées. |

Réutilisable : jetons `index.css` (`--frame-max`, `--frame-pad`, `--navy`, `--blue`, `--gray-*`), boutons `.tb-btn` / `.tb-btn.ghost`, `.beta-status`, `.beta-card`, `.beta-metrics`.

## 3. Normes retenues (le « gabarit admin »)

1. **En-tête** : bouton Retour, titre de 20 px en gras, compteur, puis les actions à droite. Le bouton d'actualisation est toujours « Actualiser » avec son icône.
2. **Bandeau de chiffres** (facultatif) : 3 à 4 tuiles, de même forme que `.beta-metrics`, placées au-dessus de la liste. Par exemple « Ouvertes / En cours / Traitées » pour l'assistance.
3. **Barre d'outils** : recherche à gauche, qui prend la place restante, puis les filtres à droite, tous à la même hauteur (40 px). Sur mobile, elle passe sur 2 lignes : recherche, puis filtres.
4. **Liste** : une seule carte blanche (bord `--gray-200`, rayon 12 px), avec une ligne par élément. Sur grand écran, chaque ligne a ses colonnes : identité, détails, statut, actions alignées à droite. Sur mobile, les éléments se mettent l'un sous l'autre, le statut restant à côté du titre.
5. **État vide** : il est placé dans la carte de liste, avec une icône, une phrase et, si des filtres sont actifs, un lien « Effacer les filtres ».
6. **Formulaires** : une grille de 12 colonnes. Sur grand écran, les champs courts (nombres) font 3 colonnes et les champs longs (nom, e-mail) en font 6. Sur mobile, chaque champ prend toute la largeur. Les libellés sont au-dessus des champs, avec la même hauteur partout.
7. **Typographie** : texte courant dans la police du site. La chasse fixe n'est gardée que pour les piles d'erreur et les empreintes.

## 4. Options

| Option | Effet visible | Pour | Contre |
|---|---|---|---|
| **A. Retouches CSS page par page** | Les écarts les plus voyants disparaissent, mais chaque page garde sa façon de faire. | Rapide, peu de risques. | Pas de norme : le prochain écran dérivera de nouveau. |
| **B. Gabarit partagé (recommandée)** | Les cinq pages se ressemblent : même en-tête, même barre, même liste, même état vide. La campagne passe sur 2 colonnes. | La norme est écrite une fois (`admin.css` + 3 petits composants) et les pages ne font plus que la remplir. Styles en ligne supprimés. | Touche les 5 pages, soit environ 600 lignes déplacées : il faut tout revérifier en capture. |
| **C. Bibliothèque de composants (shadcn, tableau de données)** | Aspect « tableau de bord » générique. | Tri et pagination fournis. | Nouvelle dépendance, rupture avec l'identité Précis, surdimensionné pour 5 pages. |

## 5. Choix recommandé : B

Composants (dans `components/admin/`) :
- `AdminShell` : il garde son rôle. Ses styles en ligne passent en classes, et il reçoit un `stats` facultatif (les tuiles).
- `AdminToolbar` : la recherche et les filtres (des enfants).
- `AdminList` + `AdminEmpty` : la carte de liste et son état vide.
- `admin.css` : toutes les classes `admin-*`, construites sur les jetons existants.

Disposition de la **campagne bêta** à 1440 px :
- Colonne gauche (environ 60 %) : « Campagne » (chiffres, puis formulaire en grille de 12), puis « Inviter ».
- Colonne droite (environ 40 %) : « Candidatures » (en attente d'abord).
- En dessous, sur toute la largeur : « Participants », en liste à colonnes (e-mail et format | jauges | statut | actions).
- Sous 1024 px, la page passe sur une seule colonne, dans le même ordre.

Page publique **`/beta`** : la carte de présentation passe sur 2 colonnes (texte et appel à l'action à gauche, quotas par format à droite), et le formulaire de candidature occupe la largeur de la carte, avec un champ de texte large. Les `max-width` 440/700 px sont supprimés.

Utilisateurs : le badge de plan qui doublait la liste déroulante est retiré. La liste déroulante reste et prend la couleur du plan.

## 6. Impacts

- Données, API, migrations : aucun.
- Sécurité : aucune. Les routes restent protégées par `AdminRoute`.
- i18n : clés harmonisées (`admin.refresh`, `admin.clear_filters`, en-têtes de tuiles), ajoutées en fr et en en.
- Performance : neutre. Le CSS remplace des styles en ligne.
- Risque : une régression visuelle sur une page peu vue (journal déplié, fenêtre de limites). Pour la parer : captures avant/après à 1440 et 375 px de chaque page et de chaque état (liste, vide, déplié, fenêtre).

## 7. Points décidés sans attendre (modifiables)

- Pas de tri ni de pagination ajoutés : ce serait une autre tâche.
- Tuiles de chiffres seulement quand les données sont déjà chargées par la page (assistance, journal, bêta). Aucun nouvel appel API.
- Le tableau Documents reste un tableau sur grand écran. Sur mobile, il devient une liste de cartes, sans défilement horizontal.

## 8. Parcours et interactions (ajout du 25/10/2026)

> « On ne doit pas être obligé de sortir de la liste des utilisateurs pour accéder aux documents d'un utilisateur. »

Constat : chaque page admin est une île. Pour voir les documents de `alice@…`, il faut ouvrir le menu, aller dans Documents, retaper l'e-mail ; au retour, la recherche Utilisateurs est perdue. Rien ne relie un ticket d'assistance ou une erreur du journal au compte concerné.

Choix (sans nouvelle API, sauf une retouche du journal) :
1. **Onglets admin sous l'en-tête** : Utilisateurs · Documents · Assistance · Journal · Bêta, l'onglet courant souligné. On passe d'une page à l'autre en un clic, sans rouvrir le menu.
2. **Fiche utilisateur en panneau latéral** : un clic sur un utilisateur ouvre à droite (plein écran sur mobile) sa fiche : identité, plan (modifiable), ses 5 derniers documents (téléchargement original / traduit), ses tickets, ses erreurs récentes. Chaque bloc a « Tout voir → » qui ouvre la page complète déjà filtrée. La liste reste visible derrière ; Échap ou ✕ ferme.
3. **Tout e-mail est cliquable** (Documents, Assistance, Journal, Bêta) et ouvre la même fiche sur place.
4. **Filtres dans l'adresse** (`?q=…&status=…&user=…`) : le bouton Retour du navigateur restaure la recherche et la fiche ouverte ; un lien copié montre la même vue.
5. Journal : la recherche couvre aussi l'e-mail de l'utilisateur (une condition ajoutée côté serveur, avec son test).

Non retenu : tableau de bord d'accueil admin et pagination (autre tâche) ; statut bêta dans la fiche (il faudrait un nouvel appel API, il reste visible via « Bêta »).
