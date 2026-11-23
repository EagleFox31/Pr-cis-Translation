# Étude — Programmes Bêta : liste à gauche, détail à droite

## Besoin
Gérer la Bêta comme la page Comptes. Une liste des programmes à gauche. À droite, le détail du programme choisi : réglages, état, participants, candidatures. Les actions disponibles sont Ouvrir, Fermer et Modifier. Le bouton « Nouveau programme » ouvre le formulaire de création dans la zone de droite, pour l'ajuster avant de l'ajouter à la liste.

## Existant
- **Un seul programme possible.** L'identifiant `"pilot"` est écrit en dur à 13 endroits :
  - `api/beta.py` (3)
  - `models/beta.py` (1)
  - `services/beta.py` (5)
  - `services/beta_abuse.py` (2)
  - `services/beta_applications.py` (2)
- Les testeurs, les candidatures et les consommations sont **déjà rattachés à un programme** (`campaign_id`). Les données sont donc prêtes pour plusieurs programmes. Seul le code suppose qu'il n'y en a qu'un.
- Chaque programme a trois états : `draft` (brouillon), `open` (ouvert) et `closed` (fermé). Le recrutement dure deux mois et se fait en deux vagues. L'accès d'un testeur est individuel et compte en jours à partir de son activation.
- La page publique `/beta` et l'activation d'un testeur lisent « le » programme.
- Front : `AdminBetaPage.tsx` affiche un seul formulaire, les candidatures et les participants. La page Comptes (`UserCard`) fournit déjà le modèle liste + fiche.

## Pratique du marché
Ces outils présentent tous une liste d'éléments, un détail en vis-à-vis, et un cycle brouillon → actif → terminé :
- TestFlight (groupes de testeurs) ;
- Google Play (pistes de test) ;
- LaunchDarkly et Intercom (campagnes).

La création se fait toujours dans un formulaire qui reprend les réglages du dernier élément créé. Un seul programme public est ouvert aux candidatures à la fois. Les programmes terminés restent consultables avec leurs participants.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Plusieurs programmes, **un seul ouvert à la fois** ; l'historique reste consultable | Page `/beta` sans ambiguïté ; le changement côté serveur reste limité (« le programme » devient « le programme ouvert ») ; conforme au marché | Migration et tests à adapter (12 fichiers de tests citent `pilot`) |
| B. Plusieurs programmes ouverts en même temps | Souple | `/beta` doit faire choisir un programme ; les plafonds et l'anti-abus se compliquent ; besoin non exprimé |
| C. Front seul : liste d'un seul élément | Rapide | Ne répond pas au besoin (impossible de créer un 2ᵉ programme) |

## Choix recommandé : A
- **Serveur**
  - Un identifiant généré par programme. La ligne `pilot` existante est conservée telle quelle, sans migration de données.
  - Routes :
    - `GET /api/admin/beta/campaigns` donne la liste ;
    - `POST /api/admin/beta/campaigns` crée un programme ;
    - `PATCH /api/admin/beta/campaigns/{id}` modifie un programme ou change son état ;
    - les candidatures, invitations et participants sont filtrés par `campaign_id`.
  - Ouvrir un programme est refusé si un autre est déjà ouvert (erreur `campaign_already_open`).
  - `/beta` et l'activation lisent le programme ouvert. L'accès d'un testeur vient de son inscription la plus récente.
- **Front**
  - Colonne de gauche : les programmes, avec nom, pastille d'état, places et dates.
  - Colonne de droite, selon l'élément choisi :
    - un programme : la fiche, avec ses réglages, les boutons Ouvrir, Fermer et Modifier, et les onglets Candidatures et Participants ;
    - « Nouveau programme » : le formulaire, prérempli avec les réglages du dernier programme, avec les boutons Créer et Annuler.
  - Le programme choisi est gardé dans l'URL (`?c=<id>`).
  - La page passe sur une colonne sous 900 px, comme Comptes.

## Impacts
- **Données :** une migration légère. L'identifiant devient généré et un index garantit un seul programme ouvert. Les tables existantes ne changent pas.
- **Sécurité :** les routes admin restent protégées. Le contrôle « un seul ouvert » est fait sous verrou.
- **i18n :** nouvelles clés `beta.campaigns.*` en fr et en en.
- **Tests :** les suites bêta sont à adapter, avec de nouveaux tests sur la liste, la création et le refus d'une double ouverture.

## Risques
- Un testeur inscrit à un ancien programme fermé garde son accès jusqu'à la fin de sa durée. C'est le comportement actuel, il est conservé.
- 12 fichiers de tests sont à relancer, sur la base de test uniquement.
- **Deux accès en même temps, cas rare.** La vérification « accès déjà en cours ailleurs » ne bloque pas les deux programmes à la fois. Exemple : à la même seconde, l'admin rétablit l'accès révoqué d'une boîte dans le programme 1 pendant que cette boîte active son invitation au programme 2 ; les deux peuvent réussir. Le cas demande une action de l'admin au même instant : accepté, l'admin peut révoquer l'un des deux.
- **Retour en arrière (migration 0017).** Le `downgrade` retire seulement l'index « un seul ouvert ». Exemple : si l'on revient à l'ancien code après avoir créé « Programme 2 », l'ancien code ne lit que le programme `pilot` ; « Programme 2 » et ses testeurs restent en base mais n'apparaissent plus. Avant un retour en arrière, fermer les programmes autres que `pilot`, ou ne pas revenir en arrière une fois un deuxième programme ouvert.

## Décisions (29/10)
1. Un seul programme ouvert à la fois.
2. Un ancien testeur peut candidater au programme suivant une fois son accès précédent terminé.
3. Le formulaire de création est prérempli avec les réglages du dernier programme.
