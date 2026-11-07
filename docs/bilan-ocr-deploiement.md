# Bilan OCR pour le déploiement

État au 05/11/2026, branche `integration/version-complete` (b0f96a3). Ce bilan sert à décider si l'OCR peut être mis en ligne, et à préparer la mise en ligne.

## 1. Conclusion

**L'OCR fonctionne dans l'image de production, mais il ne faut pas l'ouvrir au public en l'état.** Trois problèmes sont à régler avant :

1. **La limite affichée ne correspond pas à la réalité.** Le service annonce 10 pages scannées par envoi, mais 5 pages denses sont déjà refusées au bout de 94 s.
2. **Une seule page illisible fait refuser tout l'envoi**, sans dire laquelle. Le message peut aussi tromper : il demande un scan plus net alors que le temps a manqué.
3. **Les images de l'extension ne sont pas limitées entre clients.** Trois images simultanées consomment déjà jusqu'à 2,2 Go de mémoire, sur un serveur de 4 Go.

La documentation doit aussi être corrigée (§6), et un essai sur la machine de staging reste à faire (§7).

**Mise à jour du 05/11 (mission 6.13, branche `feat/ocr-file-pages-illisibles`, non fusionnée) :** les trois problèmes ont une réponse dans le code, mais l'ouverture attend encore les points du §7.

1. Les scans sont lus **page par page, en tâche de fond** : le délai de 90 s vaut pour une page, plus pour l'envoi entier, et la limite de 10 pages n'est plus tenue par un seul appel.
2. Une page illisible **ne fait plus refuser l'envoi** : le reste est traduit, la page est citée, non facturée, et le client choisit pour elle « garder l'original », « laisser vide » ou « traduire quand même » (facturé seulement si la lecture aboutit).
3. Les scans et les images de l'extension passent par **un même guichet** : au plus `OCR_SCAN_WORKERS` (3) lectures à la fois sur tout le serveur ; l'extension attend son tour 120 s au plus, puis reçoit « service occupé » sans débit.

## 2. Ce qui a été vérifié

Image construite depuis le `Dockerfile` réel : 2,07 Go, Tesseract 5.3.0 (français, anglais, orientation), modèles PP-OCR présents. Mesures avec 2 CPU et 3 Go de mémoire, pour approcher le serveur prévu (2 vCPU, 4 Go).

| Vérification | Résultat |
|---|---|
| `test_ocr.py` (vrai Tesseract, de la lecture au rendu traduit) | Réussi |
| `test_ocr_v2_detection`, `_effacement`, `_fiabilite`, `_image`, `_rendu` | Réussis, sauf le cas japonais, sauté faute de police |

**Pas vérifié :**
- le parcours complet par le site, avec une vraie traduction (`test_ocr_endpoint.py` et `test_documents_scannes.py` n'ont pas été relancés dans cette image) ;
- l'aspect des pages traduites, qui n'a pas été réexaminé : les constats de qualité du §4 datent du 01/11 ;
- le processeur réel du serveur : ces mesures viennent d'un poste de développement x86, limité à 2 CPU.

## 3. Mesures

*Mesures faites avant 6.13 (lecture de tout l'envoi d'un seul tenant). Elles restent valables pour le coût d'une page ; elles sont à refaire avec la lecture page par page (§7).*

### Scans de documents (délai fixé à 90 s par envoi)

| Envoi | Temps | Mémoire (pic) | Résultat |
|---|---|---|---|
| Livret dense, 1 page | 91,8 s | 505 Mo | Accepté |
| Livret dense, 3 pages | 87,0 s | 962 Mo | Accepté |
| Livret dense, 5 pages | 94,1 s | 1 069 Mo | **Refusé** : trop de temps |
| Livret dense, 10 pages | 76,9 s | 995 Mo | **Refusé** : pas assez lisible |
| `scan_dsh`, 10 pages | 90,1 s | 1 103 Mo | **Refusé** : « Essayez un scan plus net » |
| `scan_mv21`, 10 pages | 20,1 s | 563 Mo | **Refusé** : pas assez lisible |

Le temps d'un envoi court ne reflète pas sa difficulté : l'effacement utilise le temps restant pour améliorer le résultat. C'est pourquoi 1 et 3 pages prennent à peu près le même temps.

Les mêmes scans, envoyés une page à la fois :

| Page | Temps | Résultat |
|---|---|---|
| `scan_dsh` p. 1 | 94,9 s | Acceptée |
| `scan_dsh` p. 2 | 25,3 s | Acceptée |
| `scan_dsh` p. 3 | 86,9 s | Acceptée |
| `scan_mv21` p. 1 | 15,5 s | Acceptée |
| `scan_mv21` p. 2 | 9,0 s | **Refusée** : pas assez lisible |
| `scan_mv21` p. 3 | 92,9 s | Acceptée |

**Exemple concret :** un client envoie les 10 pages de `scan_mv21`. La page 2 est illisible, donc tout est refusé, y compris les pages 1 et 3, qui passent seules. Le message ne cite pas la page 2. Pour `scan_dsh`, les 3 premières pages passent une à une, mais l'envoi de 10 pages échoue au bout de 90 s avec « Essayez un scan plus net ». Ce résultat et ce temps pointent vers un manque de temps, et non vers un scan flou, même si la cause exacte n'a pas été isolée.

**Limite réaliste aujourd'hui : environ 3 pages denses par envoi.**

### Images de pages web (extension)

| Images en même temps | Temps de chacune | Mémoire (pic) |
|---|---|---|
| 1 | 14,3 s | 922 Mo |
| 3 | 23,1 à 24,1 s | 2 227 Mo |

La traduction était simulée : le temps d'appel au service de traduction n'est pas compté. La mémoire additionne le pic du programme et celui de ses sous-processus : c'est donc un maximum. Au-delà de 3 images, rien n'a été mesuré.

### Disque

Chaque page scannée ajoute environ 2 Mo : le livret de 13,5 Mo passe à 15,1 Mo avec 1 page reconnue, et à 20 Mo avec 3 pages.

## 4. Ce que le client peut attendre

**Scans de documents :**
- langues : français et anglais imprimés ; pas d'écriture manuscrite ;
- une ligne douteuse reste telle que scannée, donc en langue d'origine, plutôt que d'être mal traduite ;
- le fond de la page est conservé, et seul le texte est effacé puis réécrit ;
- le texte dans les photos reste en langue d'origine ;
- les petits intertitres de couleur sur bandeau restent souvent non traduits ;
- une phrase coupée par un mot douteux peut mêler une partie traduite et une partie d'origine ;
- le résultat n'est pas une copie certifiée, et un tampon ou une signature posé sur le texte peut être abîmé.

**Images (documents et extension) :**
- le lecteur PP-OCR lit mieux sur les fonds chargés, et lit aussi le japonais ;
- une image remplacée coûte 1 page dans un document, 1 crédit dans l'extension ;
- la traduction **vers** le japonais n'est pas prête : aucune police japonaise n'est installée, contrairement à ce que prévoyait l'étude OCR v2 (§9). Le test correspondant est sauté, et le rendu n'a donc pas été vu.

## 5. Risques en production

| Risque | Ce qui se passe | Gravité |
|---|---|---|
| Images de l'extension sans limite commune | Chaque client a droit à une image à la fois, mais rien ne limite le total (`api/extension.py`). Plusieurs clients simultanés peuvent saturer la mémoire et faire tomber tout le service, faute de plafond mémoire dans `docker-compose.yml` | **Haute** |
| Un seul scan à la fois | Pendant environ 90 s, tout autre client qui envoie un scan reçoit aussitôt « déjà en cours » (503), sans file d'attente | Moyenne |
| Scans et images de documents partagent le même verrou | Un document avec des images garde le verrou pendant le traitement de chaque image : un scan envoyé à ce moment-là est refusé | Moyenne |
| Effet sur le reste du service | L'OCR occupe des CPU sur une machine à 2 vCPU, et l'effet sur les traductions en cours n'a pas été mesuré | À mesurer |
| Disque | Les fichiers traduits n'expirent pas (`deploiement.md`), et le cache des images n'est jamais purgé | Moyenne, à surveiller |
| Panne de l'OCR invisible | `/health` ne contrôle ni Tesseract ni PP-OCR : le service paraît sain alors que l'OCR est en panne | Faible : l'image de production les contient, et le téléchargement des modèles bloque la construction si un fichier est mauvais |

Le délai de nginx (3 600 s) ne coupe pas un envoi de 90 s. Si un autre service frontal est placé devant, comme Caddy dans `docker-compose.https.yml`, son délai est à vérifier sur la machine de staging.

**Ajoutés par 6.13 (à surveiller, non bloquants) :** un travail « traduire quand même » abandonné est nettoyé au bout de 24 h seulement ; les images traduites d'une page relue ne sont pas transmises au moteur (la page sort avec ses images d'origine) ; un aperçu rendu pendant un « traduire quand même » montre l'état d'avant (rendu sur un instantané, voir §7, 3 bis) ; le suivant montre la page.

## 6. Documentation à corriger

| Fichier | Ce qu'il dit | Réalité |
|---|---|---|
| `README.md` (lignes 38, 57 et 90) | OCR « non déclaré livré », « feature à venir » | Le circuit est actif dans `api/translate.py`, sans interrupteur pour le désactiver |
| `docs/deploiement.md` (ligne 231) | Scans « détectés, refusés, non facturés » | Ils sont reconnus et traduits |
| `docs/ocr-production.md` | Suffixe `ocrv1`, « boîtes des mots masquées », 10 pages | `ocrv2`, effacement de l'encre, environ 3 pages denses |

**Point important :** comme il n'y a pas d'interrupteur, déployer cette branche met l'OCR en ligne immédiatement. Le correctif 3 du §7 doit donc être livré avant ou en même temps.

## 7. Check-list

**À corriger avant l'ouverture :**
- [x] 1. Pages par envoi : lecture page par page en tâche de fond (6.13, décision A).
- [x] 2. Page illisible citée, non facturée, au choix du client (6.13, décision B).
- [ ] 3. Guichet commun scans + extension en place (6.13) ; **reste à mesurer avec 5 à 10 clients simultanés**.
- [x] 3 bis. Aperçu figé pendant un « traduire quand même » : un rendu tient le verrou de la traduction pendant tout le moteur (≈ 280 s sur 285 pages), un report en attente bloque les aperçus du document et chaque report relance un rendu complet. À revoir (rendu sur un instantané, ou une seule invalidation en fin de travail) avant l'ouverture. **Fait** : le rendu lit la traduction et l'état OCR sous verrou de lecture (quelques ms), rend un instantané hors verrou, puis reporte ses retouches sans écraser une page modifiée entre-temps (`tests/test_ocr_moteur_pages.py`).
- [x] 3 ter. Vérifier qu'une clôture de travail rejouée ne refacture ni ne rembourse une page déjà débitée par « traduire quand même ». **Fait** : hors budget, correct tel quel ; en budget, deux défauts corrigés (relevé du job introuvable dans la copie → document passé en erreur et tout rendu ; page traduite après coup rendue) — le relevé est gardé dans la copie et les pages traduites de la copie restent dues (`tests/test_ocr_facturation_pages.py`).
- [ ] 4. Corriger la documentation du §6.
- [ ] 5. Décider du japonais en langue d'arrivée (voir décision C).

**À prévoir pour le serveur :**
- [ ] Image construite depuis le `Dockerfile`, avec accès HTTPS à `huggingface.co` pendant la construction (modèles PP-OCR). Aucune variable d'environnement n'est à ajouter.
- [ ] 2 vCPU et 4 Go de mémoire au minimum, comme prévu dans `deploiement.md`.
- [ ] Un seul processus uvicorn (déjà imposé par `docker-entrypoint.sh`). **Obligatoire depuis 6.13** : le guichet, les verrous de traduction et la liste des pages en cours de lecture n'existent qu'en mémoire.
- [ ] Après un redémarrage, une page dont la lecture était en cours reste « illisible » ; le client peut la relancer.
- [ ] 20 Go de disque au minimum, avec une surveillance du volume des traductions.
- [ ] Si le serveur est en ARM (le `Dockerfile` évoque une machine Oracle) : construire et tester sur cette architecture, non essayée ici.

**À vérifier sur la machine de staging :**
- [ ] Relancer les mesures du §3 sur le vrai processeur, avec un service en charge.
- [ ] Faire un parcours complet par le site : scan accepté, scan refusé sans débit, débit correct, réouverture sans nouvel OCR.
- [ ] Relancer `test_ocr_endpoint.py` et `test_documents_scannes.py`.
- [ ] Vérifier que le frontal ne coupe pas un envoi de 90 s.
- [ ] Examiner à l'œil au moins un scan dense et un scan léger traduits.

## 8. Décisions à prendre

**A. Combien de pages par envoi ?** — *tranché : tâche de fond, page par page (6.13).*
- **3 pages (recommandé) :** ce qui est accepté est tenu, mais un client avec un scan léger se trouve limité sans raison.
- **Garder 10 pages et allonger le délai :** un scan dense de 10 pages occuperait le serveur environ 5 minutes, pendant lesquelles aucun autre scan ne passe.
- **Traiter les scans en tâche de fond, page par page :** c'est la vraie solution pour les longs documents, mais c'est un chantier à part.

**B. Que faire d'une page illisible dans un envoi ?** — *tranché : le reste est traduit, la page n'est pas facturée et le client choisit (6.13).*
- **Refuser en citant la page (recommandé pour l'ouverture) :** « La page 2 n'est pas lisible ». Le changement est petit et le client sait quoi retirer.
- **Traduire le reste et laisser cette page d'origine :** c'est plus agréable, mais il faut décider si cette page est facturée.

**C. Japonais en langue d'arrivée ?**
- **Ne pas le proposer pour l'instant (recommandé) :** l'image ne grossit pas, et l'étude OCR v2 prévoit de ne l'annoncer qu'après mesure.
- **Installer une police japonaise :** l'image grossit, et le rendu reste à vérifier.
