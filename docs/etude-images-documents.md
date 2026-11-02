# Étude : traduire aussi les images d'un document (PDF, DOCX, PPTX, XLSX non scannés)

*01/11/2026 — étape 6.8 du plan. Étude avant code.*

## 1. Besoin

Un document « normal » (texte sélectionnable) contient souvent des images qui
portent du texte : schéma légendé, capture d'écran, tableau collé en image,
étiquette sur une photo. Aujourd'hui le texte du document est traduit, mais ces
images reviennent **dans la langue d'origine**.

Demande du 01/11 : faire comme l'extension.
1. Analyser le document et repérer les images qui contiennent du texte.
2. Demander à l'utilisateur s'il veut aussi les traduire, en montrant le coût
   **sans** images et **avec** images.
3. S'il accepte, rendre le document avec les images traduites.

Exemple concret : un manuel de 12 pages avec 7 schémas légendés en anglais.
Avant le lancement, l'écran indique « Sans les images : 12 pages — Avec les
7 images : 19 pages ». L'utilisateur coche ou non, puis lance.

## 2. Existant

| Brique | Où | Réutilisable ? |
|---|---|---|
| Traduction d'une image (lire, effacer, réécrire, mise en page comme le PDF) | `backend/app/services/ocr_v2/image.py` `traduire_image(data, traduire)` → `ImageTraduite` (`remplacee`, `data`, `mime`, `blocs`) | **Oui, tel quel.** Déjà éprouvé par l'extension (6.4a, 6.4c) |
| Détection seule (sans lecture) | `ocr_v2/ppocr.py` `PPOCR._detecter` | Oui, pour l'analyse rapide |
| Règle de prix image | `app/api/extension.py:77` : 1 page par image **remplacée**, 0 sinon ; contrôle de couverture avant, débit après | Oui, même règle (cohérence entre produits) |
| Lancement d'une traduction | `POST /api/translate` (`app/api/translate.py:159`) : compte les pages, contrôle et débite sous verrou **avant** de traduire, 402 `need_credits` sinon | À étendre : un champ `images` |
| Comptage | `services/documents.py` `count_pages` (PDF/PPTX : pages ; DOCX/XLSX : volume de texte) | Inchangé ; les images s'ajoutent à côté |
| Devis argent | `POST /api/payments/quote` (`app/api/payments.py:96`) | Inchangé : il prend un nombre de pages |
| Images dans le PDF | `engines/pdf/engine.py:3238-3270` (extraction : `xref` + octets), `_draw_image` `:3487` (réinjection depuis les octets ou le `xref` du source) | Un point unique pour substituer les octets traduits, par `xref` |
| Images DOCX/PPTX/XLSX | parties `word/media/`, `ppt/media/`, `xl/media/` du paquet | Remplacement de la partie, même nom et même format, après traduction du texte. Le PPTX remplace déjà des médias ainsi (aperçus OLE, `engines/pptx/engine.py:1226`) |
| Interface | `frontend/src/pages/Home.tsx` → `StorySection` : dépôt puis lancement direct ; **aucune étape d'analyse avant lancement** ; le coût n'apparaît qu'en cas de 402 | À étendre |

## 3. Mesure sur les documents d'essai

Script `mesure_images.py` (scratchpad), PDF du dossier `tests files`,
détection PP-OCR puis lecture des images où quelque chose est détecté :

| Document | Pages | Images distinctes | Avec texte lu | Détection (toutes) | Lecture (celles avec texte) |
|---|---|---|---|---|---|
| mv21.pdf | 84 | 5 | 1 | 1,3 s | 2,1 s |
| CD26052553710.pdf (2 p.) | 2 | 6 | 4 | 0,2 s | 1,7 s |
| The Data Science Handbook | 285 | 31 | 3 | 2,4 s | 1,9 s |

Ce qu'on en tire :
- **L'analyse est rapide** : 0,05 à 0,25 s par image en détection seule. Un
  document de 300 pages s'analyse en quelques secondes : on peut l'afficher avant
  le lancement sans faire attendre.
- **Peu d'images portent du texte** (1 sur 5, 3 sur 31) : le surcoût est en
  général faible, ce qui rend la question « avec ou sans » simple à trancher pour
  l'utilisateur.
- **Les logos comptent** : sur la facture CD26, 4 images sur 6 « ont du texte »
  et ce sont surtout des logos et des marques. Ils ne doivent pas être payés pour
  rien : la traduction d'un nom propre revient identique, l'image n'est alors
  **pas remplacée** et donc **pas facturée** (règle de l'extension). Le devis
  « avec images » est donc un **maximum**, pas un montant certain.
- La traduction complète d'une image (lecture + traduction + rendu) coûte
  quelques secondes ; elle se fait dans le travail de fond existant, pas dans la
  requête.

## 4. Options

### 4.1 Quand analyser

| Option | Pour | Contre |
|---|---|---|
| **A. Au dépôt du fichier**, nouvelle route `POST /api/translate/analyse` (renvoie pages texte + images à texte) | Le choix et les deux coûts sont visibles avant de lancer, comme demandé ; détection rapide (§3) | Le fichier est envoyé deux fois (analyse puis lancement) ; résultat gardé par empreinte du fichier pour ne pas refaire |
| B. Au lancement, réponse « images détectées » à confirmer (comme le 402) | Pas de nouvelle route | L'utilisateur clique « Traduire » puis doit répondre à une question : parcours en deux temps, moins clair |
| C. Ne rien demander, traduire toujours les images | Simple | Contraire à la demande ; débit surprise |

### 4.2 Comment facturer

| Option | Pour | Contre |
|---|---|---|
| D1. Débiter toutes les images détectées au lancement | Simple, même moment que le texte | Fait payer les images non remplacées (logos) : contraire à la règle de l'extension |
| **D2. Contrôler au lancement que le solde couvre texte + images détectées ; débiter le texte au lancement (comme aujourd'hui) et les images au moment de les poser, une page par image distincte réellement remplacée** | Honnête (on ne paye que ce qui change), même règle que l'extension, pas besoin d'un circuit de remboursement | Si le solde a baissé entre-temps (autre traduction en parallèle), une image traduite ne peut pas être débitée : elle reste alors en original (jamais de travail livré non payé) |
| D3. Réserver texte + images au lancement, rembourser le non-remplacé | Montant connu d'avance | Le remboursement n'existe pas (quota du forfait en lignes `usages`) : chantier à part |

### 4.3 Intégration dans les moteurs

| Format | Point d'accroche | Remarque |
|---|---|---|
| PDF | Table `{xref → octets traduits}` lue par `_draw_image` | Une image répétée (logo sur chaque page) = un seul `xref` : traduite et payée une fois |
| DOCX / PPTX / XLSX | Remplacer la partie `…/media/imageN.ext` dans le paquet de sortie | Même nom, même format (`traduire_image` garde le format) ; image partagée entre diapositives = une seule partie |

Exclus de la v1 : images vectorielles (EMF, WMF, SVG — refusées par
`verifier`), images animées, pages scannées (déjà traitées par l'OCR de page),
images sous la taille minimale de lecture.

## 5. Recommandation

**A + D2**, intégration par format comme au §4.3.

- **Analyse au dépôt** : `POST /api/translate/analyse` (connexion obligatoire,
  mêmes limites de taille que `/api/translate`) → `{pages, images: n,
  apercus: [...]}` ; détection seule, bornée en temps (au-delà : « analyse
  incomplète », les images non analysées ne sont pas proposées). Résultat
  gardé par empreinte du fichier.
- **Écran** : sous le fichier déposé, une ligne « 7 images contiennent du
  texte » avec une case « Traduire aussi les images », et les deux totaux :
  « Sans les images : 12 pages · Avec : jusqu'à 19 pages ». Le mot « jusqu'à »
  et une info-bulle expliquent qu'une image dont rien ne change n'est pas comptée.
  Si aucune image n'a de texte : rien ne s'affiche.
- **Lancement** : champ `images=1` ; contrôle de couverture texte + n ; 402
  `need_credits` inchangé (il proposera d'acheter ce qui manque, images comprises).
- **Traitement** : les images sont traduites dans le travail de fond (même
  file, même sémaphore OCR), débitées une par une au moment de la pose ; cache
  par empreinte d'image + langue ; clé de cache du document suffixée `_img`.
- **Rapport** : à la fin, « 5 images traduites sur 7 (2 inchangées, non
  comptées) ».

## 6. Impacts

| Domaine | Impact |
|---|---|
| Données | Aucune migration : le débit utilise `debiter` et `usage.record` existants |
| Sécurité | Nouvelle route authentifiée ; mêmes contrôles de paquet que `office_cost` (taille décompressée, chemins) ; images passées par `verifier` (taille, pixels, format) |
| Performance | Analyse : ~0,1 s/image. Traduction : quelques secondes par image à texte, dans le travail de fond ; sémaphore OCR partagé avec les scans |
| Coût | Un appel au moteur de traduction par image à texte (petits textes) |
| i18n | Textes de l'écran en FR/EN comme le reste de `StorySection` |
| Déploiement | Rien de neuf : PP-OCR et polices sont déjà requis par l'extension |

## 7. Risques

- **Logos et noms propres** : détectés « avec texte », ils gonflent le maximum
  affiché. Atténué par « jusqu'à » et la non-facturation des images inchangées.
- **Mise en page** : une traduction trop longue ne tient pas toujours dans
  l'image (limite connue, étude OCR v2 §7.3-7.4) ; le bloc concerné reste en
  original.
- **Double envoi** du fichier (analyse puis lancement) : acceptable jusqu'à
  100 Mo ; évité si l'on stocke le dépôt (hors v1).
- **Solde consommé entre-temps** : image laissée en original et signalée dans
  le rapport.

## 8. Points à trancher par l'utilisateur

1. **Prix** : 1 page par image remplacée, comme l'extension ? *(recommandé : oui)*
2. **Case cochée par défaut ?** *(recommandé : non — pas de débit surprise ;
   l'utilisateur coche s'il veut les images)*
3. **Choix image par image** (vignettes à cocher) ou **tout ou rien** en v1 ?
   *(recommandé : tout ou rien en v1, vignettes plus tard)*
4. **Essai gratuit / forfait gratuit** : les images comptent-elles sur la même
   couverture que le texte ? *(recommandé : oui, même règle)*

### Décisions du 01/11/2026

1. **1 page par image remplacée**, comme l'extension.
2. **Case non cochée** par défaut.
3. **Tout ou rien au lancement, puis annulation image par image sur chaque
   page** : si la détection a échoué ou si la traduction est de mauvaise
   qualité, l'utilisateur remet l'image d'origine sur la page concernée.
   Conséquences : le serveur garde, pour chaque document, la table
   `{clé d'image → original, traduite}` ; une route reconstruit le document
   avec l'image d'origine à cet endroit (PDF : `_draw_image` sans la
   substitution de ce `xref` ; Office : partie média d'origine remise) ;
   l'aperçu de la page affiche, sur chaque image traduite, « Remettre
   l'original ». Défaut retenu (à corriger si besoin) : la page de l'image
   annulée **n'est pas rendue** en v1, le travail ayant été fait ; une image
   partagée (logo répété) est remise partout où elle apparaît.
4. **Même règle en gratuit** : une image traduite consomme une page de la
   couverture, comme le texte.

## 9. Plan

1. Backend — analyse : `services/images_document.py` (`lister(data, ext)` →
   images distinctes avec leur clé : `xref` ou nom de partie ; `detecter` →
   celles à texte), route `/api/translate/analyse` ; tests (PDF, DOCX, PPTX,
   XLSX, logo répété, image vectorielle exclue).
2. Backend — traduction et pose : table de substitution dans `_draw_image` (PDF),
   remplacement des parties média (Office) ; débit à la pose ; champ `images` de
   `/api/translate`, contrôle de couverture texte + n ; tests.
3. Frontend : appel d'analyse au dépôt, case et deux totaux, rapport final ;
   `tsc`, lint, build ; essai Playwright.
   Décision de réalisation (02/11/2026) : option désactivée avec une plage de
   pages. Le serveur compte les images du document entier, l'utilisateur
   paierait donc des images hors de sa sélection.
4. Annulation par image : table original/traduite gardée avec le document,
   route de reconstruction avec l'original d'une image, bouton « Remettre
   l'original » sur l'aperçu de la page ; tests.
5. Vérification de bout en bout sur un DOCX et un PDF à schémas.

### 9.1 Conception de la pose (6.8.2)

- **Table à côté de la traduction** : `<traduction>.images.json` (rapport et
  clé d'image → fichier) et dossier `<traduction>.images/`, un fichier par
  image traduite. Le rendu la relit à chaque appel ; elle suit la traduction
  (le balayage du magasin ne la garde que si la traduction existe).
- **Suffixe `_img`** : un document lancé avec `images=1` a sa propre
  traduction (`..._img`), donc ses propres rendus et sa propre table. S'il
  existe déjà une traduction texte seul, elle est copiée : le texte déjà
  payé n'est pas retraduit.
- **Budget lu avant, débit unique après** : la route compare texte + n images
  à la couverture (402 `need_credits`, avec `images_needed`). Le job lit le
  budget restant, ne traduit que les images qu'il couvre (`sans_credit` pour
  les autres), puis débite d'un coup les images réellement remplacées, lié au
  document (remboursé si le document échoue). Un cache disque par empreinte
  évite de relire ou de repayer une même image.
- **Échec d'image ≠ échec du document** : une image illisible ou non
  traduite reste en original (`echecs`) ; une image sans texte à remplacer
  ne coûte rien (`inchangees`). Le document finit toujours.
- **Bêta et mode debug hors v1** : images ignorées. Idem pour un PDF préparé
  par l'OCR des scans, dont les `xref` ne sont plus ceux de l'original.
- **Limites constatées** : les aperçus partiels PPTX/XLSX posent les images
  mais restent bâtis sur l'original ; un GIF ou WEBP remplacé ressort en PNG
  dans une partie d'extension différente ; le XLSX n'est pas re-rendu à la
  volée (`render_translation_bytes`) ; le cache `images/` est partagé et non
  purgé.
