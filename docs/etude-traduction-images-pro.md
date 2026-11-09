# Étude — traduire les images comme un studio de PAO

*09/11/2026. Point de départ : retraduction de 4S_EN.pdf, jugée « mieux mais pas encore ça ».*

## 1. Besoin

Après traduction, une image doit ressembler à l'original : même mise en page, même style. Seule la langue change.

Défauts relevés sur les 4 images de 4S_EN.pdf (tableau « Appointment Preparation Board ») et sur les organigrammes japonais du banc d'essai :

| Défaut | Exemple concret |
|---|---|
| Le texte sort de sa case | « 不具合か否かの判定 » → la traduction déborde de 478 px vers le bas, dans 6 images du banc |
| Contour blanc ajouté | « 3 jours avant » sur fond bleu uni : un liseré blanc entoure les lettres. Il n'existe pas dans l'original |
| Alignement perdu | « Arrivée des pièces » est collé à gauche alors que « Parts Arrival » est centré |
| Place mal utilisée | Le texte traduit est plus petit que nécessaire alors que la cellule a de la place libre (occupation médiane : 59 %) |

## 2. Existant (`backend/app/services/ocr_v2/image.py`)

- `cadre()` (l. 304) : estime la largeur utilisable (x0, x1) et si le texte est centré, à partir des blocs voisins.
- `_libre()` (l. 459) : estime la hauteur utilisable en cherchant de l'encre au-dessus et au-dessous.
- `placer()` (l. 329) : choisit la taille et les retours à la ligne pour tenir dans cette place.
- `_freres()` (l. 497) : donne la même taille aux blocs de même rôle, par exemple les en-têtes de colonnes.
- `_contour()` (l. 535) : décide d'ajouter un liseré pour la lisibilité (`stroke_width`, l. 677).
- Banc de mesure : `backend/tests/banc_images.py` (18 cas, 138 blocs posés).

Limite commune : `cadre()` et `_libre()` ne savent pas où s'arrête la **case**. Ils voient le voisinage, pas le fond. Quand une case n'a pas de voisin proche, la place estimée dépasse la case.

## 3. Règles professionnelles (localisation / PAO), dans l'ordre d'application

1. **Respecter le conteneur.** Le texte reste dans sa case, et les traits et le décor ne bougent pas (contrôles QA : « tronqué, chevauchement »).
2. **Garder l'alignement d'origine** : gauche, centre ou droite.
3. **Prévoir l'allongement.** EN→FR donne +15 à 25 %. Les chaînes courtes (1 à 10 caractères) s'allongent de 100 à 200 %. On réserve donc ~30 % et on passe d'abord à la ligne.
4. **Réduire la taille en dernier**, sans descendre sous un plancher, et de façon égale entre éléments de même rôle.
5. **Même police, même graisse, même couleur.** Aucun effet ajouté, donc pas de contour qui n'existait pas.
6. **Même terme partout** : un titre se traduit de la même façon dans toutes les images (glossaire).
7. **Contrôle final** : débordement, chevauchement, texte resté non traduit.

Sources :
- [SimpleLocalize, text expansion](https://simplelocalize.io/blog/posts/text-expansion-ui-localization/)
- [Lionbridge, 10 dos and don'ts](https://www.lionbridge.com/blog/translation-localization/how-to-localize-software-10-dos-and-donts-for-a-watertight-software-localization-process)
- [LogMeIn Design, room to breathe](https://medium.com/logmein-design/space-and-why-translations-need-room-to-breathe-53348a1f1678)
- [e2f, taux de foisonnement](https://e2f.com/news/taux-de-foisonnement-expansion-rate)
- [Oxygen DITA, localising graphics](https://www.oxygenxml.com/dita/styleguide/Graphics_and_Figures/c_Localising_Graphics.html)
- [Articulate, graphics for localization](https://community.articulate.com/articles/designing-your-e-learning-course-graphics-with-localization-in-mind?page=1)
- [Argos Multilingual](https://www.argosmultilingual.com/?p=1039)
- [Acclaro, Why DTP](https://info.acclaro.com/hubfs/eBooks/Acclaro%20-%20Why%20DTP-.pdf)

Le moteur applique déjà les règles 3 et 4 (`placer`, `_freres`). Les règles 1, 2 et 5 sont celles qui manquent. Les règles 6 et 7 sont partielles.

## 4. Méthode proposée : le « conteneur »

On prend la couleur dominante derrière les lettres. On part du cœur du texte et on agrandit le rectangle de chaque côté tant que la nouvelle rangée garde au moins 97 % de pixels de cette couleur (tolérance 15). On s'arrête donc sur un trait ou sur un changement de fond, sans le toucher.

Ce rectangle donne :
- **la place utilisable** : largeur et hauteur de la case, moins une petite marge ;
- **l'alignement** : marges gauche et droite égales → centré ; sinon, le côté le plus proche ;
- **le fond uni** : si la case est uniforme à plus de 90 %, on n'ajoute pas de contour.

Garde-fous : si le rectangle touche le bord de l'image, ou s'il dépasse 40 fois la zone du texte, la case n'est pas fiable (6 était trop strict : les cartes d'organigramme ont un rapport de 7 à 20). On revient alors à `cadre()`/`_libre()`. Cela arrive pour les cases pâles sur fond blanc.

## 5. Résultats sur le banc (prototype hors dépôt)

| Mesure | Actuel (A) | Conteneur (B) |
|---|---|---|
| Blocs posés / coupés | 138 / 0 | 138 / 0 |
| Gros débordements (> 10 px) | 6 (478 px chacun) | **0** |
| Petits débordements (1 à 8 px) | 4 | 13 (en-têtes « N-days Before » à 1,4–3,6 px du trait du haut ; 基礎 à 7 px) |
| Occupation médiane de la place | 59 % | **80 %** |
| Écarts de taille entre frères | 2 | 6 |
| Contour blanc sur fond uni | oui | **non** |

En clair :
- 4S : les en-têtes sont centrés, plus grands et sans liseré.
- Organigrammes : « Détermination de la présence d'un défaut » reste dans sa case au lieu de déborder.
- Reste à régler :
  - les en-têtes touchent le trait du haut de 1 à 4 px, ce qui demande un centrage vertical dans la case ;
  - les tailles divergent un peu entre frères, parce que chaque case a sa propre place ;
  - « Arrivée des pièces » reste petit.

### 5 bis. Règles de mise en place demandées (retour du 09/11)

1. **Taille ≤ original**, jamais plus grande. Pour une source latine, la taille d'origine est mesurée par la largeur lue, plus fiable que la hauteur de boîte, qui est gonflée de ~30 %.
2. **Ordre** : d'abord le même nombre de lignes qu'à l'origine sur toute la largeur de la case, puis une ligne de plus, puis seulement ensuite une réduction de taille.
3. Interligne calculé sur la taille d'origine. Sinon, la 2ᵉ ligne descend trop bas.
4. Calage vertical à l'intérieur de la case.

Prototype `placer()` revu, rejoué sur le banc :

| Mesure | Actuel (A) | Prototype (B) |
|---|---|---|
| Débordements hors de la case | 3 (jusqu'à 7 px) | **0** |
| Organigrammes | 3 lignes pour 1 à l'origine, débordement de 478 px | 1 ligne ; une seule carte passe sur 2 lignes (texte plus long que la case) |
| En-têtes 4S | plus grands que l'original | égaux ou plus petits |

Défauts restants :
- **Lignes non centrées une à une.** Toutes les lignes d'un bloc partent du même x (`image.py`, l. 676). Un en-tête centré sur 2 lignes paraît donc calé à gauche. Correctif : centrer chaque ligne.
- Mot seul en 2ᵉ ligne (« … découverte de la / cause ») : équilibrer les deux lignes.
- « Pièces commandées » est petit, car « commandées » est plus large que la colonne. C'est conforme à la règle 2 (pas de coupure de mot avant réduction).
- Les tailles de frères divergent un peu (9 écarts contre 2), car chaque case a sa propre place.

## 6. Options

| Option | Effet visible | Pour | Contre |
|---|---|---|---|
| **1. Conteneur complet** (place + alignement + pas de contour sur fond uni), centrage vertical, tailles des frères harmonisées sur la plus petite | Textes dans leurs cases, centrés comme l'original, sans liseré | Corrige les 3 défauts signalés | Le plus gros changement (~80–120 lignes) ; à valider sur le banc et les 4 images |
| 2. Conteneur seulement pour retirer le contour | Plus de liseré ; débordements inchangés | Petit, sans risque | Ne corrige ni débordements ni alignement |
| 3. Statu quo + plafond de hauteur dans `_libre()` | Moins de gros débordements | Petit | Pas d'alignement, toujours le liseré, règle approximative |

**Recommandation : option 1.** C'est la seule qui couvre les trois défauts. Le banc montre qu'elle ne coupe aucun bloc et supprime les gros débordements. Les petits débordements restants ont une cause identifiée (centrage vertical).

Hors de cette étude, à traiter à part :
- même traduction d'un titre d'une image à l'autre (règle 6, glossaire par document) ;
- « Parts Orderd », faute dans la source, laissé en anglais ;
- image 31 : « 3-days » et « Before » lus comme deux blocs.

## 7. Impacts et risques

- Code : `image.py` seulement (nouvelle fonction `conteneur()`, branchée avant `cadre()`/`_libre()`/`_contour()`). Pas de données, pas de migration.
- Performance : une croissance de rectangle par bloc, négligeable devant l'OCR.
- Risques :
  - cases à fond dégradé ou photo : le conteneur n'est pas fiable, le garde-fou ramène à l'existant ;
  - texte aligné à droite : peu de cas, il garde l'ancien calcul.
- Cache : après mise en place, vider le cache images pour revoir les rendus.

## 8. Décision et résultat

Option 1 retenue (09/11) et mise en place dans `image.py` : `conteneur()`, `_case()`, `_equilibrer()`, `placer()` revu.

Réglages ajoutés pendant la mise en place :
- une case qui ne contient pas tout le texte est ignorée (ancien calcul) ;
- marge intérieure au plus 6 % de la largeur de la case (sinon un gros texte japonais perdait 70 px de chaque côté) ;
- un paragraphe qui remplit sa case reste aligné à gauche, même si ses marges sont égales ;
- au-delà d'une ligne de plus, la taille ne descend pas sous 80 % : une traduction bien trop longue garde l'original ;
- chaque ligne est centrée une à une ; deux lignes sont équilibrées.

Banc (18 images) : 138 blocs posés (avant : 118), 0 coupe, 2 écarts entre frères (avant : 17), encre restante inchangée. Test `test_ocr_v2_image` vert.

Limite connue : sur un schéma, une case et un cercle alignés en colonne sont traités comme des frères et prennent la plus petite des deux tailles.

## 9. Étape .6 : règles générales de la case (retour du 09/11)

Après le retour de l'utilisateur, on n'a pas corrigé les cas un par un. On a revu les règles qui servent à toutes les images.

| Règle | Avant | Après | Effet visible |
|---|---|---|---|
| Ce qui est « fond » | écart ≤ 15 à une seule couleur | écart ≤ 10 (`MUR`) au fond, **ou** au fond local (médiane glissante) | un dégradé reste du fond ; un trait gris clair arrête la case (« 得た情報… » ne fuit plus jusqu'au grand cadre) |
| Ce qui est « lettre » | toute la boîte lue | composantes d'encre qui touchent une ligne lue, de taille d'un caractère | une boîte qui mord sur une bordure n'est plus prise pour du texte (en-têtes 4S) |
| Fond uni (part) | mesuré sur toute la boîte | mesuré hors des lettres (halo JPEG exclu) | les en-têtes 4S ne sont plus rejetés |
| Côté sans mur | case rejetée (touche le bord) | la case s'étend d'au plus 12 lignes (`OUVERT`) et s'arrête à mi-distance des autres textes | « Non reproduit » utilise la place libre sans toucher ses voisins |
| Alignement gauche / droite | calé au mur de la case | retrait d'origine gardé | « Close » reste à sa place, pas collé au bord |
| Contour (liseré) | dès qu'un trait est proche | seulement sur fond chargé (texture) | plus de liseré parasite à côté d'un trait |
| Ordre de placement | — | option A : même nombre de lignes → +1 ligne → réduction | inchangé, confirmé par l'utilisateur |

Banc (18 images) :

| Mesure | Avant l'étape | Après |
|---|---|---|
| Blocs posés | 138 | **142** |
| Mots coupés | 0 | 0 |
| Écarts entre frères | 2 | **1** |
| Encre restante (restes) | 3916 | **3854** |
| Test `test_ocr_v2_image` | vert | vert |

Limites connues :
- texte coloré dominant sur un dégradé (« Cooling water » en rouge) : la couleur dominante est celle du texte, donc la case est rejetée et l'ancien calcul s'applique ;
- règle des frères : dans une colonne d'organigramme, la plus longue traduction impose sa petite taille aux autres cartes (424e5d0680).

## 10. Étape .8 : en-têtes de tableau (retour 4S du 09/11)

Causes confirmées par trace sur le banc (080a3a0031, identique à 5ba73bf0c0) :

| Symptôme | Cause mesurée | Règle générale retenue |
|---|---|---|
| « 3 jours » petit, « avant » grand dans la même case | boîtes OCR de 30 px (« 3-days », jambage du y) et 25 px (« Before ») : écart de 17 % > tolérance de 15 %, donc deux blocs traduits séparément | deux lignes latines empilées et **centrées l'une sur l'autre** : tolérance de hauteur doublée (30 %), comme pour une fin de phrase. Exclu en CJK : sans jambages, un écart de hauteur y sépare un titre de sa légende (test `test_ocr_v2_image`) |
| En-têtes sur 1 ligne et petits | « commandées » ne tient pas dans sa case (99 px utiles) au-dessus de 16 px ; les frères descendent à 16 px puis sont **recoupés** sur 1 ligne | quand un frère prend une taille plus petite, il garde **son nombre de lignes** (`n_min` dans `placer` / `_equilibrer`) |
| « Pièces commandées » collé au trait du haut | même cause : les voisins sur 1 ligne faisaient paraître le bloc décalé ; le calage vertical est déjà centré dans la case | aucun changement de calage |

L'hypothèse « interligne et marges du moteur » est écartée : à la taille d'origine, deux lignes tiennent en hauteur ; seule la largeur limite.

Banc : 141 blocs posés (deux lignes réunies en un bloc), 0 coupe, 1 écart, restes 3854 ; `test_ocr_v2_image` vert.

Limite : la taille commune des en-têtes reste imposée par la traduction la plus longue (« commandées », 16 px au lieu de ~24 px). Pour gagner ~2 px, il faudrait réduire la marge intérieure des cases (6 % de la largeur) ; ce n'est pas fait, à décider après l'essai.
