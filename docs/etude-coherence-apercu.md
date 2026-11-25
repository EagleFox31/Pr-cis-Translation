# Étude — Contrôle de cohérence : prévenir l'utilisateur et mettre l'aperçu à jour

*24/11/2026 — présentations PowerPoint traduites par l'IA.*

## 1. Le besoin

Pendant la traduction, l'utilisateur voit les diapositives traduites une par une.
Une fois toutes les diapositives traduites, un contrôle relit le document entier.
Il corrige les termes traduits de façon différente selon les diapositives.

Exemple mesuré : « Gerbeur » est traduit par « Stacker » sur quinze diapositives.
Sur la diapositive 17, il reste en français.

Ce contrôle ne peut se faire qu'à la fin. Prenons le mot « Gerbeur » sur la
diapositive 3. Pour savoir s'il a été oublié, il faut voir qu'il est traduit
ailleurs dans le document. Les diapositives 4 à 40 n'existent pas encore au
moment où la diapositive 3 est traduite.

Le problème vient de ce que les corrections sont faites sans le dire.

- Le fichier livré contient la version corrigée.
- L'aperçu montré pendant la traduction n'est jamais mis à jour.
- Quand l'utilisateur rouvre le document, l'aperçu est refait à partir du
  fichier livré. Une diapositive peut alors être différente de celle qu'il a
  vue la veille.

Cas réel : le PowerPoint de 75 diapositives testé le 23/11. Le contrôle a
modifié 577 morceaux de texte sur 21 diapositives : 1, 2, 4, 8 à 14, 23, 29,
31, 32, 34 à 37, 42, 44 et 68. L'utilisateur l'a découvert en rouvrant la
diapositive 1.

**Décision de l'utilisateur (option 2)** : on garde le contrôle à la fin, mais
plus rien ne change sans qu'il le sache.

## 2. Ce qui existe déjà

| Élément | Où | Réutilisable ? |
|---|---|---|
| Contrôle de cohérence | `backend/app/services/translation_runner.py`, `_coherence_document` | Oui. Il connaît déjà la liste des diapositives modifiées (`slides_touchees`), mais ne renvoie que le nombre de morceaux. |
| Mise à jour de l'aperçu par groupe de diapositives | même fichier, `_afficher_slides(nums)` | Oui. C'est l'outil qui affiche chaque diapositive pendant la traduction, et il traite déjà un groupe en une seule conversion lors d'une reprise. Il avertit l'écran (événement `partial`), et l'écran recharge l'aperçu. |
| Note affichée à l'écran en fin de traduction | `frontend/src/hooks/useStreamingTranslation.ts`, état `notice` | Oui. Les messages sur les images et sur les objets non traduits (`objets`) s'y ajoutent déjà. |
| Aperçu à la réouverture | rendu à partir du fichier livré (`render_cache.py`) | Inchangé. Il montre déjà la version corrigée. |

## 3. Options

| Option | Effet visible | Pour | Contre |
|---|---|---|---|
| **A. Note + aperçu mis à jour (retenue)** | Pendant le contrôle, les diapositives modifiées sont redessinées dans l'aperçu. À la fin, une note dit par exemple : « Relecture de l'ensemble : 3 diapositives harmonisées (1, 2, 17). » | Réutilise deux mécanismes existants. Ce que l'utilisateur voit correspond au fichier livré. | Une conversion de plus à la fin, de quelques secondes pour 20 diapositives. |
| B. Note seule | La note s'affiche, mais l'aperçu reste l'ancien jusqu'à la réouverture. | Plus simple. | L'aperçu et le fichier restent différents. Le défaut signalé n'est pas corrigé. |
| C. Aperçu mis à jour, sans note | Les diapositives changent sans explication. | — | C'est précisément le changement non annoncé dont l'utilisateur se plaint. |

## 4. Choix recommandé : A

Le traitement se déroule en trois temps.

1. `_coherence_document` renvoie la liste des diapositives modifiées, et plus
   seulement leur nombre.
2. Juste après, le programme appelle `_afficher_slides(liste)`. La conversion
   est faite une seule fois pour tout le groupe. Si elle échoue, rien ne
   bloque : le fichier livré reste correct.
3. Le serveur envoie un événement `coherence` avec la liste des diapositives
   (`{"slides": [1, 2, 17]}`). L'écran ajoute alors une phrase à la note de fin,
   en français et en anglais. Au-delà de 10 diapositives, la phrase se termine
   par « … et N autres ».

## 5. Impacts

- **Données et migrations** : aucun.
- **Sécurité** : aucun. L'aperçu mis à jour passe par le même point d'accès
  (`/partial`), avec le même filigrane pour les comptes d'essai.
- **Performance** : une conversion LibreOffice de plus à la fin, et seulement
  quand des diapositives ont été modifiées.
- **Traduction de l'interface** : deux phrases à ajouter (`fr`, `en`).
- **Coût** : aucun appel supplémentaire à l'IA.

## 6. Risques

- Si le lien avec l'écran est coupé pendant le contrôle, la note n'arrive pas.
  C'est la même limite que pour les objets non traduits, déjà acceptée.
  L'aperçu rouvert reste juste dans tous les cas.

## 7. Points à trancher

Ce point ne fait pas partie de cette étude, mais il a été constaté sur le même
cas.

Le contrôle n'est pas toujours une amélioration. Deux exemples :

- Diapositive 1 : le titre passe de 3 lignes à 4, parce que la ligne du milieu
  est devenue trop longue.
- Diapositive 2 : les mots « définition des » ont disparu.

La cause : le contrôle fait retraduire toute la phrase, alors qu'il devrait
changer seulement le terme. Ensuite, il ne vérifie pas que le texte tient
toujours dans la largeur.

Une fois la note en place, ces dégradations seront visibles et annoncées, mais
toujours présentes. Deux corrections possibles, à étudier ensuite :

- **Remplacer seulement le terme.** On change uniquement le terme dans la
  traduction existante, sans retraduire toute la phrase. Cela évite les pertes
  comme celle de la diapositive 2.
- **Revérifier la largeur.** Après la correction, on applique la même règle de
  largeur et de retour à la ligne que lors de la première traduction. Cela
  évite les cas comme celui de la diapositive 1.

**Recommandation : traiter ces deux corrections juste après celle-ci, dans une
étude séparée.**

## 8. Messages retrouvés à la réouverture (ajout du 24/11)

**Constat de l'utilisateur.** Il regarde quelques diapositives, quitte l'écran,
puis revient quand la traduction est finie. Le message de fin ne s'affiche
alors jamais. C'est vrai pour tous les messages envoyés pendant la traduction.

**Ce qui se passe aujourd'hui.** Les messages partent une seule fois, en direct,
vers l'écran qui a lancé la traduction. Ils ne sont enregistrés nulle part.
Un document rouvert depuis « Mes documents » n'affiche donc aucun encadré.

| Message | Envoyé par | Retrouvé à la réouverture ? |
|---|---|---|
| Pages scannées lues par OCR | réponse au lancement (`ocr_pages`) | Non |
| Objets laissés dans la langue d'origine | événement `objets` | Non |
| Termes harmonisés (nouveau) | événement `coherence` | Non |
| Bilan des images | événement `images` (écran prêt, pas encore envoyé par ce serveur) | Non |

**Décision de l'utilisateur (option 1)** : chaque message est enregistré avec le
document au moment où il est produit. En rouvrant le document, on retrouve le
même encadré que si l'on était resté.

**Comment.**

- Côté serveur, un seul point de passage : chaque message est à la fois envoyé
  à l'écran et ajouté au fichier `avis.json`, rangé avec la traduction du
  document. On suit le même principe que les choix sur les pages scannées
  (`choix.json`). Pas de changement de base de données. Le fichier disparaît
  avec le document.
- On enregistre les données (liste des diapositives, des objets), pas la phrase.
  La phrase est écrite au moment de l'affichage, dans la langue de l'interface.
- La fiche du document (`GET /api/documents`) renvoie ces messages.
- Côté écran, la fabrication des phrases est sortie dans une fonction commune.
  Le suivi en direct et la réouverture l'utilisent tous les deux : on obtient
  la même phrase dans les deux cas.
- Pendant une traduction suivie depuis « Mes documents », la fiche est relue
  régulièrement. Les messages arrivent donc aussi dans ce cas.

**Limite.** Les documents traduits avant ce changement n'ont pas de messages
enregistrés. Rien n'est recalculé pour eux.

**Plus tard, si le besoin se fait sentir (option 2).** Une pastille « à lire »
sur la ligne du document dans « Mes documents ».

## 9. Plan

1. Serveur : contrôle de cohérence qui renvoie la liste des diapositives,
   aperçu redessiné, message `coherence`. Test : la liste renvoyée est correcte.
2. Serveur : enregistrement des messages (`avis.json`) pour OCR, objets et
   cohérence, et renvoi dans la fiche du document. Tests : un message émis est
   relu dans la fiche ; un fichier abîmé ne casse pas la liste.
3. Écran : fonction commune qui fabrique les phrases (OCR, objets, cohérence,
   images), utilisée en direct et à la réouverture. Vérifier tsc, lint et build.
4. Vérification réelle : un PowerPoint court avec un terme incohérent. On quitte
   l'écran pendant la traduction, on revient à la fin par « Mes documents » :
   l'aperçu est à jour et l'encadré s'affiche.
