# Étude : vitesse de traduction des images de l'extension

06/11/2026, branche `feat/extension-distribution`, étape 9 de `PASSATION-EXTENSION.md`.

## Besoin

Sur un cours en ligne (module SCORM 937), chaque diapositive porte une image à texte japonais.
Une image mettait 18 à 37 s. Les images passaient une par une, et la même image était refaite pour chaque élève.
Il faut une approche générale, valable sur tous les sites, et non propre à ce lecteur de cours.

## Existant

- Route `POST /api/extension/image` (`backend/app/api/extension.py`) : `verifier` → couverture → **une image à la fois par utilisateur** (`_en_cours`, 429) → budget de page → `traduire_image` → débit si l'image est remplacée.
- `ocr_v2/image.py` `traduire_image` enchaîne la lecture PP-OCR, la traduction des blocs et l'effacement (`erase.py`, choix de la méthode de remplissage par « fantôme ») ; le texte est ensuite redessiné.
- Extension : `contenu/images.ts`, boucle `boucle` séquentielle, la plus visible d'abord. Une mémoire locale IndexedDB (`lib/memoire.ts`) n'évite que les images déjà vues sur ce poste.

## Mesures avant (4 images du module, en série)

| Image | Lecture | Traduction | Effacement | Total |
|---|---|---|---|---|
| 04DID012 | ~2 s | ~4 s | ~27 s | 36,8 s |
| 04DID008 | ~3 s | ~6 s | ~25 s | 37,0 s |
| 04DID002 | ~2 s | ~5 s | ~21 s | 31,0 s |
| 04DID017 | ~2 s | ~3 s | ~12 s | 18,1 s |

C'est l'effacement qui ralentit, et dans l'effacement, FSR (`xphoto.inpaint`) : 20 à 24 s. La plus grande part de ce temps n'est pas le remplissage lui-même, ce sont les essais « fantôme » : FSR est essayé sur 4 positions par zone pour juger s'il vaut mieux que les méthodes simples.

Erreur fantôme de la meilleure méthode simple, mesurée sur 37 zones de 3 images :
- proche de 0 (fond uni) → FSR ne fait jamais mieux ;
- au moins 100 (fond texturé) → FSR gagne ou fait jeu égal.

## Options

| Option | Pour | Contre |
|---|---|---|
| A. Seuils sur l'essai fantôme (FSR non essayé si ≤ 5, pris d'office si ≥ 100, sinon essayé sur une seule position face à la meilleure méthode simple) | Même rendu là où ça compte ; gain important | Seuils empiriques (mesure de 37 zones) |
| B. FSR par groupe de lettres (une boîte par groupe connexe au lieu d'une par lettre) | −25 % sur FSR, rendu identique (écart moyen 0,13) | Les boîtes peuvent se chevaucher : on n'écrit que les pixels du groupe |
| C. 2 images simultanées par utilisateur | Le temps perçu est divisé par ~2 sur une page à plusieurs images | Deux cœurs par utilisateur ; 3 laissés de côté (machine partagée) |
| D. Cache serveur par empreinte SHA-256 des octets + langue | Une image déjà traduite revient en ~10 ms, pour tous les comptes | Les images traduites sont gardées : question de confidentialité (tranchée) |
| E. Préchargement de la diapo suivante (lecteur à `data.js`) | Remplacement immédiat | Propre à un lecteur ; écarté, gardé comme futur « module par plateforme » |

## Choix

A + B + C + D.

- **Crédit débité quand même** sur un résultat en cache (décision du 06/11). Le budget de page s'applique comme d'habitude.
- **Confidentialité validée** (06/11) :
  - le cache est partagé entre comptes, sans aucune liste ni recherche : il faut renvoyer l'image elle-même pour la retrouver ;
  - chaque entrée est effacée 30 jours après son écriture (contrôle à la lecture, plus une purge lors d'une écriture, au plus toutes les 6 h) ;
  - seules les images remplacées y entrent, jamais les images de vidéo (chaque arrêt sur image diffère), ni un rendu fait à la hâte (délai dépassé, zones remplies par Telea sans analyse) ;
  - clé = SHA-256 + langue + `VERSION` (à incrémenter quand le rendu change) ; une langue hors format `[A-Za-z0-9_-]{1,16}` n'utilise pas le cache.
- Stockage : `TRANSLATIONS_DIR/_images_extension/<2 car.>/<clé>.{bin,json}`, écrit de façon atomique (le binaire d'abord). Un échec d'écriture ne fait jamais échouer la requête.
- Journal serveur, une ligne par image : `Extension, image : lecture … s, traduction … s, effacement … s, total … s`.
- Extension : `lib/parallele.ts` (`enParallele`), `PARALLELE = 2`. Un même envoi est partagé entre deux éléments qui montrent la même image (clé langue + URL).
- Exception assumée : `api/extension.py`, fichier interdit d'ordinaire, est modifié pour la concurrence et le cache.
- Tests :
  - `tests/racine.py` coupe le cache pour toutes les suites (`PRECIS_CACHE_IMAGES=0`), sinon une image vue lors d'une exécution changerait le résultat de la suivante ;
  - `tests/test_cache_images.py` l'active dans un dossier temporaire.

## Mesures après (mêmes images, mêmes modèles)

| | Série | 2 à la fois | Déjà en cache |
|---|---|---|---|
| 4 images | 56,9 s (contre 123 s) | 32,7 s | 41 ms |
| Par image | 10,2 / 25,5 / 10,4 / 10,8 s | 10,2 / 27,5 / 11,3 / 11,2 s | ~10 ms |

04DID008 reste lente (~17 s d'effacement : 11 vrais remplissages FSR sur fond texturé). C'est accepté : là, FSR est vraiment le meilleur.

## Impacts

- Disque : une image traduite pèse de quelques dizaines à quelques centaines de Ko et vit au plus 30 jours.
- CPU : au plus 2 OCR simultanés par utilisateur. La limite de la route passe de 30 à 60 appels par minute : les images en cache reviennent en quelques ms, deux à la fois, et un refus du limiteur arrêterait toute la file.
- Aucune migration, aucun changement de tarif.

## Risques

- Seuils fantôme mesurés sur un seul cours : à revoir si des fonds d'un autre genre se dégradent.
- Le cache sert le rendu du moteur au moment de l'écriture : quand le moteur change, incrémenter `cache_images.VERSION`.
- Risques acceptés (revue du 06/11) :
  - deux écritures simultanées de la même clé peuvent mêler le JSON de l'une et le binaire de l'autre ; les deux rendus valent pour la même image ;
  - la purge (au plus toutes les 6 h) tourne dans le fil d'une requête ;
  - deux travailleurs de l'extension peuvent s'écraser le message du bandeau (le dernier gagne) ;
  - une annulation de requête pendant l'OCR libère bien la place (`finally`).
