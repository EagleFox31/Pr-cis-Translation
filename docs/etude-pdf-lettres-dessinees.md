# Étude : reconstituer les mots dont une lettre est dessinée (moteur PDF)

## Besoin
Page 2 du 4S, le mot « Seiri » est fait de deux morceaux :
- un **dessin** : le « S » rouge ;
- du **texte** : « eiri ».

Un traducteur humain lit « Seiri », traduit le mot entier, puis rend la mise en valeur du mot traduit : la première lettre en rouge et plus grande. On veut faire de même, avec une règle générale.

## Existant utile
- Le moteur sait déjà repérer qu'un dessin plein **masque** une lettre de texte au pixel (`_shape_covers`, `_ink_masked`, version 1.0.13).
- Une ligne est faite de **runs** : des morceaux de texte qui ont chacun leur police, leur taille et leur couleur (`engine.py`, `ln["runs"]`). Une première lettre rouge et plus grande est donc représentable sans nouveau format.
- Un OCR existe déjà dans `app/services/ocr_v2/detect.py`.

## Deux cas
| Cas | Exemple | Comment on connaît la lettre |
|---|---|---|
| A. Lettre dessinée **posée sur** une vraie lettre | 4S : S rouge sur S gris | La lettre de texte cachée dessous la donne, **sans deviner** |
| B. Lettre dessinée **seule**, sans texte dessous | Lettrine vectorisée dans un autre PDF | Il faut la **lire** : rendu du dessin seul en image, puis OCR |

## Solution proposée (« lettre dessinée = style »)
1. **Détection.** Un dessin plein, d'une seule couleur, qui a la hauteur d'une lettre et touche un mot sur la même ligne de base :
   - **cas A** : il masque une lettre de texte, qui donne la lettre ;
   - **cas B** : l'OCR lit une seule lettre avec une confiance élevée, et elle colle à un mot sans espace.
2. **Reconstitution.** Le mot est rendu entier, par exemple « Seiri ». La lettre reçoit son propre run, avec la **couleur du dessin** et la **taille du dessin** (rapport de hauteur).
3. **Traduction.** Le traducteur reçoit le vrai mot. La mise en valeur passe à la **première lettre du mot traduit** : « Trier », avec le T rouge et grand.
4. **Rendu.** Le dessin d'origine n'est plus peint, puisque la lettre est désormais du vrai texte.

## Est-ce que ça résout tout ?
| Problème | Option 3 (étude superposition) | Cette solution |
|---|---|---|
| Lettre doublée si le texte bouge | évitée par l'ancrage | **disparue** : il n'y a plus qu'une seule lettre |
| Trou entre la lettre et la suite | évité par l'ancrage | **disparu** : le mot est d'un seul tenant |
| Mot tronqué envoyé au traducteur | mot entier | mot entier |
| Traduction qui commence par une autre lettre | S rouge sur « Trier » | **T rouge** : le cas est résolu |
| Le texte peut être réduit ou décalé | réduction seulement | **les deux**, sans risque |

### Ce qui reste hors de portée
- Une lettre **ornée** (dégradé, motif, contour décoratif, illustration) ne se refait pas avec une police. On garde alors l'option 3 : le dessin est conservé au-dessus et le texte reste ancré.
- **Logos** et sigles dessinés de plusieurs lettres : on n'y touche pas, une marque ne se traduit pas.
- **Police différente** : la lettre refaite utilise la police du mot, pas la forme exacte du dessin. C'est un écart visible mais propre, comme le ferait un studio PAO sans la fonte d'origine.

## Garde-fous (contre les faux positifs)
- Le dessin doit être **d'une seule couleur** et **plein**. Il a la hauteur d'une lettre, entre 0,8 et 3 fois le corps du mot voisin, et il est collé au mot sans espace.
- **Cas B** :
  - la confiance de l'OCR doit être au moins de 0,9 ;
  - les formes ambiguës sont refusées : un rond peut se lire O, une barre I ou l, un trait « - ».
  - en cas de doute, le dessin reste tel quel (option 3).
- Le dessin ne peut **jamais** être retiré sans qu'une vraie lettre ait été placée à sa place.

## Ordre conseillé
1. **Cas A d'abord**, sans OCR : c'est le 4S, et c'est déterministe.
2. **Cas B ensuite**, seulement si un document réel le montre : aucun dans le corpus mesuré.
3. **Option 3** comme filet pour tout ce qui n'est pas reconstituable.

## Impacts
- Fichier touché : `backend/engines/pdf/engine.py`. On ajoute la détection après `_ink_masked`, le run de mise en valeur, et la non-peinture du dessin. La règle « mise en valeur → première lettre de la traduction » se branche là où les runs sont recollés après traduction.
- Version du moteur : 1.0.14.
- Vérifications :
  - P36 108/108 ;
  - corpus de 124 pages identique ;
  - 4S page 2 : le mot traduit commence par une lettre rouge, sans doublon.
