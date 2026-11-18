# Revue de l'étape 5.3b — téléchargement des traductions libres

Registre des écarts relevés par la revue de fin d'étape (passe 1), et de leur traitement.

| N° | Endroit | Classe d'erreur | Correction | Statut |
|---|---|---|---|---|
| 1 | `backend/app/services/usage.py` (`regler_pages_libres`) | Solde lu en mémoire sous verrou : il peut être périmé, donc débité deux fois | Verrou du compte avec `populate_existing`, solde relu en base | corrigé (test `test_settlement_rereads_the_balance_under_the_lock`) |
| 2 | `frontend/src/components/story/StorySection.tsx` (ligne sous l'aperçu) | Bouton d'achat des pages libres relancé comme une nouvelle traduction | Nouvelle action `onBuyLibres` → `acheterLibres` (paiement puis règlement des pages, sans retraduire) | corrigé |
| 3 | `backend/app/api/documents.py` (`regler_libres`) | Règlement sans contrôle d'état ni d'accès | 409 si la traduction n'est pas terminée, contrôle d'accès ; un document arrêté livre ses pages payées sans règlement | corrigé (tests `test_unfinished_translation_is_not_settled`, `test_stopped_document_delivers_its_paid_pages_without_settling`) |
| 4 | `backend/app/api/payments.py` (`_apply_credit`) | Paiement ciblé qui laisse des pages libres | `pages_libres = 0` avec `paid = true` | corrigé (test `test_targeted_payment_clears_the_libre_pages`) |
| 5 | `backend/app/api/documents.py` (`_sans_pages_retirees`) | Découpe en deux passes qui décale les numéros de page | Une seule découpe, numéros de l'original | corrigé (test `test_continue_cuts_libre_and_removed_pages_in_one_pass`) |
| 6 | `frontend/src/pages/Home.tsx` (`handleDownload`) | Repli sur le fichier local après un échec, qui contient les pages non payées | Plus de repli quand le téléchargement par le serveur a été tenté | corrigé |
| 7 | `backend/migrations/versions/0026_pages_offertes_en_clair.py` | Migration trop large (débloquait des documents sans consommation) | Limitée aux documents qui ont une consommation `free_offer` ou `legacy` non remboursée | corrigé |
| 8 | `backend/app/api/documents.py` (`regler_libres`) | Ordre des verrous inversé par rapport à `translate.py` | Compte, puis document | corrigé |
| 9 | `backend/app/api/translate.py` | Pages libres calculées avant le plafond du forfait | Pages libres bornées après `cap_pages_for_plan` | corrigé |
| 10 | `frontend/src/components/library/TelechargementLibres.tsx` | Erreur réseau ou refus sans message | `try/catch` et message d'erreur pour tout refus autre que « stockage requis » | corrigé |
| 11 | `TelechargementLibres.tsx` | Nom du fichier partiel deviné côté client | Nom tiré de la réponse du serveur (`_PARTIEL`) | corrigé |
| 12 | `frontend/src/pages/Home.tsx` | Ligne « N pages en aperçu » non mise à jour après un règlement | Le nombre renvoyé par le règlement remplace l'ancien | corrigé |
| 13 | `backend/app/services/documents.py` | Repli sans fichier original | Aucun effet aujourd'hui : sans original, le rendu répond déjà 404 | rejeté |

Vérifications : 18 tests `test_traduction_libre`, 34 tests des suites voisines, compilation, lint, build, parcours navigateur (bureau, mobile, 320 px).

## Contre-revue (passe 2)

Les n° 1 à 12 sont clos et le rejet du n° 13 est confirmé. Écarts nouveaux, à traiter à l'étape 5.3c :

| N° | Endroit | Classe d'erreur | Correction prévue | Statut |
|---|---|---|---|---|
| 14 | `frontend/src/pages/Home.tsx` (`rafraichirSolde`) | État d'interface non relu après un achat : l'aperçu reste filigrané et le bouton renvoie aux tarifs | Relire le droit de lecture en clair et vider le cache d'aperçu du document après un règlement | corrigé (5.3c) |
| 15 | `backend/app/services/jobs.py:507-515` | Remboursement des pages non facturables (pages blanches de scan) calculé sans les pages libres : facturation en trop au règlement | Retrancher les pages libres de la base du remboursement ; ôter les pages non facturables des pages libres | corrigé (5.3c) : page non facturable de la zone libre retirée de cette zone et mémorisée (`hors_libres`), sans décaler les autres |
| 16 | `frontend/src/components/story/StorySection.tsx:591` | Barre « Acheter » affichée pendant la traduction : le règlement répond 409 après paiement | N'afficher la barre qu'une fois la traduction terminée | corrigé (5.3c) |
| 17 | `documents.py` (`regler_libres`) contre `usage.refund_unfinished` et `payments._apply_credit` | Ordre des verrous différent selon les chemins : interblocage possible | Ordre unique compte puis document, et contrôle 409 avant les verrous | corrigé (5.3c) |
| 18 | `backend/app/api/translate.py:585` | Pages libres enregistrées pour l'anti-abus avant la borne du forfait | Enregistrer après la borne | corrigé (5.3c) |
| 19 | `docs/etude-traduction-libre.md:61` | Renvoi de migration faux (0026 au lieu de 0027) | Renvoi corrigé | corrigé |
