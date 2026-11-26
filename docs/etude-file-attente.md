# Étude : file d'attente visible

*26/11/2026. Branche `fix/memoire-detection-images` (suite du correctif mémoire).*

## 1. Besoin

Depuis le correctif mémoire, le serveur de production (1 Go) ne traite qu'**un travail à la fois** (une « place »). Les autres attendent. Un utilisateur qui attend doit :

- savoir qu'il est en file d'attente et à quelle position ;
- avoir une estimation de la durée d'attente ;
- si l'attente est longue, recevoir une indication vague (« plus de 15 min ») plutôt qu'un chiffre précis qui décourage ou qui s'avère faux.

## 2. Ce que disent les usages reconnus

| Source | Règle retenue |
|---|---|
| D. Maister, *The Psychology of Waiting Lines* (1985) | Une attente inexpliquée ou d'une durée inconnue paraît plus longue qu'une attente expliquée et chiffrée. Il faut donc dire **pourquoi** on attend et **combien de temps**. |
| J. Nielsen, *Response Times* (1993) | Au-delà de 10 s, l'utilisateur doit voir où il en est, et l'indication doit **évoluer**. Un message figé fait croire que tout est bloqué. |
| Files d'attente des sites de billetterie (Queue-it, par exemple) | On affiche la position et un temps arrondi. Au-delà d'un seuil, on écrit « plus d'une heure » au lieu du chiffre exact. |
| Parcs d'attractions (Disney, par exemple) | On **surestime** légèrement : finir plus tôt que prévu fait plaisir, finir plus tard agace. |

Les règles qui en découlent pour nous :
1. Le temps est arrondi à la minute supérieure : « moins d'une minute », puis « environ 3 min ».
2. Au-delà d'un seuil, on écrit « plus de 15 min ».
3. La position et le temps sont mis à jour à chaque fois que la file avance.
4. On dit pourquoi on attend : « D'autres documents sont en cours de traduction ».

## 3. Existant

**Serveur**, `backend/app/services/scheduler.py` :
- Il y a deux files : les traductions (`scheduler`, 2 workers) et les scans (`scheduler_scans`, 3 workers). Elles se partagent le `budget` mémoire (`memoire.Budget`, un sémaphore). En production, ce budget n'offre qu'une seule place.
- `submit()` émet `queued {ahead}` uniquement si tous les workers de **sa** file sont occupés. `ahead` compte les travaux qui attendent dans cette file.
- Un worker qui ne trouve pas de place mémoire émet `queued {ahead: 0}`, puis attend.
- Aucun événement n'est renvoyé ensuite : la position affichée ne bouge plus jusqu'au démarrage.

**Écran** :
- `hooks/useStreamingTranslation.ts:346` lit `queued` et en tire `queuePosition`.
- `components/story/StorySection.tsx:289` affiche un bandeau bleu avec `story.queued_ahead` (« N traductions devant la vôtre ») ou `story.queued_soon` (« démarrage imminent »).
- Les textes existent en français et en anglais (`locales/*/translation.json:154-156`).

### Défauts constatés (exemple concret)

Trois utilisateurs lancent un PPTX presque en même temps. Le serveur n'a qu'une place.
- A démarre.
- B est pris par le 2ᵉ worker de traduction, qui ne trouve pas de place. B voit « **démarrage imminent** » alors qu'il attendra environ 2 min 30.
- C attend que l'un des deux workers se libère. Sa file est vide, donc `ahead` vaut 0 : C voit aussi « **démarrage imminent** », alors qu'il attendra environ 5 min.
- Quand A finit, rien n'est renvoyé. C garde le même message jusqu'à son démarrage.

Le vrai point de blocage est la **place mémoire**, partagée par les deux files. Or la position est calculée sur la file de traduction seule, sans compter les travaux qui attendent une place mémoire ni les scans.

## 4. Options

### Calcul de la position

| Option | Pour | Contre |
|---|---|---|
| A. Garder le calcul actuel (file de traduction seule) | Aucun changement | Faux dès que la mémoire est le point de blocage, c'est-à-dire tout le temps en production |
| **B. Un registre unique des travaux qui attendent, tenu par le budget** (ordre d'arrivée, traductions et scans confondus) | Une seule vérité ; la position est juste ; l'ordre d'attribution des places devient équitable (aujourd'hui le sémaphore réveille n'importe quel travail) | Il faut remplacer le sémaphore par une file ordonnée, ce qui touche le cœur du correctif mémoire. On le couvre par des tests. |

### Estimation de durée

| Option | Pour | Contre |
|---|---|---|
| a. Durée fixe en variable (par exemple 150 s par travail) | Simple et prévisible | Fausse pour une page seule comme pour un gros PPTX |
| **b. Médiane des 10 derniers travaux terminés**, 150 s au démarrage du serveur | Suit la charge réelle ; la médiane n'est pas faussée par un travail géant | Les travaux qui attendent n'ont pas tous la même taille. La surestimation volontaire et le « plus de X min » couvrent cet écart. |
| c. Estimation selon la taille de chaque document | La plus précise | Complexe (pages, images, formats) ; gain faible pour un affichage arrondi |

Formule retenue : attente ≈ arrondi supérieur de (travaux devant + travaux en cours) ÷ places × médiane. Elle compte un travail en cours comme s'il démarrait à peine, ce qui surestime légèrement l'attente (règle 4 de la section 2).

### Mise à jour

À chaque place libérée ou prise, le serveur renvoie `queued {ahead, attente_s}` à chaque travail encore en attente. Il n'y a pas d'interrogation répétée côté écran : le flux SSE existe déjà.

## 5. Choix recommandé

**B + b**, et le seuil vague en variable :
- `FILE_ATTENTE_SEUIL_MIN = 15`. Au-delà, on affiche « plus de 15 min ». `None` affiche toujours le chiffre (convention « Limites = None »).
- `FILE_ATTENTE_DUREE_DEFAUT_S = 150` (durée mesurée sur le PPTX TSA).
- Textes affichés :
  - « En file d'attente : 2 documents devant le vôtre. Début estimé dans environ 5 min. »
  - « En file d'attente : votre document passe juste après celui en cours. Début dans moins d'une minute. »
  - « En file d'attente : 6 documents devant le vôtre. Début dans plus de 15 min. Vous pouvez fermer cette page, la traduction continuera. »

  La dernière phrase n'est affichée qu'au-delà du seuil (point 3 de la section 8).

## 5 bis. Analyse de l'interface (normes UI, UX et CX)

Le bandeau bleu existant (`StorySection.tsx:289`) est **réutilisé**. Il garde le même style que l'avis bleu `translationNotice`, sans créer de nouvel écran. Le tableau confronte chaque choix aux normes reconnues.

| Norme | Exigence | Application dans le bandeau |
|---|---|---|
| Nielsen n° 1 : visibilité de l'état du système | Toujours dire où l'on en est, avec un retour qui évolue | La position et la durée se mettent à jour à chaque fois que la file avance. Le temps restant se recalcule toutes les 30 s à l'écran. |
| Nielsen n° 2 : langage de l'utilisateur | Pas de jargon technique | On parle de « documents » et de minutes arrondies, jamais de « travail », de « job » ou de « place mémoire ». |
| Nielsen n° 3 : contrôle et liberté | Pouvoir sortir de l'attente | Les boutons Pause et Arrêter existants restent disponibles. Au-delà du seuil, on indique que la page peut être fermée et que le document se retrouve dans « Mes documents » (le libellé du menu). |
| Nielsen n° 4 : cohérence | Mêmes composants, même ton | On garde le même bandeau, les mêmes couleurs et la même icône qu'aujourd'hui. Les phrases sont construites comme les autres avis de l'application. |
| Nielsen n° 5 et 9 : erreurs | Ne pas laisser croire à une panne | Si l'attente dépasse l'estimation, le bandeau ne reste pas sur « environ 0 min ». Il affiche : « L'attente est plus longue que prévu. Votre document démarrera dès que possible. » |
| Nielsen n° 8 : minimalisme | L'essentiel seulement | Deux phrases au plus : la position, puis le début estimé. La troisième (« vous pouvez fermer ») n'apparaît qu'au-delà du seuil. |
| ISO 9241-110 : conformité aux attentes | Une estimation ne doit pas surprendre | Le temps est arrondi à la minute supérieure et légèrement surestimé. Il n'y a ni compte à rebours à la seconde, ni fausse barre de progression : l'attente n'est pas un avancement. |
| Material Design et Apple HIG : indicateurs de progression | Indicateur indéterminé quand la durée n'est pas certaine | On garde l'icône qui tourne, et non une barre en pourcentage. |
| WCAG 2.2, critère 4.1.3 (messages d'état) | Annonce aux lecteurs d'écran sans déplacer le focus | `role="status"` sur le bandeau (il n'y en a pas aujourd'hui). Le texte change au plus une fois par minute, donc les annonces restent rares. |
| WCAG 2.2, critère 1.4.3 (contraste) | Au moins 4,5:1 | Texte #1e40af sur fond #eff6ff : environ 8:1. |
| WCAG 2.2, critères 1.4.1 et 2.3.3 (couleur, animation) | Ne pas reposer sur la couleur seule ; respecter le réglage « réduire les animations » | Le sens est porté par le texte. L'icône est cachée aux lecteurs d'écran (`aria-hidden`) et ne tourne plus si « réduire les animations » est activé. |
| CX : Maister, et le principe de surestimer | Une attente expliquée, juste, qui finit plus tôt que prévu | La position est juste, on dit pourquoi on attend (« devant le vôtre »), on surestime et on reste vague au-delà de 15 min. |

## 6. Impacts

- **Données** : aucune migration. La médiane est gardée en mémoire du processus et se réinitialise au redémarrage.
- **Sécurité** : `ahead` ne révèle que le nombre de travaux, jamais qui les a lancés.
- **Performance** : négligeable (une liste de quelques éléments).
- **Traductions de l'interface** : nouvelles clés en français et en anglais, accords au singulier et au pluriel.
- **Scans** : l'écran de scan ne lit pas encore `queued`. Avec le registre unique, les scans comptent dans la position des traductions. Leur propre affichage est à vérifier pendant l'implémentation.
- **Déploiement** : deux variables facultatives, avec des valeurs par défaut sûres.

## 7. Risques

- Remplacer le sémaphore pourrait bloquer les travaux si une place n'était jamais rendue. Le `finally` qui rend déjà la place est gardé, et des tests couvrent la concurrence (prendre, rendre, ordre, annulation pendant l'attente).
- Un travail mis en pause ou annulé pendant l'attente doit sortir du registre, sinon il fausse la position.

## 8. Points à trancher par l'utilisateur

1. Le seuil vague : **15 min** (recommandé), 10 min ou 30 min ?
2. L'ordre des places : **ordre d'arrivée** (recommandé), ou les forfaits supérieurs passent devant même pour la place mémoire ?
3. La phrase « Vous pouvez fermer cette page, la traduction continuera » est **vraie** : aucune route n'arrête un travail quand l'onglet se ferme, et le document se rouvre depuis « Mes documents ». Faut-il l'afficher **seulement au-delà du seuil** (recommandé) ou toujours ?
