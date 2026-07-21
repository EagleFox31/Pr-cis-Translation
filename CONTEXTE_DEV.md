# Contexte de développement — Précis Translator

> Document généré le 2026-07-20. Résume l'état du projet, les branches actives
> et les modifications en cours pour permettre à quiconque de reprendre le
> développement.

---

## État des branches

```
main                       ← base stable (6f9333c)
feat/tarification-paiement ← tarifs, paiement Campay, verrous (fusionné en amont)
feat/erreurs-sexy          ← BRANCHE ACTIVE : messages d'erreur + UI PPTX
fix/scroll-snap-and-review ← correctif CSS footer + PROMPT_FABLE.md (9488394)
```

### feat/erreurs-sexy (HEAD)

Branche de travail principale. Contient :

| Domaine | Détail |
|---------|--------|
| **Messages d'erreur** | Nettoyage de tous les leaks d'exception Python, messages 402 clairs, variables internes remplacées par du français |
| **Affichage inline** | Remplacement des toasts fugaces par des bannières rouges persistantes dans StorySection |
| **Bibliothèque** | Bannière erreur + bouton Réessayer pour les documents en échec |
| **Progressive PPTX** | Traduction slide par slide avec SSE, aperçu progressif, conversion asynchrone LibreOffice |
| **UI PPTX** | Bouton Aperçu pour tous formats, layout vertical automatique pour paysage, favicon SVG |
| **Réseau local** | Vite `host: true`, uvicorn `--host 0.0.0.0`, pré-chauffage LibreOffice |
| **Correctifs** | `FileResponse` → `Response` (fix 206), écriture atomique, `_sync_document_progress` |

### fix/scroll-snap-and-review

Contient uniquement le fix CSS `scroll-margin-top: 0` pour le footer + PROMPT_FABLE.md (prompt de relecture pour une autre branche).

---

## Modifications non commitées (working tree)

22 fichiers modifiés (~1069 insertions, ~881 suppressions) :

| Fichier | Nature |
|---------|--------|
| `backend/app.py` | +225 lignes : `_run_pptx_progressive_job`, routage PPTX, pré-chauffage LibreOffice, `_sync_document_progress` |
| `backend/pptx_translator_engine.py` | +631 lignes : extraction/injection OLE Excel, charts, layouts, masters, `_extract_zip`/`_repack_zip`, méthodes progressives slide par slide, auto-refresh COM |
| `backend/render_cache.py` | Ajustement mineur |
| `backend/requirements.txt` | +`python-pptx>=0.6.21` |
| `backend/routes/documents.py` | `FileResponse` → `Response` pour `/original`, fix 206 |
| `backend/translator_ai.py` | Ajustement mineur |
| `frontend/index.html` | +favicon SVG avec fond blanc |
| `frontend/package.json` | Suppression `--logLevel error` |
| `frontend/vite.config.ts` | +`host: true` |
| `scripts/run_uvicorn.py` | +`--host 0.0.0.0` |
| `DocumentLibrary.tsx` | Bouton Aperçu tous formats, bannière erreur + retry |
| `DocumentPreview.tsx` | Prop `translatedExt`, `previewLoading` |
| `PdfViewer.tsx` | Détection paysage/portrait par page, layout vertical/horizontal |
| `StorySection.tsx` | `translatedExt`, `previewLoading`, bannière erreur inline |
| `FileUploader.tsx` | PPTX dans `accept` + validation JS |
| `usePdfPreview.ts` | Paramètre `translatedExt` |
| `useStreamingTranslation.ts` | i18n, détection 402, `limitReached` |
| `Home.tsx` | `handleRetry`, scroll automatique, suppression toast |
| `translation.json` (fr+en) | Nouvelles clés i18n, PPTX dans `proof_formats` et `error_unsupported` |
| `package.json` (racine) | Retrait echo statique |

---

## Correctifs 2026-07-21 (session Fable/Opus)

| Sujet | Correctif | Preuve |
|-------|-----------|--------|
| **PPTX téléchargé corrompu** (« PowerPoint ne peut pas lire … .pptx ») | Le cache de rendu ne contient QUE des PDF (aperçu). `download_document` le servait pour TOUT format → PDF déguisé en .pptx. Désormais le cache n'est lu au téléchargement que pour `ext == "pdf"` ; les autres formats se régénèrent en natif. Caches empoisonnés purgés. | `test_download_format_integrity.py` 3/3 + mutation ; download HTTP starter → `PK`, ZIP valide |
| **`build_partial_pptx` destructif** | Il réécrivait `presentation.xml`/rels/`[Content_Types].xml` DANS le temp dir en retirant les slides > k : un 2ᵉ appel amputait le PPTX final (1 slide au lieu de N). Rendu NON-destructif (contrôle recalculé en mémoire, écrit dans le zip), atomique. | Appels répétés (1,3,5,26) → partiels valides, final 26 slides intact |
| **Preview PPTX progressive** | Un convertisseur de partiel PDF en arrière-plan (coalescé, 1 thread) rend l'avant/après slide par slide comme le PDF v2. `partial_path` (.pdf) complet garanti avant le job-done ; le front redemande le partiel frais sur 402. | E2E HTTP free+starter : progression par slide, partiel PDF, 402 free rastérisé (0 fuite) |
| **Layout viewer** | Suppression du bug de framing (l'`isLandscape` était lu avant que son `setState` prenne effet → 1ʳᵉ frame mal cadrée). Les deux pages sont TOUJOURS côte à côte (horizontal), dimensionnées sans état → cadrage correct dès le départ. | `tsc --noEmit` OK |

## Correctifs 2026-07-21 (session 2 — OLE, layout, serveur)

| Sujet | Correctif | Preuve |
|-------|-----------|--------|
| **Aperçu OLE Excel en langue source** | `regenerate_ole_previews` (moteur PPTX) : rend le xlsx traduit en image via LibreOffice (1 invocation ≈ 20 s), recadre au contenu, remplace l'EMF par un PNG. Câblé dans `inject_translation` (aperçu+download) et le job progressif. Sans Windows/macro. **Piège** : l'image OLE est référencée 2× (VML `mc:Choice` + DrawingML `mc:Fallback`) — repointer TOUTES les rels, pas juste le blip. | Rendu visuel : tableaux+graphiques Excel traduits ; français OLE éliminé du PDF final |
| **Layout viewer paysage** | Restauré en VERTICAL (panneaux empilés) pour les pages paysage, détecté PAR PAGE (orientations mixtes gérées), sans le bug de cadrage (orientation lue en local avant rendu, plus via un state en retard). | `tsc` OK |
| **Start/stop serveur (zombies)** | `scripts/dev.py` remplace `concurrently` : démarre backend puis frontend, sortie concise, et un Ctrl+C tue les DEUX arbres de processus (`taskkill /T`) + balaie les ports. Bonus : le prochain démarrage balaie aussi les ports. | Test cycle de vie : 2 ports up → signal → 2 ports libérés, code 0 |

## Pipeline PPTX — État actuel

### Ce qui fonctionne

- Extraction texte : slides, layouts, masters, SmartArts, graphiques XML, Excel OLE
- Traduction DeepSeek slide par slide avec streaming SSE
- Réinjection dans tous les types d'éléments
- Aperçu progressif (conversion PPTX→PDF asynchrone)
- Téléchargement du PPTX traduit final
- Détection automatique paysage/portrait pour le layout du viewer

### Ce qui est implémenté MAIS commenté/désactivé

Le fichier `backend/pptx_translator_engine.py` contient des fonctionnalités avancées
qui étaient en cours de développement mais qui ne sont **pas encore branchées**
dans le pipeline principal :

1. **`_auto_refresh_powerpoint()`** — Ouvre PowerPoint via COM pour rafraîchir
   les aperçus OLE. Appelée dans `inject_translation()`.
2. **`generate_autorefresh_pptm()`** — Génère un `.pptm` avec macro VBA
   `Presentation_Open` pour rafraîchir les OLE à l'ouverture.
3. **Extraction Excel OLE** (`_process_excel_file`) — Extrait `xl/sharedStrings.xml`
   des fichiers `.xlsx` incorporés.
4. **Réinjection Excel OLE** (`_inject_excel_file`) — Réinjecte les traductions
   dans `xl/sharedStrings.xml`.
5. **Extraction charts** — Étiquettes de graphiques XML.
6. **Extraction slideLayouts** — Sous-titres et masques de disposition.
7. **Extraction slideMasters** — Masques racine.

Ces fonctionnalités nécessitent une intégration et des tests avant activation.

---

## Éléments à consolider

### Décisions produit (fournies par l'utilisateur)

- **Abandonner** : conversion OLE → tableau natif, régénération EMF, macros VBA (`.pptm`)
- **Priorité** : intégrité du document source, pas de corruption, pas d'avertissement Office
- **Comportement accepté** : l'aperçu EMF reste en langue source jusqu'à réouverture dans PowerPoint
- **Message utilisateur** : informer que les données Excel sont traduites mais l'aperçu visuel peut rester en langue d'origine

### Prochaines étapes PPTX

1. Nettoyer le code commenté/non branché dans `pptx_translator_engine.py`
2. Activer l'extraction Excel OLE (déjà codée, juste à brancher)
3. Activer l'extraction charts/layouts/masters
4. Ajouter le rapport de traduction (JSON avec compteurs)
5. Ajouter le message utilisateur dans l'UI (encart informatif)
6. Désactiver `_auto_refresh_powerpoint` et `generate_autorefresh_pptm` (décision produit : pas de COM, pas de VBA)
7. Journalisation technique des OLE détectés

---

## Architecture technique

```
Frontend (Vite :3000)          Backend (uvicorn :8000)
├── PdfViewer                  ├── app.py
│   ├── paysage → vertical     │   ├── _run_pptx_progressive_job
│   └── portrait → horizontal  │   ├── _run_pdf_v2_job
├── DocumentPreview            │   ├── _run_translation_job (DOCX/TXT)
├── StorySection               │   └── convert_to_pdf_bytes (LibreOffice)
├── DocumentLibrary            ├── pptx_translator_engine.py
├── useStreamingTranslation    ├── docx_translator_engine.py
├── usePdfPreview              ├── pdf_engine_v2/
└── useDocumentLibrary         └── translator_ai.py
```

---

## Commandes

```bash
# Démarrer tout (frontend + backend)
npm run dev

# Frontend seul
npm --prefix frontend run dev

# Backend seul
backend\venv\Scripts\python scripts/run_uvicorn.py 8000

# Typecheck
npm --prefix frontend run lint

# Branches
git branch -a
```
