# Revue — objets incorporés 6.11.6 (facturation, exclusion OCR, compte rendu client)

Passe 1 : audit du 05/11/2026, verdict initial : non conforme. Les effets de route des n° 2 et 3 sont déduits, l'auditeur ayant tourné sur un autre Python ; ils sont maintenant couverts par des tests.

| N° | Gravité | Lieu | Classe | Correction | Statut |
|----|---------|------|--------|------------|--------|
| 1 | Bloquant | `engines/pptx/engine.py` `_a_des_objets` | objet non traité non signalé | le test repère aussi les relations `relationships/oleObject` et `relationships/package` (objet lié seul sur une diapositive) | corrigé (`test_objet_lie_seul_sur_la_diapositive`, `test_lien_hypertexte_n_ouvre_pas_le_paquet`) |
| 2 | Important | `engines/incorpores.py`, `services/images_document.py` `lister` | exception de décompression non attrapée | `_ERREURS_ZIP` partout dans `incorpores` ; en PPTX, `lister` transforme l'erreur en refus « fichier non valide » ; en DOCX et XLSX, il rend l'image sans ses octets. `poser_office` est couvert par le `except Exception` de `_poser_images_fichier` | corrigé (`ArchiveAbimee.test_refus_propre`) |
| 3 | Important | `services/images_document.py` `_lister_office` | garde-fou contourné | `reperer` n'est appelé qu'après les contrôles de `_ouvrir_zip` | corrigé (`test_le_garde_fou_passe_avant_la_decompression`) |
| 4 | Important | `engines/pptx/engine.py` `extract_slide` | doublon et accès concurrent | `incorpores.cumuler` : sans doublon sur (cible, raison), sous verrou | corrigé (`test_objet_partage_par_deux_diapositives_une_seule_fois`, `Cumul`) |
| 5 | Important | `incorpores._reinjecter`, `_redessiner_apercus`, moteurs, `translation_runner` | état sans affichage | `Modifs.restes` et `objets_restes` : remise en place ratée (`reinjection`) et aperçu non redessiné (`apercu`) arrivent au client, y compris pour un objet dans un objet (`Budget.xlsx › Interne.xlsx`) | corrigé en passe 2 (`Restes`, `Jobs`, voir P2 et n° 19) ; pas de remboursement dans ces cas, écrit dans l'étude |
| 6 | Important | `tests/test_incorpores_facturation.py` | tests insuffisants | 6 → 24 tests : chaîne OCR, DOCX et XLSX, archive abîmée, doublons, objet lié, restes, trois jobs de bout en bout | corrigé |
| 7 | Mineur | `translation_runner._signaler_objets` | donnée externe non contrôlée | liste attendue, éléments non dictionnaires écartés | corrigé (`test_rien_si_vide_ou_illisible`) |
| 8 | Mineur | `translation_runner.run_translation_job` | lecture inutile | relevé du rapport seulement hors PDF | corrigé |
| 9 | Mineur | `api/documents.py:675` | vignette absente | le panneau affiche une icône générique quand la vignette est nulle (`DocumentImagesPanel.tsx:66-71`) ; aucun plantage, anciens documents seulement | rejeté (déjà géré) |
| 10 | Mineur | `incorpores.rapport` | signature trompeuse | `Sequence`, docstring précisée | corrigé |
| 11 | Mineur | `incorpores._relever` | libellé vide | `or '?'` | corrigé |
| 12 | Mineur | `translation_runner._signaler_objets` | état sans lecteur | `jobs.set(objets)` retiré. Limite acceptée (option A) : flux coupé pendant l'événement = phrase perdue pour ce job | corrigé |
| 13 | Mineur | `.gitignore` | fichier généré | `*.tsbuildinfo` | corrigé |
| 14 | Mineur | `PASSATION.md`, étude | plan non tenu | étape cochée avec ses trois volets écrits en clair (devis, exclusion OCR, compte rendu client), bilan 6.11.6 écrit avant le séparateur de la section 8 | corrigé |
| 15 | Mineur | étude §5 | renvoi faux | renvoi vers 6.11.7 | corrigé |

## Trouvé pendant les corrections

| N° | Lieu | Classe | Correction | Statut |
|----|------|--------|------------|--------|
| 16 | `engines/pptx/engine.py` `_a_des_objets` | correctif trop large | le premier correctif du n° 1 cherchait `/package`, présent dans l'espace de noms de TOUT fichier de relations : le test « bon marché » ne filtrait plus rien. Motif resserré sur le type de relation | corrigé (test d'échec avant correctif) |
| 17 | `frontend/src/locales/en/translation.json` | clé manquante | `apercus` et `sans_nom` ajoutées en anglais (`check-i18n` les signalait) | corrigé |
| 18 | `incorpores._reinjecter` | risque de double signalement | vérifié : un objet non convertible à l'extraction n'a aucun élément, donc aucune traduction, et sort avant le `try` ; il n'est pas signalé deux fois. Aucun changement | rejeté (pas d'écart) |
| 19 | `incorpores._sous_extraction` en réinjection | panne passagère non signalée | si l'objet interne se lit à l'extraction mais plus à la relecture du parent, ses traductions sont ignorées avec un simple journal. Même fichier, même conversion en cache : la contre-revue a montré un autre chemin (budget, N2) : signalé désormais `reinjection` | corrigé en passe 2 (`test_objet_illisible_a_la_reinjection`, `test_traduction_sans_element_a_la_relecture`) |

## Passe 2 — contre-revue

Verdict : non conforme, sans bloquant. N° 1, 3, 4, 6, 7, 8, 10 à 13, 15 à 18 confirmés clos ; n° 2, 9, 14 corrigés en libellé ; n° 5 et 19 non clos, corrigés ci-dessous. Plafond de deux passes atteint : ces corrections n'ont pas eu de troisième revue, elles sont prouvées par les tests et la relecture du diff.

| N° | Gravité | Lieu | Classe | Correction | Statut |
|----|---------|------|--------|------------|--------|
| N1 | Important | `engines/pptx/engine.py`, `translation_runner` | objet non traité non signalé | `objets_hors_diapositives` : en PPTX progressif, objets des masques, dispositions et notes signalés (`hors_diapo` ou leur raison propre) | corrigé (`HorsDiapositives`, `Jobs`) |
| N2 | Important | `incorpores._reinjecter` | budget compté deux fois | relecture sous une copie du budget restant (`_relire`) : seule la remise en place décompte | corrigé (`BudgetReinjection`). Plafond réel de 512 Mio non essayé : le test emploie le budget exact consommé, plus strict |
| N3 | Mineur | `translation_runner` PPTX progressif | signalement trop tôt | relevé émis après la cohérence, qui réinjecte aussi | corrigé (relu, pas de test d'ordre) |
| N4 | Important | `incorpores._ratio`, `_ratio_ancre` | valeur forgée non contrôlée | valeurs non finies et entiers démesurés écartés : `/api/translate/analyse` répondait 500 | corrigé (`FichiersForges`) |
| N5 | Important | `incorpores._ratio_ancre` | boucle non bornée | colonnes et lignes bornées à la taille d'une feuille Excel, y compris le total des `col` | corrigé (`FichiersForges`) |
| N6 | Mineur | `incorpores.rapport` | doublon affiché | dédoublonnage sur le nom affiché et la raison | corrigé (`RapportDoublons`) |
| N7 | Mineur | `translation_runner` | `objets` vide | cas normal ; une source illisible fait déjà échouer l'injection de l'hôte | rejeté (pas d'écart) |
| N8 | Mineur | `incorpores.reinjecter` | docstring fausse | réécrite : un objet sans changement n'est pas signalé | corrigé |
| N9 | Mineur | `incorpores.py` | commentaire déplacé | « Plafonds » de nouveau avec `ENTREES_MAX` | corrigé |
| N10 | Mineur | `tests/test_incorpores_facturation.py` | tests insuffisants | parcours non progressifs XLSX et PPTX ajoutés | corrigé |
| N11 | Mineur | `engines/pptx/engine.py` `_a_des_objets` | `p:oleObj` sans relation | fichier cassé sans données, rare ; lire chaque diapositive annulerait le filtre bon marché | rejeté (coût sans gain) |
| N12 | Mineur | `services/images_document.py` | casse des noms | comparaison sans casse. Une image partagée entre un objet et une diapositive reste exclue, comme accepté à la conception | corrigé (`test_casse_differente_entre_relation_et_archive`) |
| N13 | Mineur | `incorpores._reinjecter` | double signalement | les restes de l'objet interne ne remontent qu'après la remise en place du parent | corrigé (`test_parent_perdu_seul_signale`) |
| N14 | Mineur | `translation_runner` | arrêt avant le signalement | vérifié : l'arrêt remplace la notice, rien n'est livré, et la reprise réémet le relevé | rejeté (pas d'écart) |

Non vérifié : la phrase dans un navigateur, la suite complète du backend.
