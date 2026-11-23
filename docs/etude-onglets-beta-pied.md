# Étude : onglets admin sur `/beta`, offre Bêta des tarifs, pied de la barre latérale

## Besoin
1. Un utilisateur non admin qui ouvre `/beta` (« Découvrir » depuis les tarifs) voit les onglets
   d'administration (Comptes, Documents, Assistance, Journal, Bêta).
2. La carte « Bêta » des tarifs s'affiche même quand le programme est fermé, plein ou terminé.
3. Le pied de la barre latérale (Inviter des proches, Aide & support, Déconnexion) : trois gros
   boutons encadrés, trop hauts (~170 px pris à la liste).

## Existant
- `/beta` réutilise `AdminShell` (même gabarit que l'admin), qui affichait toujours ses onglets.
  Les routes `/admin/*` sont protégées par `AdminRoute` et le serveur refuse tout appel admin :
  la fuite est **visuelle** (noms des pages internes), pas un accès aux données.
- `useBetaProgram` expose `applications_open` (déjà utilisé par `/beta` pour le formulaire).

## Choix
| Point | Retenu | Pourquoi |
|---|---|---|
| 1 | `AdminShell` prend `tabs` (vrai par défaut) ; onglets montrés seulement si `tabs` **et** `plan === 'admin'` ; `/beta` passe `tabs={false}` | Double garde : une page publique future ne peut pas les réafficher à un non-admin par oubli |
| 2 | Carte Bêta rendue seulement si `applications_open` ; grille à 4 colonnes sinon | Ne pas promettre 30 jours que personne ne peut obtenir |
| 3 | Lignes de menu (icône + libellé, 38 px), déconnexion en rouge sous un trait | Même lisibilité, 139 px au lieu de ~170 ; libellés trop longs à 375 px pour une seule rangée |

## Point 3 revu (25/10) : la version « lignes de menu » est refusée
**Ce qui ne va pas** dans la version livrée :
- tout est collé à gauche, la moitié droite du panneau reste vide, le bloc paraît bancal ;
- la Déconnexion a le même poids que les deux autres, puis un fond rouge plein au survol :
  la sortie attire plus l'œil que l'aide ;
- le trait isole la Déconnexion, mais rien ne relie les trois actions au compte du haut.

**Contraintes** : panneau large de 440 px sur ordinateur, ~360 px sur mobile ; trois actions
qui doivent rester lisibles sans infobulle ; la sortie doit se trouver vite, sans dominer.

| Option | Ce qu'on voit | Pour | Contre |
|---|---|---|---|
| A. Deux boutons côte à côte + sortie discrète | « Inviter des proches » et « Aide & support », deux boutons de même largeur sur une rangée ; dessous, « Déconnexion » en petit lien centré | Symétrique, équilibré, ~96 px de haut | La sortie est plus petite (reste visible) |
| B. Trois tuiles égales | Une rangée de trois cases : icône au-dessus, libellé court dessous (Inviter · Aide · Déconnexion) | Le plus compact (~64 px), très équilibré | Libellés raccourcis ; ressemble à une barre d'onglets |
| C. Rangée « compte » | Une ligne : « Inviter des proches » à gauche, icônes Aide et Déconnexion à droite | Une seule ligne (~48 px) | Deux actions réduites à une icône : moins compréhensibles |

**Recommandé et retenu (choix de l’utilisateur) : A.** Livré : 94 px de haut sur ordinateur et mobile (au lieu de 139), libellés sur une ligne à 375 px.

## Impacts
Front seulement (`AdminShell`, `BetaPage`, `PricingCards`, `BetaOffer`, `DocumentLibrary`, `index.css`).
Pas de donnée, pas d'i18n nouvelle (clés existantes).

## Vérification
Playwright compte non admin, 1440 et 375 px : 0 onglet admin sur `/beta`, 0 carte Bêta
(programme fermé), pied 94 px (option A), aucune erreur JS ; tsc, lint, build OK.

## Point 4 (25/10) : où placer la Déconnexion ?
**Constat** (capture utilisateur) : sous « Inviter / Aide », en petit lien gris, la Déconnexion
paraît rajoutée après coup. Elle se trouve en bas d'un panneau dont le haut parle du **compte**
(nom, e-mail, forfait) : l'action qui concerne le compte est loin de lui.

**Ce que font les applications connues** : la sortie vit avec l'identité (Google, GitHub, Notion :
on clique sur son nom ou son avatar, « Se déconnecter » est là). On la cherche près de son nom.

| Option | Ce qu'on voit | Pour | Contre |
|---|---|---|---|
| A. Dans la carte du compte, à droite du nom | Ligne du haut : avatar · nom/e-mail · badge PRO, et un petit bouton « ⇥ Déconnexion » sous le badge | Cohérent (compte = identité + sortie), visible dès l'ouverture, bas du panneau réservé à Inviter / Aide | La carte du compte prend une ligne de plus sur mobile si le nom est long |
| B. Bouton icône seul à côté du badge | « ⇥ » carré, libellé en infobulle | Très compact | Une icône seule se comprend mal ; pas d'infobulle au doigt sur mobile |
| C. Rester en bas, sur la même rangée | Trois boutons égaux : Inviter · Aide · Déconnexion | Tout regroupé | Libellés serrés sur mobile ; la sortie reste loin du compte |

**Recommandé et retenu (choix de l’utilisateur) : A.** Livré : bouton « Déconnexion » sous le badge du forfait, rouge au survol ; pied réduit à une rangée (57 px au lieu de 94), ordinateur et mobile, aucune erreur JS.

## Point 5 (25/10) : texte brut affiché avant l'écran d'accueil
**Cause** : `index.html` contient dans `#root` une présentation lisible sans JavaScript (pour les
moteurs de recherche, commit cc6a668). Elle s'affiche sans style tant que React n'a pas démarré.

| Option | Effet | Retenu |
|---|---|---|
| Supprimer le texte | Plus de flash, mais le référencement perd la page lisible sans JS | Non |
| Le cacher si JavaScript est actif (classe `js` posée en tête de page) | Visiteur : page blanche puis écran d'accueil ; robot sans JS : texte intact | **Oui** |
