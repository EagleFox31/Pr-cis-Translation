# Traduction de documents scannés — étude d'implémentation

*19/07/2026. Étude préalable, aucun code écrit.*

---

## 1. Ce qui change, et ce qui ne change pas

Un PDF numérique et un PDF scanné se ressemblent à l'écran et n'ont **rien en
commun** dans le fichier.

| | PDF numérique | PDF scanné |
|---|---|---|
| Texte | objets avec position, police, corps, couleur | **aucun** — des pixels |
| Polices | embarquées, extractibles | **aucune** |
| Dessins vectoriels (filets, cadres) | objets | **aucun** — des pixels |
| Images | objets distincts | **la page entière est une image** |
| Géométrie | exacte, au point près | **inclinée, bruitée, déformée** |

La conséquence est plus profonde qu'il n'y paraît. Le moteur v2 fonctionne
aujourd'hui ainsi : il extrait **tout** objet détectable, puis **reconstruit la
page sur une feuille vierge**. Le JSON est la seule source du rendu — rien n'est
copié depuis l'original. C'est ce qui garantit la fidélité.

Cette stratégie **ne peut pas** s'appliquer à un scan. Sur un scan, ce que l'OCR
ne reconnaît pas n'existe plus : un tampon, une signature manuscrite, un logo,
un filet de tableau, une annotation au stylo. Reconstruire sur une page vierge
reviendrait à **jeter tout ce que l'OCR n'a pas vu** — et un OCR ne voit que du
texte.

**Il faut donc inverser le principe pour les scans** : au lieu de reconstruire
la page, on **conserve l'image d'origine** et on n'y remplace que les zones de
texte traduites. Tout ce que l'OCR ignore reste intact par construction, parce
qu'on n'y touche pas.

C'est la décision d'architecture la plus importante de ce document, et elle est
irréversible : elle détermine tout le reste.

---

## 2. La bonne nouvelle : un seul point de raccordement

`engine.py` fait 4 206 lignes. La quasi-totalité — regroupement en lignes,
détection de colonnes, corridors, justification, paragraphes, césure,
croissance, rendu — **ne connaît rien à PyMuPDF**. Une seule méthode touche
l'API texte :

```python
def _extract_text(self, page, draw_els=(), img_els=()):
    raw = page.get_text("rawdict", ...)      # ← le SEUL appel
    spans = [...]                            # ← dictionnaires ordinaires
    return self._group_text_lines(spans, self._ink_walls(draw_els, img_els))
```

Tout l'aval consomme `spans`, une liste de dictionnaires dont la forme est
entièrement documentée par le code :

```python
{
  "bbox", "origin", "text", "font", "size", "color",
  "flags", "bold", "italic", "dir",
  "_gw", "_base", "_ink_x0", "_ink_x1",
}
```

**Un extracteur OCR qui produit ces mêmes dictionnaires hérite gratuitement de
tout le travail de mise en page déjà fait** — y compris les correctifs P14 à
P26 payés cher (colonnes justifiées recollées, corridors fantômes, satellites
en exposant, césure, glossaire de document). C'est ce qui rend le projet
raisonnable plutôt que démesuré.

Le plan tient donc en une phrase : **écrire un second producteur de spans, et
ne toucher à rien d'autre en amont.**

---

## 3. Ce que l'OCR ne donne pas, et comment le déduire

Un OCR (Tesseract, PaddleOCR) rend, par mot : le texte, une boîte, un indice de
confiance. C'est tout. Sept des quatorze champs manquent. Voici comment chacun
se dérive, et ce que coûte l'erreur.

| Champ | Dérivation | Si on se trompe |
|---|---|---|
| `text` | direct | contresens traduit — **le pire cas**, voir §6 |
| `bbox` | direct (après redressement) | texte décalé |
| `size` | hauteur de la boîte des minuscules sans jambage, calibrée sur la hauteur d'x | corps faux → débordement ou trou |
| `origin` / `_base` | ligne de base estimée par régression sur les bas de boîtes de la ligne | texte qui ondule |
| `color` | couleur dominante des pixels d'encre dans la boîte | texte de la mauvaise couleur |
| `bold` | épaisseur de trait rapportée à la hauteur d'x | graisse fausse (cf. P21) |
| `italic` | inclinaison des axes verticaux des glyphes | italique perdu |
| `font` | **indéductible** — voir ci-dessous | police approximative |
| `dir` | angle de redressement de la page | ligne de travers |
| `_ink_x0/_ink_x1` | direct : l'OCR ne rend que de l'encre | — |

### La police : un problème sans solution exacte

Aucun OCR ne rend l'identité d'une police. Au mieux on classe : **avec ou sans
empattement, graisse, italique, chasse fixe ou proportionnelle**. Quatre bits,
là où le moteur attend un nom.

`backend/fonts/` contient déjà **28 fichiers** (Merriweather, Montserrat, Open
Sans, Oswald, PT Serif…) en Regular/Bold/Italic/BoldItalic. C'est exactement la
matière d'une substitution par classe. Mais attention — la mémoire du projet le
consigne : **ces fichiers ont déjà été corrompus une fois** (PT Serif), et la
seule vérification qui l'a révélé est la mesure de densité d'encre par variante.
À refaire avant de s'appuyer dessus.

`_pick_font()` cherche aujourd'hui dans `self._fonts`, alimenté par les polices
**embarquées du PDF**. Un scan n'en a aucune : il faut un second seuil de repli
vers `backend/fonts/`. C'est le **deuxième** point de raccordement, et le
dernier.

---

## 4. Le vrai travail neuf : effacer sans laisser de trace

C'est la seule partie qui n'existe nulle part dans le code actuel.

Pour poser la traduction, il faut d'abord **retirer le texte d'origine de
l'image**. Le remplir de blanc ne marche pas : un scan n'est jamais blanc. Il
est jauni, texturé, ombré près de la reliure, parfois avec un fond coloré ou une
trame. Un rectangle blanc sur un scan se voit immédiatement — et se voit
d'autant plus que le document a l'air authentique par ailleurs.

Trois approches, par coût croissant :

1. **Couleur locale médiane.** On échantillonne le fond autour de la boîte
   (couronne de quelques pixels) et on remplit de cette couleur. Rapide,
   suffisant sur un scan propre et uniforme. Échoue sur les fonds texturés ou
   dégradés.
2. **Remplissage par propagation** (*inpainting*, OpenCV `INPAINT_TELEA`). On
   laisse l'algorithme prolonger le fond depuis les bords du masque. Bien
   meilleur sur les fonds non uniformes, coût encore modeste.
3. **Modèle génératif de restauration.** Hors sujet ici : coût, latence et
   imprévisibilité sans commune mesure avec le gain.

**Recommandation : (1) par défaut, (2) quand la couronne est hétérogène**, le
critère étant l'écart-type des pixels de la couronne. Un seul seuil, mesurable,
qui décide.

**Piège à ne pas manquer :** le masque doit couvrir l'**encre**, pas la boîte.
Les boîtes OCR se chevauchent souvent d'un ou deux pixels sur la ligne voisine ;
masquer la boîte entière ronge le haut des jambages de la ligne d'en dessous.
Le moteur connaît déjà cette distinction — c'est tout le sens de `_ink_x0` /
`_ink_x1` et de la règle « l'encre au mot est seule juge » (P21-P26).

---

## 5. Le redressement, avant tout le reste

Un scan est incliné : quelques dixièmes de degré à plusieurs degrés. Sans
redressement :

- l'OCR perd en précision (les lignes traversent plusieurs bandes) ;
- les lignes de base ne sont pas horizontales, donc `_group_text_lines` — qui
  regroupe **par rangée de ligne de base** — casse les lignes en morceaux ;
- la détection de colonnes voit des corridors qui n'existent pas.

Autrement dit, **l'inclinaison casse en amont toute la logique de mise en page
qu'on cherchait justement à réutiliser**. Le redressement n'est pas une
amélioration de confort, c'est un prérequis.

Ordre imposé : `redresser → OCR → spans → moteur v2 → masquer → peindre`.

Question ouverte : redresser **l'image de sortie** aussi, ou remettre la
traduction dans le repère incliné d'origine ? Redresser la sortie donne un
document plus propre que l'original, mais déplace tampons et signatures par
rapport à ce que le client a signé. **Sur un document officiel — et c'est le
cœur de votre marché — je penche pour conserver le repère d'origine** et
n'utiliser le redressement qu'en interne, pour l'analyse. À trancher.

---

## 6. La règle d'honnêteté : ne pas traduire ce qu'on n'a pas lu

C'est le risque le plus sérieux du projet, et il est de nature différente des
autres.

Sur un PDF numérique, le texte extrait **est** le texte. Sur un scan, c'est une
hypothèse. Un OCR qui lit `1000` au lieu de `l000`, `rn` au lieu de `m`, ou qui
avale une négation, produit une traduction parfaitement fluide et **fausse**.
Sur un acte de naissance, un diplôme ou un contrat — vos cas d'usage — une date
ou un montant faux ne se remarque pas, et engage.

Le moteur de traduction ne peut pas rattraper ça : il traduira fidèlement ce
qu'on lui donne. La seule défense est en amont.

**Règles à tenir :**

1. **Seuil de confiance par mot.** Sous le seuil, le mot n'est pas traduit :
   la zone reste **l'image d'origine**, non masquée. On préfère un mot en
   langue source lisible à un mot inventé.
2. **Ne jamais réécrire les nombres, dates, montants, identifiants** par une
   valeur OCR de confiance moyenne. Un nombre mal lu est indétectable à la
   relecture.
3. **Confiance de page remontée à l'utilisateur.** Si la page moyenne est
   faible, le dire — « document de qualité insuffisante, relecture
   recommandée » — plutôt que de livrer un résultat d'apparence irréprochable.
4. **Ne pas facturer une page illisible.** Elle coûte à produire et ne vaut
   rien ; la facturer coûte un client. À câbler sur `pages_facturees`.

---

## 7. Choix du moteur OCR

| | Tesseract | PaddleOCR | OCR en ligne (Google/Azure) |
|---|---|---|---|
| Coût | nul | nul | **par page — détruit la marge** |
| Hors-ligne | oui | oui | non |
| Confidentialité | totale | totale | **documents officiels chez un tiers** |
| Qualité fr/en | bonne | très bonne | excellente |
| Positions | mot, via TSV | mot et ligne | mot |
| Poids | léger | ~1 Go de modèles | nul |
| Mise en place | binaire système | pip + modèles | clé d'API |

**Recommandation : Tesseract d'abord.** Sortie TSV directement exploitable
(`left/top/width/height/conf/text`), aucun modèle lourd, et il suffit largement
à valider toute la chaîne. PaddleOCR en second temps si la qualité mesurée est
insuffisante — l'interface entre les deux est la même liste de spans, donc le
remplacement est local.

**L'OCR en ligne est à écarter**, et pas pour son prix : vos utilisateurs
déposent des actes d'état civil et des diplômes. Les envoyer chez un tiers est
un engagement qu'on ne prend pas incidemment. Votre coût actuel — 0,0007 $ la
page — s'effondrerait par ailleurs face à ~1,50 $ les 1 000 pages facturées par
ces services.

---

## 8. Comment le prouver — sans document de test

La règle du projet est explicite : *« tout correctif du moteur se prouve sur un
PDF synthétique, jamais sur les seuls documents qui l'ont révélé »*. Elle
s'applique ici mieux qu'ailleurs, parce que l'OCR permet une chose rare :
**fabriquer un scan dont on connaît la vérité**.

```
PDF synthétique (texte connu)
   → rendu en image à 150/300 dpi
   → inclinaison contrôlée (0°, 0,3°, 1,5°)
   → bruit et compression JPEG contrôlés
   → « scan » dont on connaît EXACTEMENT le texte attendu
```

On obtient alors des mesures, pas des impressions :

- **taux d'erreur caractère** de l'OCR, par dpi et par inclinaison ;
- **écart de position** entre la boîte OCR et la boîte réelle du PDF source ;
- **fidélité du masquage** : différence de pixels hors zones de texte entre
  l'entrée et la sortie — elle doit être **nulle** (c'est l'invariant central de
  la stratégie du §1 : ce qu'on ne traduit pas ne bouge pas) ;
- **régression de mise en page** : comparer les paragraphes issus de l'OCR à
  ceux issus du PDF numérique **du même document**. Ils doivent coïncider. Ce
  test unique valide d'un coup toute la réutilisation du §2.

Ce dernier test est le plus précieux du lot : il compare l'OCR à une vérité
terrain que le projet possède déjà.

---

## 9. Phasage

| Étape | Contenu | Sortie vérifiable |
|---|---|---|
| **0** | Détection : ce PDF est-il scanné ? (page sans texte + une image pleine page) | Le bon moteur est choisi, sans intervention |
| **1** | Générateur de scans synthétiques + mesure du taux d'erreur | Chiffres, par dpi et inclinaison |
| **2** | Redressement | Angle résiduel < 0,1° |
| **3** | OCR → spans, branché sur `_group_text_lines` | Les paragraphes coïncident avec ceux du PDF numérique |
| **4** | Repli de police vers `backend/fonts/` | Rendu lisible, graisse et italique respectés |
| **5** | Masquage + remplissage | Différence de pixels nulle hors zones de texte |
| **6** | Seuils de confiance et signalement | Une page illisible est signalée, non facturée |
| **7** | Intégration : quota, tarif, aperçu | Bout en bout |

Les étapes 0 à 2 ne touchent pas au moteur et sont testables seules. **L'étape 3
est le point de non-retour** : si les paragraphes ne coïncident pas, c'est que
la réutilisation du §2 ne tient pas, et tout le plan doit être revu. **C'est
donc l'étape à faire tôt, pas tard** — elle valide ou détruit l'hypothèse
centrale à moindre coût.

---

## 10. Ce que je ne sais pas encore

Honnêtement listé, parce que ces points peuvent changer le plan :

1. **Le taux d'erreur réel de Tesseract** sur vos documents (actes, diplômes,
   contrats camerounais, tampons et sceaux). L'étape 1 le mesurera. S'il est
   mauvais en français administratif, PaddleOCR devient prioritaire.
2. **Le coût CPU par page.** Le rendu est déjà le poste dominant ; l'OCR
   s'ajoute (~1-3 s/page à 300 dpi, à mesurer). Cela peut imposer un tarif
   distinct pour les scans — la grille actuelle n'en prévoit pas.
3. **Les documents multilingues et les écritures non latines.** Un acte
   bilingue français/anglais est courant au Cameroun ; Tesseract sait charger
   plusieurs langues, au prix de la vitesse et de la précision.
4. **Les tableaux sans filets.** Le moteur les gère par corridors de blanc
   (P15/P16) ; sur un scan bruité, ces corridors sont moins nets. Comportement
   à mesurer, pas à supposer.
5. **Le manuscrit.** Hors de portée de Tesseract. Politique à définir : laisser
   en l'état (recommandé) plutôt que produire n'importe quoi.

---

## 11. En une phrase

L'essentiel du travail de mise en page est **déjà fait et réutilisable**, à
condition de produire des spans de la bonne forme ; le travail neuf tient dans
le redressement, le masquage du fond et — surtout — **la discipline de ne jamais
traduire ce qu'on n'a pas lu avec certitude**.
