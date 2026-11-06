# Étude — aperçu d'un document dont les fichiers ont disparu

## Besoin
Ouvert depuis la bibliothèque, un document déjà traduit restait figé sur
« Cette page est en attente de traduction », avec un original blanc. Le
message était faux (rien n'était en cours) et les cadres n'avaient pas le
format du document (portrait pour une présentation).

## Cause
Les fichiers du magasin `backend/translations` avaient été effacés par le
ménage de démarrage (`balayer_au_demarrage`) lancé par une suite de tests
branchée sur la base de test (port 5433) : cette base ne cite aucun document
du poste, donc toutes les racines du magasin partagé passaient pour orphelines.
`/preview` et `/original` répondaient alors 404, que l'interface prenait pour
« pas encore prêt ».

## Existant
- `app/services/stockage.py` : `balayer_magasin` (pur), `balayer_au_demarrage`.
- `app/config.py` : `TRANSLATIONS_DIR` figé sur `backend/translations`.
- Front : `PdfViewer` mesure les cadres sur le PDF ; sans PDF, aucun format.

## Options
| Option | Pour | Contre |
|---|---|---|
| A. Marque `.base` dans le magasin (identité de la base, sans mot de passe) ; balayage refusé si elle diffère | Protège tout lanceur, même oublié ; aucune migration | Changer volontairement de base demande de supprimer `.base` |
| B. Couper le balayage quand `TESTING` est posé | Simple | Dépend de chaque lanceur de tests |
| C. Magasin séparé pour les tests seulement | Isolement propre | Même dépendance que B |

Choix : **A**, plus `TRANSLATIONS_DIR` surchargeable par variable (complète C).

## Interface
- 404 sur l'aperçu → état « manquant » : arrêt du suivi, message dédié
  (`preview.translation_missing` ou `preview.file_missing` si l'original manque aussi).
- Cadres dimensionnés d'après l'extension (16:9 pour pptx/ppt/odp/key, A4 sinon)
  quand aucun PDF n'est disponible.

## Impacts / risques
- Aucune donnée ni migration. Les 15 documents effacés sont irrécupérables :
  à redéposer.
- i18n : 2 clés fr/en.
