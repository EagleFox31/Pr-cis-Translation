# Étude : défilement de la visionneuse (zoom et molette)

## Besoin
1. Quand on zoome, le défilement horizontal doit permettre de voir les deux documents en entier.
2. Un mouvement de molette ne fait qu'une seule action :
   - soit il fait défiler la page ;
   - soit il change de page.

   Arrivé en bas d'une page, on s'arrête, puis on relance la molette pour passer à la page suivante.

## Existant
- `#scroll` (`index.css`, `.scroll`) est un cadre `display:flex; overflow:auto` centré par `safe center`.
- Son enfant est le conteneur `inline-flex` de `PdfViewer.tsx`, qui porte `minWidth: 100%` et `justifyContent: center`.
- La molette est gérée dans `Home.tsx` (effet clavier/molette) :
  - elle défile jusqu'au bord ;
  - dès que le bord est atteint, l'élan qui continue (molette ou inertie du pavé tactile) change de page. C'est cela que l'utilisateur ressent comme « trop agressif ».

## Cause du défaut horizontal
`minWidth: 100%` remplace la largeur minimale naturelle d'un élément flex. Le conteneur rétrécit donc à la largeur du cadre, alors que les deux pages zoomées sont plus larges. Le centrage les fait déborder **des deux côtés**, et la partie gauche reste hors d'atteinte du défilement.

Mesure (Edge sans interface, cadre de 800 px, deux pages de 700 px) :

| Situation | Bord gauche de la page 1 |
|---|---|
| Avant | −286 px (invisible) |
| Après | +24 px (la marge du cadre) |

## Options
| Option | Pour | Contre |
|---|---|---|
| A. `flexShrink: 0` sur le conteneur | 1 ligne, garde le centrage quand tout tient | — |
| B. Retirer `minWidth: 100%` | simple | casse le centrage des petites pages |
| C. Calculer la largeur en JS | contrôle total | fragile, inutile |

**Choix : A.**

## Molette : « un geste = une action » (`frontend/src/lib/molette.ts`)
- **Un geste** : une suite d'événements de molette sans pause de plus de 250 ms. L'inertie du pavé tactile fait partie du geste.
- **L'action est fixée au début du geste** :
  - la page n'était pas au bord → le geste défile, puis s'arrête au bord sans changer de page ;
  - elle y était déjà → le geste change de page une seule fois, après un élan de 60 px.
- Inverser le sens démarre un nouveau geste.
- Une page qui tient entière dans le cadre est toujours au bord : chaque geste y change une page.
- Ctrl + molette reste le zoom.

## Risques
| Risque | Parade |
|---|---|
| Une molette à crans lents (plus de 250 ms entre deux crans) crée un geste par cran | Comportement voulu : chaque cran parti du bord change une page |
| Une inertie très longue | Elle reste dans le même geste et n'est donc jamais transformée en page |

## Vérifications
- Logique de la molette : script avec 4 scénarios :
  1. un geste continu ne change jamais de page ;
  2. un nouveau geste change une seule page ;
  3. trois gestes donnent trois pages ;
  4. une inversion de sens fait défiler.
- `tsc`, `lint` et `build` passent.
