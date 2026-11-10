# Étude — Extension gratuite, limitée par page, élargie par forfait

Demande du 08/11/2026. Remplace la facturation en crédits de l'extension.

## 1. Règle demandée

- L'extension ne consomme **aucun crédit**. Elle est gratuite, dans des limites
  **par page** (même adresse) : caractères traduits et images traduites.
- Une page dans la limite : tout est traduit. Une page qui dépasse : on traduit
  **les premiers** blocs et les premières images jusqu'à la limite, le reste
  reste en original.
- Les **images sans texte** (ou seulement des étiquettes, des références) ne
  comptent pas.
- Page qui se traduit **au fur et à mesure** (cours SCORM, défilement infini) :
  les compteurs s'additionnent sur la même page. Limite atteinte → message
  « Passez à Starter ou Pro pour continuer sur cette page ».
- **Starter et Pro** : tous leurs avantages actuels (pages de documents
  incluses) + des limites d'extension plus larges.
- **Bêta** : seule la formule gratuite est proposée ; l'offre payante de
  l'extension n'est pas mise en avant pendant la bêta.

## 2. Existant (mesuré dans le code)

| Élément | Aujourd'hui | Écart |
|---|---|---|
| Texte | `debiter_texte` : 1 500 car. = 1 crédit (`services/extension.py:27,109`) | à retirer |
| Image | `debiter(…, 1)` par image remplacée (`api/extension.py:279`) | à retirer |
| Bornes par page | `limites_page.py` : 50 000 car., 30 images, 120 analyses, 100 lots, 20 captures | mêmes pour tous ; à rendre fonction du forfait |
| Page | identifiant opaque `X-Page` tiré par l'extension, jamais l'adresse | gardé |
| Durée des compteurs | 6 h, en mémoire (perdus au redémarrage) | trop court : il suffit d'attendre 6 h ou un redéploiement pour repartir à zéro |
| Dépassement | refus en bloc (le lot entier est refusé) | à changer : traduire les premiers blocs jusqu'à la limite |
| Image sans texte | déjà non comptée en « images », seulement en « analyses » | conforme |

## 3. Repères pour fixer les limites

- **Page de site** : un article de presse fait 4 000 à 8 000 caractères ; une
  page de documentation 5 000 à 15 000 ; un long article Wikipédia 30 000 à
  60 000.
- **Cours TEAM-GP** (capture du 08/11) : ~22 diapositives par module, ~300 à
  800 caractères et 1 image à texte par diapositive → un module complet ≈
  10 000 caractères et 15 à 20 images.
- **Coût** : le texte coûte peu (moteur IA, quelques millièmes d'euro pour
  10 000 caractères). Le poste cher est l'**image** : 2 à 7 s de calcul serveur
  (OCR + effacement + rendu). C'est elle qu'il faut surtout borner.

## 4. Limites retenues (décision du 08/11/2026)

Par page (même adresse), **sans limite de temps** : un compteur atteint le
reste définitivement. Pro est **illimité** par page, pour qu'aucune page ne
reste bloquée sans solution.

| | Gratuit (et bêta) | Starter | Pro |
|---|---|---|---|
| Caractères traduits / page | **30 000** | 100 000 | illimité |
| Images traduites / page | **30** | 80 | illimité |
| Texte max par image | 2 000 car. | 4 000 | illimité |
| Pages différentes traduites / jour | **30** | 150 | 500 |

Ce que cela donne :
- **Gratuit** : un article, une longue documentation, un module de cours
  TEAM-GP complet (≈ 10 000 car., 15 à 20 images), et jusqu'à 30 pages
  différentes par jour.
- **Starter** : les pages très longues et les cours à plusieurs modules sur
  la même adresse.
- **Pro** : aucune page bloquée ; seule la limite de pages par jour protège
  le serveur contre un usage automatisé.
- **Limite par jour** (décision du 08/11) : un nombre de pages différentes
  commencées dans la journée. Revenir sur une page déjà commencée ne compte
  pas une nouvelle page. Remise à zéro chaque jour (minuit UTC) ; les
  compteurs par page, eux, restent.
- **Coût** : au maximum, un compte gratuit peut demander 900 images par jour
  (30 pages × 30), soit jusqu'à ~1 h de calcul serveur. Acceptable en bêta ;
  à surveiller dans les statistiques.
- **Bêta** : tout le monde en Gratuit, bandeau de limite neutre, sans offre
  payante proposée.

Bornes techniques gardées, pour tous : 120 analyses d'image, 100 lots,
20 captures vidéo par page.

## 5. Changements à prévoir

1. **Backend** : retirer les débits de crédit de l'extension ; `limites_page`
   prend les bornes du forfait de l'utilisateur ; quand la limite tombe au
   milieu d'un lot, traduire les premiers blocs et renvoyer le reste non
   traduit avec `limite: "texte" | "images"`.
2. **Compteurs** : en base, permanents (table `extension_usage` : utilisateur,
   page, caractères, images ; + le jour de première traduction, pour compter les pages commencées par jour),
   au lieu de la mémoire sur 6 h. Passer à Starter ou Pro relève la limite des
   pages déjà comptées.
3. **Extension** : bandeau « Limite gratuite atteinte sur cette page —
   Starter ou Pro pour continuer » à la place de « Crédits épuisés » ; pendant
   la bêta, bandeau neutre sans proposition payante.
4. **Site** : la page des offres mentionne les limites de l'extension par
   forfait (après la bêta).
5. **Tests** : limite atteinte en cours de lot, cumul sur une même page,
   image sans texte non comptée, 31e page du jour refusée, page déjà commencée acceptée, forfait Starter/Pro.

## 6. Points à trancher

Tous tranchés le 08/11 (§4).
