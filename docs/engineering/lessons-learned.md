# Lessons learned

Mémoire des incidents et quasi-incidents. Consulter avant de toucher une zone citée.

## 2026-11-07 — Aucune compression HTTP en production

- **Contexte** : audit SEO du site public. HTML, CSS et JS (~800 Ko) servis sans compression, même avec `Accept-Encoding: gzip`.
- **Cause racine** : nginx tourne derrière Caddy, qui ajoute `Via: 1.1 Caddy`. Sans `gzip_proxied`, nginx ne compresse pas une réponse à une requête relayée. Le test CI interrogeait nginx directement, sans `Via`, donc ne pouvait pas le voir.
- **Classification** : configuration, écart entre l'environnement de test et la production.
- **Résolution** : `gzip_proxied any; gzip_vary on;` et types étendus dans `frontend/nginx.conf`.
- **Prévention vérifiable** : `scripts/ci/verify_public_seo.py` envoie `Via: 1.1 Caddy` et exige `Content-Encoding: gzip` (CI locale et vérification de production).
- **Leçon** : un contrôle d'infrastructure doit reproduire les en-têtes ajoutés par chaque relais présent en production.

## 2026-11-07 — Pages publiques invisibles des moteurs

- **Contexte** : `/extension` et les pages légales renvoyaient 404 au chargement direct, et toutes les routes partageaient le même `<head>` (canonical vers `/home`). Sitemap limité à `/home`.
- **Cause racine** : application monopage sans prérendu ; nginx ne connaissait qu'une liste figée de routes ; sitemap écrit à la main.
- **Résolution** : `frontend/seo/site.json` est la source unique des pages publiques. `scripts/prerender.mjs` génère au build une page HTML par route, `sitemap.xml` et `llms.txt`. nginx sert `$uri.html`.
- **Prévention vérifiable** : le contrôle SEO lit `site.json` et vérifie pour chaque page 200, canonical propre, un seul `h1`, JSON-LD `WebPage`, maillage interne, présence au sitemap et dans `llms.txt`.
- **Leçon** : toute nouvelle page publique s'ajoute dans `site.json`, jamais directement dans nginx ou le sitemap.

## 2026-11-07 — Affirmations publiques sans source vérifiée

- **Contexte** : rédaction des pages `/tarifs`, `/comparatif` et `/confidentialite-documents`. Deux quasi-incidents : un premier jet annonçait le Mobile Money dans toutes les zones (il n'existe qu'en zone A), et le comparatif de la landing (`comparison.row_data_precis` : « Supprimées sous 24h ») contredit la politique de confidentialité (documents gardés jusqu'à suppression, fichiers temporaires 7 jours).
- **Cause racine** : textes marketing écrits de mémoire, sans lien avec les constantes du backend ni avec la politique publiée.
- **Classification** : contenu, divergence silencieuse entre promesse publique et comportement réel.
- **Résolution** : prix, quotas, stockage, taille maximale, formats et mots par page des pages de contenu sont vérifiés contre `backend/app/core/pricing.py`, `models/plans.py`, `config.py` et `services/documents.py`. Le texte de la landing reste à corriger (décision produit/juridique).
- **Prévention vérifiable** : `scripts/ci/verify_public_seo.py` échoue si `frontend/seo/pages/tarifs.json` ou une limite citée diverge du backend (test de mutation : une page à 0,18 € fait échouer le contrôle). Chaque page de contenu porte une date `verified`, et le comparatif cite ses sources.
- **Leçon** : toute valeur chiffrée affichée publiquement doit avoir une source de vérité dans le code ou une source externe datée, et un contrôle qui casse quand elle change.

## 2026-11-07 — Issues créées en rafale absentes du board

- **Contexte** : création de 5 issues P2 (#60 à #64) en quelques secondes. Seules #60 et #64 sont arrivées sur le board « Précis Translator Development ».
- **Cause racine** : le workflow réutilisable `appfactory-project-automation` (SHA 14d51168) utilise un groupe de concurrence par dépôt (`project-automation-<repo>`, `cancel-in-progress: false`). GitHub ne garde qu'un seul run en attente par groupe : chaque nouvel événement annule le run en attente précédent, donc les événements intermédiaires d'une rafale sont perdus.
- **Classification** : automatisation, perte silencieuse d'événements (runs « cancelled », aucun échec visible).
- **Résolution** : resynchronisation une par une via `workflow_dispatch` (`issue_number`), en attendant la fin de chaque run. Vérifié par GraphQL : les 5 issues sont sur le board avec Priority, Work type, Phase et Size.
- **Prévention vérifiable** : après une création en lot, vérifier `projectItems` de chaque issue (pas seulement le statut des runs) ; correctif durable à porter dans le dépôt partagé (groupe de concurrence par issue/PR, ou bootstrap qui réconcilie toutes les issues ouvertes).
- **Leçon** : un run « cancelled » par concurrence n'est pas un no-op ; une synchronisation pilotée par événements doit avoir une réconciliation périodique ou par lot.
