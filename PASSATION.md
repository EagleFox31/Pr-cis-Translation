# PASSATION — 01/11/2026

## 1. Objectif en cours
6.8 (images à texte des documents normaux, devis avec/sans images) : 6.8.1 et 6.8.2 faits (commits locaux), **6.11 avancé avant 6.8.3** (demande 01/11 : gérer toutes les combinaisons d'objets incorporés ; étude faite `docs/etude-objets-incorpores.md`, décisions D1-D6 prises 01/11, §8 ; 6.11.1 et 6.11.2 faits ; **prochaine étape 6.11.3**) ; ensuite 6.8.3 → 6.9 → 6.10, puis 6.4b.2.

## 2. Fait
- Branche `feat/ocr-v2`, tout en commits locaux **non poussés** (dernier : e85f40a). OCR v2 complet (`backend/app/services/ocr_v2/`, `docs/etude-ocr-v2.md` §7-8, §11) ; extension `extension/` + routes `app/api/extension.py`, `app/services/extension.py`.
- 6.4a/6.4c (ad9a7e0, 7dd478e) mise en page des images (`ocr_v2/image.py`, `LISIBLE_PX = 24`) ; 6.4b.1 (0dc8136) avance au volume ; 6.7 (9735f18) lignes fiables des scans.
- 6.8.1 (6108fd6) : `services/images_document.py` (`lister`/`detecter`/`analyser`/`vignette`), route `POST /api/translate/analyse`.
- 6.8.2 (e85f40a) : `images_document.traduire_images`/`poser_office`/table `<trad>.images.json` + `.images/` ; PDF `engines/pdf/engine.py` `_draw_image(..., images)` + `stream._images_par_xref` ; `translation_runner._preparer_images` (débit unique lié au document, événement `images`) et `_poser_images_fichier` ; `api/translate.py` champ `images=1` → `qsuffix _img`, 402 avec `images_needed`, `reponse["images"]` ; `stockage` garde la table tant que la traduction existe ; étude §9.1.

## 3. Décisions
- Scan : seule la détection diffère, ensuite même chemin que le PDF natif. Qualité avant vitesse ; délai OCR 90 s gardé.
- Extension : 1 crédit/image remplacée, texte au volume (1 500 car. = 1 page, avance cumulée), pas de bascule silencieuse vers le payant ; mémoire locale IndexedDB (rien n'est conservé côté serveur).
- 6.8 (§8 de l'étude) : 1 page par image remplacée, case non cochée par défaut, tout ou rien + annulation par image sans remboursement en v1 (à confirmer), même règle en gratuit. Débit des images après traduction, lié au document (remboursé si le travail échoue) ; images exclues des scans OCR, de la bêta et du debug en v1 (à confirmer).

## 4. Plan
1–5. [x] branche, études OCR v2 + extension, OCR v2 complet.
6. [~] Extension et documents :
   - 6.1–6.3b [x] étude, routes, prototype, traduction par bloc ; 6.4a [x], 6.4c [x] images ; 6.6 [x] mesure livret ; 6.7 [x] scans fiables ;
   - 6.4 [~] essai réel (page locale faite dans Edge) : puis TEAM-GP (G49001) sans cliquer « Début », « Options administrateur », `lbnRegist` ni aucun postback ;
   - 6.4b [~] ne plus repayer une page (`docs/etude-memoire-extension.md` §8) : 6.4b.1 [x] ; 6.4b.2 [ ] `src/lib/memoire.ts` (clé SHA-256 `v1`+compte+langue+contenu, 30 j / 50 000 textes / 200 Mo) + IndexedDB dans `background.ts` ; 6.4b.3 [ ] popup « Mémoire : n — Effacer » ; 6.4b.4 [ ] vérif (2ᵉ visite = 0 débit) ;
   - 6.8 [~] (prioritaire) images des documents normaux, étude `docs/etude-images-documents.md` :
     - 6.8.1 [x] analyse ; 6.8.2 [x] pose + débit (tests : images_document 39, couverture_credits 29, extension 24, moteur PDF verts). Limites : aperçus partiels PPTX/XLSX non vérifiés après LibreOffice ; GIF/WEBP posé en PNG ; cache `images/` jamais purgé ; xlsx absent de `render_translation_bytes` (préexistant) ; débit échoué → images `sans_credit` ; aucun essai réel (→ 6.8.5) ;
     - 6.8.3 [ ] frontend : case « Traduire les images » (envoyer `images=1`), deux totaux (avec/sans images, depuis `/api/translate/analyse`), 402 `images_needed`, rapport (événement `images` : proposees, traduites, inchangees, sans_credit, echecs) ; tsc/lint/build, Playwright ;
     - 6.8.4 [ ] annulation par image : route de reconstruction depuis la table, bouton « Remettre l'original » sur l'aperçu ; tests ;
     - 6.8.5 [ ] essai de bout en bout DOCX + PDF à schémas ;
   - 6.11 [~] ← (avancé 01/11) objets incorporés, toutes les combinaisons. Étude faite (`docs/etude-objets-incorpores.md`, README:95) : Office dans Docker impossible (pas de Linux, automatisation serveur non prise en charge, KB 257757) → LibreOffice headless + méthode CFAO Academy (`services/apercu/classeurs.py:402-452` zone visible, `:685-736` rognage, `:768-855` cache, `service.py:613-631` relance profil) dans un module commun `engines/incorpores.py`. Décisions §8 (01/11, déléguées) : D1 texte des objets facturé, D2 aperçu LibreOffice, D3 1ʳᵉ page redessinée sauf écart de proportions > 10 %, D4 conversion 97-2003, D5 pas de Draw (Visio/PDF signalés), D6 signalement au client ; plan §7 :
     - 6.11.1 [x] repérage (`engines/incorpores.py` `reperer`/`rapport`, 21 tests ; repères think-cell `TCLayout` ignorés) ; 6.11.2 [x] extraction/réécriture + garde-fous (`extraire`/`reecrire`/`remplacer_parties`, écrivain CFB, 20 tests ; dépendance `olefile==0.47`) ; 6.11.3 [ ] ← traduction récursive (profondeur 2) ; 6.11.4 [ ] redessin des aperçus ; 6.11.5 [ ] graphiques natifs ; 6.11.6 [ ] facturation + exclusion OCR ; 6.11.7 [ ] mesure et recette Docker (`--cpus 2 --memory 3g`) ;
   - 6.9 [ ] interface de l'extension : **branding seulement**, normes des pages du site, jetons du `frontend`, impeccable en raffinement ;
   - 6.10 [ ] bilan OCR pour le déploiement (ce qui marche, limites, prérequis serveur, risques, check-list) ;
   - 6.5 [ ] pastille « Traduire ce PDF » (circuit `/api/translate`).

**Hors plan** :
- Échec CI `sync-github-app-user` : côté propriétaire. `frontend/tsconfig.tsbuildinfo` non suivi : à ignorer.
- `feat/page-beta-candidature` : push et PR sur accord, à rebaser après fusion de #53.

## 5. Pièges / contexte
- `backend/.env` est en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi. Push/PR seulement après vérification locale par l'utilisateur.
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Lancer : `npm run stop`, puis `PYTHONUTF8=1 <venv>/python.exe scripts/dev.py` (tuer un vieil uvicorn :8000 par PID au besoin).
- Tests backend : unittest, Postgres 5433, jamais la base dev 5432. Docker Desktop puis `docker run -d --rm --name precis-test-pg -p 5433:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=precis postgres:16-alpine` et `python -m alembic upgrade head` (dans `backend/`, avec `DATABASE_URL`). Ex. : `cd backend && PYTHONUTF8=1 <venv>/python.exe tests/test_images_document.py`.
- Tesseract absent en local : `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/be" -w /be/tests precis-ocr-test python /be/tests/test_ocr.py` (depuis `backend/`, chemins `/be/...`).
- Images 6.8 : clés `xref:<n>` (PDF) / nom de partie média (Office) ; budget lu via `ext_service.couverture` dans `jobs._dans_une_boucle_jetable` ; sémaphore OCR partagé `services/ocr.py:27`.
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`. Extension : `cd extension && npm run -s typecheck && npm test && npm run -s build`.
- Remote `origin` = EagleFox31. Fichiers en CRLF : éditer avec Edit. `PYTHONUTF8=1` obligatoire pour les tests.
