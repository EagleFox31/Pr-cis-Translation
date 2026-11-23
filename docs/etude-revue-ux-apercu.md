# Revue UX/UI/CX : aperçu, tiroir de compte, formulaire de traduction (22/11/2026)

Périmètre : l'aperçu (barre d'outils, pages, messages autour), le tiroir de compte complet et le formulaire de traduction. Contrôle fait dans Edge sur un compte gratuit à solde 0, avec un PDF de 10 pages, sur ordinateur (1278 × 791) et sur téléphone (390 × 800). Référence : PRODUCT.md (le document d'abord, dire vrai, peu et bien) et DESIGN.md.

Les écarts sont classés par gravité : **structure** (faux, manquant, place perdue), **aspect**, puis **finition** (mots).

## 1. Structure

### S1. Messages faux depuis la suppression de la limite
Deux documents de « Mes documents » affichent « En pause : limite d'aperçu, reprise demain à 17 h 56 ». Cette limite n'existe plus, donc le message est faux.
- **Option A (recommandée)** : afficher simplement « En pause » pour ces documents, garder « Reprendre » et retirer les textes liés à la limite (`library.paused_limit_*`, `story.stopped_at_limit*`, `story.pause_at_limit*`, `preview.libre_limit_*`, `preview.libre_remaining_*`).
- Option B : relancer automatiquement ces traductions. Cette option agit sans action de l'utilisateur, ce qui est risqué.

### S2. Le bandeau d'aperçu réduit la place du document
Le bandeau jaune « 10 pages en aperçu seulement (non payées)… » se place entre la barre d'outils et les pages. Il fait 51 px sur ordinateur et 101 px sur téléphone, soit 13 % de l'écran. Sur téléphone, la page traduite n'a plus que 408 px de haut.

De plus, il répète ce que dit déjà le bas de la page traduite (« Essai : survolez la page pour la lire · Débloquer »). Il y a donc deux boutons pour la même action, avec deux mots différents : « Acheter 10 pages » et « Débloquer ».
- **Option A (recommandée)** : supprimer le bandeau et regrouper le message dans le bas de la page traduite, qui existe déjà. Exemple : « Aperçu filigrané · 10 pages à régler pour télécharger · Débloquer ». L'aperçu retrouve toute sa hauteur et il ne reste qu'un seul bouton.
- Option B : réduire le bandeau à une seule ligne courte (« 10 pages en aperçu · Acheter »). Il reste quand même au-dessus du document.

### S3. « Traduction terminée » s'affiche deux fois, et sur téléphone la notification cache les outils
L'état apparaît dans la barre d'outils (« Traduction terminée ») et dans une notification flottante (« Traduction terminée ! rapport10_TRADUIT.pdf »). Sur téléphone, cette notification recouvre le zoom et les boutons de la barre.
- **Option A (recommandée)** : garder seulement l'état dans la barre d'outils quand l'aperçu est ouvert. La notification ne sert que si l'utilisateur a quitté l'aperçu.
- Option B : garder la notification, mais la placer en bas de l'écran sur téléphone.

### S4. Langue d'arrivée identique à la langue du document
Un document anglais a été traduit vers l'anglais (« EN — Traduction ») sans aucun avertissement. L'utilisateur paie ou consomme un aperçu pour obtenir le même texte.
- **Option A (recommandée)** : afficher un message sous le choix de langue : « Ce document semble déjà être en anglais. Choisissez une autre langue d'arrivée. » Le bouton reste utilisable.
- Option B : bloquer le bouton Traduire. C'est trop strict quand la détection se trompe.

## 2. Aspect

### A1. Vignettes : toutes les pages ont la même coche verte
Les pages en aperçu (non payées) portent la même coche verte que les pages payées. On ne voit pas lesquelles seront dans le fichier téléchargé.
- **Recommandation** : remplacer la coche par un petit cadenas sur les vignettes des pages en aperçu.

### A2. Nom du fichier coupé dans la barre d'outils
On lit « rapport10… → rapport10_TRADUI… ». Le nom traduit apporte peu d'information.
- **Recommandation** : n'afficher que le nom d'origine, avec le nom complet au survol.

### A3. Tiroir : le texte de pause est coupé
« En pause : limite d'aperçu, re… » est tronqué. Ce point disparaît avec S1, puisque « En pause » est court.

## 3. Finition (textes)

| Où | Aujourd'hui | Proposé |
|---|---|---|
| Comment ça marche, étape 1 | Téléchargement | Dépôt du document |
| Titre de section | Notre Processus de Traduction | Notre processus de traduction |
| `story.queued_ahead` | traduction(s) | vraie forme au singulier et au pluriel |
| `story.ocr_notice` | page(s) scannée(s) | vraie forme au singulier et au pluriel |
| États de chargement | Traduction en cours... | Traduction en cours… |
| `story.free_plan_title` | 5 pages équivalentes / mois | 5 pages offertes chaque mois |
| Tiroir, solde | Solde : 0 page | Il vous reste 0 page |
| Tiroir, abonnement | renouvelé le 1 déc. 2026 | Renouvellement le 1er décembre |
| Tiroir, nouveautés | E-mail | Recevoir par e-mail |
| Bandeau d'aperçu | 10 pages en aperçu seulement (non payées) : filigranées, elles ne seront pas dans le fichier téléchargé. | voir S2 |
| Jargon général | crédits, pages couvertes, Ré-injecte | pages payées, pages réglées, Remet |
| `library.archived_row` | mélange le nom du fichier et son statut | une ligne pour le nom, une ligne pour le statut |
| Doublon | « Pages restantes ce mois » apparaît deux fois | une seule fois, dans le tiroir |

## 4. Ce qui est déjà conforme
- Les messages de progression (« Traduction en cours », « Lecture du scan »…) s'affichent sur la page en cours. Ils ne prennent aucune place autour du document.
- Le panneau « pages à régler » s'affiche dans la page traduite elle-même, sans bannière ailleurs.
- Le tiroir de compte suit le gabarit prévu (440 px, en-tête, solde, nouveautés, documents, pied à trois actions).

## 5. Ordre de correction proposé
1. S1 et S2, qui touchent la justesse et la place de l'aperçu.
2. S3 et S4.
3. A1 et A2.
4. Les textes du tableau, en une seule passe en français et en anglais.

Après chaque groupe : contrôle de type, lint, build, puis vérification dans Edge sur ordinateur et sur téléphone.

## 6. Recommencer une traduction (point F)

### Constat
Aujourd'hui, pour traduire à nouveau un document terminé, il faut le déposer une deuxième fois. Exemple : un rapport traduit en anglais, qu'on veut aussi en espagnol, doit être retrouvé sur l'ordinateur puis redéposé.

La relance existe déjà pour un document en échec ou en pause (« Reprendre ») : elle reprend l'original gardé sur le serveur, avec les mêmes réglages, puis remplace l'ancien document. Elle ne permet pas de choisir une autre langue.

### Proposition d'interface
- Dans le menu « … » d'un document terminé : « Traduire à nouveau ».
- Dans l'aperçu, le même bouton dans la barre d'outils.
- Une petite fenêtre demande la langue d'arrivée (celle d'avant est proposée par défaut) puis lance la traduction. L'ancien document reste dans « Mes documents » : rien n'est supprimé.

### Prix d'une nouvelle traduction (à trancher)
- **Option A (recommandée)** : prix normal, comme un nouveau dépôt. Le gain pour l'utilisateur est de ne pas avoir à redéposer le fichier. Pour un compte gratuit, l'aperçu reste gratuit et illimité, comme pour tout dépôt. Si le résultat était mauvais, « Signaler un problème » reste le bon chemin.
- Option B : gratuit vers la même langue, prix normal vers une autre langue. Le moteur refait pourtant tout le travail, et le bouton pourrait servir à relancer en boucle sans frais.
- Option C : moitié prix vers la même langue. C'est une règle de plus à expliquer, pour un cas rare.
