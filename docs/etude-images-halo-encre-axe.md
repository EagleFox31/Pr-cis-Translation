# Étude : halo des lettres, hauteur d'encre et axe des cases (images traduites)

*09/11/2026 — étape .13g. Étude mesurée sur le banc d'images (18 cas, par lots de 5).*

## 1. Défauts constatés (organigramme b76a516aca)

| Défaut visible | Exemple | Cause |
|---|---|---|
| Ombre de l'ancien texte sous la traduction | contour gris de 基礎 derrière « Base » (312d) | le masque d'effacement s'arrête au seuil d'Otsu ; le bord adouci des lettres reste |
| Texte pâle effacé à moitié | « Vérifier le phénomène » gris clair | la bande d'encre utilise un seuil fixe (`SEUIL_ENCRE`), au-dessus du contraste d'un gris 207 sur blanc |
| Étiquettes sœurs de tailles différentes | « Entretien client » à 64 px, ses voisines à 27 px | la boîte lue d'un texte CJK court est gonflée (問診 : 59 px lus pour 42 px de lettres) |
| Texte décalé dans sa case | « Vérifier le phénomène » collé à gauche | la marge mesurée inclut des pixels parasites ; aucune règle ne recentre |
| Barre de « H » prise pour un trait de schéma | lettre mutilée | un segment plein hauteur dans une zone serrée passait pour un trait |

## 2. Règles retenues (générales, aucun cas particulier)

1. **Halo** (`mask.py`, `HALO_*`) : les pixels distincts du fond (au-dessus de 2 × le bruit du bord, au moins 4) sont gagnés de proche en proche depuis les lettres, sur 10 % de la hauteur de boîte. Il sert **à l'effacement seulement** ; toutes les mesures (couleur, contour, graisse, hauteur) se font sur le cœur des lettres (`halo=False`). Sinon, la teinte mesurée tire vers le fond.
2. **Le halo ne s'étend pas sur un trait** : le liseré d'un trait (1 px) et le bord adouci d'un trait (tracé long et droit qui sort de la boîte, même plus pâle que lui) lui appartiennent. Exemple : sur 16c13, la bordure sous le titre a un bord gris qui déborde dans les cases « 3-days » et « 2-days ». Le halo s'y étendait, l'effacement croyait qu'un trait traversait la zone et le repeignait, ce qui laissait des tirets noirs.
3. **Trait traversant** (`erase.py`, `_des_deux_cotes`) : un trait traverse une zone s'il couvre au moins 4 positions distinctes de chaque côté **et** la touche des deux côtés (à `CONTACT` = 4 px près). Deux cas ne comptent plus :
   - une jonction en T, où la bordure d'en haut ne couvre que son épaisseur ;
   - une courbe voisine au-delà d'une bordure (taches sombres sur 5ba7).
4. **Texte pâle** (`_elargie`) : le seuil d'encre suit le contraste de la ligne lue (30 %), entre 10 et `SEUIL_ENCRE`.
5. **Frères** (`_freres`) : deux blocs de même couleur sont frères si leurs lignes lues **ou** leurs lettres mesurées (`_hauteur_encre`) ont la même hauteur. Le gras ne compte pas : il ne change pas le corps (ベテラン en gras et 新人 en régulier, 43 px tous deux, sur f82d).
6. **Axe de case** (`conteneur` → `clos`, `_case`) : une ligne seule dans une case fermée des quatre côtés, centrée à 10 % près de la largeur, se centre exactement sur l'axe de la case, comme le moteur PDF.
7. **Barre de lettre** (`sort_h`/`sort_v`) : un trait doit sortir de la zone pour être un trait.

## 3. Mesures (banc, référence ancienne → actuel)

Les écarts comptent les frères de tailles différentes ; les restes, les pixels d'ancien texte visibles.

| Lot | Cas | Écarts | Restes | Diff visuel avec la version précédente |
|---|---|---|---|---|
| 0 | 080a 1256 16c13 21827 312d | 4 → 0 | 344 → 272 | 312d « Base » à la taille de 基礎, sans ombre ; 16c13 sans tirets |
| 1 | 3214 424e 5802 5ba7 6339 | 3 → 1 | 775 → 797 | 424e « Entretien client » à la taille de 問診, sur une ligne |
| 2 | 65450 8ec8 97a5 b76a cbc0 | 1 → 0 | identique à la version précédente | b76a centré, tailles égales |
| 3 | d2ad f4c9 f82d | 9 → 0 | 509 → 1121 | f82d « Résultats », « Débutant » au corps du texte |

- Aucun cas n'a reculé par rapport à la version précédente.
- Les restes de f82d (688) et de 97a5 (1069) étaient déjà à ce niveau dans la version précédente : ce ne sont pas des reculs de ce travail.
- La baisse d'occupation (59 → 29 %) sur les cas à un seul bloc vient d'une règle déjà validée : elle n'agrandit plus le texte au-delà du corps d'origine.

Tests : `test_ocr_v2_effacement.py` (cas halo, flèche gardée à 100 %) et `test_ocr_v2_image.py` (cas cases et encre) au vert.

## 4. Limites et suite

- Les restes de f82d et 97a5 sont à traiter à part (texte sur fond coloré ou dégradé).
- Le banc public d'environ 50 images (ICDAR, COCO-Text, TextOCR, schémas) n'est pas encore construit. Il demande de télécharger des jeux tiers et de payer des appels de traduction.
