# Étude : historique des forfaits et fiche compte en pleine hauteur

Date : 25/10/2026. Branche `feat/mise-a-jour-carte-invitations-visionneuse`.

## Besoin
Sur la fiche d'un compte (`/admin/users?user=<e-mail>`) :
1. Montrer l'historique des forfaits : combien d'abonnements et de renouvellements, gratuits compris, avec leurs dates.
2. Faire tenir la page sur la hauteur de l'écran : la liste et la fiche vont jusqu'en bas même s'il y a peu de contenu.
3. Ne plus lister les documents, demandes d'assistance et erreurs dans la fiche. Afficher seulement leur nombre ; un clic sur la tuile ouvre la page dédiée, filtrée sur ce compte (« Voir les documents → » à la place de « Tout voir → »).

## Existant
- `User.plan`, `plan_started_at`, `plan_expires_at` : l'état **actuel** seulement. Rien ne garde les plans précédents.
- Le plan change à trois endroits :
  - `api/payments.py::_apply_plan` (paiement réussi : nouvel abonnement ou renouvellement) ;
  - `api/admin_users.py::change_plan` (plan attribué par l'administration, sans échéance) ;
  - `core/security.py::_expire_plan_if_due` et `expire_due_plans` (échéance passée : retour au Gratuit).
- `payments` garde les paiements de forfait (`plan`, `months`, `status`, `refund_due`). Cela suffit à retrouver les achats passés, mais pas les attributions par l'administration ni les retours au Gratuit.
- Fiche : `components/admin/UserPanel.tsx` (tuiles Documents / Assistance / Erreurs avec listes) ; mise en page `.admin-duo` dans `admin.css`.

## Options pour l'historique
| Option | Pour | Contre |
|---|---|---|
| A. Le déduire des paiements réussis + date d'inscription | Aucune table, aucune migration | Ne voit ni les plans attribués par l'administration ni les retours au Gratuit : un testeur passé Pro à la main n'aurait aucune ligne |
| B. Nouvelle table `plan_events` écrite aux trois endroits ci-dessus, remplie au départ depuis les paiements | Tout est tracé (achat, renouvellement, attribution, échéance), dates exactes | Une migration ; trois points d'écriture à tenir |

## Choix : B
- Table `plan_events` : compte, type (`subscription`, `renewal`, `admin`, `expiry`), plan, nombre de mois, échéance, paiement lié, date.
- L'inscription n'est pas stockée : la fiche l'affiche comme première ligne « Gratuit » à la date de création du compte.
- Une échéance est datée du jour où le plan a pris fin, pas du jour où le serveur s'en aperçoit.
- Reprise des données : la migration crée une ligne par paiement de forfait réussi et appliqué. Un paiement du même plan que le précédent compte comme renouvellement. Les attributions et échéances passées ne peuvent pas être reconstituées ; elles sont tracées à partir de maintenant.
- API : `GET /api/admin/users/{id}/plan-history` renvoie les lignes (de la plus récente à la plus ancienne) et les totaux.
- Fiche : un bloc « Forfaits » sous l'identité, avec « 3 abonnements · 2 renouvellements » et la liste datée.

Exemple : un compte inscrit le 2 mars, passé Starter le 10 mars, renouvelé le 10 avril, laissé expirer le 10 mai, mis Pro par l'administration le 15 mai. La fiche affiche 5 lignes : Gratuit (inscription), Starter 1 mois, Starter renouvelé, retour au Gratuit, Pro attribué.

## Pleine hauteur et tuiles
- À partir de 900 px de large, les deux colonnes occupent la hauteur restante de l'écran. Chaque colonne défile à l'intérieur ; la page ne défile pas.
- En dessous de 900 px, la hauteur reste naturelle (une colonne).
- Chaque tuile devient un lien entier : titre, nombre en grand, « Voir les documents → ». Les boutons de téléchargement de la fiche disparaissent ; on les retrouve sur la page Documents.

## Impacts
- Données : migration `0016_plan_events`, réversible.
- Sécurité : la route est réservée aux admins (`require_admin`).
- i18n : nouvelles clés `admin_panel.*` en français et en anglais.
- Performance : une requête indexée par compte.

## Risques
Un nouvel endroit qui changerait le plan sans écrire de ligne laisserait un trou. La fonction commune `record_plan_event` sert aux trois endroits pour limiter ce risque.

## Points à trancher
Aucun bloquant.
