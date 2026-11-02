# PASSATION — 02/11/2026

## 1. Objectif en cours
Sur `integration/version-complete` : 6.8.5 faite (essai DOCX + PDF réussi) ; ensuite **6.11.4**, 6.10, 6.9, 6.12, 6.5, 6.4.

## 2. Fait
- Branche `integration/version-complete` (62708f0, locale, **non poussée**) : `feat/pages-legales` + `feat/paddle-live` + `feat/ocr-v2` réunies ; branches d'origine intactes. Laissées de côté et annoncées : `origin/feat/orchestrator-signed-event-inbox` (#52), `feat/journal-purge-auto`. Migration renommée `0019_extension_avance` (après 0018, idempotente).
- OCR v2 complet (`backend/app/services/ocr_v2/`, `docs/etude-ocr-v2.md` §7-8, §11) ; extension `extension/` + routes `app/api/extension.py`, `app/services/extension.py`.
- Document test : `C:/Users/IBRAH/Downloads/test-traduction-figure-annotee.docx` (pompe annotée en anglais) ; `analyser` en Docker : 1 image à texte sur 1. Sans 6.8.3, la figure reste en anglais dans l'app.
- Étude `docs/etude-distribution-extension.md` (README à jour) : boutiques + page `/extension`, `.exe` écarté car Chrome refuse les fichiers hors boutique sur Windows/Mac sauf postes gérés.
- 6.8.3 : `hooks/useAnalyseImages.ts`, case dans `TranslationSection.tsx`, `images=1` et bilan dans `useStreamingTranslation.ts`, bouton « Traduire sans les images » dans `PdfViewer.tsx`. Essai Playwright : analyse réelle du DOCX test, réponses de `/api/translate` simulées ; aucune traduction réelle lancée.
- 6.8.4 (334e6aa) : `api/documents.py` `GET`/`PATCH /{id}/images` (copie `…_d<id>` si traduction partagée, cache d'aperçu invalidé par mtime), `images_document.etat_images`/`marquer_originale` (liste `retirees`), `components/preview/DocumentImagesPanel.tsx` branché via `StorySection` `imagesPanel` dans `Home.tsx` ; tests `test_images_retirees.py` (4) ; essai Playwright aller-retour sur le DOCX test (`scratchpad/pw684.py`).
- 6.4a/6.4c (ad9a7e0, 7dd478e) mise en page des images (`ocr_v2/image.py`, `LISIBLE_PX = 24`) ; 6.4b.1 (0dc8136) avance au volume ; 6.7 (9735f18) lignes fiables des scans.
- 6.8.1 (6108fd6) : `services/images_document.py` (`lister`/`detecter`/`analyser`/`vignette`), route `POST /api/translate/analyse`.
- Compte rendu PPTX réel (01/11) : textes oubliés corrigés — 8f64c57 aperçu Excel déjà PNG, b421d2c masques + cellules `t="str"`, fa7ad72 classeur incorporé via moteur XLSX, caches de graphiques alignés (`xlsx/engine.py` `_aligner_graphiques`), `<c:f>` réécrits au renommage, `translation_ai.harmoniser` (doublons = une seule traduction). Intitulés de formation désormais traduits, code gardé (règle 6 du prompt, eac85e5) ; limite : formulation parfois variable entre diapositives (« Fictitious » / « Fictional »).
- 6.8.2 (e85f40a) : `images_document.traduire_images`/`poser_office`/table `<trad>.images.json` + `.images/` ; PDF `engines/pdf/engine.py` `_draw_image(..., images)` + `stream._images_par_xref` ; `translation_runner._preparer_images` (débit unique lié au document, événement `images`) et `_poser_images_fichier` ; `api/translate.py` champ `images=1` → `qsuffix _img`, 402 avec `images_needed`, `reponse["images"]` ; `stockage` garde la table tant que la traduction existe ; étude §9.1.

## 3. Décisions
- Scan : seule la détection diffère, ensuite même chemin que le PDF natif. Qualité avant vitesse ; délai OCR 90 s gardé.
- Extension : 1 crédit/image remplacée, texte au volume (1 500 car. = 1 page, avance cumulée), pas de bascule silencieuse vers le payant ; mémoire locale IndexedDB (rien n'est conservé côté serveur).
- 6.8 (§8 de l'étude) : 1 page par image remplacée, case non cochée par défaut, tout ou rien + annulation par image sans remboursement en v1 (à confirmer), même règle en gratuit. Débit des images après traduction, lié au document (remboursé si le travail échoue) ; images exclues des scans OCR, de la bêta et du debug en v1 (à confirmer). Option désactivée avec une plage de pages : le serveur compte les images du document entier.
- Distribution (validé le 02/11) : boutiques Chrome + Edge, `.exe` abandonné ; nom visible Précis, comptes au nom de la structure qui exploite le service (5 $ Chrome, Edge gratuit, à créer par le propriétaire) ; lancement par lien seulement (« Unlisted » / « Hidden »), puis public.

## 4. Plan
1–5. [x] branche, études OCR v2 + extension, OCR v2 complet.
6. [~] Extension et documents :
   - 6.1–6.3b [x] étude, routes, prototype, traduction par bloc ; 6.4a [x], 6.4c [x] images ; 6.6 [x] mesure livret ; 6.7 [x] scans fiables ;
   - 6.4 [~] essai réel (page locale faite dans Edge) : puis TEAM-GP (G49001) sans cliquer « Début », « Options administrateur », `lbnRegist` ni aucun postback ;
   - 6.4b [x] ne plus repayer une page (`docs/etude-memoire-extension.md` §8) : 6.4b.1 [x] ; 6.4b.2 [x] `src/lib/memoire.ts` (clé SHA-256 `v1`+compte+langue+contenu, 30 j / 50 000 textes / 200 Mo) + IndexedDB dans `background.ts` ; 6.4b.3 [x] popup « Mémoire : n — Effacer » ; 6.4b.4 [x] vérif (2ᵉ visite = 0 débit) ;
   - 6.8 [~] (prioritaire) images des documents normaux, étude `docs/etude-images-documents.md` :
     - 6.8.1 [x] analyse ; 6.8.2 [x] pose + débit (tests : images_document 39, couverture_credits 29, extension 24, moteur PDF verts). Limites : aperçus partiels PPTX/XLSX non vérifiés après LibreOffice ; GIF/WEBP posé en PNG ; cache `images/` jamais purgé ; xlsx absent de `render_translation_bytes` (préexistant) ; débit échoué → images `sans_credit` ; aucun essai réel (→ 6.8.5) ;
     - 6.8.3 [x] frontend : case, deux totaux, 402 `images_needed`, bilan (tsc/lint/build, Playwright) ;
     - 6.8.4 [x] annulation par image (bandeau sous l'aperçu, copie propre au document si la traduction est partagée ; tests 4 + essai navigateur) ;
     - 6.8.5 [x] essai de bout en bout DOCX + PDF à schémas (02/11) : rendu, débit 1 page/image, étiquette serrée corrigée (`placer`, second passage) — étude §9.3 ;
   - 6.11 [~] (avancé 01/11) objets incorporés, toutes les combinaisons. Étude faite (`docs/etude-objets-incorpores.md`, README:95) : Office dans Docker impossible (pas de Linux, automatisation serveur non prise en charge, KB 257757) → LibreOffice headless + méthode CFAO Academy (`services/apercu/classeurs.py:402-452` zone visible, `:685-736` rognage, `:768-855` cache, `service.py:613-631` relance profil) dans un module commun `engines/incorpores.py`. Décisions §8 (01/11, déléguées) : D1 texte des objets facturé, D2 aperçu LibreOffice, D3 1ʳᵉ page redessinée sauf écart de proportions > 10 %, D4 conversion 97-2003, D5 pas de Draw (Visio/PDF signalés), D6 signalement au client ; plan §7 :
     - 6.11.1 [x] repérage (`engines/incorpores.py` `reperer`/`rapport`, 21 tests ; repères think-cell `TCLayout` ignorés) ; 6.11.2 [x] extraction/réécriture + garde-fous (`extraire`/`reecrire`/`remplacer_parties`, écrivain CFB, 20 tests ; dépendance `olefile==0.47`) ; 6.11.3a [x] classeur incorporé PPTX via moteur XLSX (fa7ad72) ; 6.11.3b [x] récursion générique (profondeur 2) + 97-2003/OLE2 Package (`relever`/`reinjecter`, `tests/test_incorpores_recursion.py` ; limites dans l'étude, bilan 6.11.3 ; openpyxl absent du venv) ; 6.11.4 [x] redessin des aperçus (`engines/apercus.py` branché dans `reinjecter`, ancien `regenerate_ole_previews` retiré ; 21 tests + essai Docker ; bilan 6.11.4 dans l'étude) ; 6.11.5 [x] graphiques natifs (a–e faits, `tests/test_incorpores_graphiques.py` 6 tests ; bilan 6.11.5 dans l'étude) ; 6.11.6 [ ] facturation + exclusion OCR ; 6.11.7 [ ] mesure et recette Docker (`--cpus 2 --memory 3g`) ;
   - 6.9 [ ] interface de l'extension : **branding seulement**, normes des pages du site, jetons du `frontend`, impeccable en raffinement ;
   - 6.12 [ ] distribution de l'extension (décisions §10 prises) : manifest production + icônes, page publique `/extension`, liens et bandeau, détection (`externally_connectable`, absent), bienvenue (`onInstalled`, absent), confidentialité, fiches Chrome + Edge ; connexion par mot de passe seulement (`login-password`), comptes Google à traiter ;
   - 6.10 [ ] bilan OCR pour le déploiement (ce qui marche, limites, prérequis serveur, risques, check-list) ;
   - 6.5 [ ] pastille « Traduire ce PDF » (circuit `/api/translate`).

**Hors plan** :
- Échec CI `sync-github-app-user` : côté propriétaire. `frontend/tsconfig.tsbuildinfo` non suivi : à ignorer.
- Tests de la branche (02/11) : 85 suites, 83 vertes en local ; `test_ocr.py` et `test_ocr_endpoint.py` échouent seulement sans Tesseract et passent dans Docker. Aucun échec dû à la fusion. tsc, lint et build passent. Dans l'image, monter aussi `olefile` et `disposable_email_domains` du venv (`PYTHONPATH`).
- Ne pas tester `POST /api/auth/login` avec une adresse inconnue : cela crée un compte et envoie un vrai e-mail.
- `/api/pricing` appelé 10 fois par chargement de `/home` (`usePricing` sans partage) : à regrouper plus tard, sans urgence.
- Graphiques natifs (revue 6.11.5, sans urgence) : renommage d'onglets apparié par position ; chaque retouche `graphique` relit les deux classeurs (à mettre en cache si un fichier compte beaucoup de graphiques) ; graphique posé sur un modèle de diapositive non vu en traduction progressive ; `_aligner_graphiques` du moteur XLSX déplie toute la plage (énorme plage = lent).
- En attente : essai de connexion Google par l'utilisateur, puis objets incorporés dans l'app.

## 5. Pièges / contexte
- `backend/.env` est en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi. Push/PR seulement après vérification locale par l'utilisateur.
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Lancer : `npm run stop`, puis `PYTHONUTF8=1 <venv>/python.exe scripts/dev.py` (tuer un vieil uvicorn :8000 par PID au besoin).
- Migrations : `backend/scripts/verifier_migrations.py` (une seule fin de suite : CI + démarrage du conteneur ; `--base` : `scripts/dev.py` met la base à jour ou explique l'écart). Une base migrée depuis une autre branche ne se répare pas seule.
- Tests backend : unittest, Postgres 5433, jamais la base dev 5432. Docker Desktop puis `docker run -d --rm --name precis-test-pg -p 5433:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=precis postgres:16-alpine` et `python -m alembic upgrade head` (dans `backend/`, avec `DATABASE_URL`). Ex. : `cd backend && PYTHONUTF8=1 <venv>/python.exe tests/test_images_document.py`.
- OCR de l'app locale : Tesseract 5.4 installé dans `C:\Program Files\Tesseract-OCR`, langues dans `C:/Users/IBRAH/AppData/Local/tessdata-precis` (eng, fra, osd). Lancer `dev.py` avec ce dossier dans `PATH` et `TESSDATA_PREFIX` défini, sinon les images sont signalées « non vérifiées ». `npm run stop` et le lancement l'un après l'autre, jamais en parallèle.
- Tests OCR : `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/be" -w /be/tests precis-ocr-test python /be/tests/test_ocr.py` (depuis `backend/`, chemins `/be/...`).
- Image `precis-ocr-test` sans `olefile` : ajouter `-v "<venv>/Lib/site-packages/olefile:/ole/olefile:ro" -e PYTHONPATH=/ole`.
- Images 6.8 : clés `xref:<n>` (PDF) / nom de partie média (Office) ; budget lu via `ext_service.couverture` dans `jobs._dans_une_boucle_jetable` ; sémaphore OCR partagé `services/ocr.py:27`.
- Le rechargement auto d'uvicorn rate les nouvelles routes et le code OCR : arrêter puis relancer `dev.py`. Réessai d'images : vider `translations/<doc>/<langue>/*_img*` ET `.../images/`. Script d'essai bout en bout : étude images §9.3. Base de test 5433 venue d'une autre branche : `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` puis `alembic upgrade head`.
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`. Extension : `cd extension && npm run -s typecheck && npm test && npm run -s build`.
- Remote `origin` = EagleFox31. Fichiers en CRLF : éditer avec Edit. `PYTHONUTF8=1` obligatoire pour les tests.
