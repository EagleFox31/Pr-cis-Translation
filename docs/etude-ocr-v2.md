# Étude — OCR v2 : lire, effacer et réécrire le texte d'une image

> Statut : étude, rien n'est livré. Complète [etude-ocr.md](etude-ocr.md) (v1) ;
> la v2 **améliore** la v1, elle ne repart pas de zéro.
> Date : 31/10/2026.
>
> S'appuie sur l'analyse fournie « Traduction d'images : effacement du texte —
> analyse corrigée et testée » (30/10/2026) et son banc `banc_inpainting.zip`
> (12 cas, 108 zones, code Python exécuté). Les chiffres en dB cités ci-dessous
> en sortent, sauf mention contraire.

---

## 1. Le besoin, en un exemple

Une diapositive de cours japonais : un fond dégradé bleu, une flèche, et la
phrase « 安全確認を行う » écrite en blanc sur le dégradé. L'utilisateur veut la
même image avec « Effectuer le contrôle de sécurité » à la place, **sans tache
visible** là où était le japonais, la flèche intacte, le texte français lisible
et de la même couleur.

Aujourd'hui, la v1 ferait trois erreurs sur cette image :

| Ce que fait la v1 | Ce qu'on verrait |
|---|---|
| Ne lit que le français et l'anglais (`fra+eng`) | Le japonais n'est pas reconnu : la page est refusée |
| Remplit **tout le rectangle** du mot d'une seule couleur (médiane du pourtour) | Un pavé bleu uni au milieu du dégradé. Mesuré : 28 dB sur dégradé, rectangle nettement visible (contre 44,5 dB, invisible, avec la bonne méthode) |
| Écrit en Helvetica noire, taille calculée sur la ligne | Texte noir sur fond bleu foncé ; aucun caractère japonais possible dans Helvetica |

Repère pour lire les dB (PSNR, fidélité au vrai fond) : **au-delà de 40 dB
l'écart est invisible, sous 20 dB il saute aux yeux.**

Deux usages partagent le même besoin :

1. **PDF scannés** (existant) : pages sans texte, déjà traitées par la v1.
2. **Images d'une page web** (nouveau, voir [etude-extension-navigateur.md](etude-extension-navigateur.md)) :
   l'extension envoie une image, reçoit l'image traduite.

**Règle n°1 (confirmée par l'analyse)** : si le texte existe sous forme
vectorielle (texte sélectionnable d'un PDF, SVG, texte HTML), on remplace le
texte lui-même. L'OCR n'est que le **secours** pour les vraies images.

---

## 2. L'existant, mesuré

`backend/app/services/ocr.py` (142 lignes, `OCR_VERSION = "ocrv1"`) :

| Étape | Code actuel | Gardé / changé en v2 |
|---|---|---|
| Rendu de la page | `get_pixmap` ≤ 220 dpi, plafond 12 Mpx | **Gardé** |
| Redressement | Tesseract `--psm 0` (OSD), rotation 90/180/270 | **Gardé** |
| Reconnaissance | Tesseract TSV `fra+eng --psm 3` | **Abstrait** derrière une interface ; Tesseract reste pour fr/en, un détecteur neuronal s'ajoute (§4) |
| Règle d'honnêteté | conf moyenne ≥ 65 et 90 % des mots ≥ 40, sinon refus sans débit | **Gardée**, seuils recalibrés par moteur |
| Effacement | rectangle plein, couleur médiane de la couronne | **Remplacé** : masque des seuls pixels des lettres (§5) + méthode choisie zone par zone (§6) |
| Texte posé | `insert_text` Helvetica par ligne, le moteur PDF traduit ensuite | **Gardé pour les PDF** (le moteur PDF dessine déjà la traduction) ; on transmet en plus la **couleur** du texte |
| Rendu d'image traduite | n'existe pas | **Nouveau**, pour l'extension (§7) |
| Limites | 10 pages, 1 OCR à la fois (`BoundedSemaphore(1)`), 90 s | **Gardées** ; budget propre aux images (§6) |

Appels existants : `api/translate.py` (~l. 328-353) et `services/translation_runner.py`
(l. 1123, 1139, 1238). L'interface publique `prepare_scanned_pdf(data, pages)`
ne change pas : les appelants ne bougent pas.

Dépendances déjà présentes : PyMuPDF, Pillow, numpy. Tesseract (fra, eng, osd)
est installé dans `backend/Dockerfile`, **absent du poste Windows** : tous les
essais OCR se font dans Docker. Ni OpenCV ni SciPy ne sont dans
`requirements.txt` aujourd'hui.

### Le code fourni (`banc_inpainting`)

| Fichier | Contenu | Sort en v2 |
|---|---|---|
| `methodes.py` | masques (boîte, Otsu, **couleur**), 9 méthodes de remplissage dont LaMa ONNX | **Repris** dans le paquet v2 (sans `m_blanc`, `masque_otsu_claude`) |
| `selection.py` | indicateurs, règles, score de couture, **masque fantôme** | **Repris** : fantôme + règle corrigée ; score de couture et règles variance abandonnés (mesurés moins bons) |
| `effaceur.py` | `effacer_et_traduire(image, [(x, y, w, h, texte)])`, couleur et rendu du texte | **Repris** comme base du rendu (§7), police à remplacer |
| `cas.py`, `mesures.py`, `exp*.py` | banc avec vérité terrain, PSNR, SSIM, traits conservés | **Reprise en tests** (§8) ; scikit-image et pandas restent hors production |

---

## 3. Découpage proposé

Nouveau paquet `backend/app/services/ocr_v2/`, un fichier par étape, chacun
testable seul :

```
image ─► detect.py ─► mask.py ─► erase.py ─► (traduction) ─► render.py ─► image traduite
          lignes +      pixels     méthode                    couleur,
          texte +       des        choisie par                boîte élargie,
          confiance     lettres    masque fantôme             contour
```

`ocr.py` garde son rôle d'aiguillage et ses messages d'erreur ; il appelle ces
modules au lieu du code en ligne actuel.

---

## 4. Détection : le vrai goulot

L'analyse le montre par la mesure : **sur fond chargé, le problème n'est pas
le remplissage, c'est la détection.** Un remplissage parfait ne sert à rien si
la boîte du texte n'existe pas.

Tesseract réel sur le banc (`exp3_ocr.csv`) :

| Fond | Mots trouvés | Ce qu'il lit |
|---|---|---|
| uni, sombre, dégradé linéaire, scan, tableau | **100 %** | correct (« warning high voltage ») |
| dégradé radial, quadrillage | 67-75 % | des mots manquent ou sont inventés (« oling », « gt ge el ») |
| briques, herbe, photo | **0 %** | invente du bruit (« hf i = an ane hh ») |
| texte posé sur une flèche, sur un cercle | **0 %** | rien |

Or les diapositives de cours (le cas de l'extension) sont exactement des fonds
chargés, des schémas et des flèches.

| Moteur | Langues | Licence | Poids | Pour | Contre |
|---|---|---|---|---|---|
| **Tesseract** (actuel) | fra, eng ; `jpn` disponible | Apache-2.0 | paquets système, déjà là | Déjà intégré ; 100 % sur fond propre | 0 % sur fond chargé et texte sur trait (mesuré) ; japonais médiocre |
| **PP-OCRv6** (PaddleOCR 3.7, juin 2026) via ONNX Runtime | un modèle : chinois, anglais, **japonais**, 46 langues latines (dont français) | Apache-2.0 (code et poids : fiches officielles PaddlePaddle, vérifié le 01/11/2026) | `onnxruntime` + modèle *small* (7,7 M paramètres) | Détecteur neuronal (type DBNet) conçu pour le texte de scène ; un seul modèle fr/en/ja ; ONNX publié | Chiffres de l'éditeur seul ; à mesurer sur le banc |
| RapidOCR 3.x (enveloppe ONNX de PaddleOCR) | selon modèle | Apache-2.0 | léger | Intégration prête | Couche de plus ; ONNX Runtime suffit |
| PaddleOCR complet (framework Paddle) | idem | Apache-2.0 | plusieurs centaines de Mo | Officiel | Trop lourd pour l'image Docker |
| manga-image-translator | ja → autres | **GPL-3.0** | lourd | Pipeline de référence | Incompatible avec un service fermé : **à lire, pas à reprendre** |

**Recommandation** : interface `Recognizer`, deux implémentations.
- Tesseract reste le moteur des PDF fr/en sur fond propre (aucune régression).
- PP-OCRv6 *small* en ONNX pour les images et les langues non latines.
- Sur fond chargé, en plus de la confiance : filtre des mots absents du
  dictionnaire (Tesseract invente « oN », « HH ») ; en dessous du seuil, on
  **ne remplace pas** (règle d'honnêteté de la v1).

Le moteur doit rendre des **lignes** (polygone, texte, confiance) : le japonais
n'a pas d'espaces.

**Mesuré (étape 4, 01/11/2026)** : `app/services/ocr_v2/ppocr.py`, détecteur et
reconnaissance *small* en ONNX (det 9,9 Mo, rec 21 Mo), un seul fil.
`backend/tests/banc_detection.py`, 12 fonds × 4 positions, mots de confiance
≥ 40 :

| Fond | PP-OCRv6 | Tesseract |
|---|---|---|
| Propres (uni, sombre, scan, tableau) | 100 % | 100 % |
| Brique | 83 % (1 mot inventé) | 0 % |
| Herbe, photo | 100 % | 0 % |
| Dégradé radial, quadrillage | 100 % | 67-75 % |
| Schéma à cadre | 100 % | 0 % (cercle) |
| Schéma fléché | 75 % (« Signalinput » : le trait vertical efface l'espace) | 0 % |
| **Total** | **198/204 mots (97 %)**, fond chargé 94 % | |
| Japonais, 5 lignes sur 5 fonds (Yu Gothic) | 0 % d'erreur par caractère | non installé |

Temps : 0,14 à 0,28 s par image (480 × 300). Les mots sont découpés aux espaces
d'après la position des caractères dans la sortie du modèle ; une ligne
japonaise reste un seul mot. Tesseract reste le moteur des PDF scannés
(`ocr.py` inchangé) ; PP-OCRv6 sert aux images (extension, étape 5).

---

## 5. Le masque : n'effacer que les lettres

Mesuré : passer de la boîte entière aux pixels des lettres gagne **+2,6 dB en
moyenne** (jusqu'à +5,2 dB sur dégradé). Utile, mais ce n'est pas le facteur
principal : à masque égal, la méthode de remplissage fait **10,4 dB** d'écart
(§6).

Le masque retenu est `masque_couleur` du banc :

1. **Distance de couleur au fond** mesuré sur le bord de la boîte (et non
   niveau de gris) ; seuil d'Otsu avec un plancher.
2. **Protection des traits** : retrait des segments horizontaux ou verticaux
   plus longs qu'un tiers de la boîte. La flèche qui traverse le texte n'est
   pas effacée.
3. **Dilatation de 2 px** (confirmée : sans elle, l'anticrénelage laisse un
   liseré visible).

Résultat : à 0,06 dB d'une segmentation parfaite en moyenne. Le seuillage
Otsu en niveaux de gris proposé dans une première analyse effaçait 100 % de la
flèche : écarté.

Limite mesurée : sur photo et herbe, aucun seuillage n'est précis (23 % de
pixels de fond en trop). Seul un modèle de segmentation de texte ferait mieux :
hors première version.

Le masque sert aussi à mesurer la **couleur du texte** (médiane des pixels
masqués), réutilisée au rendu.

---

## 6. L'effacement : choisir la méthode zone par zone

### Aucune méthode ne gagne partout (masque couleur, PSNR en dB)

| Fond | Aplat (v1) | Plan | Harmonique | Telea | FSR | Structurel | LaMa (IA) |
|---|---|---|---|---|---|---|---|
| Uni | **44,8** | 44,8 | 44,5 | 43,6 | 44,7 | 44,8 | 41,0 |
| Dégradé | 28,1 | 35,5 | **44,5** | 43,1 | 43,5 | 35,5 | 41,6 |
| Scan papier | 37,7 | 37,7 | 38,1 | 37,9 | **38,2** | 37,7 | 36,0 |
| Quadrillage | 24,5 | 24,9 | 25,0 | 24,6 | **28,8** | 20,2 | 29,1 |
| Texture / photo | 19,0 | 19,5 | 21,6 | 21,3 | **23,2** | 18,4 | 25,8 |
| Schéma (traits) | 26,0 | 25,6 | 26,5 | 26,5 | 30,3 | **36,7** | 31,8 |
| Temps médian / image | 3 ms | 5 ms | 40 ms | 7 ms | 0,3 s | 12 ms | 4,9 s |

Ce qu'on en retient :
- **Aplat** : parfait sur fond uni, « pansement » ailleurs.
- **Harmonique** (équation de Laplace, SciPy) : la meilleure sur dégradé.
- **FSR** (`cv2.xphoto.inpaint`, opencv-contrib) : meilleure méthode sans IA sur
  texture et quadrillage. Piège : son masque est inversé (0 = à reconstruire).
- **Structurel** : restitue 100 % d'une flèche droite (46,6 dB) ; échoue sur les
  courbes et dégrade le quadrillage (20 dB) : à n'utiliser que si le fond est
  calme hors des traits.
- **LaMa** : meilleure sur texture/photo, mais 25,8 dB reste un raccord
  visible ; moins bonne que l'aplat sur fond uni ; 700 fois plus lente.
- Telea et Navier-Stokes se valent (< 1 dB d'écart) : on garde Telea.

### Le choix : le « masque fantôme »

On ne sait pas d'avance quelle méthode convient. On le **mesure sur l'image
elle-même** :

1. On recopie la forme exacte du masque **à côté** de la zone, sur des pixels
   de fond qu'on connaît.
2. On remplit ce faux trou avec chaque méthode candidate.
3. On mesure l'erreur réelle de chacune contre les vrais pixels.
4. On applique au vrai trou la méthode qui a le mieux reconstruit le voisinage.

Comparaison des sélecteurs mesurés sur 108 zones (`exp2_selecteurs.csv`,
« perte » = écart moyen au meilleur choix possible) :

| Sélecteur | Perte moyenne | Zones à < 1 dB du meilleur | Temps / zone |
|---|---|---|---|
| **Masque fantôme** (sans IA) | **1,2 dB** | **85 %** | ~0,6 s médian (2 cœurs) |
| Règle corrigée (résidu de modèle de fond + traits traversants) | 1,7 dB | 72 % | 0,05 s |
| Toujours FSR (référence simple) | 1,95 dB | 70 % | 0,3 s |
| Règle « variance » (1re analyse) | 2,7 dB | 52 % | — |
| Score de couture (2e analyse) | 4,5 dB | 30 % | — |

Le score de couture et les règles par variance sont **abandonnés** : mesurés
moins bons que « toujours FSR ».

**Recommandation** :
- Candidats sans IA : aplat, plan, harmonique, Telea, FSR, structurel.
- Mode **fantôme** par défaut ; bascule en **règle corrigée** quand l'image a
  beaucoup de zones (une diapositive de 20 lignes × 0,6 s = 12 s : trop pour
  l'extension). Budget de temps par image, puis règle pour le reste.
- Repli si aucune position fantôme n'est disponible (texte collé au bord) :
  règle corrigée.
- **LaMa : non en première version.** Gain moyen 0,6 dB, +2,6 dB seulement sur
  photo ; 92 Mo de modèle et 4,9 s par tuile. À réévaluer pour les images
  photographiques (MI-GAN, licence MIT, plus léger, non testé).
- Marge connue : texte écrit **sur** une flèche (35,9 dB obtenus, 39,9
  possibles) — les positions fantômes ne contiennent pas la flèche.

---

## 7. Le rendu du texte traduit (images)

Pour les PDF, le moteur PDF dessine déjà la traduction ; la v2 ne lui ajoute
que la couleur. Pour les images, on dessine nous-mêmes (base : `effaceur.py`) :

- **Couleur** : celle du texte d'origine, mesurée par le masque (§5).
- **Taille** : élargir la boîte **jusqu'à 1,35 fois** avant de réduire la
  police (sinon « Refroidissement » devient illisible). Le français est 1,5 à
  3 fois plus long que le japonais : au-delà, retour à la ligne, puis
  réduction jusqu'à un plancher lisible ; sous le plancher, on garde
  l'original et l'extension affiche la traduction en info-bulle.
- **Alignement** à gauche pour les paragraphes.
- **Contour** contrasté si un trait passe dessous ou si le fond est chargé.
- **Police** : Noto Sans (latin + japonais, licence OFL), embarquée dans
  l'image Docker. Le banc utilise DejaVu (pas de japonais) : à remplacer.
- **Original conservé** : l'utilisateur peut toujours revenir à l'image
  d'origine (cas mesurés où aucune méthode n'atteint 25 dB : herbe, photo).

### 7.1 PDF scannés : garder le style d'origine (essai du 31/10)

**Règle (décision du 31/10)** : seule la détection du texte diffère entre un
scan et un document natif. Une fois le texte lu, le scan doit suivre
exactement le même chemin que le PDF natif (mêmes règles de découpage, de
traduction, de mise en page) et donner le même résultat. Aucune règle propre
aux scans dans le rendu. Le test de référence compare donc la traduction du
scan à celle du PDF natif, paragraphe par paragraphe et style par style.

Problème constaté sur un certificat scanné : la traduction perdait le gras
des valeurs (n° d'identifiant, date, e-mail), les tailles et l'italique des
mentions légales. Approche retenue : le scan devient un **PDF intermédiaire**
(fond effacé + texte invisible stylé), puis le **moteur PDF existant**
traduit ce PDF comme un PDF natif. Le style est mesuré sur les pixels :

- **Gras, mot par mot** : quantité d'encre par longueur de trait. Cette mesure
  ne dépend ni du flou ni de l'éclairage, contrairement à l'épaisseur seule
  (qui donnait de faux gras sur les « : »). Gras si > 1,3 × la référence de
  la taille ; une ponctuation isolée suit le mot voisin.
- **Taille** : hauteur des lettres à hampe (b, d, h, l…) mesurée mot par mot,
  moyennée par paragraphe, puis ramenée aux tailles fréquentes de la page
  (un pixel d'erreur vaut ~0,5 pt à 200 dpi, la moyenne l'efface).
- **Italique** : pente des traits, décidée par ligne.
- **Couleur** : médiane de l'encre ; un gris de scan redevient noir.
- **Police** : la famille dont la chasse colle le mieux aux largeurs
  mesurées (polices Unicode embarquées, qui conservent « ’ »). Le moteur
  réécrit la traduction dans cette police : une police plus étroite que
  l'originale fait tenir plus de mots par ligne. Exemple : « Without » fait
  29,3 pt en Inter (l'originale) et 26,8 pt en Roboto ; la traduction des
  mentions légales se coupait alors un mot plus loin que celle du natif.
- **Largeur** : chaque segment occupe exactement la largeur mesurée sur le
  scan, grâce à l'espacement des caractères (opérateur `Tc`), qui ne change
  pas la taille lue par le moteur (un étirement `Tz` la faisait passer de
  10 à 10,95 pt). Les bords se calent sur la chasse des lettres, pas sur
  l'encre : on ajoute les approches latérales du premier et du dernier
  glyphe. Chaque ligne se termine par une espace, comme dans un PDF de
  traitement de texte, car le moteur compte cette espace dans la largeur
  du paragraphe (3 pt de moins suffisaient à renvoyer un mot à la ligne).
- **Gras des mots courts** : l'amincissement raccourcit chaque bout de trait ;
  sans correction (0,2 épaisseur par extrémité), « Il » ou « a » passaient
  pour gras.

Résultat sur le scan simulé (200 dpi, 0,6° d'inclinaison, JPEG 80) : gras
juste sur 262 mots sur 262, tailles 6/8/10/16 pt toutes exactes, italique sur
les 8 bonnes lignes. Le moteur traduit autant de paragraphes depuis le scan
que depuis le PDF natif. Bord droit du dernier mot de chaque ligne : écart
médian 9,1 → 0,46 pt. Quand Inter fait partie des candidates, les 36 lignes
traduites du scan sont **identiques** à celles du natif. Avec les seules
polices du dépôt (Roboto, Open Sans, Montserrat, Merriweather, PT Serif), 30
sur 36, et la plus proche en largeur est Merriweather, une police à
empattements : choisir sur la seule largeur ne suffit pas.

Avec le vrai traducteur (document fictif, rien de personnel envoyé), le gras
interne survit, y compris en milieu de phrase (« five hundred euros ») ;
scan et natif ne diffèrent que par le choix des mots d'un appel à l'autre.

**Reste à faire (5.5)** : identifier la police d'un scan par la forme, pas
seulement la largeur. On rend chaque candidate sur quelques mots du scan et
on garde celle dont l'image ressemble le plus (cela tranche empattements ou
non, et la chasse). Les candidates sont les polices courantes des documents
de bureau et leurs clones libres (Inter, Arimo pour Arial, Carlito pour
Calibri, Tinos pour Times, Roboto, Open Sans, Lato, Noto Sans), obtenues par
le résolveur existant `engines/pdf/polices.py` (cache Google Fonts). Limite
connue : la taille déduite de la hauteur des hampes dépend de la police
(Helvetica 11 pt lue 10 pt sur le document fictif, exacte en Inter).

**Conception retenue (5.5a, 01/11)** — module `ocr_v2/render.py`, appelé
par `ocr.py` à la place de l'écriture en Helvetica :

| Option | Pour | Contre |
|---|---|---|
| Largeur seule (prototype) | rapide | choisit Merriweather (serif) pour un document sans serif |
| **Forme : rendre chaque candidate sur des mots du scan** | tranche serif / sans serif et la chasse en une mesure | ~0,1 s par candidate |
| Classifieur de polices appris | robuste | modèle à entraîner, poids, licence |

- **Redressement** : l'inclinaison est mesurée et corrigée *avant* la
  lecture (les boîtes lues sont alors droites, rien à recalculer).
- **Taille propre à chaque candidate** : la hauteur des hampes mesurée est
  divisée par la hauteur des hampes de la candidate (glyphes b, d, h, k, l),
  ce qui lève la limite « Helvetica 11 lue 10 ».
- **Score** : chaque mot échantillon (mots maigres, droits, de la taille la
  plus fréquente) est rendu à sa place (bord gauche de l'encre, ligne de
  base), à deux tailles : celle des hampes et celle calée sur la largeur du
  mot. Ressemblance = recouvrement des **squelettes** adoucis (Dice), au
  pixel près. Le squelette ignore l'épaisseur des traits, que le flou du scan
  grossit : comparer les encres faisait gagner la police la plus grasse.
- **Gras** : masse d'encre par longueur de trait, rapportée au corps ; seuil
  1,3 × la référence de la page (30ᵉ centile si ≥ 20 mots, sinon 0,094).
  **Italique** : pente médiane de la ligne > 0,07.
- **Limite mesurée** : deux empattements voisins restent confondus sur un
  scan à 200 dpi agrandi à 220 dpi (PT Serif lu Merriweather, écart 0,02).
  Le texte garde la hauteur et la largeur lues ; gras et italique restent
  justes ; seul le dessin des lettres diffère légèrement. Roboto, Open Sans
  et Merriweather sont reconnus dans tous les cas.
- **Temps** : écriture et choix de la police ~1,5–2 s par page (2 cœurs),
  réservés dans le budget de 90 s (coût fixe par page 1 → 3 s).
- **Candidates** : polices de bureau et clones libres déjà sur disque
  (`Resolveur.possede`, catalogue préchargé dans Docker) — aucun
  téléchargement pendant un envoi (délai de 90 s) ; les polices du dépôt
  (Roboto, Open Sans, PT Serif…) restent toujours disponibles.
- **Repli** : si aucune ligne n'est mesurable, écriture comme en v1.
- **Preuve** : test qui fabrique un document natif (Roboto, puis PT Serif),
  le « scanne » (flou, bruit, JPEG) et vérifie police, tailles, gras et
  italique ; puis comparaison scan traduit / natif traduit.

L'image traduite pour l'extension (§7) devient l'étape 5.5b.

### 7.2 Image traduite pour l'extension (5.5b, 01/11)

Exemple : une capture de leçon porte « 冷却水 » sur un schéma. L'extension
envoie l'image ; le serveur renvoie la même image où « Eau de
refroidissement » remplace le japonais, au même endroit, dans la couleur
d'origine. Le reste de l'image n'est pas touché.

Module `ocr_v2/image.py`, fonction `traduire_image(data, traduire, …)`. La
traduction est **injectée** (`traduire(liste de textes) → liste`) : la route
`POST /api/extension/image` (étape 6) y branchera le traducteur et le débit ;
le module reste testable sans réseau ni crédit.

| Option | Pour | Contre |
|---|---|---|
| Passer l'image par le PDF intermédiaire (§7.1) | un seul chemin | le moteur PDF met en page des paragraphes de document, pas des étiquettes de schéma ; renvoyer une image demanderait de rasteriser |
| **Dessin direct sur l'image (§7)** | place exacte, aucune conversion, rapide | code de mise en place propre aux images |

Choix : dessin direct. La règle « même chemin que le natif » du §7.1 vaut
pour les PDF ; une image n'a pas d'équivalent natif.

- **Contrôles avant décodage** (§9) : type réel lu dans l'en-tête (PNG, JPEG,
  WebP, GIF non animé ; le JPEG « MPO » des smartphones compte comme JPEG),
  ≤ 10 Mo, ≤ 25 Mpx ; refus avec un code
  (`type`, `taille`, `pixels`, `animee`) que la route traduira en message.
- **Lecture** : PP-OCRv6 (Tesseract n'a pas le japonais : pas de repli ;
  sans les poids, `LectureEchouee`, la route répondra 503). **Honnêteté** : une ligne lue
  avec une confiance < 70 n'est ni effacée ni traduite.
- **Blocs** : les lignes voisines (même hauteur à 30 % près, écart vertical
  entre −0,3 et 0,8 hauteur car les boîtes PP-OCR débordent, recouvrement
  horizontal) forment un bloc traduit d'un seul
  tenant ; mots joints sans espace pour le japonais et le chinois.
- **Mise en place** : couleur = médiane des pixels du masque ; police Noto
  Sans (repli Roboto du dépôt) à la hauteur des lignes d'origine ; boîte
  élargie jusqu'à 1,35 fois (dans l'image), retour à la ligne (dans la
  hauteur du bloc : une étiquette d'une ligne ne déborde pas sur ce qui est
  dessous), puis
  réduction jusqu'à un plancher (60 % de la taille d'origine, 9 px au
  moins). Sous le plancher : le bloc **n'est pas effacé**, l'original reste
  et sa traduction est renvoyée pour l'info-bulle.
- **Contour** de la couleur opposée si un trait traverse ou si le fond est
  chargé (indicateurs de `erase.py`).
- **Sortie** : même format que l'entrée (JPEG qualité 92, sinon PNG), canal
  alpha et profil couleur conservés ; si rien n'est remplacé, l'original
  revient tel quel ; plus la liste des blocs (texte, traduction, boîte,
  remplacé ou non). `remplacee` vaut vrai si au moins un bloc a été dessiné :
  c'est ce qui déclenche le débit d'un crédit (décision du 31/10).
- **Temps** : lecture puis effacement dans un délai global (30 s par défaut,
  fantôme puis règle comme pour les scans).
- **Preuve** : test sur images générées (lecteur simulé, puis PP-OCRv6 si les
  poids sont là) : la traduction est relue au bon endroit, le texte d'origine
  a disparu, un bloc trop long garde l'original, les contrôles refusent.

**Revue de code (01/11)** — 10 écarts :

| # | Écart | Statut |
|---|---|---|
| 1 | `_contour` : masque pleine page par bloc | corrigé (recadrage `zones_par_boite`) |
| 2 | JPEG de smartphone (MPO) refusé | corrigé |
| 3 | Lignes PP-OCR qui se chevauchent non réunies | corrigé (écart ≥ −0,3 h) |
| 4 | Lecteur chargé deux fois, polices partagées entre fils | corrigé (verrou, police par fil) |
| 5 | Profil couleur perdu, ré-encodage sans remplacement | corrigé |
| 6 | Une étiquette d'une ligne ne passe jamais à la ligne | rejeté : déborderait sur le contenu dessous, non mesuré ; l'info-bulle couvre le cas |
| 7 | Retours à la ligne du traducteur dessinés tels quels | corrigé (normalisés) |
| 8 | Regroupement dupliqué de `render.paragraphes` | rejeté : celui-ci part de la taille et de la ligne de base mesurées, absentes ici |
| 9 | Seuil de texture recopié | corrigé (`erase.T_TEX`) |
| 10 | PNG temporaire sur disque avant lecture | corrigé (`PPOCR.lire_image`) |

---

## 8. Le banc d'essai : prouver sans documents réels

Repris du banc fourni, principe inchangé : chaque image est fabriquée deux
fois, sans texte (vérité) et avec texte ; on efface, on compare au vrai fond.

- 12 cas, 6 familles : uni (clair, sombre), dégradé (linéaire, radial), scan
  papier, quadrillage, texture/photo, schéma (flèche, cercle, tableau). Bruit de
  capteur identique sur l'image et la vérité.
- Mesures : PSNR et SSIM dans les boîtes, part des traits conservés, résidu de
  lettres, taux de mots trouvés par la détection, temps.
- Ajouts v2 : cas **japonais** (police Noto) et cas « texte sur trait » pour
  mesurer PP-OCRv6 contre Tesseract.
- Images générées à l'exécution, aucun fichier sous droits. La photo de café
  du banc : vérifier sa provenance avant de la versionner, sinon la remplacer
  par une texture générée.
- SSIM en numpy dans les tests (pas de scikit-image en production). Tourne
  dans Docker.

Seuils de non-régression (tirés des mesures du banc) :

| Critère | Seuil |
|---|---|
| Sélecteur fantôme, perte moyenne sur 108 zones | ≤ 1,5 dB |
| Fond uni et dégradé | ≥ 40 dB |
| Flèche droite sous le texte | 100 % du trait conservé |
| Détection sur fond propre (uni, sombre, scan, tableau) | 100 % des mots |
| Détection sur fond chargé avec PP-OCRv6 | objectif > Tesseract (0 %) ; **mesuré 94 %** (§4) |
| Japonais : erreur par caractère | objectif ≤ 10 % ; **mesuré 0 %** sur 5 lignes synthétiques |

Limite assumée par l'analyse : ce sont des images synthétiques. Les seuils de la
règle corrigée sont à recalibrer sur de vraies images (le masque fantôme n'a
pas de seuil). Un premier jeu réel : les captures du cours cible.

**Mesuré (31/10, `backend/tests/banc_effacement.py`, textures générées, police
Montserrat)** : 108 zones, perte moyenne 0,86 dB face au meilleur choix
possible, 0,8 s/zone ; uni 45,1 dB, sombre 45,2, dégradés 44,6-44,9 ; flèche
droite et tableau 100 % des traits gardés. Les moindres carrés en deux passes
ne coûtent rien (0,90 dB sans eux). Points faibles, sous les seuils mais à
suivre : brique 17,5 dB (le meilleur choix ne fait que 18,0 : limite des
méthodes sans IA), schémas 2 à 4 dB sous le meilleur choix (`structurel`
choisi d'office par la règle), cercle de `schema_boite` gardé à 34 %.

**Branché dans `ocr.py` (01/11)** : masque corrigé (une lettre qui touche le
bord de sa boîte, ou un fût de lettre long, n'est plus pris pour un trait).
Le banc passe à 0,93 dB, flèche droite 99 %. Mesures sur une page A4 simulée
(88 mots, conteneur 2 CPU), comparées à la v1 (aplat de rectangle) :

| Fond | v1 | v2 |
|---|---|---|
| Uni | 138 dB, 7 s | 138 dB, 26 s |
| Dégradé | 53,8 dB | 56,2 dB |
| Texte reconnu | identique | identique |

Le fantôme (la méthode la plus sûre, mais la plus lente) prend tout le temps
disponible de la page. Chaque page reçoit une part du délai de 90 s, après
déduction de la lecture des pages suivantes. Passé ce temps, les zones
restantes passent par la règle, puis sont remplies sans analyse. Résultat :
3 pages en 78 s en qualité maximale, 10 pages en 85 s (v1 : 65 s) avec une
qualité dégradée sur les dernières zones, sans échec.

---

## 9. Impacts

| Domaine | Impact |
|---|---|
| Données / migrations | Aucun changement de schéma pour les PDF. Images de l'extension : non conservées (voir étude extension) |
| Sécurité | Image reçue = fichier non fiable : contrôle du type réel, plafond de taille et de pixels avant décodage (`Image.MAX_IMAGE_PIXELS`), aucun téléchargement d'URL côté serveur |
| Performance | Fantôme ~0,6 s par zone sur 2 cœurs : budget par image + bascule en règle (§6). ONNX Runtime et OpenCV limités à 1 fil comme Tesseract ; le sémaphore unique reste |
| Dépendances Python | + `opencv-contrib-python-headless` (FSR, Telea, Hough), + `scipy` (harmonique), + `onnxruntime` (PP-OCRv6). Pas de scikit-image ni pandas en production |
| Déploiement | Image Docker : + ces paquets, + modèle PP-OCRv6 small (31 Mo, téléchargé au build, SHA-256 contrôlé), + Noto Sans CJK. Ordre de grandeur **+150 à 200 Mo** (sans LaMa). À mesurer sur la machine de staging |
| Coûts | CPU seulement, pas d'appel IA de plus pour l'OCR ; la traduction du texte lu reste facturée comme aujourd'hui |
| i18n | Messages d'erreur existants réutilisés ; nouveaux messages fr/en pour les images |
| Licences | OpenCV Apache-2.0 depuis 4.5.0 ; Tesseract, PaddleOCR, ONNX Runtime Apache-2.0 ; Noto OFL ; poids PP-OCRv6 Apache-2.0 (vérifié). À vérifier : LaMa (Apache-2.0 pour le dépôt, fichier ONNX du Zoo non explicite) seulement s'il est retenu |

---

## 10. Risques

1. **Détection sur fond chargé** : c'est le risque n°1, mesuré (Tesseract à
   0 %). PP-OCRv6 lit 94 % des mots sur fond chargé du banc ; reste à confirmer
   sur de vraies captures. Un trait qui traverse peut coller deux mots. Parade : règle
   d'honnêteté — ce qui n'est pas lu avec certitude n'est pas touché.
2. **Temps de calcul** du fantôme sur les images denses. Parade : budget +
   bascule en règle (0,5 dB de moins en moyenne).
3. **Traductions trop longues** : boîte élargie à 1,35×, plancher de taille,
   sinon original + info-bulle.
4. **Poids de l'image Docker** sur la machine actuelle : mesuré dès l'étape 1.
5. **Régression sur les PDF fr/en** : Tesseract y reste le moteur, les tests
   OCR existants doivent passer à l'identique.

---

## 11. Phasage

1. Banc d'essai repris dans `backend/tests/` (Docker), avec la v1 comme
   référence chiffrée.
2. Interface `Recognizer` + Tesseract (aucun changement de résultat).
3. Masque couleur + effacement par masque fantôme (aplat, plan, harmonique,
   Telea, FSR, structurel) : les PDF scannés en profitent immédiatement.
4. PP-OCRv6 en ONNX : détection sur fond chargé et japonais, mesurée sur le banc.
5. Rendu d'image traduite + point d'entrée pour l'extension.

Chaque étape est mesurée sur le banc avant la suivante.

---

## 12. Points à trancher

1. **Poids** : accepter ~+150 à 200 Mo dans l'image Docker pour OpenCV, SciPy,
   ONNX Runtime et PP-OCRv6 ? (recommandé : oui ; LaMa non, pour l'instant)
2. **Japonais** : langue *source* officielle du produit (affichée sur le
   site), ou seulement pour l'extension au début ?
3. **Prix d'une image traduite** : voir l'étude extension.

### Décisions (31/10/2026)

1. Poids accepté : OpenCV contrib, SciPy, ONNX Runtime, PP-OCRv6 *small*, Noto Sans. LaMa non retenu.
2. Japonais : d'abord pour l'extension (images de pages web) ; il ne sera annoncé comme langue source des documents qu'après mesure sur le banc.
