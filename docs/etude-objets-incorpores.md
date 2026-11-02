# Étude — Objets incorporés : traduire leur contenu et régénérer leur aperçu

*01/11/2026 — étape 6.11 du plan. Étude avant code.*

Un « objet incorporé » est un fichier rangé à l'intérieur d'un autre. Par exemple, un tableau Excel placé dans une diapositive, un document Word inséré dans une page Word, ou un graphique. Dans le document, on ne voit pas directement l'objet : on voit une **image d'aperçu** que Office a enregistrée au moment de l'insertion. Le contenu réel n'apparaît que si l'on double-clique dessus.

Chaque cas pose donc deux questions :

1. **Le contenu de l'objet est-il traduit ?** Si non, le client double-clique sur le tableau et retombe sur la langue d'origine.
2. **L'aperçu est-il refait dans la langue cible ?** Si non, la diapositive traduite affiche une image du tableau en langue d'origine, et c'est ce que tout le monde voit à l'écran comme à l'impression.

Règle retenue : l'aperçu est **régénéré à partir du fichier incorporé traduit** (on le « redessine »). Il n'est jamais traduit par OCR. L'OCR lit une image et colle du texte par-dessus, alors que le redessin reprend les vraies cellules, polices et colonnes du fichier traduit.

---

## 1. Besoin et contraintes

- **Où ça tourne** : Linux sous Docker. Les tests se font dans les mêmes limites que la production : `docker run --cpus 2 --memory 3g`.
- **Pas de Microsoft Office en production** (pas d'automatisation COM sous Windows), sauf s'il existait une solution Docker Linux sérieuse. Le § 4 montre qu'il n'en existe pas.
- **Au mieux, sans jamais casser** : si un objet ne peut pas être traité, le document est quand même livré. L'objet garde alors son contenu et son aperçu d'origine, et l'incident est noté dans le journal. Aucun document ne doit échouer à cause d'un objet incorporé.
- **Sécurité** : un objet incorporé est un fichier fourni par le client, donc non fiable. Les mêmes garde-fous que pour les images s'appliquent (taille, nombre d'entrées, profondeur d'imbrication).
- **Équité de facturation** : on ne fait pas payer ce qui n'est pas traduit. Le prix ne doit pas non plus surprendre le client (voir § 6).

---

## 2. Existant

Ce tableau mesure ce que fait le code aujourd'hui.

| Conteneur | Objet incorporé | Contenu traduit ? | Aperçu régénéré ? | Où |
|---|---|---|---|---|
| PPTX | Classeur Excel (`.xlsx`/`.xlsm`, relation `package`) | **Partiellement** : seul `xl/sharedStrings.xml` est traité, et seulement si le filtre « tableaux » est actif. Les noms d'onglets, les cellules `inlineStr`, les graphiques, les commentaires et les dessins du classeur restent en langue d'origine. | **Oui**, par LibreOffice, mais la feuille est rendue **entière** au lieu de la zone visible de l'objet (`oleSize`). | `backend/engines/pptx/engine.py:338-347`, `:377-398` (`_process_excel_file`), `:594-625` (`_inject_excel_file`), `:1087-1281` (`regenerate_ole_previews`), `:1283-1342` (mise à l'échelle sur une page) |
| PPTX | Document Word (`.docx`) | Non | Non (le filtre `progId` ne garde que « Excel », `:1136`) | `engine.py:1136` ; limite notée dans `backend/engines/pptx/CONTEXTE.md:98` |
| PPTX | Présentation PowerPoint (`.pptx`) | Non | Non | idem |
| PPTX | Ancien format binaire (`oleObject*.bin`, OLE2 : `.xls`, `.doc`, `.ppt` des versions 97-2003) | Non | Non | aucun code |
| PPTX | Graphique natif (`ppt/charts/chart*.xml`) | **Partiellement** : titres et texte riche (`a:p`). Les noms de séries et de catégories (`c:strCache`) ne le sont pas, ni le classeur caché derrière le graphique. | Sans objet (PowerPoint dessine le graphique lui-même à l'ouverture), mais les libellés non traduits restent visibles. | `engine.py:307-320` |
| DOCX | Tout objet incorporé (`word/embeddings`, `w:object`) | Non | Non | `backend/engines/docx/engine.py:240-270` (seuls le corps, les zones de texte, les en-têtes, les pieds de page et les SmartArt sont lus) |
| DOCX | Graphique natif (`word/charts`) | **Non**, pas même le titre | Sans objet | idem |
| XLSX | Tout objet incorporé (`xl/embeddings`) | Non | Non | `backend/engines/xlsx/engine.py:68-133` (liste des parties lues) |
| XLSX | Graphique natif (`xl/charts`) | **Oui** pour les titres, les axes et les libellés écrits en dur. Les caches ne sont pas traduits, mais Excel les recalcule à partir des cellules, qui elles sont traduites. | Sans objet | `xlsx/engine.py:741-840` |
| Tous | Objet **lié** (fichier externe, `TargetMode="External"`) | Non, et c'est normal : le fichier n'est pas dans le document | Non | — |

À retenir de l'existant, pour le réutiliser :

- `backend/engines/office.py` est l'unique point d'appel de LibreOffice. Il fournit `find_soffice()`, `profil_argument()` (profil partagé) et `preview_lock` (un seul rendu à la fois).
- `regenerate_ole_previews` fait déjà le plus dur :
  - il lit le ratio du cadre dans `p:xfrm/a:ext` ;
  - il rend tous les classeurs en **un seul** appel LibreOffice ;
  - il rogne l'image en conservant la transparence ;
  - il complète l'image au ratio du cadre, en la centrant ;
  - il **rebranche toutes les relations**, y compris la branche VML (`mc:Choice`) que PowerPoint affiche réellement (`:1242-1265`) ;
  - il supprime les anciens EMF devenus orphelins.

  Il est appelé dans un `try/except`, ce qui en fait un traitement « au mieux » (`engine.py:574-580`).
- Le test `backend/tests/test_ole_apercu.py` est entièrement synthétique : PDF et classeur sont fabriqués à la volée, sans LibreOffice. C'est le modèle à suivre pour les tests.
- L'ancien chemin COM/PowerShell (`engine.py:24-150`, `_auto_refresh_powerpoint`) est abandonné, car il ne fonctionne que sous Windows avec PowerPoint installé.
- Le Dockerfile de production (`backend/Dockerfile:41-45`) installe `libreoffice-writer`, `libreoffice-impress` et `libreoffice-calc`. **Draw** (nécessaire pour Visio et l'import de PDF) et **Math** (équations) n'y sont pas.
- Le module images (6.8) ignore les images vectorielles (`VECTORIELLES`, `backend/app/services/images_document.py:51`). Un aperçu EMF n'est donc jamais passé à l'OCR. Un aperçu **PNG** pourrait l'être, ce qui risque un double traitement (voir § 3, cas 14).

---

## 3. Inventaire de toutes les combinaisons et solution proposée

Les **conteneurs** sont DOCX, XLSX et PPTX. Les **objets** possibles sont : classeur, document, présentation, graphique, Visio, PDF, équation, « paquet » (fichier quelconque), en format moderne (OOXML) ou ancien (OLE2 `.bin`), et incorporés ou liés.

Les trois conteneurs déclarent leurs objets de façon différente, mais un objet se reconnaît toujours de la même manière : par son **type de relation** (`.../package` pour un fichier OOXML, `.../oleObject` pour un `.bin`), par son **progId** (`Excel.Sheet.12`, `Word.Document.12`, `PowerPoint.Show.12`, `Visio.Drawing.15`, `AcroExch.Document`, `Equation.3`, `Package`…) et par l'extension du fichier.

| # | Cas | Exemple concret | Solution proposée |
|---|---|---|---|
| 1 | Excel dans PPTX | Tableau de chiffres sur une diapo | Traduire le classeur avec le **vrai moteur XLSX** (onglets, cellules, graphiques, commentaires), et non plus seulement `sharedStrings`. Redessiner l'aperçu sur la **zone visible** (`oleSize`, méthode CFAO, § 4). |
| 2 | Excel dans DOCX | Tableau budgétaire dans un rapport Word | Même traitement. Le ratio du cadre se lit dans `v:shape style="width:…;height:…"` ou `w:object w:dxaOrig/w:dyaOrig`. Il faut rebrancher `v:imagedata r:id`. |
| 3 | Excel dans XLSX | Classeur dans un classeur | Même traitement. Le cadre se lit dans `xdr:oleObject` / `xdr:anchor` (`xl/drawings`) et le ratio d'après les ancres. |
| 4 | Word dans PPTX, DOCX ou XLSX | Lettre insérée dans une diapo | Traduire avec le moteur DOCX. Aperçu = **première page** rendue par LibreOffice Writer, rognée au contenu. Si l'objet montre une autre page ou un extrait, l'aperçu sera approximatif : c'est une décision (§ 8, D3). |
| 5 | PowerPoint dans PPTX, DOCX ou XLSX | Diapo insérée dans une autre présentation | Traduire avec le moteur PPTX. Aperçu = **première diapositive** rendue par Impress. |
| 6 | Imbrication | Excel dans un Word, lui-même dans un PPTX | Traitement **récursif** : on traduit le niveau le plus profond, on régénère son aperçu à l'intérieur de son parent, puis on remonte. Profondeur limitée à **2** niveaux sous le document (§ 6). Au-delà, l'objet reste tel quel. |
| 7 | Ancien format `.bin` (OLE2) contenant un fichier moderne | `oleObject1.bin` qui contient un flux `Package` avec un `.xlsx` | Extraire le flux avec `olefile`, traduire le fichier, le **réécrire dans le même conteneur OLE2**, puis redessiner l'aperçu. |
| 8 | Ancien format `.bin` contenant un vrai binaire 97-2003 | Flux `Workbook` (`.xls`), `WordDocument` (`.doc`), `PowerPoint Document` (`.ppt`) | Aucun moteur ne traduit ces formats. Option : faire convertir par LibreOffice en `.xlsx`/`.docx`/`.pptx`, traduire, puis **remplacer l'objet par sa version moderne** (relation `package`). Le fichier change de format interne, ce qui est à valider (§ 8, D4). Sinon, on laisse l'objet tel quel et on le signale. |
| 9 | « Paquet » (`Package`, `Ole10Native`) | Un `.txt`, `.csv` ou `.pdf` glissé dans le document et affiché comme une icône | L'aperçu est une **icône** avec le nom du fichier, et non un rendu du contenu. On ne touche pas à l'icône. Pour le contenu, on traduit seulement si le type est pris en charge par Précis (DOCX/XLSX/PPTX). Les autres types restent tels quels. |
| 10 | Objet affiché en icône (`DrawAspect="Icon"`, `showAsIcon`) | Excel montré comme une icône Excel | On traduit le contenu, mais l'aperçu ne change pas (c'est une icône). |
| 11 | Graphique natif PPTX/DOCX | Camembert « Ventes par région » | Traduire aussi les caches `c:strCache` (séries, catégories) **et** le classeur caché du graphique, avec les mêmes traductions pour que les deux restent cohérents. Sinon PowerPoint remet l'ancien libellé dès qu'on clique sur « Modifier les données ». Il n'y a pas d'aperçu à refaire. Le moteur DOCX ne lit pas du tout `word/charts` : on l'ajoute. |
| 12 | Visio (`Visio.Drawing`) | Organigramme | Contenu : il n'existe aucun moteur `.vsdx`, donc non traduit en V1. Aperçu : laissé d'origine. Option ultérieure : moteur `.vsdx` (format XML proche d'OOXML) et rendu par LibreOffice Draw (paquet `libreoffice-draw`, poids à mesurer). |
| 13 | PDF incorporé (`AcroExch.Document`) | Fiche technique PDF dans un Word | Non traduit en V1. Laissé tel quel. |
| 14 | Équation (`Equation.3`, MathType) | Formule ancienne mode | Une formule contient rarement du texte à traduire. Laissée telle quelle. Les équations modernes (`m:oMath`) sont du texte Word ordinaire et ne sont pas concernées. |
| 15 | Aperçu PNG plutôt qu'EMF | Objet inséré par un outil tiers | Après redessin, l'aperçu est notre propre PNG. Le module images (6.8) doit **ignorer les aperçus d'objets**, sinon il les passe à l'OCR et les facture une seconde fois. On marque leurs noms et on les exclut. |
| 16 | Objet **lié** (fichier externe) | Tableau lié à `\\serveur\budget.xlsx` | Impossible à traduire, puisque le fichier n'est pas dans le document. On laisse tout tel quel. Attention : à l'ouverture, Office peut proposer de « mettre à jour les liaisons » et remettre l'aperçu d'origine. À signaler au client dans le compte rendu. |
| 17 | Objet chiffré, protégé ou corrompu | Classeur protégé par mot de passe | Échec de la lecture : on laisse tel quel et on le note dans le journal. |
| 18 | Macro (`.xlsm`, `.docm`) | Classeur avec macros | On traduit le texte. Les macros ne sont **jamais exécutées** : LibreOffice est lancé sans les exécuter (à vérifier dans la configuration du profil, § 6). Le projet VBA est recopié tel quel. |
| 19 | Même objet présent plusieurs fois | Le même classeur sur trois diapos | Un seul rendu, puis réutilisation. C'est déjà le cas en PPTX (« classeurs uniques »). Cache par empreinte sha1 (méthode CFAO). |

---

## 4. Comment redessiner l'aperçu : options comparées

| Option | Possible sous Docker Linux ? | Fidélité de l'aperçu | Coût / poids | Avantages | Inconvénients |
|---|---|---|---|---|---|
| **A. Microsoft Office dans Docker** | **Non.** Office ne tourne pas sous Linux. Microsoft ne prend pas en charge Office dans les conteneurs Windows (qui demandent de toute façon un hôte Windows). L'automatisation côté serveur n'est « ni recommandée ni prise en charge » (KB 257757). La seule voie autorisée sans utilisateur est la licence « Microsoft 365 for unattended RPA », sur une machine Windows, et fournie « en l'état ». | Parfaite (c'est Office lui-même) | VM Windows + licence par machine, en plus de l'infrastructure actuelle (chiffrage à demander) | Rendu identique à Office | Hors de la contrainte Docker Linux. Fragile (boîtes de dialogue bloquantes, processus fantômes). Risque lié aux macros. Coût de licence. |
| **A bis. Office sous Wine** | Techniquement possible, non pris en charge | Inconnue (à mesurer) | Faible en argent, élevé en maintenance | — | Non pris en charge, instable, licence toujours nécessaire. À écarter. |
| **B. Microsoft Graph** (conversion en PDF via OneDrive/SharePoint, `?format=pdf`) | Oui, c'est un service web | Très bonne (moteur Microsoft) | Abonnement Microsoft 365, latence réseau (à mesurer) | Rendu Microsoft sans installer Office | **Chaque document client part chez Microsoft**, ce qui pose un problème de confidentialité et de RGPD. Dépendance externe, quotas. À écarter par défaut. |
| **C. LibreOffice sans interface** (ce que fait déjà le PPTX) | **Oui**, déjà dans l'image | Bonne pour les tableaux. Quelques écarts connus : le trou des graphiques en anneau (`c:holeSize`) est ignoré, le format % suit la langue de LibreOffice | Déjà payé (image actuelle). Coût de démarrage d'environ 4 s par appel avec un profil neuf (mesuré lors de l'étape PPTX), d'où le regroupement en un seul appel | Aucune dépendance nouvelle, local, testable dans Docker | Fidélité inférieure à Office pour certains graphiques. Démarrage lent si on l'appelle objet par objet. |
| **C bis. C + méthode CFAO Academy** | Oui | **Meilleure que C** : on rend seulement la zone visible (`oleSize`), avec un fond transparent, au bon ratio, et le format % est corrigé | Identique à C | Code déjà éprouvé en production chez CFAO (voir ci-dessous) | Le correctif « anneau » est propre à un modèle CFAO et n'est pas à reprendre tel quel |
| **D. unoserver** (un LibreOffice gardé ouvert, appelé via UNO) | Oui (paquet Python, même image) | Identique à C | Supprime le démarrage à chaque appel (gain à mesurer). Garde un processus résident d'environ quelques centaines de Mo (à mesurer) | Rapide pour les documents qui contiennent beaucoup d'objets | Processus à superviser (plantage, fuite mémoire). À n'envisager que si la mesure montre que le démarrage pèse. |
| **E. OnlyOffice Document Server** (service de conversion Docker) | Oui | Bonne a priori (à mesurer). Le traitement des objets OLE n'est pas documenté | Image de plusieurs Go (à mesurer), édition gratuite sous licence AGPL | Moteur proche d'Office pour les formats OOXML | Gros service en plus. Licence AGPL à étudier. Aucune garantie documentée sur les objets OLE. |
| **F. Aspose (Slides/Cells/Words)** | Oui (bibliothèque) | Bonne pour les tableaux | Licence payante (tarif à demander) | Bibliothèque sans LibreOffice | D'après leur propre documentation, Aspose **ne régénère pas** l'aperçu d'un OLE : il faut le dessiner soi-même (avec Aspose.Cells). Cela revient à C, en payant. |
| **G. Ne pas redessiner** | — | Aperçu en langue d'origine | Nul | Simple | Le défaut visible reste. C'est notre position de repli en cas d'échec (au mieux). |

**Ce que CFAO Academy offre à réutiliser** (projet `C:\Users\IBRAH\Documents\Projets\cfaoacademy`, en lecture seule) :

- `services/apercu/classeurs.py:402-452` (`_pour_rendu`), sur une **copie de rendu** du classeur :
  - transforme `oleSize ref` (dans `xl/workbook.xml`) en zone d'impression `_xlnm.Print_Area` ;
  - force l'ajustement sur une page en A4 paysage ;
  - remplace le format % intégré (numFmtId 9) par un `0%` explicite, sans quoi il suit la langue de LibreOffice.

  C'est la pièce qui manque à Précis : aujourd'hui, la feuille est rendue entière.
- `classeurs.py:685-736` (`_sans_blanc`, `_rogner`) : blanc → transparent, rognage, complément au ratio, centrage, PNG compressé. C'est l'équivalent de `_crop_xlsx_pdf_to_png` / `_completer_au_ratio` dans Précis. Les deux versions sont à fusionner.
- `classeurs.py:54-66` (`_ecrire`) : écrit le zip avec une date fixe (1980-01-01), si bien qu'un même contenu donne les mêmes octets. On obtient ainsi une **empreinte stable** pour le cache.
- `classeurs.py:768-855` (`rendre`) :
  - cache par `sha1(contenu + version + ratio)` ;
  - un seul appel LibreOffice pour tous les classeurs ;
  - images décodées une par une pour limiter la mémoire ;
  - délai maximal de 120 s.

  `classeurs.py:740` : `VERSION_IMAGES` invalide le cache quand on change le rendu.
- `services/apercu/service.py:613-631` (`convertir`) : **nouvel essai** quand LibreOffice, sur un profil neuf, crée le profil puis s'arrête sans convertir. C'est un piège réel à reprendre.
- `classeurs.py:39` : verrou global LibreOffice, déjà présent chez nous (`preview_lock`).
- À ne pas reprendre :
  - `_anneau_excel` (`classeurs.py:498+`), propre à un modèle CFAO ;
  - le rebranchement par le seul `rId` de l'image (`classeurs.py:981-1058`). Celui de Précis est plus complet, car il couvre aussi la branche VML.

---

## 5. Choix recommandé et architecture commune

**Recommandation : option C bis.** C'est LibreOffice, déjà présent dans l'image, enrichi de la méthode CFAO (zone visible, transparence, cache). Ensuite :

- passer à **D** (unoserver) seulement si la mesure de l'étape 6.11.6 montre que le démarrage de LibreOffice pèse sur les gros documents ;
- écarter **A**, **B** et **E** pour les raisons du § 4.

### Module commun `backend/engines/incorpores.py`

Un seul module, appelé par les trois moteurs à la fin de leur traitement, au même endroit que l'actuel `regenerate_ole_previews` :

```
traiter_objets(zip_entree, conteneur, langues, profondeur=0) -> rapport
```

1. **Repérer.** Le module lit les relations de chaque partie qui affiche des objets :
   - PPTX : `ppt/slides/_rels` ;
   - DOCX : `word/_rels/document.xml.rels`, plus les en-têtes et pieds de page ;
   - XLSX : `xl/worksheets/_rels` et `xl/drawings/_rels`.

   Il en tire une liste d'objets : `{fichier incorporé, progId, type (classeur | document | présentation | paquet | autre), affiché en icône ?, image d'aperçu, ratio du cadre, toutes les relations qui pointent vers l'aperçu}`. Les objets liés (`TargetMode="External"`) sont exclus.
2. **Extraire.**
   - Un fichier OOXML est lu directement.
   - Un `.bin` OLE2 est ouvert avec `olefile` : on lit le flux `Package`, ou `\x01Ole10Native` si le fichier embarqué est OOXML.
   - Un vrai binaire 97-2003 est converti par LibreOffice seulement si la décision D4 le permet. Sinon, l'objet est ignoré.
3. **Traduire récursivement.** Le module appelle le **moteur correspondant** (`engines/xlsx`, `engines/docx`, `engines/pptx`) sur le fichier extrait, avec les mêmes langues et le même glossaire. Ce moteur rappelle à son tour `traiter_objets(..., profondeur+1)`, jusqu'à la limite de profondeur.
4. **Redessiner l'aperçu.** On regroupe tous les objets non affichés en icône. Pour chacun, on prépare une copie de rendu :
   - classeur : zone `oleSize` → zone d'impression, une page, format % explicite ;
   - document : première page ;
   - présentation : première diapositive.

   Puis **un seul appel LibreOffice** convertit tout en PDF, sous `preview_lock`, via `office.py`, avec un nouvel essai si le profil est neuf. PyMuPDF rend chaque PDF, on rogne avec transparence et on complète au ratio du cadre. Les rendus sont mis en cache par empreinte sha1 (zip déterministe).
5. **Remplacer dans le paquet.**
   - On réécrit le fichier incorporé traduit, ré-encapsulé en OLE2 si l'original l'était.
   - On écrit l'aperçu en `media/<nom>_apercu.png`.
   - On rebranche **toutes** les relations qui pointaient vers l'ancien aperçu (branche VML comprise, comme le fait déjà `engine.py:1242-1265`).
   - On ajoute le type `png` à `[Content_Types].xml` et on supprime les anciens EMF orphelins.
6. **Au mieux.** Chaque objet est traité dans son propre `try/except`. En cas d'échec, il reste dans son état d'origine (contenu et aperçu) et le rapport l'indique. Le document est toujours livré.

L'actuel `regenerate_ole_previews` et les fonctions `_process_excel_file` / `_inject_excel_file` du PPTX sont **remplacés** par ce module. Les nouveaux moteurs DOCX et XLSX l'appellent de la même façon. Les graphiques natifs (cas 11) restent dans les moteurs, car ce ne sont pas des OLE, mais leur classeur caché passe par l'étape 3.

---

## 6. Impacts

### Performances

- Un appel LibreOffice par document et par niveau d'imbrication, et non un par objet. C'est déjà le cas en PPTX.
- Temps ajouté pour un document courant avec 1 à 5 objets : **à mesurer** dans Docker (`--cpus 2 --memory 3g`).
- Mémoire : les images sont décodées une par une (méthode CFAO), à 150-200 dpi. Pic mémoire **à mesurer**.
- La traduction récursive appelle le modèle de traduction sur un texte en plus. Le temps de traduction augmente en proportion du texte des objets.

### Facturation

- **DOCX et XLSX** sont facturés au volume de texte (`backend/app/services/documents.py:59-97`, `beta_meter.office_cost`). Si l'extraction compte aussi le texte des objets, le client paie ce qu'on traduit réellement, ce qui est cohérent. Mais un document avec un gros classeur incorporé coûtera plus cher qu'aujourd'hui, à nombre de pages égal. C'est une décision (§ 8, D1).
- **PPTX** est facturé à la diapositive, donc le contenu des objets n'est pas facturé aujourd'hui. Une diapo avec un classeur de 2 000 cellules coûte le même prix qu'une diapo vide.
- **Aucune double facturation** : un aperçu redessiné n'est jamais facturé comme « image traduite » (6.8) et il est exclu de l'OCR (cas 15).

### Sécurité (les fichiers incorporés ne sont pas fiables)

- **Profondeur d'imbrication** limitée à 2. Au-delà, l'objet reste tel quel. Cela empêche une poupée russe de faire tourner le serveur sans fin.
- **Tailles** : on reprend les plafonds du module images (`OCTETS_ZIP_MAX` = 128 Mo décompressés, `ENTREES_MAX` = 10 000 entrées) **pour chaque objet**, plus un plafond **cumulé** par document (valeur à fixer après mesure). On vérifie le taux de compression pour repérer les « bombes zip ».
- **OLE2** : `olefile` lit seulement la structure du fichier, sans rien exécuter. Un `.bin` mal formé provoque une exception attrapée, et l'objet reste tel quel.
- **Macros** : jamais exécutées. On vérifie que le profil LibreOffice partagé interdit les macros (niveau de sécurité maximal). C'est **à vérifier** dans `office.py` et le profil, puis à tester avec un `.xlsm` piégé (macro `Workbook_Open`).
- **Fichiers externes** : un objet lié n'est jamais suivi. On ne lit ni réseau ni chemin local.
- **Délai maximal** : on garde le délai de l'appel LibreOffice (120 s comme CFAO, contre 600 s aujourd'hui en PPTX, valeur à revoir après mesure). Au-delà, on arrête et on garde les aperçus d'origine.

### Risques

- **Fidélité** : un aperçu LibreOffice peut différer légèrement d'Office (polices, graphiques en anneau, mises en forme conditionnelles). Une diapo Office montrera donc un rendu « LibreOffice ». C'est un compromis à accepter (§ 8, D2).
- **Zone visible** : sans `oleSize` (objets Word, PowerPoint, anciens fichiers), l'aperçu montre la première page ou la première diapo, ce qui peut différer de l'extrait affiché à l'origine.
- **Mise à jour des liaisons** : pour les objets liés, Office peut remettre l'ancien aperçu à l'ouverture.
- **Polices** : il faut que les polices courantes (Calibri, Arial et leurs équivalents métriques Carlito, Liberation) soient présentes dans l'image. Sinon les textes traduits, souvent plus longs, déborderont. À vérifier dans l'image.
- **Régression PPTX** : le remplacement de `regenerate_ole_previews` doit garder exactement le comportement actuel. On reprend `test_ole_apercu.py` à l'identique.

---

## 7. Plan de réalisation

Chaque étape est livrée avec ses tests et vérifiée **dans Docker** (`docker run --cpus 2 --memory 3g`) avant de passer à la suivante.

**Fabriquer les fichiers de test sans Office.** On s'appuie sur les mêmes outils qu'aujourd'hui :

- `openpyxl` produit des classeurs ;
- `python-docx` produit des documents Word ;
- `python-pptx` produit des présentations ;
- pour incorporer un objet, on écrit soi-même les parties XML, les relations et `[Content_Types].xml` dans le zip, à la manière de `test_ole_apercu.py` ;
- `olefile` sait seulement lire. Pour créer un `.bin` OLE2, on utilise `compoundfiles`/`olefile` en écriture si c'est possible, sinon un petit fichier OLE2 de référence fabriqué une fois par LibreOffice (`soffice --convert-to xls`) et versionné dans `backend/tests/fichiers/`.

Les tests unitaires restent synthétiques, sans LibreOffice. Seuls les tests marqués `libreoffice` lancent un vrai rendu, dans Docker.

| Étape | Contenu | Tests |
|---|---|---|
| **6.11.1** | Module `engines/incorpores.py` : **repérage** des objets dans les trois conteneurs (relations, progId, icône, aperçu, ratio, objets liés exclus) et rapport. Aucune modification des fichiers. | Un fichier synthétique par conteneur, avec Excel, Word, PowerPoint, paquet, icône et lien. On vérifie la liste détectée, les ratios et les relations d'aperçu, VML comprise. **Fait 01/11** (21 tests). Sur le modèle réel CFAO `MODELE-REFERENCES.pptx` : 162 objets, dont 154 repères think-cell (`TCLayout.*`) et 8 classeurs Excel à redessiner, ratio ≈ 1,18. Les repères sont classés `marqueur`, ignorés et absents du rapport ; le rapport fusionne les doublons (même cible). Aucun DOCX ni XLSX réel contenant des objets n'a pu être essayé. |
| **6.11.2** | **Extraction et réécriture** OOXML et OLE2 (`Package`, `Ole10Native`), garde-fous (taille, entrées, taux de compression, profondeur). | Aller-retour : on extrait puis on réécrit, et le fichier doit être identique octet pour octet. `.bin` mal formé → objet ignoré sans exception. Bombe zip → refus. Profondeur 3 → ignorée. **Fait 01/11** : `extraire`/`reecrire`/`remplacer_parties`, écrivain MS-CFB maison (olefile ne sait réécrire qu'à taille égale), 20 tests (`tests/test_incorpores_extraction.py`) ; contrôle réel : 22 `.bin` think-cell relus/réécrits identiques (flux, CLSID, dates). Reportés en 6.11.3 : remplacement des 97-2003 convertis (D4) et rapport établi après extraction (un `Package` OLE2 contenant un docx/xlsx y est encore classé « paquet »). |
| **6.11.3** | **Traduction récursive** par le moteur correspondant, puis branchement dans les moteurs PPTX (remplace `_process_excel_file`), DOCX et XLSX. | Traducteur factice qui préfixe « [EN] ». On vérifie que les onglets, cellules, graphiques du classeur, le texte Word et le texte PPTX incorporés sont traduits, et qu'un Excel dans un Word dans un PPTX l'est aussi. Tests existants PPTX/DOCX/XLSX toujours verts. |
| **6.11.4** | **Redessin des aperçus** : on reprend `regenerate_ole_previews` dans le module et on ajoute la zone `oleSize` (méthode CFAO), le format % explicite, Word (première page), PowerPoint (première diapo), le cache sha1 et le nouvel essai sur un profil neuf. | Synthétique : PDF fabriqué → PNG rogné, transparent, au bon ratio (reprise de `test_ole_apercu.py`). `oleSize` → `Print_Area` sur la copie de rendu. Docker : vrai rendu de 3 objets en **un** appel. On mesure le temps et la mémoire. |
| **6.11.5** | **Graphiques natifs** : caches `c:strCache` et classeur caché traduits de façon cohérente en PPTX et DOCX. Lecture de `word/charts` dans le moteur DOCX. | Graphique synthétique : titre, séries et catégories traduits, et classeur caché identique aux caches. |
| **6.11.6** | **Facturation et exclusions** : texte des objets compté selon D1, aperçus exclus de l'OCR (6.8), compte rendu client listant les objets non traités (liés, Visio, PDF, anciens formats selon D4). | Devis avant/après sur un même fichier. Un aperçu PNG redessiné n'est pas proposé à l'OCR. Les objets non traités apparaissent dans le compte rendu. |
| **6.11.7** | **Mesure et recette** dans Docker sur 3 documents réels fournis par l'utilisateur (un par conteneur). Temps, mémoire et rendu comparés à Office à l'œil. Décision unoserver (D). Mise à jour des `CONTEXTE.md` des moteurs et de cette étude avec les mesures. | Documents réels : aucun échec de document, rendu jugé acceptable par l'utilisateur. Chiffres reportés ici. |

Éventuellement plus tard (hors 6.11) : moteur Visio `.vsdx` avec ajout de `libreoffice-draw` (poids de l'image à mesurer).

**Bilan 6.11.3 (02/11/2026)** — `incorpores.relever` / `reinjecter` (+ `appliquer_dossier` / `appliquer_fichier`) branchés dans les moteurs DOCX, XLSX et PPTX, profondeur 2. Objets 97-2003 convertis par LibreOffice (D4, conversion mise en cache par empreinte : une seule par objet et des ids stables). Budget anti-bombe commun à tout le document, sous-objets compris. Limites connues :
- l'ancien `.bin` d'un objet 97-2003 converti reste dans le paquet, orphelin (Office l'ignore) ;
- en traduction progressive PPTX, les objets des masques, dispositions et notes ne sont pas traités (déjà le cas avant) ;
- le devis compte désormais le texte des objets (D1) ; le détail facturable et le compte rendu client relèvent de 6.11.6.

**Bilan 6.11.4 (02/11/2026)** — nouveau module `engines/apercus.py`, appelé par `incorpores.reinjecter` : il couvre donc DOCX, XLSX et PPTX (passe finale comme traduction progressive). L'ancien redessin propre au moteur PPTX (`regenerate_ole_previews`, Excel seulement) et ses appels dans `translation_runner` sont retirés.
- **Un seul appel LibreOffice** pour tous les objets d'un fichier (nouvel essai si un profil neuf ne produit rien), sous le verrou commun des aperçus.
- **Classeur** : copie de rendu (zone visible `oleSize` en zone d'impression, autres feuilles masquées, une page A4 paysage, % explicites), puis PDF → PNG rogné au contenu, fond transparent, pages empilées, complété (jamais rogné) aux proportions du cadre.
- **Document / présentation** : première page ou diapositive ; règle D3 appliquée (écart de proportions > 10 % → aperçu d'origine).
- **Jamais redessinés** : icônes, objets liés, objets sans aperçu. En cas d'échec, l'aperçu d'origine reste.
- **Rebranchement** : un nouveau PNG `<aperçu>_traduit.png` ; toutes les relations vers l'ancien aperçu (diapositive, feuille, dessin VML) le visent, type PNG déclaré. L'ancien EMF reste dans le paquet, orphelin : il peut être partagé par un autre objet, et Office l'ignore.
- **Cache** : 64 rendus par empreinte (copie de rendu + type + version + proportions) ; un second passage sur le même fichier ne relance pas LibreOffice (6 s → 0,4 s à l'essai).
- **Preuves** : `tests/test_ole_apercu.py` (21 tests, LibreOffice simulé) ; essai réel Docker (`precis-ocr-test`, 2 CPU) sur une diapositive portant un classeur, un document et une présentation : classeur redessiné et traduit dans la diapositive rendue ; document et présentation écartés par D3 (cadre 1,5 contre 2,6 et 1,33), comme prévu.
- **Revue (corrigée)** : identifiants de format % pris libres (plus de collision avec un format existant) ; délai LibreOffice proportionnel au nombre d'objets ; un échec de rendu n'est pas mis en cache (retenté) ; une image d'aperçu partagée avec un objet non traduit (diapositive dupliquée hors plage) n'est pas redessinée.
- **À vérifier en 6.11.7** : PowerPoint réel face à l'EMF orphelin (l'ancien code évoquait une réparation). **En 6.11.5** : classeur dont la feuille active est une feuille graphique.

**Conception 6.11.5 (02/11/2026)** — un graphique natif (`ppt/charts/chartN.xml`, `word/charts/chartN.xml`) montre ses textes à deux endroits : son XML (titre, axes, caches `c:strCache` des séries et catégories) et son classeur caché (`embeddings/*.xlsx`, ouvert par « Modifier les données »). Existant : le moteur PPTX traduit le XML du graphique, jamais le classeur ; le moteur DOCX ignore `word/charts` ; le moteur XLSX aligne déjà les caches de SES graphiques sur ses cellules (`_aligner_graphiques`).

| Option | Pour | Contre |
|---|---|---|
| A. Traduire le classeur caché comme un objet incorporé (moteur XLSX), puis recopier ses cellules traduites dans les caches | Une seule traduction par texte ; caches et classeur identiques par construction ; réutilise `relever` / `reinjecter` | Une retouche de plus à écrire (lecture des cellules du classeur traduit) |
| B. Traduire les caches, puis écrire ces textes dans les cellules du classeur | Pas de passage par le moteur XLSX | Écriture de cellules à la main (`sharedStrings`) ; les cellules hors caches restent non traduites |

**Choix : A.**
- **Repérage** (`incorpores`, PPTX et DOCX seulement : un XLSX garde son propre alignement) : chaque graphique affiché par une partie (diapositive, document, en-tête…) et pourvu d'un classeur incorporé devient un objet `classeur`. Sa `partie` est la partie qui l'affiche : les filtres par diapositive du moteur PPTX s'appliquent tels quels. Le chemin du graphique est porté à part, et l'objet n'a pas d'aperçu (Office dessine le graphique lui-même). Un classeur **lié** (fichier externe) n'est pas listé : le XML du graphique reste traduit par le moteur.
- **Alignement** : après traduction du classeur, une retouche `graphique` relit le XML COURANT du graphique : chaque `c:f` suit les onglets renommés (`reecrire_references`), chaque `c:strCache` d'un `c:strRef` reçoit le texte des cellules traduites. Le classeur fait foi, comme en XLSX.
- **DOCX** : nouvelle section `charts` (titres `a:p`, étiquettes `c:v` non numériques). Les caches d'un `c:strRef` ne sont pas relevés quand un classeur incorporé existe (ils seront recopiés : pas de double facturation au volume). PPTX inchangé (prix à la diapositive).
- **Limites** : caches multi-niveaux (`c:multiLvlStrRef`) traduits par le moteur, non réalignés ; références multi-zones laissées telles quelles.
- **Aperçu** : si la feuille active d'un classeur OLE est une feuille graphique, la copie de rendu ne pose pas de zone d'impression (sans objet sur une feuille graphique).

**Bilan 6.11.5 (02/11/2026)** — fait comme conçu. `incorpores` repère les graphiques et leur classeur caché, puis la retouche `graphique` (`_aligner_graphique`) recopie les cellules traduites dans les caches et renomme les onglets dans les `c:f`. Le moteur DOCX lit `word/charts` (section `charts`). L'aperçu d'une feuille graphique n'a plus de zone d'impression. Règles communes : `incorpores.a_classeur_interne` (cible relative ou absolue) et `incorpores.sous_strref`.
- **Décision de revue** : une cellule que la traduction du classeur n'a pas changée (formule, texte écarté) ne fait pas foi : le cache garde la traduction du moteur. Sans cette règle, un libellé PPTX déjà traduit revenait en langue source.
- **PPTX** : les caches restent traduits par le moteur (prix à la diapositive, donc pas de double facturation). Si le classeur est écarté (budget, profondeur), le graphique reste traduit.
- **DOCX** : les caches couverts par le classeur ne sont pas relevés, pour ne pas les facturer deux fois. Limite : si le classeur est écarté, ces libellés restent en langue source ; l'objet apparaît alors comme non traité dans le rapport.
- Preuves : `tests/test_incorpores_graphiques.py` (6 tests : PPTX, DOCX, DOCX lié, PPTX progressif, cellule non traduite, aperçu de feuille graphique) ; régression incorpores, OLE, XLSX graphiques et PPTX verte.

---

## 8. Points à trancher

| # | Question | Effet visible de chaque choix |
|---|---|---|
| **D1** | Faut-il facturer le texte des objets incorporés ? | **Oui** : un rapport Word avec un gros tableau Excel incorporé coûte plus cher qu'aujourd'hui, mais le client paie ce qui est réellement traduit. **Non** : même prix qu'aujourd'hui, et nous absorbons le coût de traduction de ces objets. En PPTX (prix à la diapo), rien ne change dans les deux cas. |
| **D2** | Accepte-t-on un aperçu dessiné par LibreOffice ? | **Oui** : la diapo traduite montre le tableau en langue cible, avec parfois de petites différences de police ou de graphique par rapport à Office. **Non** : l'aperçu reste dans la langue d'origine tant que le client n'a pas double-cliqué sur l'objet (Office le redessine alors lui-même). |
| **D3** | Pour un objet Word ou PowerPoint, quel aperçu ? | **Première page ou première diapo** redessinée : souvent juste, parfois différente de l'extrait choisi à l'origine. **Garder l'aperçu d'origine** : jamais faux dans la mise en page, mais en langue d'origine. |
| **D4** | Les anciens objets 97-2003 (`.xls`, `.doc`, `.ppt` dans un `.bin`) | **Convertir en format moderne** : traduits et redessinés, mais l'objet devient un fichier moderne (le client ne verra pas de différence en l'ouvrant avec un Office récent). **Laisser tels quels** : non traduits, et signalés dans le compte rendu. |
| **D5** | Ajouter Draw (Visio, PDF) à l'image Docker ? | **Oui** : les organigrammes Visio pourront être traités plus tard, avec une image plus lourde (poids à mesurer). **Non** : Visio et PDF restent en langue d'origine et sont signalés. |
| **D6** | Signaler au client les objets non traités ? | **Oui** : une ligne dans le compte rendu (« 2 objets liés non traduits : budget.xlsx… »). **Non** : silence, et le client peut découvrir le reste en langue d'origine. |


### Décisions (01/11, déléguées par l'utilisateur : choix recommandés)

- **D1 oui** : le texte des objets incorporés est facturé comme le reste (même règle que les images : on paie ce qui est traduit) ; en PPTX, prix à la diapo inchangé.
- **D2 oui** : aperçu redessiné par LibreOffice (mieux qu'un aperçu resté en langue d'origine).
- **D3 première page / diapo redessinée**, sauf si ses proportions s'écartent de plus de 10 % de l'aperçu d'origine : on garde alors l'aperçu d'origine (évite un extrait faux).
- **D4 convertir** les objets 97-2003 en format moderne, au mieux ; échec → objet d'origine, signalé.
- **D5 non pour l'instant** : pas de Draw dans l'image ; Visio et PDF restent d'origine et signalés (à revoir après mesure du poids).
- **D6 oui** : une ligne dans le compte rendu par objet non traité (lié, Visio, échec).

---

## Sources

- Microsoft, « Considerations for server-side Automation of Office » (KB 257757) : https://support.microsoft.com/help/257757
- Microsoft, « Considerations for unattended automation of Office in the Microsoft 365 for unattended RPA environment » : https://learn.microsoft.com/en-us/office/client-developer/integration/considerations-unattended-automation-office-microsoft-365-for-unattended-rpa
- Microsoft Q&A, Office 2021 dans un conteneur Docker Windows : https://learn.microsoft.com/en-us/answers/questions/2105064/install-office-2021-in-windows-docker-container
- Microsoft Q&A, Excel dans une image de conteneur Windows : https://learn.microsoft.com/en-us/answers/questions/619983/install-ms-excel-on-windows-container-image
- Microsoft, conversion de format par l'API Graph : https://learn.microsoft.com/en-us/archive/blogs/sharepointdevelopersupport/using-microsoft-graph-api-to-convert-the-format-of-your-documents
- Aide LibreOffice, options « Microsoft Office » (objets incorporés) : https://help.libreoffice.org/latest/vi/text/shared/optionen/01130200.html
- Apache OpenOffice, bogue 77118 (aperçus des objets OLE) : https://bz-he-de.apache.org/ooo/show_bug.cgi?id=77118
- LibreOffice, bogue 152436 (objet OLE perdu à l'export PPTX) : https://www.libreoffice.org/bugzilla/show_bug.cgi?id=152436
- Aspose.Slides, gestion des OLE (aperçu à fournir soi-même) : https://docs.aspose.com/slides/python-net/manage-ole
- Forum Aspose, l'aperçu ne change pas après modification du classeur incorporé : https://forum.aspose.com/t/updating-the-embedded-ole-excel-sheet-data-does-not-change-ole-image-in-slide/208854
- Apache POI, structure `Ole10Native` : https://poi.apache.org/apidocs/org/apache/poi/poifs/filesystem/class-use/Ole10Native.html
- OnlyOffice, image Docker du service de conversion : https://hub.docker.com/r/onlyoffice/docs-converter/tags
