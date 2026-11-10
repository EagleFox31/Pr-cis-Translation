# Étude : texte centré dans une pastille ou un cadre (moteur PDF)

## Besoin
Sur le 4S traduit, les textes des pastilles, des cercles et des cases (« Qu'est-ce que les 4S ? », « Objets nécessaires », « Objets inutiles ») ne tombaient pas au centre de leur conteneur. Le texte d'origine était bien centré, mais une légère marge asymétrique faussait la détection.

## Existant
`_expand_paragraphs` (`backend/engines/pdf/engine.py`) choisit, pour chaque paragraphe :
- son cadre (`frame`) : une cellule, une boîte contenante, ou l'objet collé au-dessus pour une légende (`over_frame`) ;
- ses voisins à gauche et à droite (`left_block`, `right_block`) ;
- la colonne (`col_left`, `col_right`), puis le conteneur où le texte traduit est recentré.

## Causes mesurées
1. **Le contour du cadre était pris pour un voisin.** Le bord droit d'une pastille comptait comme un obstacle, et la marge de sécurité rognait le conteneur d'un seul côté. Exemple : la pastille [24,1 ; 153,4] devenait [24,1 ; 145,4], avec un centre à 84,8 au lieu de 88,75.
2. **Un voisin hors du cadre bridait la largeur.** « What is 4S? » (cadre 232–562) était limité à 468 par la colonne de la pastille du dessous. Résultat : la traduction était décalée et rapetissée.

## Règles retenues (générales)
| Règle | Effet |
|---|---|
| Le bord d'un cadre dur n'est pas un voisin (`left_block`/`right_block` et obstacles de `_line_target`) | Plus de marge prise d'un seul côté |
| Texte centré, **seul** dans un cadre dur (aucun voisin dans le cadre) et déjà centré dessus (à 10 % de la largeur près) : conteneur symétrique sur toute la largeur du cadre | Le centre tombe sur l'axe du cadre et la traduction garde sa taille |
| Marge intérieure égale des deux côtés : le plus petit des deux blancs d'origine, entre 2 et 8 pt | Le texte ne touche pas le contour |
| Légende **sous** une photo (`over_frame`) : pas de marge, elle reprend les deux bords de la photo | P18 reste exact |
| Un texte qui a un voisin dans le cadre (« Necessary items », case 308–367 dans le cadre 213–374) n'est pas recentré sur le cadre | Il reste centré sur sa propre case |

Les règles déjà en place restent inchangées : pile d'axes (`axe_pile`), alignement à gauche, habillage autour d'une photo, texte ferré à droite.

## Lettre dessinée : parent dominant
Décision de l'utilisateur : la lettre refaite prend l'apparence du parent dominant.
- Si le dessin est peint au-dessus (cas A), la lettre prend sa couleur et **toute sa taille**. Le plafond ×2 (`_INI_SCALE_MAX`) est supprimé ; le rapport reste borné par la détection (0,8 à 3).
- Si le texte domine (le dessin est en dessous ou orné, cas « filet »), le texte garde son style.

## Vérifications
- Moteur 1.0.16 (cache invalidé).
- `test_engine_v2_generic` : 108/108.
- `test_coherence_pdf` : 10/10.
- `test_textes_oublies` : 21/21.
- `test_rendu_cache_fond` : PASS.
- `test_pdf_lettres_dessinees` : 44/44. Nouveau cas C9 : grand dessin au-delà de 2 × le corps.
- Corpus de 5 PDF :
  - 4S : 10 pages changent, toutes vers le centrage (pastilles jusqu'à +42 pt de largeur utile).
  - Code de la Route, Data Science, CD : identiques.
  - mv21 : 24 pages bougent de moins de 0,1 pt ou s'améliorent.

## Risques
- Un texte volontairement décentré dans une boîte vide sera recentré s'il était à moins de 10 % de l'axe. Ce seuil est assumé : en dessous, c'est une marge parasite, pas une intention.
