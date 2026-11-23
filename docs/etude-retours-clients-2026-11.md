# Étude — retours clients du 16/11/2026 (Francko) + aperçu admin

Vérifié sur `origin/main` (2b6e380).

## Problèmes, par gravité

| # | Problème | Présent dans main ? | Preuve | Solution existante ? |
|---|----------|--------------------|--------|----------------------|
| 1 | Le client croit être obligé de payer un an pour Starter : « Annuel » est présélectionné et la bascule Mensuel/Annuel est peu visible | Oui | `frontend/src/pages/Home.tsx:36` → `useState(true)` (annuel par défaut) ; bascule `PlanToggle` à droite du titre, `PricingSection.tsx:34` | Non |
| 2 | Le bouton du hero « Voir comment ça marche » mène à la section Avantages | Oui | `frontend/src/components/hero/HeroSection.tsx:272` → `href="#features"` (section `FeaturesGrid`, id `features`) ; le lien du menu, lui, vise `#story` (`AppBar.tsx:74`), d'où la différence constatée | Non |
| 3 | Les tarifs sont trop bas sur la page | Oui | `Home.tsx` : Hero → Avantages → Démonstration (`StorySection`) → … → Tarifs (l. 909), juste avant « À propos » | Non (piste évoquée : le bouton du hero pointe vers les tarifs) |
| 4 | Traduction automatique consommée sur la bêta | Comportement voulu, à confirmer | `backend/app/api/translate.py:267` `use_beta="auto"` ; case « utiliser les crédits bêta » cochée par défaut (`TranslationSection.tsx:87`) | Oui : la case permet de choisir le forfait habituel |
| 5 | « Il y a un plan gratuit ? » | Oui, il existe | `translate.py:544` `free_pages_remaining` (5 pages/mois) | Rien à corriger ; peut-être à rendre plus visible |

## Amélioration admin : aperçu + copie de travail

Existant (`backend/app/api/admin_documents.py`) : l'admin peut seulement **télécharger** l'original et la traduction (l. 110 et 126). Aucun aperçu, aucune modification.

Côté utilisateur, les seules « modifications » possibles sont : images (`PATCH /documents/{id}/images`) et pages illisibles (`PATCH /documents/{id}/pages-illisibles`). Il n'existe **pas** d'édition du texte traduit.

À construire :
- aperçu en lecture seule dans l'admin, avec la même visionneuse que l'utilisateur ;
- bouton « Créer ma copie » : duplique original + traduction dans un nouveau document appartenant à l'admin ; toute modification se fait sur cette copie, jamais sur celle de l'utilisateur.

Point à trancher : ce que « modifier » couvre (images / pages illisibles uniquement, ou édition du texte traduit, qui n'existe pas encore).

**Choix validé : A** — aperçu en lecture seule + « Créer ma copie » ; sur la copie, retouche des images et des pages illisibles seulement. Pas d'édition du texte.

### Étude de la copie de travail (16/11/2026)

**Existant réutilisable**
- Les fichiers sont rangés dans un magasin partagé : plusieurs documents peuvent viser le même original et la même traduction. La suppression compte déjà les références (`documents.py:174`, `_racine_orpheline`) : un fichier ne part que si plus aucun document ne le vise.
- Toute retouche (image, page illisible) crée déjà une copie propre au document avant d'écrire (`services/documents.py:312`, `copie_du_document`, chemin marqué `_d<id>`). La traduction d'un autre document n'est jamais touchée.
- Rendu de la traduction pour l'admin : `_render_or_404`, déjà utilisé par le téléchargement admin (`admin_documents.py:126`). Source convertie en PDF : même logique que `/documents/{id}/original?as=pdf`.
- Visionneuse : `components/preview/PdfViewer.tsx` (pdf.js, reçoit un fichier).

**Options comparées**

| Option | Pour | Contre |
|---|---|---|
| 1. Copier physiquement tous les fichiers dans un nouveau dossier | Copie totalement indépendante | Double l'espace disque ; réécrit la logique des chemins ; rien de neuf n'en dépend |
| 2. Nouvelle fiche document de l'admin qui vise les mêmes fichiers, avec photo immédiate de la traduction (`copie_du_document` appelé à la création) | Quelques lignes ; aucun fichier dupliqué sauf la traduction (JSON + images, léger) ; les retouches existantes marchent telles quelles ; le document du client reste intact | La copie garde le fichier original du client tant qu'elle existe (voir point à trancher) |

**Retenu : option 2.**
- `POST /api/admin/documents/{id}/copie` : crée un document appartenant à l'admin (même nom, langues, réglages, pages), `storage_charged = 0`, `paid = vrai`, colonne nouvelle `copie_de` = id du document client. Refusé si la traduction n'est pas terminée ou si un fichier manque. Si l'admin a déjà une copie de ce document, elle est renvoyée au lieu d'en créer une autre.
- `GET /api/admin/documents/{id}/apercu` (traduction rendue en PDF) et `GET /api/admin/documents/{id}/original?as=pdf` : lecture seule, journalisée comme les téléchargements.
- Écran admin : bouton « Aperçu » par ligne → fenêtre original | traduction côte à côte (`PdfViewer`), bouton « Créer ma copie » → la copie apparaît dans la bibliothèque de l'admin, où les outils habituels (images, pages illisibles) s'appliquent.

**Impacts**
- Données : une migration Alembic (colonne `copie_de`, nullable, indexée).
- Quotas : rien débité à l'admin (`storage_charged = 0`). Une page illisible relancée en « traduire » sur la copie passe par le contrôle habituel des pages de l'admin.
- Sécurité : routes protégées par `require_admin` ; chaque aperçu et chaque copie journalisés (qui, quel document, de qui).
- i18n : libellés FR/EN de l'écran admin.

**Risques**
- Le client modifie ensuite son document : sans effet sur la copie (photo prise à la création).
- Rendu long sur un gros document : l'aperçu admin utilise le même cache de rendu que le client.

**Point à trancher**
- Quand le client supprime son document, que devient la copie de l'admin ? (a) supprimée avec lui — recommandé : la suppression demandée par le client est respectée, aucun fichier du client ne survit ; (b) conservée jusqu'à ce que l'admin la supprime.

**Décision (16/11/2026) : (b).** L'accès admin sert au contrôle qualité et à l'amélioration de l'outil, ce que prévoient les conditions générales. Quand le client supprime son document, seule sa fiche disparaît : la copie de l'admin et les fichiers qu'elle vise restent, pour garder les retouches et les analyses déjà faites. Le comptage des références protège déjà ces fichiers (`_racine_orpheline`) ; aucune suppression en cascade.
