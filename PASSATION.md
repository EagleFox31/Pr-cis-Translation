# PASSATION — 09/11/2026
## 1. Objectif en cours
(00) Traduire les images comme un studio de PAO (4S_EN.pdf + organigrammes du banc). Étude : `docs/etude-traduction-images-pro.md` (§5 bis = règles de l'utilisateur et derniers résultats). Option 1 retenue et mise en place (§8 de l'étude). **ATTENTE : l'utilisateur retraduit 4S_EN.pdf et donne son avis.**
- Règles de l'utilisateur (09/11) : taille traduite ≤ originale ; ordre = même nombre de lignes sur toute la largeur de la case → +1 ligne → seulement ensuite réduction.
- Prototype hors dépôt (scratchpad `C:\Users\IBRAH\AppData\Local\Temp\claude\6d6c80c79a7942fb\42c03571-7b91-4a3a-9fd2-6b8799712cd9\scratchpad`) : `proto.py` (conteneur/alignement), `placer3.py` (placer revu : s0 = min(hauteur, largeur lue) en latin, interligne rapporté à s_h, calage vertical dans `libre`), `proto3.py` (banc A/B, sorties `C/`), `dbg4.py <cas> <texte>` (trace placer pour un cas). Lancer depuis `backend/` avec `RATIO=40` et le dossier scratchpad en argument.
- Dernier banc : B = 0 débordement / 117 (A : 3) ; 0 coupe ; écarts entre frères 9 (A : 2) ; organigrammes sur 1 ligne (une carte sur 2 lignes car trop longue).
- Défauts restants à corriger dans l'implémentation : (a) chaque ligne doit être centrée une à une (`image.py:676`, toutes les lignes partent de `p["x"]`) ; (b) équilibrer 2 lignes (éviter « … de la / cause ») ; (c) frères : harmoniser sur la plus petite ; « Pièces commandées » petit (mot plus large que la colonne, conforme à la règle).
- Étapes .1–.4 [x] (banc 138 posés / 0 coupe / 2 écarts, ocr_v2_image vert) ; .5 [~] cache vidé, retraduction par l'utilisateur. Rappel : .1 `conteneur()` + garde-fous (bord, RATIO 40) dans image.py ; .2 branchement cadre/_libre/_contour + placer revu ; .3 centrage par ligne + équilibrage + frères ; .4 banc (0 coupe, 0 débordement) + ocr_v2_image vert ; .5 vider le cache images, l'utilisateur retraduit 4S_EN.pdf.
- Restes antérieurs : image 31 « 3-days »/« Before » séparés ; même titre traduit différemment d'une image à l'autre (glossaire) ; « Parts Orderd » (faute source).
- (a) 6.17 FAIT (16d4840, 985238d, 10d1839, 499873b sur `feat/extension-gratuite-forfaits`, non poussés) : essai local par l'utilisateur, puis PR #56 (brouillon). App lancée via `scripts/dev.py` avec `EXTENSION_OFFRE=1`.

## 2. Fait
- 6.15.1 (07–08/11) : 2 lots du worktree `Precis-Translator-extension` fusionnés ici. Lot 1 : `feat/extension-distribution`, 24 commits, 8e38a2f. Lot 2 : `feat/extension-analyse-images`, 13 commits, e967d3c ; l'analyse d'image est séparée de la traduction.
  - `backend/app/api/extension.py` : cache partagé `cache_images`, limites par page, 2 images par utilisateur, guichet OCR via `_tour()` ; `_occupe` attrape aussi `ocr_file.OCROccupe` et renvoie 503.
  - `backend/app/services/ocr_v2/image.py` : `lire_image(..., tour=)` et `traduire_image(..., lus=, tour=)` ; le délai court à partir du tour obtenu.
  - Vérifs : test_extension 30/30, cache_images, limites_page, ocr_file (10), ocr_v2_image ; extension 53/53 + build (dist 1.0.0) ; front tsc/lint/build OK. Suite backend complète relancée le 08/11 : 98/98 vertes, après correction de `test_invitations` (798e2cd, le test était périmé depuis 6.16). `test_ocr` exige Tesseract dans le PATH et `TESSDATA_PREFIX`.
  - ⚠ `backend/tests/test_extension.py:287,291` corrigés ici (la réponse d'analyse contient `texte`) ; ils restent faux sur la branche du worktree. À reporter ou à signaler à l'utilisateur.
- 6.16 e-mails Spacemail : commits 6a0504a + 7e16ee4, non poussés. `_expediteur()` et carte 540 px `_carte` dans `backend/app/core/email.py` ; alias `precis@` (expéditeur), `support.precis@`, `alertes.precis@`. Aucun client ne doit voir le nom ni l'adresse d'Ibrahim.

## 3. Décisions
- Scan : seule la détection diffère du PDF natif. Qualité avant vitesse ; délai OCR de 90 s.
- Extension :
  - 1 crédit par image remplacée ; le texte se facture au volume (1 500 car. = 1 page).
  - Pas de bascule silencieuse vers le payant ; mémoire locale IndexedDB.
  - Distribution : boutiques Chrome + Edge, nom visible Précis, d'abord par lien seulement.
- « Traduire quand même » débite même si le résultat est du charabia : voulu, on facture l'usage.
- Budget à la page (P5) : page illisible ou blanche sautée sans compter. Voulu, rien à changer.
- 6.8 : 1 page par image remplacée ; case non cochée par défaut ; débit après traduction, remboursé si le travail échoue.

## 4. Plan
1–5. [x] branche, études, OCR v2.
6. [~] Extension et documents :
   - 6.15 [x] demande du 06/11 : .1 intégration extension [x] (2 lots) ; .2 [x] ; .3 [x] ; .4 [x] PR #56 en brouillon : CI verte sauf `sync-github-app-user` (hors code). Ne pas la sortir du brouillon sans l'utilisateur.
   - 6.17 [x] extension gratuite par page : commit 16d4840 sur `feat/extension-gratuite-forfaits` (issue de `feat/ocr-file-pages-illisibles`), non poussé. Table `extension_usage` (migration 0020, à appliquer sur la base dev : `alembic upgrade head`), `limites_page.FORFAITS/reserver/rendre/verifier`, env `EXTENSION_OFFRE` (défaut 0 = bêta, pas d'offre). Vérifs : test_limites_page OK, test_extension 55/55, test_cache_images OK, extension 53/53 + typecheck. Défauts choisis : image au-delà du plafond de texte → laissée en original sans message ; lots/analyses/captures toujours sur 6 h en mémoire ; enterprise/admin = Pro. Reste : essai local par l'utilisateur.
   - Suite 6.15 [ ] ← choisir avec l'utilisateur : suite backend complète, essai local, push.
   - 6.16 [~] e-mails : .4 reste à poser les secrets prod `SMTP_*` + `ADMIN_ALERT_EMAIL`, puis vérifier un vrai code de connexion en prod.
   - 6.11.7 [ ] recette Docker (`--cpus 2 --memory 3g`). **Attend 3 documents réels et l'avis de l'utilisateur.**
   - 6.4 [~] essai réel sur TEAM-GP (G49001). Ne cliquer ni « Début », ni « Options administrateur », ni `lbnRegist`, ni aucun postback.
   - 6.9 [ ] interface de l'extension : branding seulement, jetons du `frontend`.
   - 6.12 [ ] distribution : `externally_connectable`, `onInstalled`, page `/extension`, fiches boutiques.
   - 6.5 [ ] pastille « Traduire ce PDF ».
   - 6.14 [ ] messages d'erreur et d'information (`docs/etude-notifications.md`).

**Hors plan** :
- `doc.paid` n'est pas recalculé après `refund_unfinished`.
- Fichiers `budget_<job>.json` jamais purgés.
- Spacemail limite les envois par jour : passer à Amazon SES si le volume monte.

## 5. Pièges / contexte
- Interdits :
  - `backend/.env` est en LIVE pour Fapshi et pour Spacemail : ne jamais valider une invite de paiement réelle.
  - Ne pas afficher les `.env` (`grep -c` seulement). Jamais de clé dans un fichier suivi.
  - Ne jamais tester `POST /api/auth/login` avec une adresse inconnue : cela crée un compte et envoie un vrai e-mail.
  - Push ou PR seulement après vérification locale par l'utilisateur.
- venv : `C:\Users\IBRAH\Documents\Projets\Precis_Translator_backup_2026-06-10_13-10\backend\venv\Scripts\python.exe`. Toujours avec `PYTHONUTF8=1`.
- Proxy Windows mort (192.168.137.1:8080) actif sur cette machine : Python l'utilise et les appels DeepSeek tournent en boucle. Lancer avec `$env:NO_PROXY="*"`, ou le désactiver dans Paramètres > Réseau > Proxy.
- Lancer l'app : `npm run stop` puis `scripts/dev.py`, l'un après l'autre. Un uvicorn orphelin sur le port 8000 peut servir du vieux code : le tuer par PID.
- Tests backend : unittest sur Postgres 5433, jamais sur la base dev 5432. Conteneur `precis-test-pg` (postgres:16-alpine), puis `alembic upgrade head`.
- Front : `cd frontend && npx tsc --noEmit -p . ; npm run lint --silent ; npm run build --silent`.
- Extension : `cd extension && npm run -s typecheck && npm test && npm run -s build`. Faire `npm ci` si une dépendance manque.
- Tests backend = scripts (`python tests/test_x.py`), pas `unittest` / `discover`.
- Fichiers en CRLF : les éditer avec Edit, jamais avec `sed -i`. Remote `origin` = EagleFox31.
