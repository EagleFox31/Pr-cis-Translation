# Registre de revue : refonte admin (étape 4f)

*25/10/2026, passe 1 (`/code-review`) sur la branche `feat/mise-a-jour-carte-invitations-visionneuse`*

| N° | Fichier:ligne | Classe | Correction | Statut |
|---|---|---|---|---|
| 1 | `app/models/anti_abus.py:42` | Cascade qui efface une preuve d'abus | — | Différé : l'application n'a pas de suppression de compte. À revoir le jour où elle en aura une (noté dans PASSATION, Hors plan). |
| 2 | `migrations/versions/0015_beta_mailbox_unique.py` | Migration qui ne recalcule pas les données existantes | — | Rejeté : la bêta n'est pas en production (branche seulement), il n'y a aucune ligne à recalculer. |
| 3 | `app/services/beta_abuse.py:237` | Une transaction pour plusieurs tâches de fond indépendantes | Une transaction et un `try` par tâche : l'échec de l'anonymisation ne bloque plus la purge. | Corrigé |
| 4 | `app/services/anti_abus.py:187` | Règle sans effet (`new_account` neutralisée par `touch`) | — | Différé : décision produit posée à l'utilisateur (durcir = un nouveau compte bloqué 24 h). |
| 5 | `app/api/beta.py:241` | Conflit d'index unique remonté en erreur 500 | `IntegrityError` (au flush d'`activate` ou au commit) donne 409 `mailbox_used`. Test `test_concurrent_activation_of_one_mailbox_is_a_clean_409`, qui échoue sans le correctif. | Corrigé |
| 6 | `app/services/beta_abuse.py` (casefold → lower) | Clés existantes calculées avec l'ancienne règle | — | Rejeté : même raison que n° 2. |
| 7 | `app/api/translate.py:263` | Case bêta ignorée hors format bêta | — | Rejeté : c'est voulu (commentaire « Hors format bêta, la case n'a pas d'objet »), et la case n'est affichée que pour les formats bêta (`TranslationSection.tsx:83`). |
| 8 | `app/api/logs.py:94`, `admin_documents.py:89`, `support.py:135`, `admin_users.py:54` ; `UserPanel.tsx:101` | Recherche `ILIKE` sans échappement des jokers `%` et `_` | Les 4 recherches admin passent par `icontains(q, autoescape=True)`. Le journal reçoit un filtre exact `user_email`, que la fiche utilisateur emploie. Test dans `test_error_logs.py` § 3c. | Corrigé (4 occurrences + la fiche) |
| 9 | `UserPanel.tsx:72` | État affiché d'une requête précédente | `useBlock` repasse en « chargement » quand l'e-mail change. | Corrigé |
| 10 | `pages/LoginPage.tsx:187` | Bouton réactivé sans jeton anti-robot | — | Rejeté : c'est voulu (`Turnstile.tsx:40`) ; le serveur répond par un message clair au lieu d'un bouton grisé sans fin. |

À côté de la revue : `tests/test_google_profile.py` n'était plus à jour (argument `response` de `google_auth`). Il est corrigé.

Preuves :
- Suites bêta, journal et documents : OK.
- Suite complète : seuls `test_ocr*` échouent, et ils échouaient déjà avant (pas d'OCR en local).
- `tsc`, lint, i18n et build : OK.

Contre-revue (passe 2) : les 5 corrections sont closes, et le diff ne crée pas de nouvel écart. Plus aucune recherche `ilike(f"%…")` dans `backend/app`.
