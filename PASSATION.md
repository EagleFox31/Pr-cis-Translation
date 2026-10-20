# PASSATION

## 1. Objectif en cours
Invitations : depuis n'importe quel compte, saisir une ou plusieurs adresses et envoyer un e-mail personnalisé, à la marque Précis, invitant à découvrir l'app (https://precis-translator.trigenys.com/).
Worktree `C:\Users\IBRAH\Documents\Projets\Precis-Translator-invitations`, branche `feat/invitations` (commits `164ee4f` backend, `ed81196` frontend).

## 2. Fait
- API `POST /api/invitations` : `backend/app/api/invitations.py:43` (constantes l.30-35).
- E-mail : `GABARIT_INVITATION` `backend/app/core/email.py:114`, `send_invitation_email` l.365 ; textes fr/en `TEXTES_INVITATION` dans `backend/app/core/email_content.py:80`.
- Modèle `backend/app/models/invitation.py` + migration `backend/migrations/versions/0010_invitations.py` (après 0009_abonnements).
- Front : `frontend/src/components/invite/InviteModal.tsx` + `inviteBus.ts` ; monté dans `pages/Home.tsx` à côté de `SupportModal` ; bouton « Inviter des proches » au-dessus de « Aide & support » dans le pied de `components/library/DocumentLibrary.tsx` ; bloc i18n `invite.*` (fr/en).
- Preuves : `tests/test_invitations.py` 19/19, `tests/test_emails.py` 27/27, `npm run lint` (tsc + check-i18n) OK, `vite build` OK.

## 3. Décisions prises
- Anti-abus : 5 req/min (IP), 10 adresses par envoi, 20 invitations/jour/compte, pas de renvoi à la même adresse sous 7 jours : l'e-mail part sous le nom Précis, donc pas de relais de spam.
- Comptes existants et doublons écartés **en silence**, réponse générique `{ok, count}` : sinon l'API permettrait de savoir qui a un compte.
- Expéditeur = marque (`Précis <SMTP_USER>`), `Reply-To` = inviteur : pas d'usurpation SPF/DKIM, mais les réponses vont à la personne.
- Nom et mot de l'inviteur échappés en HTML ; sujet ramené à une seule ligne (pas d'injection d'en-tête).
- Une trace n'est enregistrée qu'après un envoi réussi ; si tout échoue, 503.
- Langue de l'e-mail = langue de l'interface de l'inviteur (Accept-Language).

## 4. Plan
1. [x] Modèle + migration 0010
2. [x] Gabarit e-mail + textes fr/en + tests e-mail
3. [x] Endpoint + garde-fous
4. [x] Fenêtre front + bouton + i18n ; lint/build
4b. [x] Étude `docs/etude-invitations.md` (rédigée après coup)
4c. [x] Décisions : SMTP actuel gardé ; « Copier le lien » ; purge > 30 j au démarrage + après chaque envoi (pas d'attribution ?ref=, pas de rappel)
5. [x] `/code-review` + convergence : envoi en tâche de fond (pas d'oracle temporel, pas de session tenue pendant SMTP), traces réservées sous `pg_advisory_xact_lock` par compte, trace effacée si l'envoi échoue, `app/services/invitations.py`, TLS 465 corrigé (`start_tls=(SMTP_PORT != 465)`), front try/finally + toast 422 + indice « 10 max »
6. [ ] `tests/test_invitations_api.py` : à lancer par l'utilisateur (base requise) ←
7. [ ] Vérif Playwright de la fenêtre : non faite (connexion à la bibliothèque requise)
8. [x] Note déploiement inutile : en prod, `docker-entrypoint.sh` applique les migrations (en local, `alembic upgrade head` à la main ; 0010 appliquée le 20/10)
9. [ ] Push + PR vers main

**Hors plan** : rien.

## 5. Pièges / contexte
- Ne pas toucher le dépôt principal `Precis-Translator` (branche `feat/paiement-paddle`, modifs non commitées).
- Ne jamais lire ou grep les `.env` ; `backend/.env` est LIVE (Fapshi).
- Le worktree n'a pas de `.env` : `test_invitations_api.py` a besoin de `DATABASE_URL`. Le charger depuis le `.env` principal a été refusé. À lancer par l'utilisateur :
  `cd backend && PYTHONUTF8=1 <venv>/python.exe tests/test_invitations_api.py` (la table est créée puis supprimée si 0010 n'est pas appliquée).
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`.
- Front : `npm run lint` = tsc + contrôle de concordance i18n ; pluriels i18next en `_one` / `_other`.
- Sans `EMAIL_ENABLED` ou `SMTP_HOST`, l'e-mail est seulement journalisé `[DEV]`.
