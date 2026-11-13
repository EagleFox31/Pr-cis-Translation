# Passation : robustesse OCR (worktree Precis-Translator-ocr, branche fix/ocr-robustesse-documents)

Étude : docs/etude-robustesse-ocr.md. Registre : docs/revues/robustesse-ocr.md.

## Objectif en cours
Finir l'alignement de groupe (R1/R2) : rejeu 2 → ne montrer que les cas changés (mieux/pire), puis niveau 1 de la nouvelle méthode.

## Plan
1. [x] Étude + tirage des 30 nouvelles images (80 cas, 2 refus).
2. [x] Diagnostic lots 0 → 15 (`--live`, 5 cas), défauts consignés au registre avec l'étape fautive.
3. [x] Regroupement par cause, classement par nombre de cas.
4. [ ] Corrections par cause, dans l'ordre de docs/etude-robustesse-ocr.md (Résultats) :
   [x] N corrigé (11/11, non committé : `_couleur()` cœur de l'encre, test `cas_couleur_petit_corps`, registre § Corrections) ; rejeu 16 lots + interne 0–3 fait, aucune régression.
   [~] A+2bis (non committé) : `blocs()` backend/app/services/ocr_v2/image.py ~l.249 — libellé « X: » /
   valeur / nombre seuls ; `rangee` ; test RETOUR ; interligne `dessous` ; ligne lue entre deux. Test
   `cas_blocs` OK. Interne 0–3 identique. **Accepté par l'utilisateur le 11/11** (recommandation : garder
   tel quel, cas limites « Sender + Charles Duggan » etc. non traités).
   Rejeu public avant/après (ancien `blocs()` via banc_base.py) :
     [x] lots 0 → 9 et 14 : détail par cas au registre (lignes « rejeu A+2bis »).
     [x] lots 10 → 13, 15 (13/11) : 10 mieux (accepté) ; 11 b30c un peu mieux ; 12 b5df nettement mieux, bec7/c8dd mieux,
         **b3374ed8d5 RECUL** (liste de marques empilée fusionnée en 4 lignes, « General Nutrition Center » traduit) ;
         13 ca0f mieux mais « Patterson and Fischer » → « et » (nom propre), cbac mieux ; 15 f455 et fdc8 nettement
         mieux (fdc8 : plus de « 15 millions » inventé sur l'axe), fd41 mieux. Planches : scratchpad 2582ec3f…/lotN, cmp_<cas>.jpg.
     [x] 13/11 recul b3374ed8d5 corrigé : `_liste()` (image.py, avant `blocs()`), test dans `cas_blocs`.
         Ne touche que b3374ed8d5 (lot 11) et 6739490c68 (lot 7) ; rejoués, planches vues : marques à part.
         Restent (cause C, traducteur) : « Your Life » → « Votre vie », « General Nutrition Center » traduit.
         Non traité : « Copper / Calcium » fusionnés (« 6.0 (estimated) » pas reconnu comme nombre de rangée).
     [x] ligne A+2bis au registre § Corrections.
     [x] (réglé par R1) l'utilisateur demandait si tous les cas ont été pesés avant la règle `_liste()`.
         Revue faite (non exhaustive, banc 80 cas : seuls 2 déclenchés). Risques identifiés :
         (1) texte TOUT EN CAPITALES en colonne étroite (isupper vrai partout) → paragraphe découpé ;
         (2) titre en majuscules initiales sur ≥3 lignes courtes (« Annual / Sales / Report ») → découpé ;
         (3) allemand (noms à majuscule) en colonne étroite ; (4) liste de 2 éléments, ou 1er élément
         sur la rangée du libellé (« Food Stores / Drug Stores / Mass Merchandising » encore fusionnés) ;
         (5) pas irrégulier → toute la chaîne rejetée ; (6) marque en minuscule (« iPhone ») coupe la chaîne.
         Options proposées : A resserrer (exclure les lignes sans minuscule + test capitales et titre),
         B élargir aussi au cas (4), C garder tel quel. Attendre le choix, puis tests + rejeu lots 7, 11.
         Idées de l'utilisateur (13/11), analysées, en attente d'accord :
         R1 (règle PDF : ponctuation finale + majuscule + 1er mot qui aurait tenu = nouvelle ligne voulue) →
         la majuscule ne compte que si le texte contient des minuscules (règle le risque capitales = option A).
         R2 (centrage par équilibre des marges) : existe déjà DANS un bloc (`case()` image.py ~l.636,
         écarts des bords gauche/axe/droite) ; à étendre à un GROUPE de blocs voisins (lignes séparées par
         A+2bis : en-tête officiel, liste) qui partagent le même axe → même sens pour tous. Cadre = colonne,
         pas la page (en-têtes camerounais à 2 colonnes FR/EN). Corrige « aligné à gauche posé centré » (2bis).
     [x] R1 + R2 faites et commitées (14/11). `_liste` exige des minuscules (R1). `_axes()` aligne les blocs
         empilés d'une colonne (R2) ; corps proches exigés (`GROUPE_CORPS` 1,5 : titre ≠ libellé) ; l'alignement
         du groupe cède s'il rapetisse le bloc (sinon `_freres()` propage) ou le coupe sur plus de lignes.
         Rejeu public 16 lots : mieux 9661, 03a5, 1ec6, 3faa, bec7, 35a4 (en partie) ; plus aucun recul.
         Interne 0–3 identique avec/sans `_axes`. Restent ouverts (déjà là avant) : libellés empilés à aligner
         à droite (5c83, bord droit commun contre les barres) ou à gauche (848b, retrait « GULAI » 35a4) ;
         b3374 « Cuivre Calcium » fusionnés.
   [ ] ← **prochain** : **Nouvelle méthode (13/11, acceptée)**, niveau 1 structure à attaquer : un problème à la fois, par gravité, résolu sur TOUS ses cas,
       contrôle automatique des cas qui changent (plus de revue lot par lot). Ordre :
       Niveau 1 structure : 2bis ancrage/texte déplacé → D chevauchements + nombres coupés → B bandeaux perdus
         → ligne effacée laissée vide. + contrôle automatique de structure (traduction posée sur l'original).
       Niveau 2 aspect : alignement (R2 fait ; reste libellés empilés droite/gauche) → corps inégaux (D) → gras → couleur.
       Niveau 3 finition : police H → noms propres C+M → mots, G, J.
5. [ ] Rejeu des lots touchés + banc interne lots 0–3 + pytest.
6. [ ] Rapport, revue, commit (pas de push sans accord).

## Décisions / règles notées (11/11, 13/11)
- Lots traités deux à deux : rejouer 2 lots, un seul bilan.
- Nom propre (société, équipe) jamais traduit, même « and » (ca0f, 5a61, fdc8 « Trail Blazers ») : cause C.
- Règle du doute : le moteur n'invente rien ; texte non identifiable ou hors contexte → laissé tel quel.
  Mais un texte lisible et sensé laissé non traduit est un défaut (M). Mesurer les deux sens.
- Nouvelle règle (cause D) : un montant / nombre ne se coupe jamais sur 2 lignes, on réduit le corps
  (05e8 : « 200 / 000,00 IDR » chevauché).
- Retours utilisateur lot 0 au registre : « CREATIVEINPUT » espace perdu (L), bandeaux noirs des titres
  perdus (B), texte aligné à gauche posé centré (2bis ancrage), corps inégaux dans une colonne (D),
  police chasse fixe perdue (H, plus tard).
- Lot 1 : « Tax Id + IBAN » et « Cash / Change » encore fusionnés (A), « Smith Ltd » → « SARL » (C),
  ligne « Teh Tawar » effacée vide, mot coupé « B / esar » traduit en deux morceaux (A).
- Indicateurs : « restes » peut monter quand le rendu est meilleur (comparer les planches, pas le chiffre).

## Commandes
P=C:/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe
(cd backend) NO_PROXY='*' $P -I -X utf8 tests/banc_images.py --banc _banc_public --lot N --live  (= après)
Avant (ancien blocs()) : NO_PROXY='*' $P -I -X utf8 $S/banc_base.py $S/image_head.py --banc _banc_public --lot N --live
  S=C:/Users/IBRAH/AppData/Local/Temp/claude/6d6c80c79a7942fb/55b6abb0-9bda-4283-bdc2-3a60dd0e16c1/scratchpad/ocr
  (aussi blocs_dump.py <cas…>, manque.py <cas>). Les deux écrivent dans sorties/lotN : copier les planches
  entre les deux passes (avant/ et apres/ dans le scratchpad de session), lancer « avant » d'abord.
Tests ocr : (cd backend) $P -X utf8 tests/test_ocr_v2_image.py (script, pas pytest).
Piège : `sed 'Na\ …'` avec plusieurs lignes en guillemets doubles fusionne les lignes → guillemets simples.
