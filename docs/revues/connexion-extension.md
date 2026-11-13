# Revue — connexion de l'extension par le site (10/11/2026)

| n° | Fichier | Classe | Correction | Statut |
|---|---|---|---|---|
| 1 | `frontend/src/pages/ExtensionConnectePage.tsx` | état affiché sans preuve | texte « Autorisation accordée » + conduite à tenir si l'onglet reste ouvert (le site ne peut pas savoir si l'échange a réussi) | corrigé |
| 2 | `backend/app/api/extension.py` (`echanger_code`) | date naïve/consciente | `_aware(echeance)` comme dans `auth.py` | corrigé |
| 3 | `extension/src/background.ts` (`terminerConnexionSite`) | garde posée après un `await` | `echangesEnCours.add` avant tout `await` | corrigé |
| 4 | idem | demande consommée par un retour étranger | la demande n'est retirée que si onglet **et** `state` correspondent | corrigé |
| 5 | `backend/app/api/extension.py`, `core/security.py` | état du compte non revérifié | échange refusé si e-mail non vérifié ; `revoke_user_tokens` sans client annule aussi les codes en attente (réinitialisation du mot de passe) ; 3 tests ajoutés | corrigé |
| 6 | `backend/app/api/auth.py` (`/logout`) | déconnexion du site sans effet sur l'extension | — | rejeté : voulu (étude §4) ; l'extension se déconnecte depuis sa fenêtre, la réinitialisation du mot de passe coupe tout |
| 7 | `extension/src/popup.ts` | redessin sur rotation du jeton | redessin seulement si le jeton apparaît ou disparaît | corrigé |
| 8 | `backend/app/api/extension.py` | import d'une fonction privée d'un autre routeur | — | rejeté : pas d'import circulaire (`auth` n'importe pas `extension`) ; un renommage casse à l'import, donc visible aux tests |
| 9 | `core/security.py`, `api/extension.py` | empreinte dupliquée | `hash_token()` unique, 4 occurrences remplacées | corrigé |
| 10 | `frontend/src/App.tsx` | modification parasite | espace rétabli (ligne identique à `HEAD`) | corrigé |

Preuves : `test_extension_auth` 36/36, `test_extension` 57/57 (base 5433) ; front tsc/lint/build OK ; extension typecheck, 62/62, archive refaite.
