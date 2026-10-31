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
| **PP-OCRv6** (PaddleOCR 3.7, juin 2026) via ONNX Runtime | un modèle : chinois, anglais, **japonais**, 46 langues latines (dont français) | Apache-2.0 (code) ; licence des poids **à vérifier** | `onnxruntime` + modèle *small* (7,7 M paramètres) | Détecteur neuronal (type DBNet) conçu pour le texte de scène ; un seul modèle fr/en/ja ; ONNX publié | Chiffres de l'éditeur seul ; à mesurer sur le banc |
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
| Détection sur fond chargé avec PP-OCRv6 | à mesurer ; objectif > Tesseract (0 %) |
| Japonais : erreur par caractère | à mesurer, objectif ≤ 10 % |

Limite assumée par l'analyse : ce sont des images synthétiques. Les seuils de la
règle corrigée sont à recalibrer sur de vraies images (le masque fantôme n'a
pas de seuil). Un premier jeu réel : les captures du cours cible.

---

## 9. Impacts

| Domaine | Impact |
|---|---|
| Données / migrations | Aucun changement de schéma pour les PDF. Images de l'extension : non conservées (voir étude extension) |
| Sécurité | Image reçue = fichier non fiable : contrôle du type réel, plafond de taille et de pixels avant décodage (`Image.MAX_IMAGE_PIXELS`), aucun téléchargement d'URL côté serveur |
| Performance | Fantôme ~0,6 s par zone sur 2 cœurs : budget par image + bascule en règle (§6). ONNX Runtime et OpenCV limités à 1 fil comme Tesseract ; le sémaphore unique reste |
| Dépendances Python | + `opencv-contrib-python-headless` (FSR, Telea, Hough), + `scipy` (harmonique), + `onnxruntime` (PP-OCRv6). Pas de scikit-image ni pandas en production |
| Déploiement | Image Docker : + ces paquets, + modèle PP-OCRv6 small, + Noto Sans CJK. Ordre de grandeur **+150 à 200 Mo** (sans LaMa). À mesurer sur la machine de staging |
| Coûts | CPU seulement, pas d'appel IA de plus pour l'OCR ; la traduction du texte lu reste facturée comme aujourd'hui |
| i18n | Messages d'erreur existants réutilisés ; nouveaux messages fr/en pour les images |
| Licences | OpenCV Apache-2.0 depuis 4.5.0 ; Tesseract, PaddleOCR, ONNX Runtime Apache-2.0 ; Noto OFL. À vérifier : licence des poids PP-OCRv6 ; LaMa (Apache-2.0 pour le dépôt, fichier ONNX du Zoo non explicite) seulement s'il est retenu |

---

## 10. Risques

1. **Détection sur fond chargé** : c'est le risque n°1, mesuré (Tesseract à
   0 %). Si PP-OCRv6 ne fait pas nettement mieux sur le banc, les images de
   diapositives resteront partiellement traduites. Parade : règle
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
