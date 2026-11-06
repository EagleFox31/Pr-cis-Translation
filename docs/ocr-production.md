# OCR des PDF scannés

Les pages sélectionnées sans texte extractible sont lues une par une **pendant
la traduction**, plus dans la requête d'envoi. Tesseract tourne localement
(français, anglais, orientation). Les pages numériques et les pages hors
sélection sont conservées. **Pas encore ouvert au public** : voir
`docs/bilan-ocr-deploiement.md`.

## File d'attente

- Les scans passent dans un ordonnanceur à part (`OCR_SCAN_WORKERS`, 3 par
  défaut) : leur attente n'occupe jamais les workers des documents à texte.
- Un guichet unique (`services/ocr_file.py`) ne laisse lire qu'une page à la
  fois, par priorité du plan ; un ticket qui attend plus de
  `OCR_FILE_ANTI_FAMINE_S` (300 s) passe devant. Pause et annulation agissent
  aussi dans la file.
- Chaque page a son délai de lecture (`OCR_DELAI_PAGE_S`, 90 s), compté une
  fois le tour obtenu. Les images de l'extension attendent au plus 120 s,
  puis reçoivent 503 « Réessayez ».
- Plus de plafond de 10 pages par envoi : restent la limite du forfait et la
  taille d'envoi.

## Pages non lues

- **Page blanche** : gardée telle quelle, non facturée, sans question.
- **Page illisible** (ou solde épuisé pendant la lecture) : l'original est
  affiché par défaut, et la page est remboursée à la fin du travail (crédits
  achetés d'abord, une seule fois). Le panneau sous l'aperçu propose pour
  chaque page, ou pour toutes : traduire quand même, afficher l'original,
  laisser vide (`GET`/`PATCH /api/documents/{id}/pages-illisibles`).
- **Traduire quand même** relit la page en mode permissif ; 1 page est
  débitée seulement si du texte est lu. Sans couverture : 402, rien n'est
  lancé.
- Texte imprimé français et anglais ; pas de manuscrit. Polices et
  composition approximatives ; un tampon ou une signature sur le texte peut
  être affecté. Ne pas présenter le résultat comme une copie certifiée.

## Persistance et reprise

L'original déposé reste intact. Chaque page lue est enregistrée dans
`<traduction>.ocr/` (`p0012.json` statut et motif, `p0012.pdf` si lue,
`choix.json`) : une reprise ne relit rien. `<traduction>.json.source.pdf` est
reconstruit à la demande si ce dossier est plus récent. Le suffixe `ocrv3`
sépare ces caches des précédents ; les anciens documents rouvrent normalement.
Un choix sur une traduction partagée crée une copie propre au document
(`…_d<id>`). La purge suit celle du JSON.

## Vérification

- `test_ocr.py` et `test_ocr_v2_*` (Docker, vrai Tesseract) ;
  `scripts/verify_ocr_runtime.py` (lecture réelle + traduction d'un document
  fictif ; clé de traduction requise).
- `test_ocr_file.py` (guichet), `test_ocr_pages.py`, `test_ocr_moteur_pages.py`,
  `test_ocr_facturation_pages.py` (remboursements), `test_ocr_pages_choix.py`
  (routes de choix), `test_ocr_endpoint.py`, `test_documents_scannes.py`.
