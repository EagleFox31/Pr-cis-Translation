# Étude : crédibilité de la page d'accueil et comparatif

## Besoin
Chaque phrase de la page d'accueil doit pouvoir être vérifiée par le produit ou la politique de confidentialité. Un comparatif court doit montrer les avantages réels de Précis face aux assistants IA généralistes (ChatGPT, Gemini…) et aux traducteurs de documents en ligne.

## État de l'existant : textes faux ou invérifiables

Sources : `locales/fr|en/translation.json`, `lib/languages.ts` (36 entrées), `content/legal/fr.ts` (section Conservation), `backend/app/config.py`.

| # | Où | Texte actuel | Réalité | Correction proposée |
|---|---|---|---|---|
| 1 | Carte « 50+ Langues » | « plus de 50 paires de langues » | 23 langues, 36 variantes (le hero le dit déjà) | « 36 langues et variantes » : « 23 langues et leurs variantes régionales ; écritures non latines proposées en Word et en texte. » (détection automatique non vérifiée, donc non affirmée) |
| 2 | Carte « IA + Expertise Humaine » | « systématiquement relue par des traducteurs humains certifiés » | Aucune relecture humaine dans le produit | Carte remplacée par « IA + méthode du traducteur professionnel » : fiche du document (domaine, pays, registre, terminologie), puis règles du métier (noms officiels conservés, rien d'ajouté ni d'abrégé, chiffres intacts) |
| 3 | Carte Sécurité + ligne du comparatif | « supprimées sous 24h », « RGPD garantie » | La politique dit : documents gardés **jusqu'à ce que vous les supprimiez**, fichiers temporaires 7 jours au plus ; texte transmis au prestataire de traduction | « Bibliothèque privée, que vous videz quand vous voulez. Fichiers temporaires effacés sous 7 jours. Prestataires listés dans notre politique de confidentialité. » |
| 4 | Comparatif, ligne OCR | Autres : « Non disponible » | Les traducteurs de documents en ligne connus proposent l'OCR | Ligne supprimée ou reformulée (voir comparatif) |
| 5 | Comparatif, ligne données | Autres : « Conservées (hors offre pro) » | Invérifiable, souvent faux | Ligne supprimée |
| 6 | Carte Mise en forme | « Conservez 100 % de la structure » | Bonne fidélité, pas 100 % garanti (scans, polices absentes) | « Polices, tableaux, colonnes et images restent à leur place, sans remise en page manuelle. » |
| 7 | Hero (démo), formulaire | « Mise en page conservée à l'identique » | Même remarque | « Mise en page conservée » |
| 8 | Tarifs Entreprise | « Support dédié et SLA garanti » | Aucun SLA écrit n'existe | « Support dédié » (SLA seulement s'il existe un contrat type) |
| 9 | Processus, étape 1 | « n'importe quel format » | PDF, DOCX, PPTX, XLSX, TXT | « Déposez un PDF, Word, PowerPoint, Excel ou texte. » |
| 10 | Processus, sous-titre | « garantir la meilleure qualité possible » | Superlatif creux | « Quatre étapes, et vous voyez le résultat avant de le télécharger. » |
| 11 | Carte Fidélité | « IA de pointe qui comprend les nuances culturelles » | Formule marketing invérifiable | « Une seule terminologie pour tout le document… Un passage oublié ou resté non traduit est repris automatiquement. » |
| 12 | Section Fonctionnalités, sous-titre | « traductions irréprochables » | Promesse absolue | « Ce que Précis fait concrètement de vos documents. » |

Ce qui est vrai et reste : OCR FR/EN jusqu'à 10 pages, « 23 langues, 36 variantes », « Vous payez ce qui est traduit », Mobile Money ou carte, « Zéro débordement » (le moteur ajuste le texte à son bloc ; sous-titre déjà honnête).

Toutes les corrections sont faites en français et en anglais.

## Comparatif proposé (remplace le tableau actuel, reste repliable)

Il compare des **catégories d'outils**, sans nommer de marques : aucune affirmation datée sur un concurrent ne risque d'être fausse, et rien ne relève de la publicité comparative nominative.

| | Précis | Assistants IA (chat) | Traducteurs de documents en ligne |
|---|---|---|---|
| Ce que vous récupérez | Votre fichier (Word, PowerPoint, Excel, PDF), mis en page | Du texte dans la conversation, à remettre en page | Votre fichier, mise en page variable selon le format |
| Long document | Traduit en entier, page par page | Souvent abrégé ou coupé au-delà de quelques pages | Traduit en entier, dans des limites de taille |
| Avant de télécharger | Aperçu côte à côte avec l'original | Pas de rendu à vérifier | Téléchargement direct |
| Traduction interrompue | Reprise sans payer deux fois | À relancer | À relancer |
| Paiement | À la page, Mobile Money ou carte, en FCFA | Abonnement mensuel par carte, en dollars | Abonnement par carte, en euros ou en dollars |

Les autres outils sont décrits de façon générale (« souvent », « variable ») : c'est vérifiable à la date du test. Il y a 5 lignes au lieu de 6, et le bloc reste replié par défaut, donc la section ne s'alourdit pas.

## Options d'intégration

| Option | Pour | Contre |
|---|---|---|
| A. Nommer les concurrents (DeepL, Google, ChatGPT) | Plus parlant | Se périme vite ; risque juridique et de crédibilité si un point devient faux |
| **B. Catégories d'outils (recommandé)** | Durable, honnête, lisible | Un peu moins percutant |

## Impacts
- Front seul : les deux fichiers de traduction, `FeaturesGrid.tsx` (clé de carte `human` → `method`, icône `BookCheck`), `ComparisonTable.tsx` (3 colonnes, 5 lignes ; sur mobile, une carte par outil).
- Les anciennes clés de traduction sont retirées.
- Aucun impact sur la base de données, la sécurité ou le déploiement.

## Décisions (validées)
1. Comparatif par catégories d'outils, sans marque.
2. Carte « Expertise humaine » → « IA + méthode du traducteur professionnel ».
3. Carte Sécurité : renvoi à la politique de confidentialité, sans nommer le prestataire.
4. « SLA garanti » retiré (« Support dédié »).

Livré : textes FR/EN, `FeaturesGrid.tsx`, `ComparisonTable.tsx`, styles `.comp-box--3` / `.comp-note` dans `index.css`. Vérifié : tsc, contrôle i18n, captures 1280 / 390 / 320 px sans débordement.
