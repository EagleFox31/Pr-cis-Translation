# Revue — limite d'aperçu (retour 3, option A)

Traduire jusqu'à la limite (pages payées + aperçu restant), pause automatique,
reprise le lendemain ou après achat ; une pause manuelle rend les pages
d'aperçu non faites.

## Registre des écarts (passe 1)

| N° | Emplacement | Classe | Correction | Statut |
|----|-------------|--------|------------|--------|
| B1 | `engines/pdf/stream.py` (boucle des pages) ; `services/jobs.py` `sync_status` | Contrôle de limite contourné | Le contrôle du plafond se fait devant toute page de la sélection, avant l'OCR et le cache. Une clôture `done` d'un document plafonné en deçà de sa sélection devient `paused` à la limite. | corrigé (tests `test_a_capped_job_ending_done_stays_paused_at_the_limit`, `PauseAuPlafondTests.test_page_beyond_the_cap_pauses_at_the_limit`) |
| B2 | `services/documents.py` `borner_libres_a_l_arret` | Compte des pages atteintes faux | Les pages atteintes vont jusqu'à la dernière page traduite : une page vide au milieu ne rend plus les suivantes. Un plafond 0 est retiré au lieu d'être écrit, car 0 se lirait « sans plafond ». | corrigé (tests `..._empty_preview_page_...`, `..._keeps_no_zero_cap`) |
| I1 | `api/translate.py` (402 `partial_possible`) | Offre incohérente avec l'état | Pas de traduction partielle sur un document en pause qui a des pages d'aperçu. | corrigé (test `test_no_partial_offer_on_a_paused_document_with_preview_pages`) |
| I2 | `api/translate.py` (validation de `resume_of`) | Reprise sur une autre sélection | La reprise est refusée si la sélection diffère : un nouveau document est créé. | corrigé (test `test_resume_with_another_page_selection_starts_a_new_document`) |
| I3 | `api/documents.py` `_pause_apercu` ; `services/translation_runner.py` ; `services/jobs.py` | État déduit au lieu d'être marqué | La pause à la limite est marquée sur le job (`pause_limite`) puis dans les réglages. La carte « limite d'aperçu » ne s'affiche que pour elle. | corrigé (tests `test_launch_up_to_the_limit_then_pause`, `test_a_manual_pause_of_a_capped_document_is_not_shown_as_the_limit`) |
| M1 | `api/translate.py` (heure de reprise du 402) | Valeur hors borne | L'heure se calcule sur au plus `LIBRE_MAX_PAGES` pages : pour un document de plus de 20 pages, elle dit quand la tranche suivante est libre (option A, traduction par tranches). Pas d'heure seulement s'il n'existe aucune attribution. | corrigé (test `test_document_larger_than_the_cap_gets_the_next_slice_time`) |
| D1 | `api/translate.py` `avance` | Indice d'affichage | Comparé au cache partagé, `avance` peut proposer une pause qui n'avancerait pas. Effet d'affichage seulement, et rare. | différé (passation) |
| D2 | `services/anti_abus.py` (LibreGrant) | Compteur non rendu | Les pages d'aperçu payées après un achat restent comptées dans les 24 h. Cela pénalise l'utilisateur sans créer de fuite. | différé (passation) |
| D3 | `services/documents.py:300-302` | Robustesse | `hors_libres` est ignoré. Fragile, mais sans effet aujourd'hui. | différé (passation) |
| R1 | réponse 402 | Information au client | Le 402 renvoie `pages_missing` et, pour l'aperçu, `libre_used`, `libre_max`, `libre_needed`, `libre_reprise`, `pause_possible` : que des compteurs du compte, aucune donnée d'un autre utilisateur. | rejeté (conforme) |

## Registre des écarts (passe 2, contre-revue)

| N° | Emplacement | Classe | Correction | Statut |
|----|-------------|--------|------------|--------|
| N1 | `api/documents.py` `_traduction` | Aperçu incomplet | L'aperçu d'un document en pause montre aussi ses pages d'aperçu (filigranées) ; le téléchargement reste limité aux pages payées. | corrigé (test `test_preview_of_a_paused_document_shows_its_preview_pages`) |
| N2 | `api/translate.py` (heure du 402) | Décision contredite | M1 gardé, commentaires et tests alignés (voir M1). | corrigé |
| N3 | `services/translation_runner.py` `avant_page` | Pause manuelle lue comme limite | Une pause manuelle déjà demandée prime : la page suivante n'est pas marquée « limite ». | corrigé (test `PauseAuPlafondTests.test_manual_pause_already_requested_is_not_the_limit`) |
| N4 | `services/jobs.py` garde-fou | Faux « en pause » | Les pages que l'utilisateur a laissées vides ne comptent pas comme restant à traduire. | corrigé (test `test_capped_job_done_with_only_empty_pages_left_stays_done`) |
| I2 bis | test de reprise | Test sans preuve | Le cache de l'autre sélection est prérempli avant la reprise. | corrigé (test renforcé) |

## Vérifications

- Backend : traduction_libre 37/37, arret_job 42/42, reprise_reglages 18/18,
  documents_purge 19/19, anti_abus 29, reprise_lots 7/7, beta_* OK,
  admin_documents OK, documents_scannes OK, proposition_images 8/8.
- Front : tsc, lint et build OK.
