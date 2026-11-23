# Étude — fiche d'un programme Bêta plus lisible

## Besoin
Sur `/admin/beta`, la fiche de droite empile cinq blocs : chiffres, liste des réglages, boutons, formulaire d'invitation, puis deux onglets (Candidatures / Participants). Résultat : trop d'éléments à la fois.
Demande : deux actions dans l'en-tête de la fiche, une seule liste par défaut (candidatures et participants ensemble, avec valider / refuser / retirer), les réglages seulement en mode « Modifier ».

## Existant
- `frontend/src/pages/AdminBetaPage.tsx` : fiche `card`, onglets `tab`, formulaire `SettingsForm`, fenêtre `dialog` des limites.
- Une candidature validée crée une inscription « invitée » (`services/beta_applications.py:88-91`) : la même personne apparaîtrait deux fois si l'on montrait aussi les candidatures validées.
- Aucune route serveur à changer.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. En-tête « Inviter » + « Modifier » ; liste unique ; réglages, ouverture/fermeture en mode Modifier ; invitation dans une fenêtre | Fiche réduite à 3 chiffres + 1 liste ; actions toujours visibles | Ouvrir/fermer demande un clic de plus |
| B. Garder les onglets, replier réglages et invitation | Moins de code changé | Deux listes séparées, ce que la demande écarte |

## Choix : A
- Liste unique : candidatures en attente ou refusées + toutes les inscriptions (les candidatures validées sont déjà dans les inscriptions). En attente d'abord.
- Un seul filtre : Tous / groupe Candidatures (en attente, refusées) / groupe Participants (invités, actifs, expirés, retirés) + case « signalés seulement ».
- Actions par ligne : candidature → Valider, Refuser ; participant → Limites, Retirer / Rétablir (retirer une invitation = l'annuler).
- Mode Modifier : formulaire des réglages + bouton Ouvrir / Fermer les inscriptions ; « Annuler » revient à la liste.

## Impacts
Front seul, aucune migration ni nouvelle route. i18n : libellé « Modifier le programme ». Risque faible : mêmes appels API qu'avant.
