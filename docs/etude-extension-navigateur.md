# Étude — Extension navigateur : traduire une page entière, images comprises

> Statut : étude, rien n'est livré. Date : 31/10/2026.
> Dépend de [etude-ocr-v2.md](etude-ocr-v2.md) pour la traduction des images.

---

## 1. Le besoin, en un exemple

Un salarié suit un cours en ligne en japonais (lecteur SCORM, site
`team-gp.study.jp`). Il clique sur l'icône Précis Translator :

1. le texte de la page passe en français, à sa place, sans recharger ;
2. une bandeau demande : « Cette page contient 14 images avec du texte.
   Les traduire ? (14 crédits) » ;
3. s'il accepte, chaque image est remplacée par sa version française ; un
   bouton permet de revenir à l'original à tout moment.

Ce que les traducteurs de page actuels (Edge, Google) ne font pas ici :

| Contenu de la page | Traducteur intégré du navigateur | Besoin |
|---|---|---|
| Texte HTML de la page principale | traduit | traduit |
| Texte dans les cadres du lecteur de cours (iframes) | souvent ignoré | traduit |
| Texte dessiné en SVG (Storyline 360 par défaut) | ignoré | traduit |
| Texte contenu dans les images | ignoré | traduit **après accord** |

---

## 2. L'existant, mesuré

| Brique | Où | Réutilisable pour l'extension |
|---|---|---|
| Authentification | jetons `access_token` / `refresh_token` renvoyés en JSON, envoyés en `Authorization: Bearer` | **Oui tel quel** : une extension ne peut pas compter sur les cookies du site |
| CORS | liste `ALLOWED_ORIGINS` dans `backend/app/__init__.py` (~l. 127-150) | À compléter avec l'origine de l'extension (`chrome-extension://<id>`, `extension://<id>` pour Edge) |
| Traduction de texte | `engines/translation_ai.py` : `translate_json` (l. 713), lots `_translate_batch` (l. 381), OpenAI | **Oui** : une page = une liste de segments, exactement ce que fait `translate_json` |
| Point d'entrée de traduction | `/api/translate` : un **fichier** + langue cible, connexion obligatoire, crédits, 402 `need_credits` | Non adapté (fichier, pas segments) : nouveau point d'entrée léger, même contrôle des crédits |
| OCR d'image | n'existe pas (la v1 ne traite que des PDF) | Nouveau, fourni par l'OCR v2 |
| Frontend | Next.js | Seulement pour la page de connexion / achat de crédits vers laquelle l'extension renvoie |

Aucun code d'extension n'existe dans le dépôt.

---

## 3. Comment l'extension lit la page

Manifest V3 (seul format accepté par Chrome et Edge).

### 3.1 Texte HTML
- Parcours des **nœuds texte** (`TreeWalker`), en ignorant `script`, `style`,
  `code`, `pre`, champs de saisie, `contenteditable`, et ce qui est marqué
  `translate="no"`.
- Attributs visibles traduits aussi : `alt`, `title`, `placeholder`,
  `aria-label`.
- Segments envoyés par lots, puis réécrits **à la même place** ; l'original est
  gardé en mémoire pour le bouton « revenir ».
- **Shadow DOM** ouvert : parcouru. Fermé : inaccessible (limite assumée).
- **Contenu chargé plus tard** (diapositive suivante du cours) :
  `MutationObserver`, avec regroupement (une requête toutes les ~300 ms, pas
  une par nœud).

### 3.2 Cadres (iframes)
Le lecteur de cours charge le contenu dans des cadres.
- `all_frames: true`, `match_about_blank`, `match_origin_as_fallback` dans le
  manifeste.
- Un cadre d'une **autre origine** n'est atteint que si son adresse fait partie
  des sites autorisés. Choix recommandé : **permission demandée au clic**
  (`activeTab` + `scripting`, permissions optionnelles par site) plutôt que
  « tous les sites » dès l'installation — moins inquiétant à l'installation et
  mieux reçu par les stores.

### 3.3 SVG (Storyline 360)
- Le texte des éléments `<text>` / `<tspan>` est du texte : il se traduit comme
  un nœud texte, mais la place est fixe. Même règle qu'au §7 de l'étude OCR :
  réduction jusqu'à un plancher, sinon info-bulle.
- Si le texte SVG est dessiné en **chemins** (lettres vectorisées), il n'est
  plus lisible : on le traite comme une image (OCR, avec accord).
- Repli conseillé à l'utilisateur : le mode « texte accessible » du lecteur
  Storyline (roue dentée), qui affiche le texte en HTML.

### 3.4 Images
- Candidates : `<img>`, `background-image` CSS, `<canvas>` lisible, SVG en
  chemins. Ignorées : images < 64 × 64 px, icônes, images sans texte.
- **Aucune image n'est envoyée sans accord** (§5).
- L'extension envoie **les octets de l'image** (lus depuis la page), jamais
  son adresse : le serveur ne télécharge rien (pas de requêtes vers des
  adresses fournies par un tiers, pas d'accès aux contenus protégés par la
  session de l'utilisateur côté serveur).
- Image d'une autre origine sans en-têtes CORS : récupérée par le service de
  fond de l'extension (autorisé sur le site accordé) ; si impossible
  (canvas « contaminé »), l'image est signalée « non traduisible ».

### 3.5 Ce que contient réellement TEAM-GP (mesuré le 01/11/2026)

143 leçons de la catégorie G4, lues sans lancer de leçon (aucune progression
enregistrée).

| Famille | Nombre | Comment le contenu arrive | Japonais restant dans la version française |
|---|---|---|---|
| Leçons classiques (G40, G41, guides G48xxx-M01) | 81 | Textes dans un fichier `data.js`, pages HTML ordinaires | Texte : quelques segments dans 10 leçons sur 81. Images : **107 images sur 1 563 sont les mêmes fichiers que la version japonaise** — ce sont elles qui gardent leur texte japonais |
| Tests (G4xxxx-T0x) | 38 | Choix de la langue, puis questions lues dans `fr/xml/q_info.xml` ; affichées dans un cadre de 1000 × 650 px agrandi par CSS | Questions en français. Certaines fenêtres de confirmation (« 採点します。よろしいですか？ ») restent en japonais |
| Formation virtuelle (G49001, G49003, G49020) | 3 | Textes injectés **après** l'affichage (`text_l28.js` pour le français) ; animations en suites d'images PNG | Textes : 191 segments, tous français. Restent en japonais : 4 libellés écrits en dur (« ヒント », « 結果 », « ＜作業開始＞ », « エンジンNo : ») et le **texte incrusté dans 3 vidéos de démonstration** (« トルクレンチ », « 規定トルク »…) |
| Fiches de contrôle (G48001 à G48020) | 19 | Écran de la plateforme réservé à l'évaluateur | Hors de portée de l'apprenant (bouton désactivé) : rien à traduire |
| PDF liés aux guides | 14 documents × 14 langues | Lien vers un PDF à texte natif | Une version `_fr` existe ; vérifiée sur G48006-09 : français, aucun japonais, aucune image |

**Conclusion** : la cible prioritaire est bien l'image restée japonaise
(107 images dans les leçons classiques), puis les vidéos de la formation
virtuelle. Le texte HTML est presque entièrement traduit par le site.

### 3.6 Texte qui arrive tard
La formation virtuelle remplit ses zones de texte après l'ouverture de la
page, et les tests changent de question sans recharger. Le
`MutationObserver` du §3.1 couvre les deux ; il surveille aussi
`characterData` (texte remplacé dans un nœud existant), pas seulement
l'ajout de nœuds.

Une fenêtre `confirm()` / `alert()` du navigateur n'est pas dans la page :
l'extension ne peut pas la traduire. Limite assumée (cas rare, message court).

### 3.7 Suites d'images (fausses vidéos)
La formation virtuelle anime des pièces en remplaçant l'image d'un `<img>`
toutes les 50 ms (64 suites, 1 639 images). Aucune ne contient de texte
lisible (vérifié sur une image par suite).
- Règle : une image remplacée plus de 3 fois en 2 secondes dans le même
  élément est une **animation** ; elle n'est pas proposée à la traduction (ce
  serait payer des centaines d'images pour rien).
- Un vrai `<canvas>` (aucun dans TEAM-GP) est traité comme une image fixe
  s'il ne change pas, ignoré s'il est animé.

### 3.8 Vidéos
Le texte incrusté dans une vidéo fait partie de l'image : on ne peut pas le
« remplacer » comme dans un `<img>`.

| Option | Ce que voit l'utilisateur | Pour | Contre |
|---|---|---|---|
| A. Ignorer les vidéos | Vidéo en japonais | Rien à faire | Le besoin « tous les contenus » n'est pas couvert |
| B. **Calque de traduction au moment de la pause** | Il met la vidéo en pause, clique « Traduire cette image » : la vue figée est traduite (comme une image, 1 crédit) et posée par-dessus ; elle disparaît à la reprise | Réutilise exactement la traduction d'image ; coût maîtrisé ; marche sur toute vidéo lisible | Pas en continu |
| C. Sous-titres traduits en continu | Bandeau de texte français pendant la lecture | Fluide | Une lecture d'image toutes les secondes : cher et lent ; inutile pour des libellés d'interface qui ne bougent pas |
| D. Vidéo entière retraitée côté serveur | Nouvelle vidéo française | Résultat parfait | Lourd (minutes de calcul, gros fichiers), hors du périmètre OCR v2 |

**Recommandation : B.** Les vidéos de TEAM-GP montrent un écran fixe dont on
lit les libellés ; une image figée traduite répond au besoin. Une vidéo
d'une autre origine sans en-têtes CORS ne peut pas être lue : signalée
« non traduisible », comme une image.

### 3.9 PDF ouverts dans le navigateur
La visionneuse PDF de Chrome et d'Edge est une page interne : une
extension ne peut pas y écrire. Le PDF est donc traité comme un **document**,
avec le moteur existant :
- un lien vers un `.pdf` dans la page reçoit une petite pastille
  « Traduire ce PDF » ; le clic télécharge le fichier (avec la session de
  l'utilisateur, côté extension) et l'envoie à `/api/translate`, comme un
  dépôt sur le site ; le résultat s'ouvre dans un nouvel onglet ;
- facturation et contrôles inchangés (ceux des documents).

Sur TEAM-GP, la version française des PDF existe déjà : la pastille servira
surtout aux PDF laissés en japonais ailleurs.

---

## 4. D'où vient la traduction du texte

| Option | Pour | Contre |
|---|---|---|
| **A. API de traduction intégrée au navigateur** (Translator / Language Detector, sur l'appareil) | Gratuite, hors ligne, rien ne quitte le poste | Disponible sur Chrome bureau (138+) ; sur Edge, annoncée mais statut à vérifier au moment du développement ; qualité inférieure sur le vocabulaire technique ; aucune maîtrise de la terminologie |
| **B. Moteur Précis (OpenAI, côté serveur)** | Même qualité et même glossaire que les documents ; fonctionne partout | Coût par page, donc crédits ; le texte de la page quitte le poste |
| **C. Hybride** : A pour le texte si disponible, B sur demande (« qualité Précis ») et toujours B pour les images | Gratuit par défaut, payant quand ça apporte quelque chose | Deux chemins à tester |

**Recommandation : C.** Le texte courant ne coûte rien à l'utilisateur ni à
nous quand le navigateur sait le faire ; les crédits portent sur ce que seul
Précis sait faire (images, terminologie). Si l'API intégrée est absente
(Edge non supporté, Firefox), bascule automatique sur B, signalée.

---

## 5. L'accord avant les images

- Bandeau dans la page (pas une fenêtre système) : nombre d'images détectées,
  **coût en crédits**, boutons « Traduire les images » / « Pas maintenant ».
- Case « Toujours pour ce site » (mémorisée localement, révocable dans les
  réglages de l'extension).
- Les images sont traitées une par une, les plus visibles d'abord ; chaque
  image déjà faite apparaît aussitôt.
- Bouton « Original » par image et pour toute la page.
- Une image que l'OCR ne lit pas avec certitude n'est **pas** remplacée et
  **pas** débitée (règle d'honnêteté de la v1).

---

## 6. Ce que le serveur ajoute

| Point d'entrée | Rôle | Contrôles |
|---|---|---|
| `POST /api/extension/segments` | Traduit une liste de segments (option B) | Connexion, plafond de segments et de caractères par appel, débit au volume, 402 `need_credits` |
| `POST /api/extension/image` | Reçoit une image, renvoie l'image traduite (OCR v2) | Connexion, type réel vérifié, ≤ 10 Mo et ≤ 25 Mpx avant décodage, une à la fois par utilisateur, débit seulement si l'image est remplacée |

- **Rien n'est conservé** : ni le texte des pages, ni les images ; seul le
  débit de crédits est journalisé (nombre, pas contenu).
- Limitation de débit par utilisateur (une page de cours peut déclencher
  beaucoup d'appels).
- Ces deux points d'entrée réutilisent `translate_json` et le paquet `ocr_v2` :
  pas de second moteur.

---

## 7. Authentification dans l'extension

- Connexion par la page de connexion existante, ouverte dans un onglet ; le
  site transmet les jetons à l'extension (`externally_connectable` limité au
  domaine Précis), qui les garde dans `chrome.storage.session` (effacé à la
  fermeture du navigateur) ; le jeton de renouvellement dans
  `chrome.storage.local`.
- Les jetons ne sont jamais visibles du site traduit : seuls le service de fond
  et la fenêtre de l'extension les manipulent ; les scripts injectés dans la
  page n'y ont pas accès.
- Déconnexion depuis la fenêtre de l'extension.

---

## 8. Facturation

| Action | Proposition |
|---|---|
| Texte traduit par le navigateur (option A) | Gratuit |
| Texte traduit par Précis (option B) | Au volume, aligné sur la règle des documents (à fixer) |
| Image traduite | 1 crédit par image remplacée ; 0 si non remplacée |

Le prix exact est un **point à trancher** (§12).

---

## 9. Publication

| Store | Ce qu'il faut | Délai indicatif |
|---|---|---|
| Chrome Web Store | compte développeur (frais uniques), politique de confidentialité publique, justification de chaque permission | quelques jours d'examen, plus si « tous les sites » |
| Microsoft Edge Add-ons | compte Partner Center (gratuit), mêmes pièces | quelques jours |
| Firefox (plus tard) | MV3 compatible à quelques détails près | — |

Avant les stores : installation manuelle en « mode développeur » pour les
essais sur le cours cible. La politique de confidentialité doit dire : texte
et images envoyés seulement sur action de l'utilisateur, non conservés.

---

## 10. Impacts

| Domaine | Impact |
|---|---|
| Code | Nouveau dossier `extension/` (TypeScript, sans framework, construit par le même outillage Node) ; deux routes backend ; origines CORS de l'extension |
| Données / migrations | Aucune table nouvelle si le débit réutilise le journal de crédits existant (à confirmer à l'implémentation) |
| Sécurité | Images non fiables (§6) ; jetons hors de portée de la page (§7) ; permissions minimales (§3.2) ; contenu traduit inséré **en texte**, jamais en HTML (pas d'injection) |
| Performance | Lots de segments ; OCR v2 un par un ; budget de temps par image (étude OCR §6) |
| i18n | Interface de l'extension en fr/en (`_locales`) |
| Coûts | Option A gratuite ; B et images dans le modèle de crédits |
| Juridique | Texte de pages tierces traité à la demande de l'utilisateur, non stocké ; à mentionner dans les CGU / confidentialité |

---

## 11. Risques

1. **Le cours cible peut ne pas se laisser lire** (cadres d'origine
   différente, texte vectorisé). Parade : essai sur la page sauvegardée
   (Ctrl+S ou `outerHTML` des cadres) **avant** d'écrire l'extension complète.
2. **Mise en page cassée** par des traductions plus longues. Parade :
   plancher de taille, info-bulle, bouton « Original ».
3. **Coût OpenAI** si l'option B devient le défaut. Parade : option C.
4. **Refus ou délai des stores** sur des permissions larges. Parade :
   permissions au clic.
5. **API intégrée absente sur Edge** au moment du développement : bascule
   sur B, signalée à l'utilisateur.

---

## 12. Points à trancher

1. **Prix** : 1 crédit par image remplacée ? texte « qualité Précis » au
   volume ? (recommandé : oui aux deux, texte navigateur gratuit)
2. **Navigateurs au lancement** : Edge + Chrome (recommandé), Firefox plus tard ?
3. **Publication** : stores publics dès la première version, ou d'abord
   installation manuelle pour un groupe d'essai ?
4. **Page du cours** : fournir une sauvegarde de la page (Ctrl+S) ou les
   `outerHTML` des cadres pour valider l'approche avant le développement.

### Décisions (31/10/2026)

1. Prix : 1 crédit par image remplacée, 0 si non remplacée ; texte traduit par le navigateur gratuit ; texte « qualité Précis » au volume (règle des documents).
2. Navigateurs : Edge et Chrome au lancement ; Firefox plus tard.
3. Publication : installation manuelle pour un groupe d'essai d'abord, stores ensuite.
4. Page du cours : sauvegarde demandée à l'utilisateur ; en attendant, l'OCR v2 avance.

### Décisions (01/11/2026, prises au vu des mesures du §3.5)

5. Vidéos : calque traduit sur la vue en pause (§3.8 B), 1 crédit comme une image.
6. Suites d'images animées : ignorées (§3.7).
7. PDF : pastille « Traduire ce PDF » qui passe par le circuit des documents (§3.9).
8. Fiches de contrôle G48 : hors périmètre (réservées à l'évaluateur).
