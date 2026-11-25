# Étude — problèmes du test « gros fichier » (24/11)

Fichier de test : le PowerPoint de Gérold (19,8 Mo, 75 diapositives).
Règle fixée par le commanditaire : on veut **déployer maintenant** ce qui est fait.
Les corrections qui touchent au **moteur de traduction** (ce qui produit le
document traduit) passent **en dernier**, après le déploiement : la version
actuelle est stable, on ne la remet pas en jeu.

## 1. Classement

### Lot 1 — avant le déploiement (écrans et envoi du fichier, moteur inchangé)

Ordre : argent d'abord, puis ce qui fait perdre du temps ou trompe l'utilisateur,
puis le confort.

| # | Problème | Gravité | Pourquoi à cette place |
|---|---|---|---|
| 1 | Solde de pages faux ou figé (P7) | Argent | Un client qui voit 230 au lieu de 225, ou « Gratuit — 0 page » alors qu'il a payé, croit qu'on le vole. |
| 2 | Un seul envoi du fichier (P1, P2, P4, P13) | Structure | Aujourd'hui le fichier part 3 à 4 fois : la traduction démarre en retard et l'aperçu met 4 minutes. |
| 3 | Écran trompeur pendant l'envoi (P3) | Structure | L'utilisateur croit que la traduction tourne alors que le fichier n'est pas encore arrivé. |
| 4 | « Mes documents » pas à jour (P6) | Aspect | Le document n'apparaît qu'après rechargement de la page. |
| 5 | Changement silencieux en fin de traduction (P8) | Aspect | 21 diapositives changent sans prévenir. Option 2 déjà validée (étude `etude-coherence-apercu.md`). Ne change pas la traduction, seulement l'information donnée et l'aperçu. |

### Lot 2 — après le déploiement (moteur)

| # | Problème | Pourquoi plus tard |
|---|---|---|
| 6 | Contrôle qualité complet (P12) | À faire en premier dans ce lot : il peut révéler d'autres défauts et les regrouper avec ceux ci-dessous. |
| 7 | Dégradations du contrôle de cohérence (P9) | Touche la façon dont le texte corrigé est réinjecté. |
| 8 | Textes qui débordent (P10) | Touche le calcul de taille du texte dans les formes. |
| 9 | Formes de mise en évidence décalées (P11) | Touche la position des formes après traduction. |
| 10 | Vitesse : 26 s par diapositive (P5) | Il faut d'abord mesurer où part le temps ; tout changement touche le moteur. |

Puis une nouvelle traduction complète du même fichier, comme preuve finale.

## 2. Lot 1 en détail

### 2.1 Solde de pages (P7)

Constat : le compte payé avait 300 pages. Après une traduction de 75 diapositives,
le panneau affiche 230 (300 − 70), il ne bouge pas tant qu'on ne recharge pas, et
un autre panneau affiche « Gratuit — 0 page ».

À vérifier d'abord, avant tout correctif : **combien a réellement été débité en
base**. Deux cas :
- 70 débités : écart de 5 pages, à expliquer (pages offertes ? diapositives
  vides non comptées ?). Si c'est une règle voulue, on l'affiche ; sinon c'est un
  bug de facturation.
- 75 débités : seul l'affichage est faux.

Correctif d'affichage recommandé : relire le solde dès que la traduction est
acceptée et à la fin (le mécanisme `refreshUser` existe déjà, il n'est pas appelé
à ces moments-là) ; le libellé « Gratuit » doit se baser sur les pages achetées,
pas seulement sur la formule.

### 2.2 Un seul envoi du fichier (P1, P2, P4, P13)

Exemple concret, avec une connexion moyenne : 20 Mo mettent environ 2 minutes à
partir. Aujourd'hui, à la sélection du fichier, il part une fois pour deviner sa
langue ; au clic sur Traduire, il repart pour l'aperçu (deux fois sur le serveur
de test) et une fois de plus pour la traduction. Les envois se partagent la
connexion, d'où les 4 minutes avant de voir l'original. Si l'on clique avant la
fin du premier envoi, celui-ci est abandonné et perdu.

| Option | Effet visible | Pour | Contre |
|---|---|---|---|
| A. Griser Traduire pendant l'analyse et supprimer le doublon d'aperçu | Le bouton attend la fin du premier envoi | Très petit changement | Le fichier part quand même 3 fois ; l'attente totale ne baisse presque pas |
| B. Supprimer l'envoi d'analyse et faire l'aperçu de l'original sur le serveur à partir du fichier de la traduction | Un seul envoi, au clic | Gros gain de temps | L'avertissement « même langue » n'arrive qu'après le clic ; l'attente de l'envoi reste au moment du clic |
| **C. Envoyer le fichier une seule fois, dès qu'il est déposé** | Une barre « Envoi du fichier : 45 % » apparaît dès le dépôt ; Traduire s'active quand l'envoi est fini ; l'aperçu et la traduction partent aussitôt, sans renvoi | Un seul envoi ; l'envoi se fait pendant que l'utilisateur choisit sa langue ; la progression est visible ; la taille est refusée avant l'envoi | Changement plus large : le serveur garde le fichier déposé quelques heures |

**Recommandation : C.** Pour limiter le risque avant déploiement :
- le serveur accepte toujours l'ancien envoi direct ; si le dépôt échoue,
  l'écran retombe sur le fonctionnement actuel ;
- les fichiers déposés mais jamais traduits sont effacés au bout de 24 heures ;
- un dépôt n'est lisible que par le compte qui l'a envoyé.

Limites (P13) traitées au passage :
- 100 Mo : refus immédiat dans le navigateur (déjà en place) **et** refus par le
  serveur dès l'annonce de la taille, avant de recevoir le fichier.
- 500 pages par paiement : point à trancher (§ 4).

### 2.3 Écran pendant l'envoi et le démarrage (P3)

Constat : « 0/1 pages », un bouton pause et « Préparation de l'aperçu… »
s'affichent alors que rien n'est encore traduit.

**Décision du commanditaire (24/11)** : ne pas refaire l'écran de traduction.
Le bouton Traduire du formulaire reste grisé pendant l'envoi du fichier, avec la
progression de l'envoi affichée (« Envoi du fichier : 45 % »), et se débloque
quand le fichier est arrivé. L'écran de traduction ne s'ouvre donc qu'avec un
fichier déjà reçu et affiche ce qu'il faut. Retouche minimale seulement si un
faux compteur « 0/1 » subsiste dans les premières secondes.

**Vitesse** : chercher aussi les gains de temps sans risque (envois en double,
conversions refaites, attentes inutiles). Règle : un système lent qui marche vaut
mieux qu'un système rapide qui risque de planter ; tout gain qui touche le moteur
va au lot 2.

### 2.4 « Mes documents » (P6)

Recommandation : recharger la liste dès que la traduction est acceptée par le
serveur (le document y figure alors « en cours »), puis à la fin.

### 2.5 Changement silencieux en fin de traduction (P8)

Option 2 validée : à la fin, l'aperçu des diapositives modifiées est redessiné et
une phrase prévient : « Pour garder les mêmes termes partout, les diapositives 1,
2, 4… ont été ajustées. » Détail dans `etude-coherence-apercu.md`.

Attention : ce lot ne corrige pas les dégradations de ce contrôle (P9, lot 2).
Après déploiement, la diapositive 1 aura toujours un titre sur 4 lignes et la
diapositive 2 perdra toujours « définition des ». Voir § 4.

## 3. Impacts et risques

- Données : pas de migration. Les fichiers déposés vivent dans un dossier
  temporaire, effacé après 24 heures.
- Sécurité : le dépôt exige d'être connecté, comme l'aperçu aujourd'hui ; un
  compte ne peut utiliser que ses propres dépôts.
- Traductions : français et anglais pour chaque nouveau texte.
- Déploiement : un nouveau point d'entrée côté serveur, rien à configurer.
- Risque principal : l'envoi unique change le début de chaque traduction. Il est
  couvert par le retour automatique à l'ancien envoi et par un test complet sur le
  fichier de Gérold avant de rendre la main.

## 4. Points tranchés (24/11)

Validé : option C (envoi unique dès le dépôt, Traduire grisé avec progression
jusqu'à la fin de l'envoi), P9 laissé tel quel jusqu'au lot 2. Point 3 (500 pages)
sans réponse : rien n'y est changé pour l'instant.

## 4 bis. Points qui étaient à trancher

1. **Envoi du fichier** : option C (recommandée), B ou A.
2. **Dégradations du contrôle de cohérence (P9) d'ici le lot 2** :
   - a) laisser tel quel (recommandé : il corrige plus de diapositives qu'il n'en
     abîme, et le lot 1 rend ses changements visibles) ;
   - b) le couper jusqu'au lot 2 (plus de titre sur 4 lignes, mais des termes
     redeviennent incohérents d'une diapositive à l'autre).
3. **500 pages par paiement** : que faut-il revoir ? Le plafond lui-même, ou le
   message quand un document dépasse ce plafond ?
