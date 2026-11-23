# Étude : présenter les erreurs et les informations sans gêner l'utilisateur

*05/11/2026 — tâche 6.14 du plan (PASSATION.md). Étude seule, aucun code modifié.*

## 1. Besoin

Un système de messages plus adapté que l'actuel : l'utilisateur doit voir ce qui compte, au bon endroit, sans être interrompu pour rien ni rater une erreur.

## 2. Existant (mesuré le 05/11)

| Mécanisme | Où | Constat |
|---|---|---|
| Notification flottante `components/ui/Toast.tsx` (`showToast`) | 22 appels, 9 fichiers (Home 4, InviteModal 5, admin…) ; monté une fois dans `App.tsx:83` | Disparaît seule : 4 s, **6 s pour une erreur**, même si la souris est dessus. Couleurs écrites en dur. |
| Bandeau `components/ui/Alert.tsx` (`ui-alerte`) | Connexion, inscription, code | Bon modèle : `role="alert"`, jetons CSS. Seulement 3 écrans. |
| Bandeau d'erreur de traduction | `StorySection.tsx:346` | Bien placé (au-dessus du document) mais style en ligne recopié, **sans `role="alert"`** : un lecteur d'écran ne l'annonce pas. |
| `beta-error`, erreurs de `PaymentModal`, `FileUploader` | Bêta, paiement, dépôt | Trois styles de plus, chacun le sien. |

Exemple concret du défaut principal : l'utilisateur clique « Arrêter », l'arrêt échoue (`Home.tsx:424`). Une carte rouge apparaît en haut à droite, loin du bouton, et s'efface au bout de 6 s. S'il regardait son document, il ne l'a jamais vue — et croit que la traduction est arrêtée.

## 3. Références étudiées

- **Material Design 3 (snackbar)** : un seul message à la fois, bref, au plus une action ; réservé aux retours sur une action qui vient d'être faite.
- **Carbon (IBM)** et **Atlassian** : distinguent message en ligne (près de l'élément), bandeau de section, notification flottante, fenêtre. Une erreur qui demande d'agir **ne s'efface pas seule**.
- **GOV.UK** : erreur de formulaire écrite à côté du champ, avec un résumé en haut ; le texte dit quoi faire, pas un code.
- **Nielsen Norman Group** : le message doit apparaître là où l'utilisateur regarde ; plus il interrompt, plus il doit être rare.
- **WCAG 2.2** : 2.2.1 (un message qui disparaît doit laisser le temps de le lire : pause au survol ou au clavier) et 4.1.3 (un message d'état doit être annoncé aux lecteurs d'écran sans prendre le focus).

## 4. Proposition : quatre niveaux, choisis selon la gravité et l'endroit où l'on regarde

| Niveau | Quand | Exemple dans Précis | Comportement |
|---|---|---|---|
| **1. En ligne** | Le problème concerne un champ ou un élément précis | Fichier refusé au dépôt, e-mail mal saisi | Écrit juste sous l'élément, reste jusqu'à correction |
| **2. Bandeau de section** | Le problème bloque le travail en cours sur un document | Traduction échouée, crédits insuffisants, pages illisibles, arrêt impossible | Au-dessus de l'aperçu, avec un bouton qui règle le problème (« Réessayer », « Recharger mes crédits ») ; reste jusqu'à ce qu'on le ferme ou que le problème disparaisse |
| **3. Notification flottante** | Confirmer une action que l'on vient de faire, sans rien demander | « Lien copié », « Forfait modifié », « Traduction terminée » | Disparaît après 4–5 s, **se met en pause au survol ou au clavier**, 3 au plus empilées ; jamais pour une erreur bloquante |
| **4. Fenêtre** | Décision irréversible ou paiement | Supprimer un document, payer | Réservée à ces cas, jamais pour informer |

Plus un cas propre aux travaux longs (file OCR de plusieurs minutes) : si l'utilisateur est parti sur un autre onglet, le titre de l'onglet change (« ✓ Traduction prête — Précis ») ; une notification du navigateur seulement s'il l'a autorisée lui-même (option, pas par défaut).

**Règles d'écriture** (toutes les langues) : dire ce qui s'est passé, pourquoi en une phrase, et quoi faire ; pas de code d'erreur visible ; un seul message par événement (pas une carte flottante *et* un bandeau pour la même erreur).

## 5. Ce que cela change à l'écran

- L'échec de « Arrêter » passe d'une carte rouge éphémère en haut à droite à un bandeau persistant au-dessus du document : « L'arrêt n'a pas abouti, la traduction continue. [Réessayer] ».
- Les confirmations restent des cartes flottantes, mais ne s'effacent plus pendant qu'on les lit.
- Tous les bandeaux ont le même aspect (celui de `Alert.tsx`, étendu à « attention » avec un bouton d'action) et suivent les jetons du site.

## 6. Plan de réalisation proposé (6.14)

1. Étendre `Alert.tsx` : ton `warning`, bouton d'action, bouton fermer ; jetons CSS.
2. `Toast.tsx` : pause au survol/focus, 3 au plus, jetons CSS, erreurs non bloquantes gardées jusqu'à fermeture.
3. Remplacer les cinq styles d'erreur (`StorySection`, `beta-error`, `PaymentModal`, `FileUploader`) par `Alert` ; reclasser les 22 appels `showToast` selon le tableau du §4 (les échecs d'arrêt et de relance passent en bandeau).
4. Titre d'onglet à la fin d'un travail long.
5. Vérification : tsc, lint, build, Playwright à 1280 et 360 px, lecteur d'écran sur un bandeau et une carte.

À décider par l'utilisateur : notification du navigateur en fin de travail (proposée en option, désactivée par défaut).
