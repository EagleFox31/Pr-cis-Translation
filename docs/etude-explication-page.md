# Étude : expliquer ce qu'est une « page » (page Tarifs)

## Besoin

Sous la grille des forfaits, une ligne bleue en gras dit :
« PDF : pages · PowerPoint : diapositives · Word, Excel et TXT : 1 page pour 500 mots, arrondie au supérieur. »
Retour utilisateur : elle sonne « robot » et n'est pas à la bonne place.

## Existant

- `PricingCards.tsx` : `<p className="pricing-annuel">` entre la grille et l'encadré « Sans abonnement, à la page ».
- `.pricing-annuel` est le style des mentions de prix (« 120 000 FCFA facturés par an ») : bleu, gras, 12 px.
  La règle de calcul ressemble donc à une mention de prix, sans titre, collée sous les cartes.
- Le nombre de mots vient de l'API (`pricing.words_per_page`).
- Les cartes parlent de « pages équivalentes » et l'encadré « à la page » vend des pages : la règle sert aux deux.

## Problèmes

1. Ton : une liste à puces compressée (« PDF : pages ») au lieu d'une phrase.
2. Rien ne dit à quelle question la ligne répond.
3. Aucun exemple : « arrondie au supérieur » reste abstrait.
4. Place : collée aux cartes, elle semble appartenir au dernier forfait et coupe la grille de l'offre « à la page ».

## Options

| | Ce que voit le visiteur | Pour | Contre |
|---|---|---|---|
| A. Reformuler sur place | Même ligne, phrase plus douce | Minimal | Toujours sans titre, toujours au mauvais endroit |
| B. Infobulle « ? » sur « pages équivalentes » | Petit « ? » dans chaque carte | Explication au point d'usage | Caché ; peu pratique au doigt ; répété sur chaque carte |
| C. Encadré « Comment compte-t-on une page ? » sous l'offre à la page | Titre + trois lignes + un exemple chiffré | Lisible, répond à une vraie question, couvre forfaits et achat à la page | Un bloc de plus |

## Choix : C

- Placé **après** l'encadré « Sans abonnement, à la page », en fin de section : on lit les offres, puis la règle commune.
- Ton discret (gris, fond clair, sans bouton) pour ne pas concurrencer les offres.
- Contenu :
  - Titre : « Comment compte-t-on une page ? »
  - PDF : chaque page du document compte pour une page.
  - PowerPoint : chaque diapositive compte pour une page.
  - Word, Excel et texte : une page tous les 500 mots entamés.
  - Exemple : « un document Word de 1 200 mots compte pour 3 pages ». Exemple calculé à partir de `words_per_page`.

## Impacts

- `PricingCards.tsx` : la ligne `pricing.equivalence` remplacée par l'encadré.
- `index.css` : styles `.pricing-units`.
- Locales FR/EN : `pricing.units.*` remplace `pricing.equivalence`.

## Vérification

tsc, lint (concordance des dictionnaires), build, capture Playwright de la section Tarifs (bureau + mobile).
