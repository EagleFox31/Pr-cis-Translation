# Étude — ne plus repayer une page déjà traduite (extension, étape 6.4b)

Date : 01/11/2026. Suite de `docs/etude-extension-navigateur.md` (§6, §8).

## 1. Besoin

> « Ne plus repayer une page déjà traduite. »

Exemple concret : un apprenant ouvre la leçon G49001 sur TEAM-GP, lance la
traduction (texte + 5 images), puis revient sur la même leçon le lendemain.
Aujourd'hui il paie **tout une seconde fois** : le texte repart au moteur et
les 5 images repassent à l'OCR, 5 crédits de plus.

Critères d'acceptation :
- revisiter une page déjà traduite (même navigateur, même compte, même
  langue) ne débite rien et ne rappelle pas le serveur pour ce qui est connu ;
- une page en partie nouvelle ne paie que la partie nouvelle, au volume
  réel (pas une page entière pour une ligne) ;
- une image identique (mêmes octets), même sous une autre adresse, n'est
  payée qu'une fois ;
- la promesse actuelle tient : le serveur ne garde ni texte ni image.

## 2. État de l'existant

| Élément | Comportement actuel | Conséquence |
|---|---|---|
| `extension/src/contenu/images.ts` — `resultats` (Map par adresse) | Mémoire **le temps de la page** : une même adresse vue deux fois dans la page n'est envoyée qu'une fois | Perdue au rechargement ou à la page suivante |
| `extension/src/background.ts` — `segments()` | Envoie tous les blocs de la passe, découpés en lots (`lib/lots.ts`) | Aucun souvenir d'une passe à l'autre |
| `backend/app/services/extension.py` — `pages_pour_segments` | `max(1, ⌈caractères / 1 500⌉)` **à chaque appel** | Une passe tardive de 40 caractères (menu qui s'ouvre, compteur) coûte 1 page entière |
| `backend/app/api/extension.py` | « Rien n'est conservé » (docstring, promesse de l'étude §6) | Un cache serveur du contenu romprait cette promesse |
| `content.ts` — passes tardives (`DELAI_REGROUPEMENT_MS = 300`) | Chaque vague de nouveau texte = un appel | Multiplie l'arrondi ci-dessus |

Point clé : **une mémoire seule ne suffit pas**. Avec elle, une page revisitée
où un seul bloc a changé enverrait ce bloc seul… et paierait encore 1 page
entière à cause de l'arrondi par appel. Il faut aussi compter au volume
cumulé.

## 3. Options

### 3.1 Où garder les traductions déjà payées

| Option | Pour | Contre |
|---|---|---|
| **A. Mémoire dans l'extension** (IndexedDB du service de fond, clé = empreinte du contenu + langue + compte) | Aucune donnée de plus côté serveur ; zéro appel pour le connu (instantané) ; aucune migration | Propre à un navigateur : un autre ordinateur repaie une fois |
| B. Registre serveur d'empreintes payées (pas le contenu) | Vaut sur tous les appareils | Le serveur doit **retraduire gratuitement** (coût du moteur et de l'OCR pour nous) ; table + migration ; plus lent |
| C. Cache serveur des traductions | Tous appareils, sans retraduction | Rompt « rien n'est conservé » (contenus de cours privés gardés chez nous) ; risque de fuite entre comptes |

### 3.2 Comment compter le texte

| Option | Pour | Contre |
|---|---|---|
| Actuel : arrondi à la page à chaque appel | Simple | Paie des pages vides : 10 passes de 40 car. = 10 pages pour 400 car. |
| **D. Avance au volume côté serveur** : une page payée couvre 1 500 caractères, la part non utilisée est gardée en avance pour les appels suivants | Paie exactement le volume cumulé ; s'accorde avec la mémoire | Une colonne de plus sur l'utilisateur (migration) |
| E. Regrouper plus longtemps côté extension | Aucun changement serveur | Ne règle pas l'arrondi ; traduction affichée plus tard |

Exemple de D : premier appel 400 car. → 1 page payée, avance 1 100 ;
appels suivants de 40 car. → 0 page tant que l'avance couvre ; au-delà, une
nouvelle page, etc. L'avance ne contient qu'un nombre, aucun texte.

## 4. Choix recommandé : A + D

**Mémoire dans l'extension** (service de fond, IndexedDB — base de
l'extension, illisible par les sites visités et par nos scripts de page) :
- texte : clé = SHA-256(compte, langue, bloc balisé) → traduction. Seuls les
  blocs absents partent au serveur ; le contexte envoyé ne change pas. Une
  réponse identique au texte d'origine n'est pas gardée (c'est aussi la
  réponse « balises fausses », qu'une relance peut réussir) ;
- image : clé = SHA-256(compte, langue, octets de l'image source) → image
  traduite et ses blocs ; une image « non remplacée » est aussi gardée (pour
  ne pas refaire l'OCR, elle n'était déjà pas payée). Images de vidéo : non
  (chaque arrêt sur image est différent) ;
- bornes : 30 jours sans usage, 50 000 textes, 200 Mo d'images ; au-delà, les
  plus anciennes partent d'abord ;
- popup : ligne « Mémoire : n traductions — Effacer ». Gardée à la
  déconnexion (sinon se reconnecter ferait repayer) ; séparée par compte.

**Avance au volume côté serveur** : colonne `users.extension_avance`
(caractères déjà payés non utilisés, entier, défaut 0), lue et mise à jour
sous le verrou de `debiter`. `pages = ⌈(caractères − avance) / 1 500⌉` si
positif, sinon 0 et l'avance diminue. Un appel à 0 page ne débite rien et
n'écrit rien au registre de consommation. Les images restent à 1 page.

## 5. Impacts

- Données : une migration Alembic (colonne entière, défaut 0) ; rien d'autre.
  Aucun contenu gardé côté serveur.
- Sécurité / vie privée : les traductions restent sur le poste, dans la base
  de l'extension ; « Effacer » les supprime ; un autre compte sur le même
  navigateur ne les voit pas (clé par compte).
- Performance : une page revisitée s'affiche sans appel réseau ; empreinte
  SHA-256 des images ≈ quelques ms.
- Coûts : moins d'appels moteur et OCR ; recette en baisse sur le texte (on
  ne facture plus l'arrondi).
- Déploiement : extension rebâtie et rechargée ; migration à passer en prod
  avant la nouvelle route.

## 6. Risques

| Risque | Parade |
|---|---|
| Un site change une image sans changer d'adresse | Clé par octets, pas par adresse : nouvelle image → nouvelle traduction |
| Traduction améliorée côté moteur, l'ancienne reste en mémoire | Clé versionnée (préfixe `v1`) : un changement de moteur notable incrémente la version |
| Quota du navigateur atteint | Bornes du §4 ; un échec d'écriture n'empêche jamais l'affichage |
| Appels simultanés (deux onglets) et avance | Avance lue et écrite sous le verrou existant |

## 7. Points à trancher

1. Compter le texte au volume cumulé (option D, migration) — recommandé ; à
   défaut, la mémoire seule laisse payer 1 page par petite passe.
2. Mémoire gardée à la déconnexion (recommandé) ou effacée à chaque
   déconnexion (plus discret sur un poste partagé, mais on repaie).
3. Autres appareils (option B) : hors v1, à revoir si les apprenants
   changent souvent de poste.

### Décisions (01/11/2026)

1. Texte compté au volume cumulé (option D, colonne `users.extension_avance`).
2. Mémoire gardée à la déconnexion, séparée par compte, bouton « Effacer » dans le popup.
3. Autres appareils (option B) hors v1.

## 8. Plan

1. Backend : colonne + migration, `debiter_texte` avec avance, route segments ;
   tests (avance, 0 page sans registre, verrou).
2. Extension : `lib/memoire.ts` (clés, bornes, testable hors navigateur) +
   IndexedDB dans `background.ts` (texte et images) ; tests.
3. Popup : compteur + « Effacer ».
4. Vérif : typecheck, tests, build ; backend ; essai page locale (2ᵉ visite =
   0 débit, 0 appel).
