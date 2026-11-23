# Étude — Une page traduite entière, images comprises

## Besoin (décision utilisateur, 23/11)
On prend une page et on analyse tout ce qu'elle contient : le texte, les images à texte et le reste. On traduit l'ensemble, puis on rend la page **entièrement traduite**.
- La page est facturée une seule fois. Les images n'entraînent aucun débit en plus.
- Une page payée s'affiche en clair. Une page non payée s'affiche en aperçu filigrané.
- L'offre de fin « Traduire les images (N pages) » disparaît.
- Il n'y a plus de pages dont les images restent non traduites. Il n'y a plus d'images posées après la livraison.

Cette décision remplace l'option D1 (commit 0a76c75), le problème 4 (archivé dans `archive/probleme-4-images-beta`) et la version du 20/11 de cette étude.

## Existant (main local 23c3107, PR #99 comprise)
| Élément | Où | Devient |
|---|---|---|
| Débit des pages, réservé au lancement | `api/translate.py:682-696`, clôture `services/jobs.py:465-583` | **Inchangé.** Il couvre déjà la page entière. |
| Filigrane des pages non payées | `api/documents.py:278-323` (`pages_filigranees`), aperçu `translate.py:1009` | **Inchangé.** Une image traduite fait partie de la page, elle est donc filigranée comme le reste. |
| Lecture des images en parallèle, puis offre de fin | `translation_runner.lancer_proposition`, `images_document.proposer`, `proposition.json` | **Supprimée.** Elle est remplacée par une lecture page par page. |
| Route payante des images | `POST images/traduire` (débit `extension.debiter`), `GET images/proposition` | **Supprimée.** |
| Cache des images par empreinte | `images_document._lire_cache/_ecrire_cache` | **Gardé.** |
| Choix « garder l'original » | `GET`/`PATCH /{id}/images`, `marquer_originale` | **Gardé.** |
| Exclusions actuelles des images | `translate.py:428` (bêta, sélection de pages, scans) | **Retirées.** Pour un scan, l'OCR lit déjà toute la page, images comprises. |

## Règle retenue
1. **PDF.** Avant de livrer une page, on attend la traduction de ses images. On lit aussi d'avance les images des trois pages suivantes, pour que le client n'attende pas.
2. **PowerPoint.** Même principe, diapositive par diapositive.
3. **Word.** Le document est livré d'un seul bloc : il part quand toutes ses images sont traduites.
4. **Page ajoutée après coup** (« traduire quand même », page hors sélection). Ses images sont traduites avec elle.
5. **Image illisible ou en échec.** Elle reste d'origine et la page part quand même.
6. **Plafond, budget et pause.** On ne lit jamais les images d'une page qui ne sera pas traduite. Rien n'est engagé pour rien.

## Plan
- **Backend**
  - `images_document` : nouvel objet `ImagesDuTravail` (index page → images, lecture d'avance, attente sans limite de temps que seuls la pause et l'annulation interrompent) et écriture de la table image par image. Une page lue par OCR ne lit jamais ses images, et une image déjà traduite n'est pas relue à la reprise. `proposer` et `proposition.json` sont supprimés.
  - `engines/pdf/stream.py` : les images de la page sont posées juste avant son rendu.
  - `translation_runner` : le travail PDF, le travail PowerPoint, le travail Word, ainsi que `_inclure_page` (les images n'entrent dans la table qu'une fois la page payée). `_traduire_page_illisible` n'est pas modifié : une page lue par OCR est déjà traduite en entier.
  - `api/documents.py` : suppression des routes de l'offre. `api/translate.py` : images actives partout, sauf en mode structure.
  - `content/nouveautes.py` : texte public corrigé.
- **Front.** `DocumentImagesPanel` ne garde que la liste avant/après avec « Garder l'original ». L'offre, l'interrogation régulière du serveur et les libellés correspondants sont retirés (fr/en). `useDocumentLibrary`, `Home`, `TranslationSection` sont adaptés.
- **Tests**
  - `test_proposition_images.py` est supprimé et remplacé par `test_images_avec_la_page.py`.
  - Une page PDF n'est livrée qu'avec ses images.
  - Une image en échec reste d'origine, et la page part quand même.
  - Une pause ou une annulation interrompt l'attente, même si le fil des images s'est déjà arrêté.
  - Aucun débit en plus.
  - Aucune image n'est lue au-delà du plafond.
- **Données.** Aucune migration. Les anciens `proposition.json` ne sont plus lus. Le cache et les tables déjà payées restent valables.

## Risques
- **File d'attente OCR partagée.** Elle peut ralentir une page qui contient beaucoup d'images. La lecture d'avance est à mesurer sur le banc.
- **Coût.** Chaque image à texte coûte une lecture et une traduction, sans recette en plus.
- **PowerPoint.** Les images des masques sont rattachées à la diapositive 1. C'est à vérifier sur le banc.

## Décisions (utilisateur, 23/11)
1. **Pas de délai.** La page attend la traduction de ses images, sans limite de temps. Seule une erreur de lecture laisse l'image d'origine (règle 5). La pause et l'annulation du client interrompent l'attente.
2. **Excel.** Hors périmètre pour cette fois, parce qu'Excel ne traite pas les images aujourd'hui.
3. **Anciens documents à qui l'offre a été proposée.** Ils gardent le texte seul.
