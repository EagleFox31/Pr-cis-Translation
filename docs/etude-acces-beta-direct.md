# Étude — accès Bêta direct et fiche programme simplifiée

## Besoin
1. Une invitation acceptée ou une candidature validée donne l'accès tout de suite, sans étape « Activer ».
2. Ligne participant : format, date et quotas sur une seule ligne.
3. Nouveau programme : case « Fermer les programmes ouverts » avec confirmation.
4. Formulaires : zone d'actions en bas. « Fermer les inscriptions » en rouge à gauche, les autres boutons à droite. Tous les boutons principaux en bleu, y compris « Créer une invitation ».
5. Bouton « Copier le lien d'invitation » à gauche du filtre.

## Existant
- `services/beta.py:186` `activate()` : c'est le testeur qui active lui-même (route `POST /api/beta/activate`, bouton sur `BetaPage`). L'activation contrôle e-mail vérifié, inscriptions ouvertes, boîte déjà utilisée, accès précédent en cours. Elle enregistre aussi l'empreinte IP / appareil.
- `services/beta_applications.py:88` : valider une candidature appelle `invite()`, qui crée une inscription « invitée » (`activated_at` vide).
- Un seul programme ouvert à la fois (`otherOpen` côté front, contrôle serveur).

## Choix
- **Candidature validée** : `review()` appelle `invite()` puis active tout de suite pour le compte du candidat, avec les mêmes contrôles qu'`activate()`. On extrait un `activate_enrollment(db, enrollment, user, campaign, signals=None)` commun. Si un contrôle échoue (e-mail non vérifié, par exemple), l'inscription reste « invitée » et l'activation se fait seule à la connexion suivante.
- **Invitation par e-mail** : à la lecture du statut Bêta (`GET /api/beta/...` « me »), une invitation non activée dont l'e-mail correspond s'active automatiquement, avec les signaux de la requête. Le bouton « Activer » disparaît de `BetaPage`.
- Libellé de l'état `invited` : « Invitation envoyée » au lieu de « À activer ».
- Nouveau programme : la case est cochée par défaut s'il existe un programme ouvert. À l'envoi, `window.confirm` nomme les programmes concernés, puis le front ferme chacun (PATCH `state: closed`), crée le nouveau et l'ouvre. Pas de route nouvelle.
- Zone d'actions : composant CSS `.admin-form-footer` (bordure haute, `justify-content: space-between`). Bouton danger rouge : réutiliser la classe danger existante si elle existe, sinon `.admin-btn--danger`.

## Impacts
- Sécurité : les contrôles anti-abus restent identiques, seul le déclencheur change. Tests à adapter : `test_beta_program.py`, `test_beta_applications.py`.
- Pas de migration. i18n FR/EN.

## Risques
- Activation au simple affichage du statut : elle doit rester idempotente et ne jamais lever d'erreur bloquante pour la page (les erreurs sont avalées et l'état reste « invitée »).
