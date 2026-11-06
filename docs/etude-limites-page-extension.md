# Étude — limites par page de l'extension (anti-abus)

## Besoin
Nombre de pages traduites illimité, mais chaque page plafonnée, avec une marge
généreuse, sur tout ce qui fait grossir l'usage DeepSeek : longueur du texte,
nombre d'appels et nombre d'images.

## Existant
- `POST /api/extension/segments` : 300 segments, 20 000 caractères et 10 000 de
  contexte **par appel**, 60 appels par minute. Facturation au volume
  (1 500 caractères = 1 page équivalente), mais un forfait illimité
  (`get_plan_monthly_pages` → `None`) ne paie rien au volume : c'est la faille.
- `POST /api/extension/image` : 30 par minute, une à la fois par utilisateur.
- Rien ne borne **une page** : un fil qui défile sans fin (réseau social) ou un
  livre entier dans une page envoie des lots sans fin.
- Le serveur tourne avec un seul worker (`docker-entrypoint.sh`) : un compteur
  en mémoire est cohérent.

## Ce qui gonfle l'usage DeepSeek, par page
| Facteur | Borne retenue |
|---|---|
| Texte envoyé (balises `[[n]]` comprises, car elles coûtent des jetons) | 150 000 caractères (~100 pages équivalentes, un très long article Wikipédia) |
| Nombre de lots (chaque lot renvoie le prompt et jusqu'à 2 500 caractères de contexte) : défilement infini, mutations | 300 lots |
| Images de la page (OCR + traduction) | 40 |
| Images de vidéo (à la demande, sur pause) | 100 |

Le texte déjà en mémoire locale ne part pas au serveur et ne compte donc pas.
Un lot ou une image est accepté tant que le compteur est **sous** la borne :
le dernier lot peut dépasser (au plus 20 000 caractères), ce qui va dans le sens
de la générosité. Le compteur augmente avant l'appel au moteur : un échec
du moteur a déjà coûté.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Bornes seulement dans l'extension | Simple | Contournable : ce n'est pas une protection |
| B. Le serveur compte par identifiant de page (`X-Page`) | Vraie borne pour un client normal, rien à stocker en base | Un client modifié peut changer d'identifiant à chaque appel |
| C. Plafond de volume par utilisateur et par jour | Ne se contourne pas | Contraire à « pages illimitées » |

**Choix : B**, avec l'extension qui affiche un message clair une fois la borne
atteinte. L'identifiant est un UUID tiré au hasard pour chaque adresse visitée
pendant le chargement de la page : l'adresse ne quitte jamais le navigateur.
Une navigation dans une application web (nouvelle adresse) ouvre un nouveau
budget ; arrêter puis relancer la traduction sur la même adresse, non.
Les compteurs restent en mémoire 6 h, avec au plus 50 000 pages suivies.

## Impacts
- Aucune migration, aucune donnée gardée (compteurs en mémoire, effacés au redémarrage).
- Nouvelle réponse `413 {"reason": "page_limit", "limite": …}` ; l'extension
  arrête alors le texte ou les images de cette page et l'explique dans le bandeau.
- Les traductions déjà faites restent affichées.

## Risques et points à trancher
- Contournement par un client modifié (option B) : il reste limité par le débit
  (60 lots et 30 images par minute). Si l'abus apparaît sur les forfaits
  illimités, ajouter l'option C pour ces forfaits seulement (plafond journalier
  très haut).
- Les valeurs se règlent dans `backend/app/services/limites_page.py`.
