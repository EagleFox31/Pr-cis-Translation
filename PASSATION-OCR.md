# Passation : robustesse OCR (worktree Precis-Translator-ocr, branche fix/ocr-robustesse-documents)

Étude : docs/etude-robustesse-ocr.md, docs/etude-defauts-colonnes.md (non suivi). Registre : docs/revues/robustesse-ocr.md.

## Objectif en cours
G3 commité (16fc0e3). G4 abandonné (18/11, choix utilisateur option 1, code annulé, noté au registre). Suivant : G5, à expliquer simplement puis attendre l'ok.
Reprise : worktree C:/Users/IBRAH/Documents/Projets/Precis-Translator-ocr, branche fix/ocr-robustesse-documents.
## Fait (historique, tout commité)
- T3, backend/app/services/ocr_v2/image.py : `_VALEUR`, `GRILLE`=3, `_suite`, `_en_face` (après `LISTE_PAS`). Dans `blocs()`,
  une ligne avec une valeur numérique en face sur la même rangée est une `rangee` si ≥3 rangées partagent le bord gauche ET la colonne
  de valeurs. Test `cas_blocs` (Zinc/Manganese/Copper/Calcium, plus un contre-cas hors grille).
  Regroupements : seuls b3374 (Copper/Calcium séparés) et 4e98 changent ; banc interne identique.
- `_proteger(mask, bgr, intactes, effacees)` (~l.254, appelé dans `traduire_image` ~l.1289). L'encre des deux lignes qui se
  chevauchent (masque_couleur sans halo ni dilatation, sur leurs boîtes) est répartie tache par tache vers le milieu le plus proche.
  Une tache qui couvre les deux milieux est coupée à mi-chemin. La part de la ligne intacte, dilatée de DILATATION, sort du masque.
- Comparaison avec/sans (traducteur factice) : environ 15 cas publics changent, tous en gain, plus rien d'abîmé à tort
  (TELEVISION 3253, OE 4e98, 18-76 77d6, BETHESDA 6739, 212-450-4000 d24b, The Japanese b780).
  Banc interne : aucune différence. Tests image / effacement / rendu : OK.
- Défaut résiduel : léger voile gris là où l'effacement touche une ligne gardée (sous « New York » d24b, au-dessus de
  « Ind/Lor » a2a3). Cause : l'inpainting reprend la couleur de l'encre voisine, désormais conservée.
  Sur a2a3, le voile brouille aussi le trait horizontal du tableau sous « Volume » : c'est un recul de structure.
  Maquette : docs/maquette-voile-gris.png (non suivie).
- Autres défauts visibles sur la maquette, présents avant cette règle : sur a2a3, le trait du haut du tableau a des trous
  (cause B/traits) ; le gras est perdu (d24b, a2a3) ; la police à empattements passe sans empattements (a2a3, cause H).

## Plan
1-3. [x] Étude, diagnostic des lots 0→15, regroupement par cause.
4. [ ] Corrections par cause : N, A+2bis, `_liste`, R1+R2 [x] faits et commités (14/11).
   Nouvelle méthode (choix A, 14/11) : une règle à la fois, par gravité. Après chaque règle : rejeu 80 cas + banc interne
   + tests, montrer l'avant/après des cas qui changent, zéro régression.
   [~] T3 + `_proteger` : choix B retenu (14/11). Fait (non committé) : `_proteger` renvoie l'encre gardée
       (liseré compris, sauf traits de tableau repérés sur une fenêtre élargie de MARGE_TRAITS=40) ;
       `effacer(..., gardee=)` la traite comme inconnue pour le remplissage sans la réécrire.
       Session 14/11 (2) : `effacer` ne rend plus l'encre gardée « inconnue » ; `_fond_sous()` (erase.py) la
       remplace par le fond clair voisin (quart le plus clair, jamais assombrie). d24b OK, trait sous « Volume » OK.
       a2a3 : la tache grise derrière « Ind/Lor Volume » vient du remplissage fsr de cette zone coincée entre
       deux traits ; sans la règle il laisse des stries, avec il laisse une tache (fsr sensible à tout le voisinage,
       vu avec scratchpad 64aa…/fsr.py). Défaut de choix de méthode, préexistant : choix A (14/11), classé niveau 2
       (« tache fsr entre deux traits »). Tests ocr_v2 (5 scripts) OK. Rejeu public → 64aa…/protD(.txt),
       banc interne → 64aa…/protI : FAIT. Interne identique ; public 26 cas changent, tous en gain sauf tache a2a3 (classée).
       Registre à jour. COMMITÉ (8408549).
   [~] T1/T2 : `couper_colonnes` (image.py, avant `blocs`, appelé avant `_symboles`) + test. 98 cas : 4 changent, tous
       en gain (3faab, b3374, c0ed, fd411) ; interne identique ; tests ocr_v2 OK. COMMITÉ (33fde87).
   [x] T4 : ensemble `entete` dans `blocs()` + test. Seul b3374 change (gain). COMMITÉ (919361b).
   [x] F1/F2 : `haut` et `champ` dans `blocs()` + test. 848b et 70ced changent (gains) ; interne identique. COMMITÉ (d2e212d).
   [x] F4 : déjà couvert par `_proteger` (8408549) : rendu 848b libellés traduits, valeurs gardées nettes.
       Problème « fiche » clos. PROCHAIN : colonne G1+F3+G2 (libellés recentrés 848b, graphique 5c83).
   Traits de tableau troués à l'effacement (a2a3) : cause B, garder sa place dans l'ordre prévu (décidé 14/11).
   Après chaque traitement : sur chaque image concernée, lister TOUS les défauts visibles (même hors sujet),
   en précisant pour chacun s'il est déjà dans la liste (où) ou nouveau.
   [x] colonne G1+F3+G2 : COMMITÉ (b37590f). Recul 9a53 (« Slovenia » sur la barre) corrigé par `_aplat`
       (bord du fond = aplat d une autre couleur → reste une limite ; APLAT_ECART=150 pour ne pas prendre une carte pâle, f6ae).
       Gains : f4554, 09fe, 0c30, 5a61, 3faab, b3374, f6ae, 9a53 ; 6739 corps 33→25 acceptable. Tests + `cas_aplat` OK, interne identique.
       Défauts préexistants vus : prix « 59 » coupé (09fe), lignes minuscules chevauchées (3faab), « Drug S » coupé (b3374).
   [x] G3 + A limité (18/11, COMMITÉ) : `placer(serie=)` : libellé de colonne rapetisse jusqu au plancher sur ses
       lignes d origine (`serie="rang"`) ; la ligne de plus (rendu normal) n est gardée que si elle fait n0+1 lignes, un
       corps STRICTEMENT plus grand et reste dans `bornes` = `_bornes()` (part des lignes voisines et des traductions
       posées) resserré par `_traits()` (trait de tableau entre la boîte et le bord de l effacement, que `_libre()` ne voit pas).
       Public : gains 09fe, 0c30, 5a61, 497e, f4554, 0fc2, 5c83, 9406, ca0f, c8dd, fdc8, 5707, b2b5, b780, 6739 « Sample # » ;
       05e8 et 6739 « Carb » identiques à G3 ; compromis assumé : 1ec6 « Name: » 9→13, 3651 « Lizard »/« Caterpillar » plus grands.
       Interne lots 0–3 identique à avant G3 (f82 corrigé). Tests ocr_v2 5/5 OK. À surveiller : 9a53 « 8 liters » touchait déjà
       « OurWorldInData » dans G3.
   [x] G4 ABANDONNÉ (18/11) : trois votes de graisse rejoués, autant de reculs que de gains (mesure d épaisseur fausse).
       Code annulé ; registre : « mesure de graisse peu fiable », défaut d aspect niveau 2 (cause H).
   [ ] G5 (effacement s arrête au dessin).
   Ensuite niveau 1 suite (2bis ancrage, D chevauchements/nombres coupés, B bandeaux, ligne effacée vide),
   niveau 2 aspect, niveau 3 finition.
5. [ ] Rejeu complet + banc interne + tests.
6. [ ] Rapport, revue, commit (pas de push sans accord).

## Hors plan
- Dépôt principal (feat/nouveautes) : fiche EN Edge, E.5, déploiement des PR #70→#76, fichiers boutique non suivis.

## Décisions / règles
- Une règle générale, jamais au cas par cas ; tolérance zéro ; un défaut visible est montré, pas caché.
- Nom propre jamais traduit (cause C). Le moteur n'invente rien ; texte lisible laissé non traduit = défaut M.
- Un nombre ne se coupe jamais sur 2 lignes (réduire le corps).
- « restes » peut monter quand le rendu est meilleur : juger sur les planches.
- T3 : une valeur « en face » doit commencer par un nombre. Avec « toute case en face », 3253, b780, f455, 92a3… cassaient.

## Commandes / pièges
P=C:/Users/IBRAH/Documents/Projets/Precis_Translator_backup_2026-06-10_13-10/backend/venv/Scripts/python.exe
(cd backend) NO_PROXY='*' $P -X utf8 tests/banc_images.py --banc _banc_public --lot N --live   (écrit dans sorties/lotN)
Tests : $P -X utf8 tests/test_ocr_v2_image.py (scripts, pas de pytest). test_ocr.py échoue déjà avant (service OCR externe).
Scratchpad S=C:/Users/IBRAH/AppData/Local/Temp/claude/6d6c80c79a7942fb/031f9379-b3f1-481b-99a8-3b70d27e5306/scratchpad :
  protege.py <banc> <dest ABSOLU> [cas1,cas2…] (rendu avec/sans `_proteger`, `-u` pour voir la sortie au fil de l'eau)
  zones.py <src> <dest> (découpe les zones qui diffèrent) ; groupes.py <sortie> [banc] (regroupements).
Scratchpad G4 S2=C:/Users/IBRAH/AppData/Local/Temp/claude/6d6c80c79a7942fb/98d1cb75-5330-46b2-aa3e-93af744a53dc/scratchpad :
  banc_clu.py <dest> <off|on|clu|clu2> [banc] [args] (depuis backend/ ; off = G3) ; compare.py <avant> <après> <dest> ;
  crops.py <avant> <après> <dest> <noms…> (original | avant | après recadrés). Rendus : pub_off, pub_on, pub_clu, pub_clu2.
Un rendu public prend environ 1 min par cas : passer les commandes longues en arrière-plan.
