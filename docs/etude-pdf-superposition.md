# Étude : respecter la superposition texte / dessins (moteur PDF)

## Besoin
Page 2 du 4S : le « S » rouge de « Seiri » est un **dessin** posé **par-dessus** une lettre « S » grise, qui est du vrai texte. L'utilisateur demande de garder cet ordre (dessin au-dessus du texte) et de le faire de façon générale. Le cas où le texte traduit est **décalé ou réduit** doit rester sûr.

## Existant
- À l'extraction (`engine.py`), les graphiques (dessins, images) sont triés par ordre de peinture puis placés **avant** tout le texte. `render_page_into` repeint dans cet ordre : le texte passe donc toujours au-dessus de tous les dessins.
- Correctif 1.0.13 (`_shape_covers` / `_ink_masked`) : une lettre masquée au pixel par une forme peinte après elle est **retirée** du texte. On envoie alors « eiri » au traducteur.
- Mesure sur les 40 premières pages (dessins peints après un texte qu'ils chevauchent) :

  | Document | Contours | Formes pleines |
  |---|---|---|
  | 4S | 12 contours de rectangles | 1 forme pleine (le S), 1 contour de forme |
  | mv21 | 1 contour de rectangle | — |
  | Autres documents | — | — |

  Le cas est donc rare, et seules les formes **pleines** posent problème.

## Risques d'un ordre respecté naïvement
| # | Risque | Exemple |
|---|---|---|
| R1 | Lettre doublée | Le texte traduit se décale : le « S » gris réapparaît à côté du S rouge |
| R2 | Trou | « eiri » se réduit ou se recentre, ce qui laisse un vide entre le S rouge et la suite |
| R3 | Texte traduit caché | Une traduction plus longue passe sous une forme pleine fixe |
| R4 | Cadres par-dessus le texte | Un contour dessiné barre le texte traduit qui déborde |
| R5 | Surligneur | Un aplat « multiply » repeint au-dessus assombrit le texte : il ne masque pas, il teinte |
| R6 | Pastille | Une pastille posée sur un mot couvre un autre mot après traduction |

## Options
| Option | Ce qu'on voit | Pour | Contre |
|---|---|---|---|
| 1. Actuel (lettre retirée) | Le S rouge reste, « eiri » est traduit seul | Déjà en place | Le traducteur voit un mot tronqué ; R2 |
| 2. Ordre seul | Le dessin repeint au-dessus du texte | Fidèle tant que rien ne bouge | R1, R3, R4 et R5 dès que le texte bouge |
| **3. Ordre + texte entier + ancrage** | Le S rouge au-dessus, « Seiri » traduit en entier, la ligne ne bouge pas | Fidèle, et sûr si le texte réduit | Un peu plus de code |

## Option 3 recommandée (règles générales)
1. **Avant-plan restreint** : seul un graphique **plein et opaque**, peint après un texte, **et** qui le masque au pixel dans l'original, est repeint après le texte.
   - Les contours restent derrière (parade à R4).
   - Les aplats « multiply » ou transparents restent derrière (R5).
2. **Texte entier** : la lettre n'est plus retirée. Le traducteur reçoit « Seiri » et la lettre grise reste sous le S rouge, comme dans l'original.
3. **Ancrage** : une ligne recouverte par un avant-plan garde son point de départ et sa ligne de base.
   - La réduction de taille est permise : le début de la ligne reste sous le dessin.
   - Le décalage est interdit : pas de flux vertical, de recentrage ni d'échelle de groupe qui la déplace (R1, R2).
4. **Obstacle fixe** : un avant-plan est un obstacle pour le flux vertical, et aucun autre texte n'est poussé dessous (R3).
5. **Pastille** (R6) : la règle 1 ne s'applique que si le dessin masque **une partie** de la ligne. Un aplat qui couvre des mots entiers est un cache volontaire et reste traité comme aujourd'hui.

## Limite
La lettrine dessinée ne change pas. Si la traduction commence par une autre lettre, par exemple « Seiri » traduit en « Trier », on lira « S » rouge par-dessus le « T ». Ce cas est identique à aujourd'hui et ne peut pas se corriger sans redessiner l'image.

## Impacts
- Fichier touché : `backend/engines/pdf/engine.py`, en trois points :
  - marquage `_avant_plan` à l'extraction ;
  - ordre de peinture dans `render_page_into` ;
  - ancrage dans le flux et la mise à l'échelle.
- Version du moteur : 1.0.13 → 1.0.14, ce qui invalide le cache.
- Vérifications :
  - P36 108/108 ;
  - corpus de 124 pages identique, hors 4S ;
  - 4S page 2 : le S rouge reste au-dessus, sans lettre doublée.

## Points à trancher
- Option 3 (recommandée) ou garder l'option 1.
