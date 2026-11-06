# Étude : fiche utilisateur intégrée à la page Comptes

Date : 25/10/2026. Branche `feat/mise-a-jour-carte-invitations-visionneuse`.

## Besoin
Sur `/admin/users`, voir la liste des comptes à gauche et la fiche du compte choisi à droite, sur une seule page, sans panneau qui glisse par-dessus la liste. Modèle : page Utilisateurs de Reporting RH (`reporting-rh-app/frontend/src/pages/admin/Utilisateurs.tsx`).

## Existant
- `components/admin/UserPanel.tsx` : fiche en panneau latéral modal (voile, piège de focus, Échap), ouvert par `?user=<e-mail>` sur toutes les pages admin et monté par `AdminShell`.
- `UserLink` : e-mail cliquable utilisé dans Documents, Assistance, Journal et Bêta.
- `AdminUsersPage.tsx` : liste en lignes larges (e-mail, nom, date, bouton « Voir la fiche », sélecteur de plan).
- Reporting RH : grille `5fr / 7fr`, ligne choisie surlignée par une barre à gauche, invitation en pointillés quand rien n'est choisi, une seule colonne sous 900 px.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Deux colonnes sur `/admin/users` ; les e-mails des autres onglets mènent à cette page avec la fiche ouverte ; panneau latéral supprimé | Un seul endroit pour la fiche, plus de recouvrement, lien copié toujours valable | Depuis Documents, on change d'onglet (Retour du navigateur ramène à la vue filtrée) |
| B. Deux colonnes sur `/admin/users`, panneau latéral gardé ailleurs | Pas de changement d'onglet | Deux présentations de la même fiche à maintenir ; ne répond pas à « ne plus utiliser le panneau » |

## Choix : A
- Liste à gauche (≈ 40 %) : e-mail, nom · date d'inscription, plan en pastille ; la ligne est un bouton, la ligne choisie est surlignée.
- Fiche à droite (≈ 60 %), collée en haut de l'écran pendant le défilement de la liste : identité + plan modifiable, puis Documents / Assistance / Erreurs côte à côte quand la largeur le permet.
- Changement de plan déplacé dans la fiche (une seule commande par compte, comme Reporting RH).
- Rien de choisi : invitation « Choisissez un compte dans la liste ».
- Sous 900 px : une colonne, la fiche passe au-dessus de la liste quand un compte est choisi.
- `?user=<e-mail>` reste l'adresse de la fiche (Retour, lien copié, rechargement).

## Impacts
Front seul (aucune API, aucune donnée). i18n : une clé `admin_users.pick`. Accessibilité : la fiche n'est plus une fenêtre modale (plus de piège de focus) ; la ligne choisie porte `aria-current`.

## Risques
Plus de 200 comptes : la liste reste limitée comme aujourd'hui par l'API ; la recherche reste le moyen de trouver un compte.

## Points à trancher
Aucun bloquant.
