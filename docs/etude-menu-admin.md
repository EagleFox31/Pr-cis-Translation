# Étude — « Administration » dans le menu principal

## Besoin
Le bouton « Administration ▾ » (menu déroulant, à droite de FR/EN) doit devenir une
entrée du menu principal, sans déroulant. La page d'administration doit suivre la
même logique.

## Existant
- `components/navbar/AdminMenu.tsx` : déroulant partagé par `Navbar` (accueil) et
  `AdminShell` (pages `/admin/*`), 5 entrées.
- `Navbar.tsx` : menu centré `.nav-links` (Accueil, Fonctionnalités…), repris dans
  `MobileMenu` sous 768 px (hamburger).
- `AdminShell.tsx` : barre identique sans menu central + bouton « Retour » + rangée
  d'onglets (Comptes, Documents, Assistance, Journal, Bêta) sous le titre.
  Résultat : trois façons d'aller au même endroit (déroulant, onglets, Retour/logo).

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Lien « Administration » dans le menu de l'accueil ; sur `/admin/*`, les onglets montent dans le menu central de la barre | Une seule navigation par écran ; la barre admin a la même forme que celle de l'accueil ; plus de doublon déroulant/onglets | La rangée d'onglets disparaît du corps de page |
| B. Lien « Administration » dans le menu, onglets gardés sous le titre | Changement minimal | Barre admin vide au centre ; onglets loin du menu |

## Choix : A
- Accueil (admin seulement) : 6ᵉ lien « Administration » → `/admin/users`, aussi dans le menu mobile.
- Pages admin : menu central = Comptes · Documents · Assistance · Journal · Bêta (lien actif souligné comme sur l'accueil) ; menu mobile (hamburger) sous 768 px.
- En-tête de page : titre + compteur + actions ; « Retour » retiré (le logo et l'avatar ramènent à l'accueil), gardé sur `/beta` (page publique sans menu).
- `AdminMenu.tsx` et son CSS supprimés.

## Impacts / risques
Front seul, pas de données ni d'i18n nouvelle (clés `admin.menu`, `admin.tabs.*` existantes).
Risque constaté : à 900 px le menu central chevauchait déjà FR/EN (même sans le 6ᵉ lien) →
hamburger dès 1100 px, liens sur une ligne, logo réduit à « P » sous 420 px. Vérifié Playwright 1440/1000/375.

## Complément — sortie, icônes, erreurs longues
- **Sortir de l'admin** : bouton « ← Retour à l'accueil » dans la barre, avant FR/EN (flèche seule sous 600 px) ; le logo reste un second chemin.
- **Documents** : icône du type de fichier devant chaque nom (mêmes icônes et couleurs que la bibliothèque : PDF rouge, Word bleu, PowerPoint orange, Excel vert).
- **Journal** : titre d'erreur limité à 70 caractères de large (coupé par « … », texte complet au dépli) ; étiquettes niveau / nombre / statut de largeur fixe pour rester alignées d'une ligne à l'autre.
Vérifié Playwright 1440/375, sans défilement horizontal.
