# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Particuliers et professionnels qui doivent traduire un document (PDF, Word, PowerPoint, Excel, texte) et le rendre tel quel, sans refaire la mise en page. *Hypothèse : profils déduits des pages SEO et du README, non confirmés par une étude d'usage.*
- Utilisateurs de l'extension navigateur, qui traduisent des pages web et relient l'extension à leur compte depuis le site.
- Proches invités par un utilisateur (e-mail d'invitation).
- Testeurs du programme bêta.

## Product Purpose

Précis Translator traduit un fichier en gardant sa structure : extraction du texte avec sa géométrie et ses styles, traduction, puis réinjection dans les conteneurs du document. Le succès, c'est un fichier traduit qui reste un document utilisable. L'approche ne garantit pas l'identité au pixel près (README, « Promesse produit »).

## Positioning

La fidélité structurelle du document, et non la traduction de texte brut. Précis est édité par Trigenys, un collectif d'indépendants.

## Operating Context

- Interface en français et en anglais (locales `fr` et `en`).
- Compte par e-mail avec code de connexion ; bibliothèque de documents dans un tiroir de compte ; quotas de traduction et de stockage affichés.
- Aperçu avant téléchargement et visionneuse côte à côte (original et traduction).
- E-mails transactionnels sur une carte commune (vérification, invitation, alertes), envoyés depuis le backend.

## Capabilities and Constraints

- Formats : PDF numérique, DOCX, PPTX, XLSX, texte. Maturité déclarée : bêta (README).
- 23 langues, 36 variantes (`backend/app/core/email_content.py`).
- Word : 100 Mo au maximum ; PowerPoint : une diapositive compte pour une page ; Excel : comptage en mots (pages SEO).
- Essai : cinq pages de document utilisables par mois (CHANGELOG 1.6.0).
- PDF scannés : l'OCR est implémenté mais **pas ouvert au public** (README, « Limites et transparence »). Ne pas le présenter comme livré.
- Nouveautés (en cours de conception, `docs/etude-nouveautes.md`) : page `/nouveautes`, fenêtre d'accueil montrée une fois aux comptes existants, fenêtre « Depuis votre dernière visite », un seul interrupteur d'abonnement, envoi manuel d'un e-mail par version, contenu rédigé à partir du CHANGELOG et du code.

## Brand Commitments

- Nom : Précis (logo hibou, mot-symbole « récis » en Pinyon Script). Éditeur : Trigenys, collectif d'indépendants.
- Ton sobre et vérifiable : aucune affirmation inventée, aucun chiffre sans source dans le code ou le README.
- Ne jamais mentionner la ville ni le pays de l'éditeur sur les pages publiques (commit 7c2ac7f).

## Evidence on Hand

- `CHANGELOG.md` (versions 1.4 à 1.7.0) : source du journal des nouveautés.
- `README.md` : promesse, formats, limites.
- Démonstrations : `frontend/public/demo_journal_avant.pdf` et `demo_journal_apres.pdf`.
- Logo : `frontend/public/Logo.png`, `backend/app/core/assets/logo.png`.
- Absences à ne pas combler : aucun témoignage, aucun client nommé, aucun chiffre d'usage, aucune certification. Les textes de `FeaturesGrid` (« 100 % », « 50+ langues », « traducteurs humains certifiés ») ne sont pas sourcés.

## Product Principles

1. Le document d'abord : chaque écran sert à obtenir un fichier traduit utilisable.
2. Dire vrai : on annonce ce qui existe, avec ses limites.
3. Peu et bien : une information à la fois, pas de relance insistante (un seul interrupteur, une seule fenêtre d'accueil).
4. Bilingue par construction : tout texte existe en français et en anglais.

## Accessibility & Inclusion

*Hypothèse : aucune norme formelle établie.* Pratique observée dans le code : cibles tactiles de 44 px au moins sur mobile, focus visible (contour bleu de 2 px), contraste du texte ≥ 4,5:1.
