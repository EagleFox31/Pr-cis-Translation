# PASSATION — 09/11/2026
## 1. Objectif en cours
(00) Traduire les images comme un studio de PAO (4S_EN.pdf + organigrammes). Étude : `docs/etude-traduction-images-pro.md` (§9–§12). Branche `feat/traduction-images-pao`, commits non poussés jusqu'à **8521d22** (visionneuse).
- Règles utilisateur : taille traduite ≤ originale ; même nb de lignes en réduisant jusqu'au seuil (10 %, `TOLERE`) → +1 ligne seulement si le seuil est atteint → réduction plus forte. **Règles générales, jamais cas par cas.** Précision « chirurgicale » exigée.
- Étapes .1–.12 [x] (traits de tableau, centrage optique, case fermée, `TOLERE` = 10 %).
- .13 [x] 0ff9fac (étude §12) : césure pyphen (mot plus large que sa case, passe +1 ligne), `_freres` sur toute la figure (`MEME_CORPS`), `CENTRE_CASE`, `FLOTTANT` garde le centre, centrage optique CJK, tirets de numérotation (`image.py:71` `_PUCE` ; tiret dessiné dans `_symboles`). Banc 141/6/1/55.2/3829/0 ; tests image + effacement verts. Aucun cas réel « numéro + tiret » au banc : vérifier sur l'image que fournira l'utilisateur.
- .13b [x] e51874a (`docs/etude-pdf-formes-cadres.md`) moteur PDF 1.0.13 : lettre cachée sous une forme pleine peinte après elle (`_shape_covers`/`_ink_masked`) ; étiquettes dans deux cadres distincts non fusionnées (`_two_frames`). P36 108/108, corpus 124 p. identique.
- .13c [x] visionneuse (`docs/etude-visionneuse-defilement.md`) : zoom qui coupait la page gauche (`PdfViewer.tsx` `flexShrink: 0`) ; molette « un geste = une action » (`lib/molette.ts`).
- Branche `feat/lettres-dessinees-visionneuse` (issue de 8521d22), non poussée.
- .13d [x] 2d47bdf moteur 1.0.14 : cas A (forme unie sur 1re lettre → mot entier traduit, 1re lettre stylée, `_segs_avec_initiale`, `style_sig[9]`), filet (forme ornée repeinte au-dessus, ligne ancrée qui grandit vers le bas). Tests `tests/test_pdf_lettres_dessinees.py` 43/43, planche `tests/out_lettres_dessinees/planche.png` ; P36 108/108, cohérence 10/10, textes oubliés 21/21. Limite : lettre ornée + traduction commençant par une autre lettre (« S » sur « Trier »).
- .13e [x] 50273a8 visionneuse : Pleine page (défaut) / Largeur, champ « n / N », rideau Comparer ; touche 0 = Pleine page. tsc/lint/build verts.
- .13f [x] 160f79b moteur 1.0.16 (`docs/etude-pdf-centrage-cadre.md`) : texte seul dans un cadre dur → conteneur symétrique sur l'axe du cadre (bord du cadre ≠ voisin, marge égale 2–8 pt, 0 pour légende sous photo `over_frame`) ; lettre dessinée = parent dominant, plafond ×2 supprimé (cas C9). P36 108/108, cohérence 10/10, oubliés 21/21, lettres 44/44 ; corpus : seul 4S change (10 p., mieux centré).
- .13g [x] commité (étude `docs/etude-images-halo-encre-axe.md`) : banc par lots de 5 (`banc_images.py --lot N`), écarts 17 → 1, aucun recul face à la version précédente ; ajouts : halo exclu des tracés longs (`_longs`/`_sortants`), trait traversant = des deux côtés + contact (`_des_deux_cotes`), frères sans condition de police. Reste : banc public ~50 images (ICDAR/COCO-Text/TextOCR, schémas) à faire ; restes f82d 688 / 97a5 1069 préexistants.
- (historique .13g) organigramme b76a516aca : halo des lettres non effacé (`mask.py` HALO_*), texte pâle mal borné (`_elargie` seuil selon contraste), étiquettes sœurs à tailles différentes (`_hauteur_encre`, `encres` dans `_freres`), texte non centré dans sa case (`conteneur` → `clos`, `_case` branche `axe`), barre de « H » prise pour un trait (`sort_h`/`sort_v` : un trait doit sortir de la zone). Tests image + effacement verts (`cas_cases_et_encre`, `cas_halo`).
  - Sources restaurées (nouvelle version, `sort_h` présent). Docstring `conteneur` : 6 valeurs, pas 4. Comparaison montrée à l'utilisateur : « Entretien client » passe de 64 px (ancien moteur) à 27 px comme ses frères (cause : `_freres` lisait mal la hauteur de 問診 → corrigé par `encres`). Script de comparaison original/avant/après : `cmp_b76.py <cas> <sortie.jpg>` (prend l'« avant » dans `sorties/`, donc lancer avant tout nouveau banc).
  - Reculs au banc à corriger par règles générales : écarts de corps 1 → 11 (f4c9, 080a, 21827, f82d…), restes 16c13 0 → 126, cbc0 0 → 34 (piste : `_elargie` déplace aussi la bande de mesure des restes ; enchaînement union-find par le critère d'encre). Mieux : 21827 restes 344 → 250.
  - Puis : analyse des 18 sorties une par une → étude `docs/etude-images-halo-encre-axe.md` + ligne README → banc public ~50 images (ICDAR/COCO-Text/TextOCR, schémas) avec rapport → commit sans push.
- .14 [ ] ← essai par l'utilisateur dans l'interface (4S à retraduire : pastilles, cercles, « Objets nécessaires/inutiles »), puis push/PR seulement avec son accord.
- Limites connues : 424e libellés à 27 px (frères de « Vérification et sauvegarde des données ECU », règle validée) ; texte coloré sur dégradé ; couleur `_couleur()` (« Non reproduit ») ; marge intérieure des cases (6 %) à trancher ; glossaire inter-images ; « Parts Orderd » (faute source).
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
- Moteur images : `backend/app/services/ocr_v2/image.py` — `conteneur()` → `_case()` (cadre, libre, uni, milieu) → `placer()` (passes : même nb de lignes jusqu'à `TOLERE`, puis +1 ligne, puis plancher, puis coupure) → `_freres()` (union-find, taille mini, `n_min`) → `_equilibrer()`.
- Tests backend = scripts (`python tests/test_x.py`). Images : `tests/banc_images.py`, `tests/test_ocr_v2_image.py`, `tests/test_ocr_v2_effacement.py` (venv + `PYTHONUTF8=1 NO_PROXY=*`).
- Fichiers en CRLF : les éditer avec Edit, jamais avec `sed -i`. Remote `origin` = EagleFox31.
