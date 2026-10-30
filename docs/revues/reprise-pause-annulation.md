# Revue — reprise après arrêt (g2), passe 1 → corrections g2b

| N° | Lieu | Classe | Correction | Statut |
|----|------|--------|------------|--------|
| 1 | `services/jobs.py` `sync_status` | état de facturation écrasé par un job périmé | doc disparu ou `resumed` → aucun changement (ni statut, ni remboursement, ni refacturation) ; ligne verrouillée | corrigé (test « job tardif ») |
| 2 | `services/jobs.py` `sync_status` | échec qui perd une remise | échec d'un job avec `deja > 0` → `interrupted` + `refund_unfinished(faites − deja)` | corrigé (3 tests) |
| 3 | `api/translate.py` reprise, `services/beta.py` `office_billed` | unité bêta Office non comptée comme payée | DOCX/XLSX bêta non remboursé → `payees = total` | corrigé (pas de test bêta Office dédié) |
| 4 | `api/translate.py` réglages, `services/documents.py` `_selection_du_document` | suffixe de cache incomplet | `qsuffix` complet enregistré (OCR, qualité) et relu ; repli sur `precise` pour les anciens documents | corrigé (test réglages) |
| 5 | `api/translate.py` | statut consommé sans contrepartie | `resumed` seulement si `deja_payees > 0` | corrigé (test « sans remise ») |
| 6 | `api/translate.py` | reprise non comparée à l'origine | qualité et `qsuffix` comparés, sinon pas de reprise | corrigé |
| 7 | `api/translate.py` contrôle e-mail | refus avant de connaître le reste à payer | contrôle déplacé après le calcul de `needed` pour une reprise | corrigé (pas de test dédié) |
| 8 | `services/beta.py` `refund_unfinished` | lecture sans verrou | enrollments verrouillés puis lignes `with_for_update` + `populate_existing` | corrigé |
| 9 | anti-abus `FreeGrant` | remboursement non reporté sur l'historique anti-abus | — | différé : `FreeGrant` n'a pas de lien au document (changement de schéma), même défaut préexistant que `refund_for_document` ; noté dans PASSATION |
| 10 | `usage.rebill_for_document` | refacturation partielle | — | différé : ne concerne que plusieurs processus simultanés (déploiement à un seul processus, limite écrite dans la docstring de `refund_unfinished`) ; noté dans PASSATION |
| 11 | `services/stockage.py` `balayer_au_demarrage` | cache payé purgé | fichier partiel des documents `interrupted` ajouté aux références | corrigé (test « ménage ») |

## Contre-revue (passe 2)

| N° | Lieu | Classe | Correction | Statut |
|----|------|--------|------------|--------|
| 12 | `library/DocumentCard.tsx` | état sans affichage | `resumed` affiché (« Reprise — la suite est dans la traduction relancée »), aperçu et téléchargement désactivés ; clés fr/en | corrigé (tsc, lint, i18n OK) |
| 13 | `api/translate.py` contrôles préalables e-mail et bêta | contrôle contourné par un `resume_of` quelconque | contrôles sautés seulement si `resume_of` désigne un document du compte au statut `interrupted` (lecture légère avant l'OCR) | corrigé |
| 14 | `api/translate.py` `partiel` | condition sur la mauvaise variable | `deja_payees == 0` au lieu de `reprise is None` | corrigé |
| 15 | `usage.refund_unfinished` docstring | limite non écrite | ordre de verrous inverse `sync_status` / reprise : interblocage seulement en multi-processus | corrigé (documenté) |

## Revue g4 — pause / annulation (passe 1)

| N° | Lieu | Classe | Correction prévue | Statut |
|----|------|--------|-------------------|--------|
| 16 | `engines/pdf/stream.py:157-168` | arrêt pris après le travail fini | ne contrôler l'arrêt qu'avant une page de la sélection non encore en cache | corrigé (`arret()` seulement dans `if not has_translation` ; test moteur PDF dans `test_arret_job`) |
| 17 | `translation_runner.py:139` (DOCX), `:294` (XLSX) | arrêt pris après le travail fini (traduction payée au fournisseur perdue) | `verifier_arret` seulement si `not success` | corrigé (`verifier_arret` dans la branche d'échec DOCX/XLSX) ; pas de test moteur DOCX/XLSX : le traitement réel exige le fournisseur, chemin relu au diff |
| 18 | `scheduler.py:88` + `translation_runner.py:82/219/637/1106` | état sans issue | écrire l'original dans la route avant `scheduler.submit` | corrigé (`_sauver_original` dans la route avant `submit` ; testé) |
| 19 | `api/translate.py:764-779` + `scheduler.py:88` | délai d'arrêt d'un job en file | planificateur marque « démarré » ; la route arrête tout de suite un job en file (sans course) | corrigé (`jobs.demander_arret` → `en_file`/`en_cours` et `jobs.demarrer`, même verrou ; testé) |
| 20 | étude point 4 / `PASSATION.md` | écart à l'étude non décidé | décision E (étude) : livrer le partiel d'un document annulé (aperçu + téléchargement), reprise conservée | corrigé (`traduction_partielle_du_document` + `_traduction` dans download/preview, nom `_TRADUIT_PARTIEL` ; PDF testé par l'API, PPTX par `render_translation_bytes` (test_reprise_pptx §6) ; DOCX/XLSX : rien à livrer avant g6) |
| 21 | `DocumentCard.tsx:117`, `AdminDocumentsPage.tsx:104`, `Home.tsx:281`, `useDocumentLibrary.ts:29` | état sans affichage | statuts paused/cancelled au front + clés i18n fr/en | corrigé g5 (carte, reprise, libellés admin, clés fr/en ; build + check-i18n) |
| 22 | `api/translate.py:857` `/result`, `api/documents.py:443` | état de job non traité | traiter paused/cancelled comme états finaux | corrigé (`/result` → 409 ; aperçu : `STATUTS_ARRET` dans les états finaux ; testé) |
| 23 | `jobs.py:356`, `translate.py:719`, `:773` | valeur en dur dupliquée | constante `STATUTS_ARRET` près de `STATUTS_REPRENABLES` | corrigé (`STATUTS_ARRET` dans jobs.py, utilisé par jobs/translate/documents ; grep des littéraux = 0) |
| 24 | `api/translate.py:765-779` route d'arrêt | contrat de route | `verify_api_key`, `Literal["pause","cancel"]`, docstring « demande, pas un état » | corrigé |
| 25 | `jobs.py:8`, `translate.py:277/441-444/472/686`, `translation_runner.py:999-1000`, `usage.py:137`, `documents.py:55-56`, `stockage.py:184` | commentaire périmé | mentionner paused/cancelled | corrigé (9 commentaires + docstring SSE) |
| 26 | `docs/api/index.html` | doc API périmée | `npm run docs:api` | corrigé (`scripts/docs_api.py`) |
| 27 | tests | arrêt non joué par les vrais traitements PDF/DOCX/XLSX, SSE `stopped` à la reconnexion, bêta | ajouter ces cas à `test_arret_job.py` | corrigé sauf bêta et moteurs DOCX/XLSX (différés : nécessitent fournisseur/inscription bêta réels, écrit ici) ; test_arret_job 33/33, test_reprise_pptx 17/17 |

## Contre-revue g4 (passe 2, plafond)

Écarts 16-27 vérifiés clos. Le diff en créait cinq, tous corrigés ; plafond de deux passes atteint.

| n° | fichier:ligne | classe | correction | statut |
|---|---|---|---|---|
| 28 | `services/documents.py` `traduction_partielle_du_document` | droit non borné par le paiement | le fichier de traduction est partagé par empreinte entre comptes : livrer au plus `payées` pages (premières de la sélection, payées + `deja`) ; PPTX : repli sur la traduction finale si un autre compte l'a terminée (la reprise disparaît) | corrigé (`pages_traduites`, `_traduction` async ; rendu partiel jamais mis en cache ; test_arret_job « partiel borné au payé », test_reprise_pptx §7) |
| 29 | `services/render_cache.py` `store_render` | cache périmé par course | rendu fait pendant qu'un job complète la traduction : plus récent qu'elle, tenu valide alors qu'il manque des pages | corrigé (`mtime_source` relevé avant le rendu, pas d'écriture s'il a changé ; download, preview, construction de fond ; test_polices « traduction modifiée pendant le rendu ») |
| 30 | `api/translate.py` | original purgé par une course | une suppression de document de même empreinte pouvait purger l'original pendant `_save_document_for_user` (qui valide) | corrigé (second `_sauver_original` après l'enregistrement ; le premier reste : s'il échoue, rien n'est enregistré) |
| 31 | `api/translate.py` | valeur en dur dupliquée | `{"pause": "paused", ...}` → dérivé de `STATUTS_ARRET` | corrigé |
| 32 | tests | cas non couverts | plan gratuit (402 / aperçu rastérisé), fichier partagé, document repris sans partiel | corrigé (test_arret_job 38/38, test_reprise_pptx 20/20) |
