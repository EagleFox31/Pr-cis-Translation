# Étude — navigation du site (G.12, piste B)

Maquettes : `docs/maquettes/navigation-tarifs/` (`navigation.html` = pistes comparées, `parcours.html` = parcours validé le 12/11/2026).

## 1. Besoin
- Avant : la barre du haut changeait selon la page (accueil = `Navbar.tsx`, autres pages = `AppBar.tsx` avec « Retour à l'accueil »). Hors de l'accueil, on perdait Tarifs, À propos, etc.
- Demande : même menu partout, libellés concrets, FR/EN, **aucune superposition à aucune largeur**.

## 2. Existant
| Élément | Avant | Après |
|---|---|---|
| Accueil | `navbar/Navbar.tsx` + `navbar-extension.css` | supprimés, remplacés par `AppBar` |
| Autres pages | `AppBar` (props `links`/`exit`) | `AppBar` (props `section`, `sub`, `onAccount`) |
| Repli | seuil fixe 1100 px | `navbar/useRepli.ts` : repli mesuré, 4 crans |
| Décalage du contenu | hauteurs codées (72 px…) | variable `--nav-total` publiée par `AppBar` |

## 3. Options
| Piste | Pour | Contre |
|---|---|---|
| Actuel | rien à faire | menu instable, sections perdues |
| A : menu unique seul | simple | rubriques à plusieurs pages (légal, admin, intégrations) sans repère |
| **B : menu unique + 2ᵉ rangée** ★ | stable, repère local clair | une rangée de plus (44 px) sur ces pages |
| C / D (latéral, méga-menu) | riches | trop lourds pour la taille du site |

Choix : **B** (validé par l'utilisateur).

## 4. Règles retenues
- Rangée principale : logo · sections de l'accueil (Avantages, Comment ça marche, Tarifs, Qui sommes-nous) · trait fin · liens vers une autre page, fléchés ↗ (Extension et API, Administration pour l'admin) · FR/EN · compte. Même regroupement dans le menu ☰ (pages en bas, sous un séparateur).
- Nouveautés retiré du menu (12/11/2026) : accessible depuis le panneau du compte et le bloc Qui sommes-nous.
- Changement de page : fondu de 0,25 s (`avecFondu` dans `AppBar.tsx`, View Transitions ; la barre reste fixe). Immédiat si le navigateur ne le gère pas ou si « réduire les animations » est actif. `BrowserRouter` ignore l'option `viewTransition` de React Router, d'où l'appel direct à `document.startViewTransition`.
- Depuis une autre page, un clic sur une section ramène à l'accueil et défile jusqu'à elle (`navigate('/home', {state:{section}})`, effet dans `Home.tsx`).
- 2ᵉ rangée seulement pour les rubriques à plusieurs pages : Intégrations (Extension, API), Informations légales (4 pages, libellés courts), Administration (onglets).
- Rien ne rétrécit ni ne passe à la ligne : quand la place manque, `useRepli` replie d'un cran — 1 espacements resserrés, 2 menu ☰, 3 logo sans texte, 4 « Se connecter » dans le menu. Mesure avant affichage (`useLayoutEffect` + `flushSync`), nouvelle mesure après chargement des polices.
- 2ᵉ rangée trop longue : défilement horizontal, jamais de retour à la ligne.
- Menu ☰ : sous la barre entière (`top: var(--nav-total)`), défilable.

## 5. Impacts
- i18n : nouvelles clés FR/EN (`npm run lint` : dictionnaires concordants).
- CSS : `--nav-total` remplace les hauteurs codées (index, legal, extension-page, nouveautes, admin, modal).
- Correctifs de contenu trouvés par le contrôle : grilles `.pricing-grid` et `.about-layout` en `minmax(0, 1fr)`, onglets `.nv-toc` défilables sous 520 px, prix et liens sociaux qui passent à la ligne (débordements à 300–320 px).
- Ni données, ni sécurité, ni déploiement touchés.

## 6. Vérification
Script Playwright (7 pages × 3 rôles × 2 langues) : chevauchement deux à deux des éléments de la barre, sortie d'écran, hauteur, liens sur une ligne, défilement horizontal de la page, `--nav-total` exact, contenu sous la barre, repli défait au retour en grand écran, présence de la 2ᵉ rangée.
- 9 largeurs types : 342 situations, 0 défaut.
- Balayage 300 → 1560 px par pas de 20 : 2 432 situations, 0 défaut.

## 7. Risques
- Une nouvelle entrée de menu ou un libellé plus long : géré par le repli mesuré, pas de seuil à retoucher.
