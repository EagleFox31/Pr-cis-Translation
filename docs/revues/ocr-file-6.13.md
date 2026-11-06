# Registre de revue — 6.13 OCR avant ouverture

Revue auditeur du 05/11/2026 sur le diff non commité de `feat/ocr-file-pages-illisibles`.
Verdict : conforme avec réserves, aucun bloquant. À corriger par classe (skill convergence), deux passes au plus.

## Importants (avant push)

| # | Classe | Lieu | Écart | Correction | État |
|---|---|---|---|---|---|
| I1 | Débit sans contrepartie | `translation_runner.py:1614-1623` | `_debiter_une_page` avant `_reporter_page` : si `os.replace` échoue (Windows) ou plantage, page payée et restée illisible ; aucune clôture ne rembourse (commentaire l.1620 faux) | Reporter d'abord sous verrou d'écriture, puis débiter ; débit refusé → page remise illisible motif `solde` (étude §10) ; sinon rembourser dans `except` | corrigé : `_reporter_page` pose la page puis débite sous le verrou d'écriture, remet l'ancien JSON si refus ou erreur ; page déjà `ok` ni reposée ni débitée |
| I2 | Lecture non verrouillée | `translation_runner.py:1604` | `shutil.copy2` du JSON hors verrou de lecture `render_cache.verrou_traduction` | Copier sous verrou de lecture | corrigé : copie sous `.lire()` |
| I3 | Création de copie sans verrou | `api/documents.py:685-704` (appels l.737, 819) ; l.812 | Deux PATCH simultanés copient T→C, le second écrase C après report d'une page débitée. Filtre `pages_en_cours` calculé sur T au lieu de C | Verrou par document autour de la copie + relecture de `doc.translated_path` ; filtre sur le chemin final ; `copytree` en ignorant `*.tmp` (mineur m4) | corrigé : `_copie_du_document` sous verrou par chemin, JSON copié en dernier (tmp + `os.replace`), filtre sur `_copie_prevue(doc)` |
| I4 | Section critique trop large | `api/extension.py:97`, `images_document.py:478` | Le tour du guichet englobe aussi l'appel réseau de traduction | Limiter le tour à la reconnaissance (vérifier `ocr_v2.image.traduire_image`) | corrigé : `traduire_image(..., tour=)` n'encadre que `_lire` (extension, images du document) |

## Mineurs

| # | Lieu | Écart → correction | État |
|---|---|---|---|
| m1 | `extension.py:97` | `delai=120` en dur → `OCR_DELAI_EXTENSION_S` dans `config.py` | corrigé : `OCR_DELAI_EXTENSION_S` |
| m2 | `jobs.py` ~413-430 | Page OCR « ok » sans paragraphe traduit facturée à `done` mais pas à la pause → même critère `_page_traduite` | corrigé : `pages_lues_sans_traduction` exclue à `done` |
| m3 | `render_cache.py` | Verrou lecture/écriture sans préférence écrivain → bloquer les nouveaux lecteurs quand un écrivain attend | corrigé : `_ecrivains_en_attente` |
| m4 | `documents.py:700` | `copytree` `.ocr` peut tomber sur un `.tmp` → `ignore=` (traité avec I3) | corrigé avec I3 |
| m5 | `translation_runner.py:1502` | `_pages_en_cours` en mémoire seulement → documenter dans l'étude §10 | corrigé : étude §10 « Lectures en cours » |
| m6 | `translation_runner.py` | Détection debug par `split("_")` → booléen explicite | corrigé : `mode_structure(path)` (le nom de fichier reste la seule trace du mode) |
| m7 | `ScanPagesPanel.tsx:45,54` | GET en échec silencieux → état d'erreur + chargement initial | corrigé : erreur + « Réessayer », rien avant le premier chargement ; `getIllegiblePages` lève sauf 404 |
| m8 | `useDocumentLibrary.ts:315` | 409 : message générique, état non rechargé → remonter `detail`, recharger | corrigé : message du 409 remonté, état relu après tout refus |
| m9 | `useDocumentLibrary.ts:34` | `motif: string` → `string \| null` | corrigé |
| m10 | `ScanPagesPanel.tsx:82` + locales | `aria-pressed` sur « traduire » jamais persistant ; clé `state_traduire` morte → retirer | corrigé : `aria-pressed` hors « traduire », `state_traduire` retirée (fr/en), état affiché seulement pour original/vide |
| m11 | `ScanPagesPanel.tsx:105-108` | « Traduire » pour toutes : nombre de pages facturées non affiché → `do_traduire_all` avec `{count}` | corrigé : `do_traduire_all` au pluriel (fr/en) |
| m12 | `ScanPagesPanel.tsx:112` | `aria-live` par carte → une seule région sur le compteur | corrigé en passe 2 : région `aria-live` toujours présente, hors du bouton, seul son texte change |

## À vérifier (non couvert par l'audit)

- `doc.paid` : vérifié, `ext_service.debiter` ne le change pas (seul `payments.py` le pose). Une page débitée sur un document d'essai reste donc en aperçu : décision produit posée à l'utilisateur (PASSATION). Tranché le 05/11 : même règle qu'au lancement (`translate.py`), un débit en pages achetées pose `doc.paid` dans `extension._debiter` ; tests `test_essai_sur_pages_offertes_reste_en_apercu`, `test_essai_paye_en_credits_devient_telechargeable`.
- `git grep` de mentions d'IA dans le diff : aucune.
- Fait le 05/11 : `test_ocr_pages_choix`, `test_ocr_facturation_pages`, `test_ocr_file`, `test_ocr_pages`, `test_ocr_moteur_pages`, `test_images_document`, `test_documents_scannes`, `test_beta_program`, `test_extension` (faux `traduire_image` adapté au paramètre `tour`), crédits achetés, endpoint ; Docker : `test_ocr` (OCR réel), `test_ocr_pages`, `test_ocr_moteur_pages` ; frontend tsc, lint, build. Reste : relancer `test_ocr_pages_choix`, `test_ocr_facturation_pages`, `test_ocr_file`, suites OCR + Docker ; contre-revue ciblée sur I1–I4.

## Passe 2 — contre-revue ciblée (05/11)

Verdict : I2–I4, m1–m11 clos ; I1 et m12 clos en partie. Écarts nouveaux, aucun bloquant.

| # | Gravité | Lieu | Écart | État |
|---|---|---|---|---|
| N1 | important | `translation_runner._reporter_page` | Statut `ok` écrit après le débit : son échec laisse une page payée et redébitable | corrigé : JSON et statut `ok` posés avant `debiter()`, l'un et l'autre remis sur refus ou erreur |
| N2 | important | `ocr_v2/image.py` | Délai calculé avant `tour()` : l'attente au guichet le consomme | corrigé : `fin` recalculé dans le `with tour()` |
| N3 | important | `render_cache` + `_reporter_page` | Un rendu tient le verrou de lecture pendant tout le moteur (≈ 280 s pour 285 pages) ; un report en attente fige les aperçus du document, et chaque report relance un rendu complet | différé : problème de conception (rendre sur un instantané du JSON, ou invalider une fois le travail fini) ; écrit au bilan §7 et en PASSATION, à traiter avant déploiement |
| N4 | important | tests | Retour arrière, garde `ok`, copie réutilisée, préférence écrivain, `pages_lues_sans_traduction`, délai après `tour` sans test | corrigé : `tests/test_ocr_report_page.py` + `test_solde_epuise_pendant_le_travail` complété |
| N5 | mineur | étude §10 « solde » | Motif `solde` posé sur refus seulement, pas sur erreur | corrigé : texte aligné |
| N6 | mineur | étude §10, docstring | « plusieurs processus sérialisés » faux : verrous propres au processus | corrigé : « un seul processus ; à revoir avant d'en ajouter » |
| N7 | mineur | `_reporter_page` | Échec du retour arrière masque la cause | corrigé : cause journalisée avant le retour arrière |
| N8 | mineur | `mode_structure` | Docstring « empreinte » inexacte | corrigé : renvoi à `translation_path_for` |
| N9 | mineur | `documents._copie_du_document` | Copie réutilisée non comparée | corrigé : commentaire (seul cas : clôture rejouée, qui ramène sur la traduction partagée) |
| N10 | mineur | `ScanPagesPanel` | Après un refus, aperçu non recalculé si la page a été lue ailleurs | corrigé : `onChanged` si une page quitte la liste |

Non vérifié par la contre-revue : clôture `done` rejouée après un « traduire quand même » (le débit séparé d'une page entre-t-il dans `refund_unfinished` / `rebill_for_document` ?) — ajouté au bilan §7.
