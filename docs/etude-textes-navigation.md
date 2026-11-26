# Étude : textes affichés quand on quitte, rouvre, met en pause ou reprend un document

## 1. Besoin
Signalé par l'utilisateur après la démo de la file d'attente :
- Il a quitté une traduction en cours puis ouvert un autre document qui attendait son tour. Rien ne lui a dit que ce document était en attente.
- Il a ouvert un document pas encore traduit. L'écran affichait le message d'harmonisation, sans qu'il sache pourquoi.

Critère : à chaque ouverture et pour chaque état (en file, en cours, en pause, annulé, interrompu, terminé), le texte affiché correspond à l'état réel du document.

## 2. Existant
- Le bandeau de file (`components/story/QueueBanner.tsx`) n'était alimenté que par le flux de la traduction lancée depuis l'écran. Un document rouvert depuis « Mes documents » n'avait pas cette information.
- Les avis d'un document (harmonisation, pages réduites…) étaient lus par l'écran sans tenir compte de son état : un avis gardé d'une traduction précédente du même fichier s'affichait sur un document pas encore traduit.
- La carte de la bibliothèque affichait « Traduction en cours » pour un document qui attendait encore son tour.
- Aucun texte n'expliquait l'état « interrompue » à la réouverture d'un document.

## 3. Options

| Option | Pour | Contre |
|---|---|---|
| A. Le serveur renvoie l'état de file et les seuls avis valables pour l'état du document ; l'écran les affiche | Une seule source de vérité, juste aussi pour la bibliothèque et à la réouverture | Touche le serveur et l'écran |
| B. L'écran devine l'état à partir de ce qu'il a déjà | Rien à changer côté serveur | Faux dès que le document a été lancé ailleurs ou que la page a été rechargée |

Choix : **A**.

## 4. Ce qui a été fait
- Serveur :
  - `avis_document.pour_document` ne renvoie les avis de fin (harmonisation…) que pour un document terminé ;
  - `scheduler.etat_file` donne la position et l'attente estimée ;
  - `documents.py` ajoute `attente` à chaque document et l'en-tête `X-File-Attente` à l'aperçu d'un document en file (réponse 202) ;
  - `__init__.py` rend l'en-tête lisible par l'écran.
- Écran :
  - `useDocumentLibrary.ts` lit `attente` et `X-File-Attente` ;
  - `Home.tsx` alimente le bandeau de file pour un document rouvert et affiche le texte d'arrêt (pause, annulation, interruption) à sa réouverture ;
  - `DocumentCard.tsx` affiche « En file d'attente » au lieu de « Traduction en cours » ;
  - nouvelles clés FR/EN `library.status_queued` et `story.stopped_interrupted`.

## 5. Vérification dans un vrai navigateur
Trois documents lancés à la suite, puis ouverture, sortie et réouverture de chacun, pause, reprise, annulation et interruption.
- Document en file : bandeau « 1 document devant vous, environ N min » à la réouverture ; carte « En file d'attente ».
- Document pas encore traduit : plus de message d'harmonisation. Il n'apparaît qu'une fois le document terminé.
- Pause, annulation, interruption : le texte correspondant s'affiche à la réouverture, et les menus proposent les bonnes actions pour chaque état.
- Reprise : les 7 pages déjà traduites réapparaissent dans l'aperçu en une dizaine de secondes (le serveur confirme « reprise de 7 diapositive(s) déjà traduite(s) »). La carte de la bibliothèque affiche « 0/16 » quelques secondes de plus, jusqu'à son prochain rafraîchissement. Cet écart est bref et se corrige seul : aucun changement.

## 6. Risques et limites
- La durée affichée reste une estimation (médiane des derniers travaux).
- L'en-tête `X-Render` du mode démo n'est lisible que sur l'environnement de démo, ce qui ne change rien en production.

## 7. Tests
`test_avis_document.py` 22/22, `test_file_attente.py` 4 OK, `test_memoire_conteneur.py` 24 OK, `test_stockage.py` 20/20 ; contrôle de types de l'écran sans erreur.
