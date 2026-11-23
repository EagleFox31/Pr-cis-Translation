# Étude : retours du 18/11, points 5 à 9 (aspect et finition)

Suite de `docs/etude-retours-18-11.md` (points 1 à 4, branche `fix/apercu-admin`).
Branche : `fix/retours-18-11-aspect`, partie de `main` (64fabf4).

## 5. Les nouveautés ne s'ouvrent pas d'elles-mêmes

### Constat
L'ouverture automatique fonctionne (`pages/Home.tsx:707`), mais le serveur répond souvent « rien de neuf ».
Le serveur compare la date écrite à la main dans le catalogue au jour de la dernière visite du client (`services/nouveautes.py:40-41`, « date de l'élément > jour de la visite »).

Cette date n'est pas la date de mise en ligne. Exemple réel :
- quatre éléments datés du 15/11 ont été mis en ligne le 18/11 (#91) ;
- un client venu le 16/11 a une dernière visite au 16/11 ;
- comme 15/11 n'est pas après 16/11, ces éléments ne lui sont jamais montrés.

Deuxième cas : un élément daté du 18/11 mis en ligne le 18/11 à 15 h. Un client venu le matin même ne le verra jamais, car la comparaison se fait au jour près et exige une date strictement postérieure.

### Options
| Option | Effet visible | Pour | Contre |
|---|---|---|---|
| **A. Retenir les éléments vus, un par un** (recommandé) | Tout élément mis en ligne s'affiche une fois, quelle que soit sa date | Exact, plus de dépendance à la date écrite | Une migration : une colonne liste d'identifiants sur le compte |
| B. Dater par numéro de version | Le client voit ce qui est sorti depuis la dernière version qu'il a vue | Pas de liste à stocker | Migration aussi, et un élément oublié dans une version reste caché |
| C. Comparer au jour près avec « ≥ » | Corrige le second cas seulement | Une ligne | Le premier cas (date antérieure à la mise en ligne) reste faux |

### Choix A, en détail
- Nouvelle colonne `nouveautes_vues` (liste d'identifiants, vide par défaut) sur `users`.
- « À voir » = éléments du catalogue dont l'identifiant n'est pas dans la liste. Fermer la fenêtre ajoute les identifiants montrés.
- Comptes existants (liste vide, date de visite connue) : la première fois, on garde comme déjà vus les éléments datés de plus de 7 jours avant leur dernière visite. Les éléments manqués comme ceux du 15/11 s'affichent alors une fois. Le premier accueil (compte neuf) ne change pas.
- La pastille du panneau de compte suit la même règle (même route `/a-voir`).
- Tests : élément daté avant la dernière visite mais jamais vu → montré ; vu → plus montré ; compte neuf → accueil inchangé.

## 6. Soldes « 5/5 » sans unité

### Constat
Dans le panneau de compte, la ligne Bêta affiche une icône de format suivie de « 5/5 » (`BetaAllowances.tsx:21`). L'unité (pages, diapositives, feuilles) n'apparaît qu'au survol, invisible sur mobile.

### Options
| Option | Exemple | Pour | Contre |
|---|---|---|---|
| **A. Restant + unité courte, total au survol** (recommandé) | `PDF 5 pages` · `PPTX 20 diapos` · `XLSX 3 feuilles` | Lisible d'un coup d'œil, tient sur deux lignes dans le panneau | Le total n'est plus affiché en clair |
| B. Restant + unité + total | `5 pages sur 5` | Complet | Trop long pour 4 formats sur la largeur du panneau |
| C. Une ligne par format | `PDF : 5 pages restantes sur 5` | Très clair | Le panneau s'allonge de 4 lignes |

### Décision (utilisateur, 22/11)
- Afficher seulement le restant, sans « / total » : en-tête replié « Solde : 5 pages » ; ligne du forfait « 5 pages » ; ligne Bêta, par format, « PDF 5 pages · PPTX 20 diapos · XLSX 3 feuilles » (les unités diffèrent, on ne les additionne pas).
- Un solde expiré par la date (Bêta `expired`, forfait payant au-delà de `plan_expires_at`) disparaît de la liste (`AccountPanel.tsx` `ligneBeta`, aujourd'hui grisée `off`) et n'a plus de barre de progression.

## 7. Filigrane trop fort sur les pages libres

### Constat
Le filigrane des pages en aperçu (`services/trial_preview.py:84`) pose quatre bandes de grands mots en italique, bleu nuit, à 16 % d'opacité, par-dessus tout le texte.

### Options
| Option | Effet visible | Pour | Contre |
|---|---|---|---|
| **A. Plus clair et passé sous le texte** (recommandé) | Bandes à environ 8 %, qui n'assombrissent plus les lettres : le texte reste aussi net que l'original | Le texte est lisible, le filigrane reste visible dans les blancs | Réglage à valider sur captures |
| B. Seulement plus clair (8 %) | Le texte reste légèrement voilé là où une bande passe | Une ligne | « Ne pas couvrir le texte » n'est pas tenu |
| C. Moins de bandes (2 au lieu de 4) | Moins de surface couverte | Simple | Toujours sur le texte là où il passe |

Pour A, le filigrane est fusionné en mode « produit » (le plus sombre des deux l'emporte) : un pixel de texte noir reste noir, seul le fond blanc prend la teinte. Le filigrane reste cuit dans l'image, il ne se retire donc pas plus facilement qu'aujourd'hui. Je montrerai l'avant / après sur 2 pages réelles avant de valider.

## 8. « Voir les tarifs » passe à la ligne (accueil)

Constat : le lien secondaire (`HeroSection.tsx:274`) contient le texte et le badge « Bêta ouverte ». Quand la place manque, le texte se coupe sur deux lignes, faute d'interdiction de retour à la ligne sur `.btn-ghost` (`index.css:911`).
Correction décidée : le texte ne se coupe plus, et le badge passe sous le texte si la ligne est trop courte. Vérification à 1280, 390 et 320 px, Bêta ouverte et fermée.

## 9. Journal prod « Script error. »

Constat : le navigateur remplace par « Script error. », sans fichier ni ligne, toute erreur venant d'un script d'un autre site. Le message est inexploitable et n'a aucun effet pour le client.
Correction décidée : `lib/errorReporting.ts:88`, ne pas envoyer une erreur dont le message est « Script error. » et qui n'a ni fichier ni pile. Les autres erreurs restent remontées.

## Impacts
- Données : une migration (point 5, colonne nullable, sans réécriture). Aucune autre.
- i18n : unités courtes FR/EN (point 6).
- Performance : point 7, le calque reste construit une fois par format de page.
- Déploiement : la migration passe par `deploy-vps.yml`.

## Décisions (22/11)
1. Point 5 : A par défaut (non tranché explicitement, aucune objection).
2. Point 6 : voir « Décision » au point 6.
3. Point 7 : A validé, avec exigence : le filigrane passe en arrière-plan de TOUT le contenu (texte, images, tableaux, traits), pas seulement du texte. Mode « produit » : tout pixel plus foncé que le filigrane reste intact. Captures avant/après à montrer.
