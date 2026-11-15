# Étude — navigation des pages d'intégration (`/extension`, `/integrations/api`)

## Besoin
Les pages d'intégration doivent naviguer comme les pages d'administration
(`docs/etude-menu-admin.md`) : même barre, mêmes sorties, même place pour le titre.

## Existant
| | Pages admin (`AdminShell.tsx`) | Pages intégration (`IntegrationsNav.tsx`) |
|---|---|---|
| Barre | logo, menu central (onglets), FR/EN, avatar, hamburger | logo, menu central (Extension · API), FR/EN, hamburger — **copie** de la même barre |
| Sortie | « ← Retour à l'accueil » **dans la barre**, avant FR/EN (flèche seule < 600 px) | « ← Retour » **sous la barre**, à gauche du titre |
| Compte | avatar (initiale) → `/home` | rien, même connecté |
| Titre | seul dans l'en-tête de page | précédé du bouton Retour |

Exemple concret : un utilisateur connecté qui passe de `/admin/users` à `/extension`
voit le bouton de sortie changer de place et son avatar disparaître.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Extraire la barre d'`AdminShell` en composant partagé `AppBar`, utilisé par l'admin et les intégrations | Une seule barre, plus de copie qui dérive ; même sortie, même avatar | Touche `AdminShell` (refactor limité au JSX de la barre) |
| B. Recopier dans `IntegrationsNav` le bouton de sortie et l'avatar | Changement minimal | Deux barres à maintenir, l'écart reviendra |

## Choix : A
- `components/navbar/AppBar.tsx` : logo → accueil, liens centraux (badge facultatif, ex. « Bientôt » sur API), bouton « ← Retour à l'accueil », FR/EN, avatar si connecté, hamburger + menu mobile si liens.
- Accueil visé : `/home` si connecté, `/` sinon (pages publiques). Admin : `/home` comme aujourd'hui.
- `ExtensionPage` / `ApiPage` : bouton Retour retiré de l'en-tête de page (il est dans la barre) ; la colonne de sections (Installation, Tarif, Permissions, FAQ) est propre au contenu, inchangée.
- Libellés : clés existantes `admin.back_home`, `admin.my_account` (FR/EN).

## Impacts / risques
Front seul ; pas de données, pas de nouvelle clé i18n. Risque : régression de la barre admin
→ vérification Playwright admin + intégrations à 1440 et 375 px.
