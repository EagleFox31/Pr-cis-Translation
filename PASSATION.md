# PASSATION — 01/11/2026

## 1. Objectif en cours
Extension navigateur qui traduit une page entière (texte, images après accord, vidéo en pause) ; OCR v2 terminé.

## 2. Fait
- Branche `feat/ocr-v2`, commits locaux non poussés jusqu'à c5678dc. OCR v2 complet (étape 5, détail dans le plan et `docs/etude-ocr-v2.md` §7-8, §11) : `backend/app/services/ocr_v2/` (mask, erase, ppocr, detect, render, image).
- Extension : étude `docs/etude-extension-navigateur.md` §3.5-3.9, §8 (règle 1 500 car.), décisions 1-8 ; routes `backend/app/api/extension.py` + `app/services/extension.py` (532aacb) ; prototype `extension/` (c5678dc) : `src/background.ts` (jetons, refresh, appels API), `src/popup.ts`, `src/content.ts` + `src/contenu/*` (texte, moteur, images, vidéo, bandeau, calques), `src/lib/*` testé.
- TEAM-GP (31/10-01/11, lecture seule) : contenu des leçons dans `/rpv/contents/2/_scorm/<sid>/js/data.js` ; le japonais reste dans 107 images (nettes : G41056, G41062, G41065, G41071, G40001). Scripts `scratchpad\gp\` de la session 0c3ed8c0….

## 3. Décisions
- Scan : seule la détection diffère, ensuite même chemin que le PDF natif (`translate_pdf_progressive`) ; test de référence = scan traduit comparé au natif.
- Qualité avant vitesse ; délai OCR de 90 s gardé (OCR dans la requête d'envoi, `api/translate.py:312`).
- Extension : 1 crédit/image remplacée, 0 sinon ; tout le texte par le moteur Précis, par bloc avec balises `[[n]]` et contexte, au volume (décision 9, 01/11 : le navigateur traduisait mot à mot) ; pas de bascule silencieuse vers le payant ; Edge + Chrome ; essai manuel avant stores ; comptes bêta via le forfait normal.

## 4. Plan
1. [x] Créer `feat/ocr-v2` depuis `main`.
2. [x] Étude `docs/etude-ocr-v2.md`, révisée avec l'analyse et le banc fournis (`banc_inpainting.zip` dans Téléchargements) : masque couleur, sélecteur « masque fantôme », détection = goulot (PP-OCRv6), LaMa hors v1.
3. [x] Étude `docs/etude-extension-navigateur.md` (MV3, cadres, SVG, accord images, option hybride navigateur/Précis, 2 routes backend, jetons, stores).
4. [x] Décisions prises (31/10, options recommandées, notées en fin d'études) : poids Docker accepté sans LaMa ; japonais d'abord pour l'extension ; 1 crédit/image remplacée, texte navigateur gratuit ; Edge + Chrome ; essai manuel avant stores. Sauvegarde de la page du cours toujours attendue.
5. [x] OCR v2 (phasage étude §11) :
   - 5.0 [x] prototype rendu stylé des scans (étude §7.1) ; [x] trait coloré traversant effacé ; [x] vrai traducteur : gras interne conservé ; [x] largeur mesurée (Tc + approches + espace final + famille la plus proche) : 36/36 lignes identiques au natif si Inter est candidate, 30/36 avec les polices du dépôt. Prototype : scratchpad de la session 217549bb… `orig\couche_texte.py` (variable `FONTS` = dossier des candidates, `polices\` y contient Inter) ; scripts `lignes_diff.py`, `largeurs.py`, `gras\vrai_traducteur.py` (à lancer depuis `backend/`) ;
   - 5.1 [x] fait 31/10 : `tests/banc_effacement.py` OK (perte 0,86 dB, chiffres dans l'étude §8), `cas_banc` ajouté au test rapide ; faiblesses notées (brique, schémas, cercle 34 %). Ancienne consigne : banc `backend/tests/banc_effacement.py` (port de `cas.py` : textures brique/herbe/photo générées, polices Montserrat `backend/fonts/`, SSIM numpy) + compléter `test_ocr_v2_effacement.py` (3 cas déjà en place ; vérifier que `_ajuster` ne coûte pas de dB sur les 108 zones) (script `import racine` + `main()`, référence v1 = aplat du rectangle, seuils §8 : perte fantôme ≤ 1,5 dB sur 108 zones, uni/dégradé ≥ 40 dB, flèche droite 100 % conservée ; recalibrer si besoin) ;
   - 5.2 [x] fait 31/10 : `ocr_v2/detect.py` (`Recognizer`, `Mot`, `Tesseract`, `LectureEchouee`), `ocr.py` l'utilise (messages v1 inchangés). Vérifié en Docker léger (`python:3.12-slim` + tesseract apt, `--cpus=2 --memory=2g`, paquets `app` vides pour éviter FastAPI) : ancien (HEAD) contre nouveau identiques (texte + pixels) sur scan droit, couché, fond blanc, page vide, sans tesseract. Script : `%TEMP%\claude\c--Users-IBRAH-Documents-Projets-Precis-Translator\0c3ed8c0-1686-4139-8530-b771278bfa32\scratchpad\compare_ocr.py` (+ `ocr_ref.py`) ;
   - 5.3 [x] masque + fantôme branchés dans `ocr.py` pour les PDF scannés (voir Fait) ;
   - 5.4 [x] PP-OCRv6 ONNX (voir Fait) ;
   - 5.5a [x] `ocr_v2/render.py` : port de `couche_texte` (prototype `217549bb…\scratchpad\orig\couche_texte.py`) + police par la forme (étude §7.1 « Conception retenue ») ; redressement avant lecture dans `ocr.py` ; test `test_ocr_v2_rendu.py` (natif Roboto / PT Serif scanné → police, tailles, gras, italique) ;
   - 5.5b [x] `ocr_v2/image.py` : `traduire_image(data, traduire, lecteur)` → `ImageTraduite(data, mime, blocs)` (contrôles taille/type/pixels/animée, blocs de lignes, mise en place élargie/réduite, effacement, dessin dans la couleur mesurée) ; test `test_ocr_v2_image.py` (PP-OCRv6 relit « Pompe à eau » sur le japonais). Revue de code : 8 corrigés, 2 rejetés (étude §7.2).
6. [ ] Extension (demande 31/10 : traduire **tous les types de contenu**, en priorité les images qui gardent leur langue, règle : image dont le texte est détecté avec assez de confiance → traduite) : compléter l'étude d'extension (§3) pour vidéos, PDF intégrés, canvas, leçons G48xxx ; essai sur TEAM-GP ; puis prototype.
   - 6.1 [x] étude §3.5–3.9 + décisions 5–8 (mesures TEAM-GP : 81 leçons classiques, 107 images restées japonaises ; vidéos → calque en pause ; animations ignorées ; PDF → circuit documents ; G48 hors périmètre) ;
   - 6.2 [x] routes `app/api/extension.py` + service `app/services/extension.py` (débit forfait puis pages achetées, 1 500 car. = 1 page, image = 1 page si remplacée) ; `tests/test_extension.py` 11/11 ;
   - 6.3 [x] prototype `extension/` (MV3, TS, esbuild) : texte (API du navigateur ou « qualité Précis »), MutationObserver, images avec accord et animations ignorées, vidéo en pause ; typecheck OK, `npm test` 16/16, build OK ; **pas encore essayé dans un vrai navigateur**. Limites notées : refresh token dans `storage.local` (lisible par nos scripts de contenu, pas par la page) ; texte par l'API du navigateur rejeté par l'utilisateur (voir 6.3b) ;
   - 6.3b [x] traduction par bloc (typecheck OK, `npm test` 20/20, build OK, backend 18/18 ; logique DOM vérifiée dans Chromium headless : balises, réordonnancement, balise perdue → original, page modifiée → original, nœuds réutilisés, restauration exacte) (étude §4 révisée, décision 9) :
     - contenu : blocs (p, li, td, th, h1-h6, label, button, div/span à texte direct, texte SVG) ; enfants en ligne → `[[n]]…[[/n]]` + table n → élément d'origine ; envoi avec titre et blocs voisins ; reconstruction avec les éléments d'origine (attributs gardés), restauration ; balises encore fausses après relance → bloc laissé en original (jamais de mise en forme cassée) ;
     - backend : `traduire_textes` / route segments acceptent balises + contexte (`contexte_page`, contrôle `runtags.defauts` et relance du moteur) ; débit sur `runtags.sans_balises` ;
     - retirer `contenu/moteur.ts` (API Translator) et la case « qualité Précis » ; tests des deux côtés ;
   - 6.4 [ ] ← essai réel : Playwright Chromium headed, `launch_persistent_context` avec `--disable-extensions-except` + `--load-extension=extension/dist` ; backend local :8000, compte de test vérifié avec crédits (base dev) ; d'abord une page locale (texte, img avec texte japonais, iframe, vidéo), puis TEAM-GP (leçon classique à images japonaises, G49001) sans cliquer « Début », « Options administrateur », `lbnRegist` ni aucun postback ;
   - 6.5 [ ] pastille « Traduire ce PDF » (§3.9, circuit `/api/translate`), hors du prototype ;

**Hors plan** :
- `frontend/tsconfig.tsbuildinfo` non suivi (à ignorer).
- Échec CI `sync-github-app-user` : à régler côté propriétaire, hors code.
- `feat/page-beta-candidature` : push et PR sur accord, à rebaser après fusion de #53.

## 5. Pièges / contexte
- `backend/.env` est en LIVE pour Fapshi : ne jamais valider d'invite réelle. Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi.
- Lancer :
  - `npm run stop` ;
  - puis, en arrière-plan à la racine, `PYTHONUTF8=1 <venv>/python.exe scripts/dev.py`.
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`.
- Tests backend : unittest (pas de pytest), sur Postgres 5433, jamais la base dev 5432. Aucune base 5433 permanente : lancer Docker Desktop, puis `docker run -d --rm --name precis-test-pg -p 5433:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=precis postgres:16-alpine`, puis `python -m alembic upgrade head` (dans `backend/`, avec `DATABASE_URL`) avant les suites.
- Tests extension/OCR : `cd backend && PYTHONUTF8=1 <venv>/python.exe tests/test_extension.py` (Postgres local actif suffit).
- Tesseract est absent en local : tester l'OCR dans un conteneur léger, pas l'image backend (LibreOffice lourd ; l'utilisateur demande de ménager la machine) — voir la commande de 5.2 ; pip peut couper en SSL : `--retries 10 --timeout 60`.
- Image traduite (5.5b) : MPO (JPEG de smartphone) accepté comme JPEG ; `PPOCR.lire_image` lit sans passer par le disque ; seuil de texture `erase.T_TEX` partagé ; rien à remplacer → l'original revient tel quel. Une traduction longue depuis le japonais ne tient souvent pas dans la boîte : le bloc est gardé (info-bulle côté extension). `PYTHONUTF8=1` obligatoire pour les tests (sorties en japonais).
- 6.3b : moteur `backend/engines/translation_ai.py` — `_translate_batch(batch, lang, cb, ..., cadre={"fiche","page","n_page"})` l.381, consigne balises l.255-265, relance si balise perdue l.543-593, cadres des documents l.832-836 ; le faux `Moteur` de `tests/test_extension.py` devra accepter `cadre`.
- Extension : `cd extension && npm run -s typecheck && npm test && npm run -s build` ; `API_BASE` dans `src/config.ts`.
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent | tail -n 8`.
- Remote `origin` = EagleFox31. Locales en UTF-8 sans réencodage.
