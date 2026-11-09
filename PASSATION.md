# PASSATION — 09/11/2026
## 1. Objectif en cours
(00) Traduire les images comme un studio de PAO (4S_EN.pdf + organigrammes). Étude : `docs/etude-traduction-images-pro.md` (§9–§11). Branche `feat/traduction-images-pao`, commits non poussés : 9b1ef5d, b7288f8, ef414bf, **a886a73**.
- Règles utilisateur : taille traduite ≤ originale ; même nb de lignes → +1 ligne → seulement ensuite réduction. **Règles générales, jamais cas par cas.** Précision « chirurgicale » exigée.
- Étapes : .1–.8 [x] ; .9b [x] a886a73 : traits de tableau 2 px anticrénelés gardés (`mask.py` `_pixels_du_trait` : pixel = mélange fond→cœur du trait, plus la médiane). Banc 141/0/1/restes 3820 ; tests image + effacement verts ; cbc0dcf3fa vérifié net.
- .10 [x] centrage vertical optique : dans une case fermée haut/bas, `placer(milieu=)` pose le milieu « haut des capitales → ligne de base » au milieu de la case (banc 312d4ab391).
- .11 [x] case fermée haut/bas : `conteneur()` suit la bande au-delà de `OUVERT` tant que ses deux murs continuent (banc 1256de4600 : point 1 sur 1 ligne ; point 4 sur 2 lignes, conforme : trop long pour la bande à taille d'origine). Banc inchangé 141/0/1/3820, tests verts.
- .12 [ ] essai 4S par l'utilisateur, puis push/PR seulement avec son accord.
- Limites connues : frères d'une colonne d'organigramme à la plus petite taille (424e, 97a) ; texte coloré sur dégradé ; couleur `_couleur()` (« Non reproduit ») à contrôler ; marge intérieure des cases (6 %) à trancher ; glossaire inter-images ; « Parts Orderd » (faute source).
- (a) 6.17 FAIT (`feat/extension-gratuite-forfaits`, non poussé) : essai local utilisateur puis PR #56 (brouillon).

## 2. Fait
- 6.15.1 : 2 lots du worktree extension fusionnés (8e38a2f, e967d3c) ; suite backend 98/98 le 08/11. ⚠ `backend/tests/test_extension.py:287,291` restent faux sur la branche du worktree.
- 6.16 e-mails Spacemail : 6a0504a + 7e16ee4 non poussés (`backend/app/core/email.py`). Aucun client ne voit le nom/l'adresse d'Ibrahim.

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
- Tests backend = scripts (`python tests/test_x.py`). Images : `tests/banc_images.py`, `tests/test_ocr_v2_image.py`, `tests/test_ocr_v2_effacement.py` (venv + `PYTHONUTF8=1 NO_PROXY=*`).
- Fichiers en CRLF : les éditer avec Edit, jamais avec `sed -i`. Remote `origin` = EagleFox31.
