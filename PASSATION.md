# PASSATION — 19/11/2026

## 1. Objectif en cours
Corriger les défauts PPTX du PowerPoint de Gerold (R6/R7) selon `docs/etude-pptx-qualite-gerold.md`. On est dans le worktree `Precis-Translator-pptx-qualite`, sur la branche `fix/pptx-qualite`. Rien n'est poussé : on attend la validation locale de l'utilisateur.

## 2. Fait
- a02225c (étapes a, b, e) dans `engines/pptx/engine.py` et `engines/runtags.py` :
  - un titre coupé par des sauts de ligne manuels est traduit en une seule unité, puis recoupé en lignes équilibrées (`decouper_lignes` et `joindre_lignes`) ;
  - un libellé court coupé en paragraphes est fusionné de la même façon ;
  - un symbole seul n'est pas envoyé au modèle, et un préfixe symbole est conservé ;
  - aucun espace double n'est créé.
  - Tests : `tests/test_pptx_porteurs.py`.
- cef7439 (étape d) :
  - `runtags.traductions_majoritaires` : pour un même original d'au moins deux mots, la majorité stricte (≥ 2) l'emporte ; en cas d'égalité, rien ne change.
  - Elle est branchée dans `_coherence_document` (`app/services/translation_runner.py` ~l.549), avant la reprise des termes incohérents. Elle ne fait aucun appel au modèle et ne réinjecte que les diapositives touchées.
  - L'étude, section (d), est mise à jour.
- Preuves :
  - test_pptx_porteurs 21 passés ;
  - test_pptx_preview 38/38 ;
  - test_runtags 41/41.
  - Auparavant : reprise_pptx, apercu_progressif, contexte_traduction, ole_apercu, xlsx, rendu_structure, download_format, tous verts.

## 3. Décisions
- d2 abandonné : imposer la traduction d'un libellé partout dans les phrases dégradait le texte (« HRD policy » donnait « Politique HRD » au lieu de « politique RH »). La fiche est un texte libre, pas un glossaire.
- Mots seuls exclus de l'unification : « Customer » peut donner Accueil ou Client selon l'endroit.
- Contrôle commun à toutes les étapes : réinjecter la source rend exactement l'original (aller-retour).

## 4. Plan
1. [x] (a) + R6 sauts de ligne et libellés coupés
2. [x] (b) symboles
3. [x] (e) espaces doubles
4. [x] (d) cohérence : même original, majorité
5. [x] (c) débordement de zone : `engines/pptx/debordement.py` (mesure par largeurs Arial, `ajuster` avec un plancher de 80 %), `engine.py` (`_inject_in_xml`, `debordements`), `translation_runner._compacter_slide` (retraduction plus courte). Tests : `tests/test_pptx_debordement.py`.
5b. [x] Réduction de police écrite dans le texte (`sz`), avec repli `normAutofit` si la taille vient du masque ; marge de 3 % sur la largeur.
   - Reste pour l'étape 6 : « Caractéristiques » (diapositive 6) et « Entretien Rappel d'entretien… » (diapositive 10) ne tiennent pas, même à 80 % : il faut la retraduction plus courte.
   - Bandeau « Niveaux de certification » : `wrap=none` + `spAutoFit`. Il est sur une ligne dans PowerPoint ; seul LibreOffice le coupe.
6. [ ] ← Rejouer Gerold (`original.pptx` → nouvelle traduction) et montrer seulement les cas qui changent.
7. [ ] Rapport à l'utilisateur. Push/PR seulement après sa validation locale.

**Hors plan** : la même règle de débordement pour XLSX (accord de l'utilisateur ; branche à part).

## 5. Pièges / contexte
- Fichiers Gerold : `C:/Users/IBRAH/AppData/Local/Temp/claude/6d6c80c79a7942fb/1158bb8f-57e3-42af-8146-b3911ec69fb7/scratchpad/gerold/{original,traduit}.pptx`.
- Scripts d'analyse dans `C:/Users/IBRAH/AppData/Local/Temp/claude/6d6c80c79a7942fb/34e53c1c-5d86-4eb3-bd86-a334927c8f09/scratchpad/` :
  - `verif.py` : diff des extractions et aller-retour ;
  - `termes.py` : incohérences.
- Python : il n'y a pas de venv dans le worktree. Utiliser `/c/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe -X utf8` (pytest y est installé).
- Beaucoup de tests sont des scripts avec `main()` : les lancer avec `python -X utf8 tests/x.py`, pas avec pytest.
- Les tests qui ont besoin de la base exigent `backend/.env` :
  - copier celui du dépôt principal ;
  - lancer les tests ;
  - puis `rm .env`, car il est ignoré par git et ne doit pas rester.
- Commits : ne mentionner l'IA nulle part et ne pas ajouter de trailer.

## 2026-11-25 06:24 — Landing : positionnement EN, sections « pour qui » et FAQ
- Branche `feat/landing-international`, PR #105 vers `main` (rebasée sur main 1.12.1, conflits locales/css/Home/PASSATION résolus en gardant les deux côtés). Contexte : offre Précis à vendre à l'international (traducteurs, consultants immigration, bureaux internationaux).
- EN `hero.*` réécrit (promesse : même fichier en retour, mise en page conservée) ; FR inchangé.
- Nouveau `components/audience/AudienceSection.tsx` : 3 cartes cibles (`audience.*`) + FAQ 5 questions (`faq.*`, `<details>`), inséré après `FeaturesGrid` dans `Home.tsx` ; CSS `.faq-*` dans `index.css`.
- `Home.tsx` : `lang`, `<title>` et meta description suivent la langue côté client (`seo.*`) ; le head statique prerendu reste FR → contrat CI SEO intact (1 h1, canonical, `/` → 308 `/home` conservé volontairement).
- Preuve : `npm run lint` OK, `npm run build` OK (15 pages), preview EN vérifiée (hero, cartes, FAQ).
- Limites : OG/twitter restent FR (pas de JS côté crawler) ; pas de hreflang (même URL) ; `verify_public_seo.py` non rejoué en local (nginx docker).
- Restant : fusionner #105 après CI, déployer via `deploy-vps.yml` après fusion ; Paddle live et domaine `.com` optionnel (voir dossier offre).

## 2026-11-25 08:03 — PR #105 ouverte, suivi auto activé
- PR #105 `feat/landing-international` → `main`, fusionnable après fusion de main 1.12.1 (commit a55c87a), lint/build verts en local, CI absente (facturation GitHub).
- Suivi auto de la PR activé dans la session (CI, conflits, commentaires). Verrou : fusion sur accord du commanditaire.
- Prochaine étape : fusion de #105, puis `deploy-vps.yml` ; prospection selon les fichiers d'offre (non suivis par git, racine du dépôt).
