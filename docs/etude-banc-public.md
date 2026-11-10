# Étude : banc public de 50 images réelles (traduction des images)

## Besoin et contraintes
Le banc interne (`backend/tests/banc_images.py`, 18 cas) ne contient que des images
venues des utilisateurs : les règles du moteur y sont réglées, donc il ne mesure plus
leur généralité. Il faut un second banc, **tiré au hasard** dans des jeux publics,
jamais choisi à la main ni inventé, pour voir comment le moteur se comporte sur des
images qu'il n'a jamais vues.

Contraintes :
- 50 images, traitées par lots de 5 (diff et rapport à chaque lot), puis un passage complet.
- Corrections par règles générales seulement, sans recul sur le banc interne.
- Images de tiers = données non fiables : hors dépôt, dossier isolé, Python lancé avec `-I`
  pour tout script qui les lit.
- Traductions réelles (API payante) figées dans `memoire.json` : un seul paiement.

## Existant
- `banc_images.py` : corpus `backend/translations/_banc_images/` (ignoré par git),
  `cas/<id>/source.img` + `lus.json` (lecture OCR figée), `memoire.json` (traductions),
  `reference.json`, planches `sorties/<id>.jpg`. Le corpus se construit depuis le
  cache d'images (`--figer`), pas depuis un dossier d'images quelconques.
- Indicateurs déjà définis : poses, coupes, écarts, occupation, restes, manque.
- `--lot N` rejoue les cas `[5N:5N+5]` triés par nom.

## Sources (téléchargement direct, sans compte)
Les jeux sont lus par l'API publique du visualiseur Hugging Face
(`datasets-server.huggingface.co/rows`), une ligne à la fois : pas d'archive de
plusieurs Go à télécharger.

| Jeu | Contenu | Taille | Licence (usage de test interne, non redistribué) |
|---|---|---|---|
| AI2D (`lmms-lab-encoder/ai2d`, test) | schémas scientifiques étiquetés | 3 088 | Apache 2.0 (AI2) |
| FUNSD (`nielsr/funsd`, test) | formulaires scannés | 50 | recherche |
| DocVQA (`lmms-lab-encoder/DocVQA`, validation) | pages scannées (UCSF IDL) | 5 349 | recherche |
| ChartQA (`HuggingFaceM4/ChartQA`, test) | graphiques (barres, courbes, secteurs) | 2 500 | GPL-3.0 |
| Wikimedia Commons, `Category:Organizational charts` | organigrammes | ~ 1 000 | licence libre par fichier |
| Wikimedia Commons, `Category:Process flow diagrams` | schémas de procédé | ~ 190 | licence libre par fichier |

Répartition : **15 schémas AI2D, 15 scans (7 FUNSD + 8 DocVQA), 10 graphiques ChartQA,
10 schémas Wikimedia (5 organigrammes + 5 schémas de procédé)** = 50.

**Réorientation du 10/11/2026** : un premier tirage (graine 20261109) prenait des photos
de rue (ICDAR 2015, COCO-Text, TextOCR) ; rejeté, car la cible du produit est l'image de
document (schéma, scan, graphique). Ces 50 photos ont été retirées du banc.

| Option | Pour | Contre |
|---|---|---|
| A. Archives complètes des jeux | provenance officielle | volume, comptes parfois requis |
| **B. API ligne à ligne (retenue)** | quelques Mo, sans compte, tirage exact par indice | dépend de copies HF des jeux |
| C. Images glanées sur le web | variété | pas un jeu public, tirage non reproductible |

## Tirage (reproductible)
- Graine fixe **20261110** ; pour chaque source, `random.Random(graine + rang de la source)`
  tire des indices sans remise dans le split.
- Règle d'admission unique, la même pour toutes les sources : l'image est gardée si
  l'OCR du moteur y lit au moins **2 textes contenant une lettre** ; sinon l'indice
  suivant de la même suite est pris. Les refus sont notés (sans cela, une photo sans
  texte n'éprouve rien).
- Provenance notée par cas dans `provenance.json` : jeu, split, indice, URL, licence.

## Intégration retenue
- `banc_images.py` reçoit `--banc NOM` (défaut `_banc_images`) : le banc public vit dans
  `backend/translations/_banc_public/`, même structure, mêmes indicateurs, même `--lot`.
- `--importer DIR` : construit les cas depuis un dossier d'images (id = 10 premiers
  caractères de l'empreinte SHA-256, lecture OCR figée dans `lus.json`).
- Script de tirage `backend/tests/banc_public_tirage.py` : télécharge, applique la règle
  d'admission, écrit les images et la provenance dans le dossier isolé.

## Impacts
- Données : rien en base ; dossier ignoré par git.
- Coût : 50 images × ~15 textes ≈ 750 courtes traductions, une seule fois (mémoire figée).
- Sécurité : images décodées par Pillow/OpenCV seulement, taille plafonnée au
  téléchargement (10 Mo), scripts hors du dossier des images, `python -I`.
- Aucun effet sur l'application ni le déploiement.

## Risques
- Copies HF retirées ou renommées : la provenance garde l'indice et le jeu d'origine.
- Scans anciens (FUNSD, DocVQA) au texte petit ou bruité : défauts de lecture OCR, pas de
  rendu ; ils sont classés à part dans le rapport, pas « corrigés » dans le rendu.
- Organigrammes déjà en français : rien à traduire ; comptés comme tels.

## Résultats
**Tirage (10/11/2026, graine 20261110)** : 50 cas (AI2D 15, FUNSD 7, DocVQA 8,
ChartQA 10, organigrammes 5, schémas de procédé 5). Refus par la règle d'admission :
schémas de procédé 3, AI2D 2. FUNSD n'a que 50 images : le nombre d'essais est borné à
la taille du jeu. La lecture OCR d'une image à la limite de la règle peut varier d'un
passage à l'autre : une relance a admis 2 AI2D de plus, retirées en gardant les 15
premières dans l'ordre du tirage.

_(lots : rempli lot par lot)_
