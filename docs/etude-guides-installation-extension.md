# Étude — installation directe sur les 5 navigateurs (06/11/2026)

## Besoin
Rendre l'extension disponible sur /extension pour chaque navigateur déjà compatible, avec un guide par navigateur (captures quand possible).

## Existant
- Une seule extension MV3 (Chromium ≥ 120) : Chrome, Edge, Brave, Opera, Vivaldi.
- Aucune boutique publiée (`VITE_EXTENSION_URL_*` vides) → bouton « Bientôt disponible » désactivé.
- ZIP servi à `/extension/precis-extension.zip` (`EXTENSION_ZIP`), clés `extension_page.manual.*` déjà traduites mais inutilisées.

## Options
| Option | Pour | Contre |
|---|---|---|
| Attendre les boutiques | Mises à jour auto | Bloquant (comptes éditeur) |
| ZIP + guide par navigateur (retenu) | Disponible tout de suite, sans compte | Mises à jour manuelles, mode développeur |

## Choix
Sans adresse de boutique : bouton « Télécharger pour {navigateur} » (ZIP) et guide en 5 étapes propre au navigateur (adresse `xxx://extensions` à copier, libellés, captures réelles Chrome et Edge dans `frontend/public/guides/`). Dès qu'une adresse de boutique est renseignée, la fiche repasse au parcours boutique en un clic.

## Impacts / risques
- i18n : ajouts dans `extension_page` (FR/EN). Images webp ~110 Ko, chargement différé.
- Brave, Opera, Vivaldi non installés ici : guide texte sans capture. Libellés d'Opera variables selon la langue.
- Remplace la consigne 6.12.9 « aucune mention du ZIP » tant qu'aucune boutique n'existe.
