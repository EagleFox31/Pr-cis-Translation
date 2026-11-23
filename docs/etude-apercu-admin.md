# Étude : aperçu admin lent et Journal muet (R5)

## Besoin

Quand un administrateur ouvre l'aperçu d'un gros document appartenant à un autre compte, l'attente dure plus d'une minute. Pendant ce temps, rien ne permet de récupérer le fichier d'origine. Côté Journal, aucune trace n'apparaît : ni les appels qui échouent, ni les messages d'erreur montrés à l'écran, ni la lenteur elle-même.

Les correctifs doivent valoir pour tous les formats (PDF, Word, PowerPoint) et ne dégrader aucun d'entre eux.

## Reproduction locale

On a reproduit le cas avec trois documents rangés dans le compte non admin `demo-gratuit`. Chacun est ouvert depuis `/admin/documents` avec le bouton « Aperçu ». Le test passe par un navigateur piloté, avec les caches vidés avant chaque mesure.

- **PowerPoint** : 75 diapositives, 82 Mo.
- **Word** : 40 pages, 26 Mo.
- **PDF** : 2 pages.

## État de l'existant : causes trouvées

1. **L'original était converti plusieurs fois.** L'effet qui ouvre l'aperçu se relançait à chaque re-rendu, avec 5 à 7 appels à `source-pdf`. Côté serveur, ces appels simultanés lançaient chacun une conversion LibreOffice complète, l'une après l'autre. Le cache ne servait qu'une fois la première conversion terminée.
2. **L'aperçu traduit était demandé deux fois.** La même relance provoquait un second rendu complet de la traduction.
3. **Pas de bouton « Télécharger l'original ».** Il n'était proposé que pour un fichier ouvert par l'utilisateur lui-même, jamais pour un document consulté en tant qu'admin.
4. **La copie admin restait introuvable.** Le message « Copie créée » ne permettait pas de l'ouvrir.
5. **Le Journal restait muet.** `authFetch` ne signalait ni les pannes réseau ni les erreurs 5xx. Les messages d'erreur affichés à l'écran n'étaient pas enregistrés, et la lenteur ne l'était pas non plus.

## Options

| Point | Option retenue | Écartée | Pourquoi |
|---|---|---|---|
| Conversions répétées | Un verrou par fichier dans `convert_to_pdf_bytes` : la 2e demande attend la 1re puis lit le cache. S'y ajoute un garde côté écran qui ne traite qu'une fois chaque demande d'ouverture. | Garde côté écran seul | Deux onglets ou deux admins relanceraient encore la conversion. Le verrou protège tous les appelants. |
| Aperçu demandé deux fois | Une seule demande en vol par document (`apercuEnVol`) | Annuler la requête au démontage | L'annulation n'arrête pas le rendu déjà lancé côté serveur. |
| Bouton original | Affiché dès qu'un document admin est ouvert | — | Il réutilise la route de téléchargement admin existante. |
| Copie | Action « Ouvrir ma copie » dans le message, qui ouvre la copie dans la bibliothèque | Redirection automatique | L'admin peut vouloir rester sur l'aperçu. |
| Journal | Signalement par `reportClientError`, déjà limité à un envoi par 10 s et par message | Nouvelle route | La route `/api/logs/client` existe déjà. |

## Changements

- `backend/app/services/office.py` : un verrou par fichier, une seconde lecture du cache sous verrou, et une écriture atomique (`.tmp` puis `os.replace`).
- `frontend/src/pages/Home.tsx` :
  - chaque demande d'ouverture n'est traitée qu'une fois, et une seule demande d'aperçu admin est en vol par document ;
  - le bouton original est affiché pour un document admin ;
  - le message de copie porte l'action « Ouvrir ma copie » ;
  - un avertissement « Aperçu lent » est envoyé au Journal au-delà de 15 s.
- `frontend/src/services/api.ts` : les pannes réseau et les réponses 5xx sont signalées au Journal. Une annulation volontaire ne l'est pas.
- `frontend/src/components/ui/Toast.tsx` : chaque message d'erreur affiché est aussi signalé au Journal.
- `backend/tests/test_conversion_unique.py` : 7 contrôles. Il échoue sans le correctif, avec 3 conversions au lieu d'une.

## Mesures avant / après

Mesures en développement, avec React StrictMode et les caches vidés.

| Document | Appels à l'original | Appels à l'aperçu | Aperçu affiché | Bouton original |
|---|---|---|---|---|
| PowerPoint, avant | 5 | 2 | 66,5 s | jamais |
| PowerPoint, après | **1** | **1** | 56 s | **1,4 s** |
| Word, avant | 5 | 2 | 126 s | jamais |
| Word, après | **1** | **1** | **23,9 s** | **1,4 s** |
| PDF, avant | 7 | 2 | 1,7 s | 3,0 s |
| PDF, après | **1** | **1** | 1,4 s | **1,4 s** |

Les 56 s qui restent sur le PowerPoint viennent de deux conversions LibreOffice successives, l'original puis la traduction. LibreOffice ne traite qu'un document à la fois sur le serveur. Il n'y a plus aucun travail en double.

Les entrées suivantes ont été vérifiées dans le Journal, à partir des envois relevés vers `/api/logs/client` :

- `Aperçu lent : N s` (avertissement) ;
- `API 500 : GET …/apercu` (réponse 500 forcée) ;
- `Réseau échoué : GET …/source-pdf` (panne réseau simulée) ;
- `Message d'erreur affiché : La copie n'a pas pu être créée. — …` (refus forcé).

## Impacts

- **Données et migrations** : aucun impact.
- **Sécurité** : aucun impact. Les messages envoyés au Journal contiennent un chemin d'API et un identifiant de document, jamais de contenu.
- **Performance** : le travail de conversion est divisé par 5 à 7 sur l'ouverture d'un aperçu admin.
- **i18n** : une clé ajoutée en français et en anglais, `admin_docs.copy_open`.

## Risques

- Un verrou par fichier pourrait rester en mémoire. Il est retiré dès que plus personne ne l'attend, ce que le test vérifie.
- Le Journal pourrait être inondé. Ce risque est couvert par la limite existante d'un envoi par 10 s pour un même message.
